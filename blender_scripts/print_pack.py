"""Bake a collection's parts into a print-ready handoff: parts.blend + one STL per part.

Usage: blender -b model.blend -P print_pack.py -- --outdir models/<m>/print
       [--collection Print] [--gap 5] [--bed 256] [--flat 'Tenon_*' ...]
       [--rules '[{"match": "Clip_*", "rotate": [90, 0, 0]}]'] --result r.json

For a printing agent (e.g. bambi), which exports every visible mesh of a mm .blend:
- every visible mesh in the collection is evaluated (modifiers, GN, booleans applied) into
  a plain mesh with its world transform baked in, keeping materials;
- each part is dropped onto the bed (lowest point at z=0) in its modelled orientation,
  unless its name matches a --flat pattern: then its largest flat face goes down;
  --rules ([[print.part]] match/flat/rotate/into, later rules win key by key) can set flat
  per part or rotate it (Euler XYZ degrees) before it is dropped; flat beats rotate;
- a part with `into` (an AMS inlay or glue-in piece) is not placed on its own: it takes its
  host's rotation and move, so it stays where it was modelled inside the host;
- each part's "joints" / "fit" custom properties (JSON string or ID property) are
  passed through to the result for the manifest;
- hosts and free parts are laid out in non-overlapping rows (gap mm apart) so nothing collides;
- parts.blend contains only those parts, in mm (1 BU = 1 mm), saved as a new file;
- each part is also written as <name>.stl in Blender units (mm).
The source .blend is never saved. The result JSON lists each part's size, volume and
footprint, and flags any part larger than the bed.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bmesh
import bpy
from _common import MODEL, model_objects, parse, reveal, write_result
from mathutils import Euler, Matrix, Vector

parser = argparse.ArgumentParser()
parser.add_argument("--outdir", required=True)
parser.add_argument("--collection", default="Print")
parser.add_argument("--gap", type=float, default=5.0)
parser.add_argument("--bed", type=float, default=256.0)
parser.add_argument("--flat", action="append", default=[], help="part name glob")
parser.add_argument(
    "--rules", default="[]", help="JSON [{match, flat?, rotate?, into?}]"
)
opts = parse(parser)
rules = json.loads(opts.rules)

scene = bpy.context.scene
per_bu = scene.unit_settings.scale_length or 1.0
mm = 0.001 / per_bu  # Blender units per mm in the source file
if opts.collection != MODEL:
    reveal(opts.collection)  # e.g. a Print collection hidden in the file
dg = bpy.context.evaluated_depsgraph_get()
sources = model_objects(collection=opts.collection)
if not sources:
    raise SystemExit(f"no visible meshes in collection {opts.collection!r}")


def flat_matrix(me) -> Matrix:
    """Rotation that turns me's largest planar face (summed area per normal) to face the bed."""
    area = defaultdict(float)
    for poly in me.polygons:
        area[tuple(round(c, 3) for c in poly.normal)] += poly.area
    down = Vector(max(area, key=area.get)).normalized()
    return down.rotation_difference(Vector((0, 0, -1))).to_matrix().to_4x4()


def matches(name: str, match) -> bool:
    globs = [match] if isinstance(match, str) else match
    return any(fnmatch(name, g) for g in globs)


def placement(name: str) -> tuple[bool, list[float], str]:
    """(lay flat?, rotate degrees, host) for a part: --flat globs, then rules, later wins."""
    merged = {}
    for rule in rules:
        if matches(name, rule["match"]):
            merged.update(rule)
    flat = merged.get("flat", any(fnmatch(name, pat) for pat in opts.flat))
    rotate = [float(a) for a in merged.get("rotate", (0, 0, 0))]
    return bool(flat), ([0.0, 0.0, 0.0] if flat else rotate), merged.get("into", "")


