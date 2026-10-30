# Print sweep parts, one collection (= one print pack) per family in catalog.FAMILIES.
# Per joint: a nominal A and one B per sweep clearance (one A tests every B). Loose
# joints carry the clearance in both bars' sockets, so they get an A+B pair per
# clearance and one nominal loose part. Sizes from params.toml [base]; clearances from
# catalog.py. Each part carries obj["joints"] for the print spec. print-pack drops and
# lays parts out itself; the layout here is for viewing.
import importlib
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import catalog

importlib.reload(catalog)
from kit import gn, params, scene
from patterns import joints
from patterns.joints import joint_bar

GAP = 8.0  # between parts in the viewing layout
ROW_MAX = 240.0  # wrap a joint's row before it leaves the bed

p = params.load("base")
dg = bpy.context.evaluated_depsgraph_get


def specs(j):
    """(name, part, clearance, label) per printed part."""
    if not j.loose:
        out = [(f"{j.code}_A", 0, 0.0, catalog.label(j, None))]
        out += [
            (f"{j.code}_B{catalog.tag(c)}", 1, c, catalog.label(j, c)) for c in j.sweep
        ]
        return out
    out = []
    for c in j.sweep:
        t, lab = catalog.tag(c), catalog.label(j, c)
        out += [(f"{j.code}_A{t}", 0, c, lab), (f"{j.code}_B{t}", 1, c, lab)]
    return out + [(f"{j.code}_K", 2, 0.0, "")]


def mates(j, part, c) -> list:
    """print-spec joints[] entries for one part."""
    base = {
        "kind": j.kind,
        "param": f"builders/catalog.py:{j.code}.fit",
        "coupon": j.code,
    }
    if j.loose:
        pairs = [
            (f"{j.code}_A{catalog.tag(s)}", f"{j.code}_B{catalog.tag(s)}", s)
            for s in j.sweep
        ]
        if part == 2:
            return [{**base, "id": f"{j.code}-{catalog.tag(s)}{e}", "mate": m, "clearance_mm": s}
                    for a, b, s in pairs for m, e in ((a, "a"), (b, "b"))]  # fmt: skip
        return [{**base, "id": f"{j.code}-{catalog.tag(c)}{'ab'[part]}", "mate": f"{j.code}_K", "clearance_mm": c}]  # fmt: skip
    if part == 0:
        return [{**base, "id": f"{j.code}-{catalog.tag(s)}", "mate": f"{j.code}_B{catalog.tag(s)}", "clearance_mm": s}
                for s in j.sweep]  # fmt: skip
    return [{**base, "id": f"{j.code}-{catalog.tag(c)}", "mate": f"{j.code}_A", "clearance_mm": c}]  # fmt: skip


y = (
    -40.0
)  # top edge of the next row; packs lie below the board (-y), family after family
for fam, coll_name in catalog.FAMILIES.items():
    members = [j for j in catalog.JOINTS if j.family == fam]
    coll = bpy.data.collections.get(coll_name)
    if coll is not None:
        scene.clear(coll)
    if not members:
        if coll is not None:
            bpy.data.collections.remove(coll)
        continue
    coll = scene.collection(coll_name)
    coll.hide_render = True
    for j in members:
        pattern = getattr(joints, j.pattern)
        x, row_h = 0.0, 0.0
        for name, part, c, text in specs(j):
            obj = gn.host(name, coll)
            joint_bar.apply(obj, Part=part, Label=text)
            pattern.apply(obj, Part=part, Clearance=c, **j.inputs)
            params.apply(p, objects=[obj])
            obj["joints"] = json.dumps(mates(j, part, c))
            obj["joint"] = j.code
            ev = obj.evaluated_get(dg())
            xs = [v[0] for v in ev.bound_box]
            ys = [v[1] for v in ev.bound_box]
            w, d = max(xs) - min(xs), max(ys) - min(ys)
            if x and x + w > ROW_MAX:
                x, y = 0.0, y - row_h - GAP
                row_h = 0.0
            obj.location = (x - min(xs), y - max(ys), 0.0)
            x += w + GAP
            row_h = max(row_h, d)
        y -= row_h + 2 * GAP
