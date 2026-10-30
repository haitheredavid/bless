"""params.toml -> GN modifier inputs, plus unit helpers and a live variant grid.

params.toml (next to model.blend):

    [base]
    Depth = 40.0                # every GN modifier with a "Depth" input gets it
    "Frame/Rabbet Width" = 6.0  # only object Frame's modifiers

    [variants.deep]             # overrides only
    Depth = 60.0

Params are the source of truth; a hand-tuned modifier value that should stick goes back
into params.toml (see .context/modeling-guide.md).
"""

import tomllib

import bpy
from mathutils import Vector

from kit import gn, scene

GRID = "Variants"


def load(variant: str = "base") -> dict:
    """[base] merged with [variants.<variant>]."""
    path = bpy.path.abspath("//params.toml")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return {}
    base = dict(data.get("base", {}))
    if variant == "base":
        return base
    if variant not in data.get("variants", {}):
        raise KeyError(f"no [variants.{variant}] in params.toml")
    return {**base, **data["variants"][variant]}


def variants() -> list[str]:
    path = bpy.path.abspath("//params.toml")
    try:
        with open(path, "rb") as f:
            return ["base", *tomllib.load(f).get("variants", {})]
    except FileNotFoundError:
        return ["base"]


def targets() -> list:
    """Objects params apply to by default: Model and Work (a Work object can drive Model
    parts, e.g. a rig the parts read through Object Info), minus the variant grid."""
    grid_objs = (
        set(bpy.data.collections[GRID].all_objects)
        if GRID in bpy.data.collections
        else set()
    )
    return [
        o
        for o in (*scene.model().all_objects, *scene.work().all_objects)
        if o not in grid_objs
    ]


def apply(params: dict | str = "base", objects=None) -> dict:
    """Push params into GN inputs of objects (default: targets()). Returns
    {"set": [(obj, modifier, input, value)], "unused": [keys that matched nothing]}."""
    if isinstance(params, str):
        params = load(params)
    objects = list(objects if objects is not None else targets())
    applied, used = [], set()
    for key, value in params.items():
        target, _, name = key.rpartition("/")
        for obj in objects:
            # grid copies are named "<variant>:<object>"
            if target and target not in (obj.name, obj.name.partition(":")[2]):
                continue
            for mod in gn.gn_modifiers(obj):
                if gn.has_input(mod, name):
                    gn.set_input(mod, name, value)
                    applied.append((obj.name, mod.name, name, value))
                    used.add(key)
    return {"set": applied, "unused": sorted(set(params) - used)}


def missing(params: dict | str = "base", objects=None) -> list[str]:
    """Value inputs (not geometry/object/collection/material) on the GN modifiers of
    objects (default: targets()) that no params key covers, as "Object/Input". A rebuild that
    re-creates an input resets it to the socket default, so an uncovered input can change
    silently; builds should treat a non-empty result as an error."""
    if isinstance(params, str):
        params = load(params)
    keys = set(params)
    objects = list(objects if objects is not None else targets())
    out = []
    for obj in objects:
        for mod in gn.gn_modifiers(obj):
            for name in gn.inputs(mod):
                sock = gn._items(mod.node_group, "INPUT")[name]
                if sock.socket_type in (
                    "NodeSocketObject",
                    "NodeSocketCollection",
                    "NodeSocketMaterial",
                ):
                    continue
                if name not in keys and f"{obj.name}/{name}" not in keys:
                    out.append(f"{obj.name}/{name}")
    return sorted(set(out))


# --- units -----------------------------------------------------------------------


def _per_metre() -> float:
    """Blender units per metre in this file (1000 for an mm model, 1 for metres)."""
    return 1.0 / (bpy.context.scene.unit_settings.scale_length or 1.0)


def inch(x: float) -> float:
    return x * 0.0254 * _per_metre()


def mm(x: float) -> float:
    return x * 0.001 * _per_metre()


def cm(x: float) -> float:
    return x * 0.01 * _per_metre()


# --- live variant grid -------------------------------------------------------------


def grid(names: list[str] | None = None, gap: float = 0.25, axis: str = "X") -> dict:
    """Lay variants side by side for one `look`: each variant is a copy of every Model
    object (sharing mesh data and node groups) with that variant's params, offset along
    axis by the model's size plus gap (a fraction). Copies go in Work/Variants with a text
    label; Model is hidden until clear_grid()."""
    clear_grid()
    names = names or variants()
    src = [o for o in scene.model().all_objects if o.type == "MESH"]
    if not src:
        raise RuntimeError("Model is empty")
    # objects the parts read through GN object inputs (e.g. a Work rig) are copied too, so
    # a variant's params on them reach that variant's parts
    deps = []
    for o in src:
        for mod in gn.gn_modifiers(o):
            for name, sock in gn._items(mod.node_group, "INPUT").items():
                if sock.socket_type != "NodeSocketObject":
                    continue
                ref = gn._read(mod, sock.identifier)
                if (
                    ref is not None
                    and ref not in src
                    and ref not in deps
                    and gn.gn_modifiers(ref)
                ):
                    deps.append(ref)
    dg = bpy.context.evaluated_depsgraph_get()
    corners = [
        o.matrix_world @ Vector(c) for o in src for c in o.evaluated_get(dg).bound_box
    ]
    i = "XYZ".index(axis)
    size = max(c[i] for c in corners) - min(c[i] for c in corners)
    low = min(c[1] for c in corners)
    step = size * (1 + gap)
    coll = scene.collection(GRID, scene.work())
    coll.hide_render = True
    out = {}
    for k, name in enumerate(names):
        offset = Vector((0, 0, 0))
        offset[i] = k * step
        copies, remap = [], {}
        for o in deps:  # unmoved: parts read them in ORIGINAL space
            c = o.copy()
            c.name = f"{name}:{o.name}"
            coll.objects.link(c)
            remap[o] = c
        for o in src:
            c = o.copy()
            c.name = f"{name}:{o.name}"
            c.location = o.location + offset
            coll.objects.link(c)
            copies.append(c)
        for c in copies:
            for mod in gn.gn_modifiers(c):
                for sname, sock in gn._items(mod.node_group, "INPUT").items():
                    if (
                        sock.socket_type == "NodeSocketObject"
                        and gn._read(mod, sock.identifier) in remap
                    ):
                        gn.set_input(mod, sname, remap[gn._read(mod, sock.identifier)])
        res = apply(load(name), [*remap.values(), *copies])
        label = bpy.data.objects.new(f"{name}:label", bpy.data.curves.new(name, "FONT"))
        label.data.body = name
        label.data.size = size * 0.08
        label.location = offset + Vector((0, low - size * 0.15, 0))
        coll.objects.link(label)
        out[name] = {"objects": [c.name for c in copies], "unused": res["unused"]}
    scene.model().hide_viewport = True
    return out


def clear_grid() -> None:
    coll = bpy.data.collections.get(GRID)
    if coll is not None:
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(coll)
    scene.model().hide_viewport = False
