# Print sectioning + joinery: four mitered rails, joined at the corners.
#
# Rails (Print collection) are live GN_SectionPiece cuts of Frame: edit the frame (its
# Control outline or modifier inputs) and the rails follow. Each miter runs at 45 deg
# through the sight and rabbet corners (joinery.K); a wedge cutter per rail end removes
# the neighbour's side and leans SEAM_CHAMFER into the back edge (elephant's foot).
#
# Joints (joinery.py), one identical set per corner, cut into Frame as live booleans
# before sectioning so they cross the miter:
# - Key_<corner>: an L tenon pressed into an L pocket on the back. Snap arms catch under
#   the pocket's mouth lip, so it clicks in and holds the corner closed.
# - Spline_<corner>: a 10 mm alignment tenon across the miter at the sight corner, above
#   the glazing lip, keeping the visible miter line flush.
# Neither stands proud of a rail, so the 356 mm rails keep their 45 deg bed fit.
import importlib
import math
import sys
from pathlib import Path

import bmesh
import bpy
from kit import mesh, scene
from mathutils import Vector, geometry
from patterns import section_piece

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

BED = 256.0
BED_MARGIN = 2.0  # keep this much clear of the bed edge at the best rotation

frame = bpy.data.objects["Frame"]
parts = scene.parts()
for o in list(parts.objects):  # rebuild Print: drop our parts, unlink shared ones
    if len(o.users_collection) == 1:
        bpy.data.objects.remove(o, do_unlink=True)
    else:
        parts.objects.unlink(o)

keys = joinery.union(
    "Cut_Keys",
    [s for c in joinery.CORNERS for s in joinery.key_pocket_shells(c)],
    scene.work(),
)
spline_bm = bmesh.new()
for c in joinery.CORNERS:
    joinery.spline_socket(spline_bm, c)
for cutter in (keys, mesh.from_bmesh("Cut_Splines", spline_bm, scene.work())):
    # EXACT empties the frame on the key cut (or, with self-intersection on, leaves two
    # open edges at the BR horn tip); Manifold cuts both cleanly
    mesh.boolean(frame, cutter).solver = joinery.SOLVER

bpy.context.view_layer.update()
dims = frame.evaluated_get(bpy.context.evaluated_depsgraph_get()).dimensions
big = max(dims) * 2
# rail: (box min, box max, (corner, side kept) per miter end)
RAILS = {
    "T": ((-big, 0), (big, big), (("TR", "H"), ("TL", "H"))),
    "B": ((-big, -big), (big, 0), (("BR", "H"), ("BL", "H"))),
    "R": ((0, -big), (big, big), (("TR", "V"), ("BR", "V"))),
    "L": ((-big, -big), (0, big), (("TL", "V"), ("BL", "V"))),
}
for r, (lo, hi, ends) in RAILS.items():
    bm = bmesh.new()
    for corner, keep in ends:
        joinery.miter_wedges(bm, corner, keep, top=dims.z + 10)
    cutter = mesh.from_bmesh(f"Cut_Miter_{r}", bm, scene.work())
    cutter.display_type, cutter.hide_render = "WIRE", True
    rail = mesh.from_bmesh(f"Rail_{r}", bmesh.new(), parts)
    section_piece.apply(
        rail,
        Source=frame,
        Box_Min=Vector((*lo, -1)),
        Box_Max=Vector((*hi, dims.z + 10)),
        Cutter=cutter,
    )

for c in joinery.CORNERS:
    key = joinery.union(f"Key_{c}", joinery.key_shells(c), parts)
    mesh.clean(key)
    key.color = (0.9, 0.55, 0.2, 1)
    key["corner"] = c
    bm = bmesh.new()
    joinery.spline_part(bm, c)
    spline = mesh.from_bmesh(f"Spline_{c}", bm, parts)
    spline.color = (0.9, 0.55, 0.2, 1)
    spline["corner"] = c
for part in (
    o for o in scene.model().objects if o.name.startswith(("Prong_", "Hanger"))
):
    parts.objects.link(part)


def bed_fit(obj) -> tuple[float, float]:
    """Smallest square side the part's footprint fits in, and the z rotation (deg) for it."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).data
    pts = [v.co.to_2d() for v in me.vertices]
    hull = [pts[i] for i in geometry.convex_hull_2d(pts)]
    best = (math.inf, 0.0)
    for step in range(0, 900, 5):
        a = math.radians(step / 10)
        ca, sa = math.cos(a), math.sin(a)
        xs = [p.x * ca - p.y * sa for p in hull]
        ys = [p.x * sa + p.y * ca for p in hull]
        side = max(max(xs) - min(xs), max(ys) - min(ys))
        best = min(best, (side, step / 10))
    return best


bpy.context.view_layer.update()
for r in RAILS:
    rail = parts.objects[f"Rail_{r}"]
    side, deg = bed_fit(rail)
    assert side <= BED - BED_MARGIN, f"Rail_{r} needs a {side:.1f} mm square"
    rail["bed_fit"] = (round(side, 1), deg)
    w, h, d = rail.evaluated_get(bpy.context.evaluated_depsgraph_get()).dimensions
    print(
        f"sections: Rail_{r} {w:.1f} x {h:.1f} x {d:.1f} mm, fits {side:.1f} at {deg} deg"
    )
print(
    f"sections: 4 x Key {joinery.KEY_LEG:.0f} mm legs x {joinery.KEY_W:.0f} x "
    f"{joinery.KEY_T:.0f}; 4 x Spline {2 * joinery.SPLINE_D:.0f} x {joinery.SPLINE_W:.0f} x "
    f"{joinery.SPLINE_H + joinery.SPLINE_W / 2:.1f} (gable)"
)
