# Requirement checks (brief.md), run by build_all.py after params are applied: fail the
# build on hard ones, warn on ones the current stage can't meet yet. Results go to
# bpy.app.driver_namespace["build_report"] for `blend build`.
#   fail: Mask and Body one closed piece each, Visor one per eye; each eye sees at least
#         FOV_MIN (outward, down, up; rays from the eyeball centres) past the Mask AND the
#         side heads; Mask (+ Visor) over MASK_MAX_G.
#   warn: Body over BODY_MAX_G (it's solid until it's shelled).
import math

import bmesh
import bpy
from kit import params
from mathutils import Vector

FOV_MIN = {"out": 45, "down": 60, "up": 12}  # degrees per eye
PUPIL_X, EYEBALL_Y = 31.0, 10.0  # IPD 63; eyeball centre ~10 mm behind the eye plane
MASK_MAX_G, BODY_MAX_G, DENSITY = 200.0, 600.0, 1.27  # g (brief.md), PETG g/cm3

eye_z = params.load()["Eye Height"]
dg = bpy.context.evaluated_depsgraph_get()
fails, warns, report = [], [], {}


def _mesh(name):
    obj = bpy.data.objects[name]
    ev = obj.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.data)
    bm.transform(obj.matrix_world)
    return obj, ev, bm


def _islands(bm) -> list[tuple[int, list[int]]]:
    """(face count, centre [x, y, z] mm) per connected piece, biggest first."""
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        n, c, stack = 0, Vector(), [f]
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            n += 1
            c += x.calc_center_median()
            stack += [g for e in x.edges for g in e.link_faces if g.index not in seen]
        out.append((n, [round(v) for v in c / n]))
    return sorted(out, reverse=True)


PIECES = {"Mask": 1, "Body": 1, "Visor": 2}  # visor: one grille lens per eye
for name, want in PIECES.items():
    _, _, bm = _mesh(name)
    islands, open_edges = _islands(bm), sum(1 for e in bm.edges if not e.is_manifold)
    report[name] = {
        "faces": len(bm.faces),
        "pieces": len(islands),
        "open_edges": open_edges,
        "cm3": round(bm.calc_volume() / 1000, 1),
    }
    if len(islands) != want or open_edges:
        where = ", ".join(f"{n} faces at {c}" for n, c in islands)
        fails.append(
            f"{name}: {len(islands)} pieces ({where}), {open_edges} open edges (want {want} closed)"
        )


def _fan(objs, origin, plane, side):
    """Degrees from straight ahead (-Y) until a ray hits one of objs (within 400 mm)."""
    a = 0
    while a < 120:
        ang = math.radians(side * a)
        d = (
            Vector((math.sin(ang), -math.cos(ang), 0))
            if plane == "h"
            else Vector((0, -math.cos(ang), math.sin(ang)))
        )
        for ev, inv in objs:
            ok, *_ = ev.ray_cast(inv @ origin, inv.to_3x3() @ d, distance=400.0)
            if ok:
                return a
        a += 1
    return a


def _evs(*names):
    return [
        (
            bpy.data.objects[n].evaluated_get(dg),
            bpy.data.objects[n].matrix_world.inverted(),
        )
        for n in names
    ]


fov = {}
for eye, x in (("L", -PUPIL_X), ("R", PUPIL_X)):
    o, out_side = Vector((x, EYEBALL_Y, eye_z)), (-1 if x < 0 else 1)
    seen = _evs("Mask", "Body")
    fov[eye] = {"out": _fan(seen, o, "h", out_side), "down": _fan(seen, o, "v", -1),
                "up": _fan(seen, o, "v", 1), "out_mask_only": _fan(_evs("Mask"), o, "h", out_side)}  # fmt: skip
    for k, lo in FOV_MIN.items():
        if fov[eye][k] < lo:
            what = (
                "a side head"
                if k == "out" and fov[eye]["out_mask_only"] > fov[eye][k]
                else "the Mask"
            )
            fails.append(
                f"FOV {eye} eye {k} {fov[eye][k]} deg, blocked by {what} (want >= {lo})"
            )
report["fov_deg"] = fov

grams = {n: report[n]["cm3"] * DENSITY for n in ("Mask", "Body", "Visor")}
report["weight_g"] = {n: round(g) for n, g in grams.items()}
if grams["Mask"] + grams["Visor"] > MASK_MAX_G:
    fails.append(
        f"mask ~{grams['Mask'] + grams['Visor']:.0f} g (want <= {MASK_MAX_G:.0f})"
    )
if grams["Body"] > BODY_MAX_G:
    warns.append(
        f"shoulder piece ~{grams['Body']:.0f} g solid (want <= {BODY_MAX_G:.0f}); not shelled yet"
    )

bpy.app.driver_namespace["build_report"] = {
    "report": report,
    "fails": fails,
    "warns": warns,
}
for w in warns:
    print(f"checks: WARN {w}")
print(f"checks: {report}")
if fails:
    raise AssertionError("checks failed:\n  " + "\n  ".join(fails))
