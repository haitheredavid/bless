# Concept sketches (sketches/front.svg, top.svg; 1 unit = 1 mm, origin at the pupils) as
# outline curves in Ref/Ref_Sketches, aligned on the pupils at Eye Height. Ref is
# user-owned: imported once; delete Ref_Sketches/<file> to re-import an edited sketch.
import math

import bpy
from kit import params, scene
from mathutils import Matrix, Vector

EYE = params.load()["Eye Height"]
SKETCHES = bpy.path.abspath("//sketches/")
guides = scene.collection("Ref_Sketches", scene.collection(scene.REF))


def place(fname, anchors, plane):
    if bpy.data.collections.get(fname) is not None:
        return 0
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=SKETCHES + fname)
    coll = bpy.data.collections[fname]
    new = [o for o in bpy.data.objects if o not in before]
    for parent in [c for c in bpy.data.collections if coll.name in c.children] + [
        bpy.context.scene.collection
    ]:
        if coll.name in parent.children:
            parent.children.unlink(coll)
    guides.children.link(coll)
    pts = [
        bpy.data.objects[n].matrix_world @ Vector(c)
        for n in anchors
        for c in bpy.data.objects[n].bound_box
    ]
    m = plane @ Matrix.Translation(-sum(pts, Vector()) / len(pts))
    for o in new:
        o.matrix_world = m @ o.matrix_world
        o.hide_select = True
        if o.type == "CURVE":  # outlines only: filled shapes hide the model
            o.data.dimensions = "2D"
            o.data.fill_mode = "NONE"
    return len(new)


# front: stood up in XZ, 180 mm ahead of the pupils; top: flat under the heads (the
# crania anchor sits 5 mm behind the pupils)
front = Matrix.Translation((0, -180, EYE)) @ Matrix.Rotation(math.radians(90), 4, "X")
top = Matrix.Translation((0, -5, EYE - 140))
n = place("front.svg", ["Socket_L", "Socket_R"], front) + place(
    "top.svg", ["Cranium_L", "Cranium_R"], top
)
if n:
    print(f"30_guides: imported {n} sketch curves")
