# Corner coupon: a cheap test print of the TR corner and the hanger before the four rails.
# Three rail offcuts cut from the live Frame by the rails' own miter cutters and trimmed
# flat at z = TOP, just above the alignment spline's socket: Rail_T from x = T_FROM and
# Rail_R from y = R_FROM (both to the horn tip), and Rail_T's middle (+-M_HALF). They carry
# the real key pocket, spline sockets, seam chamfer, rabbet, glazing lip, the T+75 prong
# slot and the hanger's two slots, plus copies of Key_TR, Spline_TR, that prong and the
# Hanger. Checks: the key clicks in and holds, the spline closes the miter flush, the
# prong and hanger tongues snap into their slots, the prong presses a scrap of the real
# backboard, and a nail head enters the keyhole and locks behind its lip.
#
# Coupon collection: beside the model (+X), not rendered. Pack it on its own with
# `blend print-pack witch-frame --collection Coupon` (print/coupon/).
import importlib
import math
import sys
from pathlib import Path

import bmesh
import bpy
from kit import mesh, scene
from mathutils import Vector
from patterns import section_piece

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

OFFSET = Vector((300.0, 0.0, 0.0))  # beside the model, +X
PRONG = ("T", 75.0)  # the prong slot the coupon keeps
T_FROM = PRONG[1] - joinery.PRONG_W / 2 - 6.0  # Rail_T offcut starts here (x)
R_FROM = joinery.RY + joinery.KEY_GAP + joinery.KEY_W - joinery.KEY_LEG - 12.0  # (y)
M_HALF = joinery.HANGER_W / 2 + 6.0  # Rail_T middle offcut, +-x
SPLINE_TOP = (
    joinery.SPLINE_Z0 + joinery.SPLINE_H + joinery.SPLINE_W / 2
    + joinery.SPLINE_CLEAR * math.sqrt(2)
)  # fmt: skip
TOP = SPLINE_TOP + joinery.WALL + 1.0

frame = bpy.data.objects["Frame"]
coll = scene.collection("Coupon")
coll.hide_render = True
scene.clear(coll)

dims = frame.evaluated_get(bpy.context.evaluated_depsgraph_get()).dimensions
big = max(dims)
for name, r, lo, hi in (
    ("T", "T", (T_FROM, 0, -1), (big, big, TOP)),
    ("R", "R", (0, R_FROM, -1), (big, big, TOP)),
    ("M", "T", (-M_HALF, 0, -1), (M_HALF, big, TOP)),
):
    piece = mesh.from_bmesh(f"Coupon_{name}", bmesh.new(), coll)
    piece.location = OFFSET
    section_piece.apply(
        piece,
        Source=frame,
        Box_Min=Vector(lo),
        Box_Max=Vector(hi),
        Cutter=bpy.data.objects[f"Cut_Miter_{r}"],
    )

site = joinery.prong_sites().index(PRONG) + 1
for src in ("Key_TR", "Spline_TR", f"Prong_{site:02d}", "Hanger"):
    o = bpy.data.objects[src]
    copy = bpy.data.objects.new(f"Coupon_{src.split('_')[0]}", o.data)
    copy.location = OFFSET
    copy.color = o.color
    coll.objects.link(copy)

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for o in coll.objects:
    w, h, d = o.evaluated_get(dg).dimensions
    print(f"coupon: {o.name} {w:.1f} x {h:.1f} x {d:.1f} mm")
