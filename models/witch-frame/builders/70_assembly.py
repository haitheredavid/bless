# Assembly animation: how the printed parts go together, in its own scene "Assembly".
#
# The parts are copies of the Print collection (rails stay live GN cuts of Frame) plus
# the glazing/art/backboard proxies, flipped face-down (back up) the way the frame is
# assembled on a table. Render with:
#   uv run blend animate witch-frame --scene Assembly --collection Assembly --isometric
# Timeline (24 fps): splines slide into their rider rails (TR, BR into Rail_R; TL, BL
# into Rail_L) -> Rail_T closes onto Rail_R and Rail_B onto Rail_L, each along its miter's
# normal -> the two L halves close along the diagonal (TL and BR at once) -> the back
# keys drop into their pockets and click -> glazing, art, backboard drop into the rabbet
# -> prongs drop onto the board and slide out into their slots.
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).parent))
import joinery

SCENE, COLL = "Assembly", "Assembly"
FPS = 24
LIFT = 70.0  # how far drop-in parts start above their seat (mm)
SLIDE = 25.0  # how far a spline starts out of its socket (mm)
SPREAD = 45.0  # how far a rail starts out along a miter normal (mm)
APPEAR = 8  # drop-in parts show up this many frames before they move
# (first frame, last frame) per beat
SPLINES, CLOSE_1, CLOSE_2, KEYS = (12, 34), (42, 66), (74, 98), (106, 126)
GLAZING, ART, BOARD = (134, 154), (152, 172), (170, 190)
PRONGS_DROP, PRONGS_IN, HOLD = (198, 214), (218, 234), 258

main = bpy.data.scenes["Scene"]
sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
sc.unit_settings.system = main.unit_settings.system
sc.unit_settings.scale_length = main.unit_settings.scale_length
sc.unit_settings.length_unit = main.unit_settings.length_unit
sc.frame_start, sc.frame_end, sc.render.fps = 1, HOLD, FPS

coll = bpy.data.collections.get(COLL)
if coll is None:
    coll = bpy.data.collections.new(COLL)
if coll.name not in sc.collection.children:
    sc.collection.children.link(coll)
for o in list(coll.objects):  # rebuild: drop the previous copies
    bpy.data.objects.remove(o, do_unlink=True)

FLIP = Matrix.Rotation(math.pi, 4, "X")  # face down, back up (z -> -z, y -> -y)


def flip(v) -> Vector:
    """A model-space offset as seen in the flipped assembly."""
    return FLIP.to_3x3() @ Vector(v)


def copy(name: str) -> bpy.types.Object:
    src = bpy.data.objects[name]
    obj = src.copy()  # shares mesh data; GN/boolean modifiers come along
    obj.name = f"Asm_{name}"
    obj.animation_data_clear()
    coll.objects.link(obj)
    obj.matrix_world = FLIP @ src.matrix_world
    return obj


def path(obj, keys: list[tuple[int, Vector]], appear: int | None = None) -> None:
    """Key obj.location at home + offset for each (frame, model-space offset); appear
    hides it until that frame, so waiting parts don't cover the earlier ones."""
    home = obj.location.copy()
    for frame, off in keys:
        obj.location = home + flip(off)
        obj.keyframe_insert("location", frame=frame)
    if appear is not None:
        for frame, hidden in ((1, True), (max(1, appear), False)):
            obj.hide_render = obj.hide_viewport = hidden
            obj.keyframe_insert("hide_render", frame=frame)
            obj.keyframe_insert("hide_viewport", frame=frame)


def into_h(corner) -> Vector:
    """Unit normal of a corner's miter, pointing into its horizontal rail (model space)."""
    sx, sy = joinery.CORNERS[corner]
    return Vector((-sx, sy, 0)) / math.sqrt(2)


zero = Vector()
half = (
    Vector((1, 1, 0)).normalized() * SPREAD
)  # T+R half, open from B+L (TL, BR normals)
rail_open = {  # model-space offset per rail: (before CLOSE_1, between the closes)
    "T": (half + into_h("TR") * SPREAD, half),
    "R": (half, half),
    "B": (into_h("BL") * SPREAD, zero),
    "L": (zero, zero),
}
for r, (o1, o2) in rail_open.items():
    path(copy(f"Rail_{r}"), [(1, o1), (CLOSE_1[0], o1), (CLOSE_1[1], o2),
                             (CLOSE_2[0], o2), (CLOSE_2[1], zero)])  # fmt: skip

# each spline goes into its rider first (along the miter normal, from the far side),
# then rides with it while the frame closes
for corner, rider in (("TR", "R"), ("BR", "R"), ("TL", "L"), ("BL", "L")):
    _, o2 = rail_open[rider]
    out = into_h(corner) * SLIDE  # starts on the horizontal rail's side of the miter
    path(copy(f"Spline_{corner}"), [(1, o2 + out), (SPLINES[0], o2 + out),
                                    (SPLINES[1], o2), (CLOSE_2[0], o2),
                                    (CLOSE_2[1], zero)], appear=SPLINES[0] - APPEAR)  # fmt: skip

lift = Vector((0, 0, -LIFT))  # model -z = toward the back = up in the assembly
for corner in joinery.CORNERS:
    path(copy(f"Key_{corner}"), [(1, lift), (KEYS[0], lift), (KEYS[1], zero)],
         appear=KEYS[0] - APPEAR)  # fmt: skip

for name, (a, b) in (
    ("Glazing_Proxy", GLAZING),
    ("Art_Proxy", ART),
    ("Backboard_Proxy", BOARD),
):
    path(copy(name), [(1, lift * 1.4), (a, lift * 1.4), (b, zero)], appear=a - APPEAR)

for src in sorted(
    (o for o in bpy.data.collections["Print"].objects if "rail" in o),
    key=lambda o: o.name,
):
    inward = -Vector((*joinery.RAILS[src["rail"]], 0)) * (joinery.PRONG_DEPTH + 1)
    path(copy(src.name), [(1, inward + lift * 0.6), (PRONGS_DROP[0], inward + lift * 0.6),
                          (PRONGS_DROP[1], inward), (PRONGS_IN[0], inward),
                          (PRONGS_IN[1], zero)], appear=PRONGS_DROP[0] - APPEAR)  # fmt: skip

print(f"assembly: {len(coll.objects)} parts, frames 1-{HOLD} at {FPS} fps")
