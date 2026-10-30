# step 4: Sketch guides as 2D outline curves (fill off) so they don't hide the heads
import math

import bpy
from mathutils import Matrix, Vector

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
D = bpy.path.abspath("//sketches/")
EYE = 260.0
ref = bpy.data.collections["Ref"]
guides = bpy.data.collections.get("Ref_Sketches") or bpy.data.collections.new(
    "Ref_Sketches"
)
if guides.name not in ref.children:
    ref.children.link(guides)


def place(fname, pupil_name, plane):
    """Import an mm SVG (1 unit = 1 mm) into Ref_Sketches and stand it so the named
    shape's centre (the pupils) sits at the head's eye point, on a plane behind/beside it."""
    old = bpy.data.collections.get(fname)
    if old:  # idempotent: replace the previous import
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=D + fname)
    coll = bpy.data.collections[fname]
    new = [o for o in bpy.data.objects if o not in before]
    for parent in [c for c in bpy.data.collections if coll.name in c.children] + [
        bpy.context.scene.collection
    ]:
        if coll.name in parent.children:
            parent.children.unlink(coll)
    guides.children.link(coll)
    if pupil_name:
        anchor = sum(
            (
                bpy.data.objects[n].matrix_world @ Vector(c)
                for n in pupil_name
                for c in bpy.data.objects[n].bound_box
            ),
            Vector(),
        ) / (8 * len(pupil_name))
    else:
        anchor = Vector((0, 0, 0))
    m = plane @ Matrix.Translation(-anchor)
    for o in new:
        o.matrix_world = m @ o.matrix_world
        o.hide_select = True
        if o.type == "CURVE":  # outlines only: filled shapes hide the model
            o.data.dimensions = "2D"
            o.data.fill_mode = "NONE"
    return len(new)


# Front: stand up in XZ, 180 mm in front of the pupils (clear of the snouts).
front = Matrix.Translation((0, -180, EYE)) @ Matrix.Rotation(math.radians(90), 4, "X")
# Top: lie flat under the heads; SVG -y (forward) -> world -Y. The crania anchor sits at
# SVG y = 5, i.e. 5 mm behind the pupils.
top = Matrix.Translation((0, -5, EYE - 140))
print(
    {
        "front": place("front.svg", ["Socket_L", "Socket_R"], front),
        "top": place("top.svg", ["Cranium_L", "Cranium_R"], top),
    }
)