def plain(value):
    """ID property (group, array, list) or JSON string -> plain JSON data."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if hasattr(value, "to_dict"):
        return {k: plain(v) for k, v in value.to_dict().items()}
    if hasattr(value, "to_list"):
        return [plain(v) for v in value.to_list()]
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


baked = []
flat = set()
rotated = {}
extras = {}
hosts = {}  # inlay name -> host name
orient = {}  # part name -> rotation applied before dropping on the bed
for src in sources:
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    me.transform(src.matrix_world)
    if mm != 1.0:  # normalise to 1 BU = 1 mm
        me.transform(Matrix.Scale(1.0 / mm, 4))
    lay, rotate, host = placement(src.name)
    if host:
        hosts[src.name] = host
    elif lay:
        orient[src.name] = flat_matrix(me)
        flat.add(src.name)
    else:
        orient[src.name] = (
            Euler([math.radians(a) for a in rotate], "XYZ").to_matrix().to_4x4()
        )
    rotated[src.name] = rotate
    extras[src.name] = {k: plain(src[k]) for k in ("joints", "fit") if k in src}
    me.name = src.name
    baked.append((src.name, me))

for name, host in hosts.items():
    if host in hosts or host not in orient:
        why = "an inlay itself" if host in hosts else "not in the collection"
        raise SystemExit(f"{name}: into {host!r} is {why}")
    if host in flat:
        flat.add(name)
    rotated[name] = rotated[host]
    orient[name] = orient[host]
for name, me in baked:
    me.transform(orient[name])

# drop the source scene's objects; only the baked parts go in the pack
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for coll in list(bpy.data.collections):
    bpy.data.collections.remove(coll)
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.001
scene.unit_settings.length_unit = "MILLIMETERS"
parts_coll = bpy.data.collections.new("Parts")
scene.collection.children.link(parts_coll)


def bounds(meshes) -> tuple[Vector, Vector]:
    co = [v.co for me in meshes for v in me.vertices]
    xs, ys, zs = zip(*co)
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


# shelf layout of groups (a host with its inlays, or a free part): largest footprints first,
# rows along +X, wrapping at a wide row length; one move per group keeps inlays in place
groups = {name: [me] for name, me in baked if name not in hosts}
for name, me in baked:
    if name in hosts:
        groups[hosts[name]].append(me)
items = [(name, meshes, *bounds(meshes)) for name, meshes in groups.items()]
items.sort(key=lambda it: -(it[3].x - it[2].x) * (it[3].y - it[2].y))
row_len = max(opts.bed * 2, max(it[3].x - it[2].x for it in items))
x = y = row_h = 0.0
for _, meshes, lo, hi in items:
    w, d, _ = hi - lo
    if x and x + w > row_len:
        x, y, row_h = 0.0, y + row_h + opts.gap, 0.0
    move = Matrix.Translation(Vector((x, y, 0)) - lo)  # group min corner -> (x, y, 0)
    for me in meshes:
        me.transform(move)
    x += w + opts.gap
    row_h = max(row_h, d)

parts = []
for name, me in baked:
    lo, hi = bounds([me])
    w, d, h = hi - lo
    obj = bpy.data.objects.new(name, me)
    parts_coll.objects.link(obj)
    bm = bmesh.new()
    bm.from_mesh(me)
    volume = abs(bm.calc_volume())
    manifold = all(e.is_manifold for e in bm.edges)
    bm.free()
    parts.append(
        {
            "name": name,
            "size": [round(w, 2), round(d, 2), round(h, 2)],
            "volume_cm3": round(volume / 1000.0, 2),
            "manifold": manifold,
            "fits_bed": max(w, d) <= opts.bed and h <= opts.bed,
            "flat": name in flat,
            "rotate_deg": rotated[name],
            **extras[name],
        }
    )

out = Path(opts.outdir).resolve()
stl_dir = out / "stl"
stl_dir.mkdir(parents=True, exist_ok=True)
for old in stl_dir.glob("*.stl"):
    old.unlink()
for obj in parts_coll.objects:
    for o in scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(
        filepath=str(stl_dir / f"{bpy.path.clean_name(obj.name)}.stl"),
        export_selected_objects=True,
        apply_modifiers=True,
        ascii_format=False,
    )
for screen in bpy.data.screens:  # 0.1 mm - 10 m view clip for the mm pack
    for area in screen.areas:
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.clip_start, space.clip_end = 0.1, 10000.0
bpy.ops.wm.save_as_mainfile(filepath=str(out / "parts.blend"), copy=True)
write_result(
    opts.result,
    {"blend": str(out / "parts.blend"), "stl_dir": str(stl_dir), "parts": parts},
)
