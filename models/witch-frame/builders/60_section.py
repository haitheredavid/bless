# Live section cut, beside the model (Section collection; never checked/exported/rendered).
#
# Copies of the frame, prongs and proxies sit under Section_Root (offset -X so they don't
# overlap Model). Each copy has a boolean against Section_Cutter, a box parented to the
# Section_Plane empty: it removes everything on the plane's -X side, and the cut faces turn
# red. Move or rotate Section_Plane (it uses model coordinates) to move the cut:
#   X = 0      mid-span of the top/bottom rails (the narrowest wall)
#   X = 75     through the top-right prong and its slot
#   rotate Z   45-ish to cut along a hip line toward a corner tip
# Cam_section frames the whole cut; Cam_section_rail zooms on the top rail's profile.
import math

import bpy
from kit import materials, scene

OFFSET = (-450.0, 0.0, 0.0)  # -X: the cameras look from -X, so Model is behind the cut
PLANE_X = 0.0

sec = scene.collection("Section")
sec.hide_render = True
scene.clear(sec)

root = bpy.data.objects.new("Section_Root", None)
root.location = OFFSET
root.empty_display_size = 20
sec.objects.link(root)

plane = bpy.data.objects.new("Section_Plane", None)
plane.empty_display_type = "SINGLE_ARROW"  # arrow = +X, the side that's kept
plane.empty_display_size = 60
plane.parent = root
plane.location = (PLANE_X, 0, 0)
sec.objects.link(plane)

cut_mat = materials.principled("Section_Cut", "#C8323C", roughness=0.8)
cutter_me = bpy.data.meshes.new("Section_Cutter")
s = 1000.0
verts = [(x, y, z) for x in (-s, 0) for y in (-s, s) for z in (-s, s)]
faces = [
    (0, 1, 3, 2),
    (4, 6, 7, 5),
    (0, 4, 5, 1),
    (2, 3, 7, 6),
    (0, 2, 6, 4),
    (1, 5, 7, 3),
]
cutter_me.from_pydata(verts, [], faces)
cutter_me.materials.append(cut_mat)
cutter = bpy.data.objects.new("Section_Cutter", cutter_me)
cutter.parent = plane
cutter.display_type = "WIRE"
cutter.hide_render = True
sec.objects.link(cutter)

modes = [
    i.identifier
    for i in bpy.types.BooleanModifier.bl_rna.properties["material_mode"].enum_items
]
sources = [o for o in scene.model().objects if o.type == "MESH"]
sources += [
    bpy.data.objects[n]
    for n in ("Backboard_Proxy", "Art_Proxy")
    if n in bpy.data.objects
]
for src in sources:
    obj = src.copy()
    obj.name = f"Sec_{src.name}"
    # own mesh with the cut material already in a slot: the viewport only draws as many
    # materials as the object has slots, so a transferred-only material shows grey
    obj.data = src.data.copy()
    obj.data.materials.append(cut_mat)
    obj.modifiers.clear()
    obj.parent = root
    obj.matrix_parent_inverse.identity()
    sec.objects.link(obj)
    mod = obj.modifiers.new("Section", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    if "TRANSFER" in modes:
        mod.material_mode = "TRANSFER"  # cut faces take the cutter's red material

for name, target, scale in (
    ("Cam_section", (0, 0, 20), 420.0),
    ("Cam_section_rail", (0, 160, 20), 70.0),
):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    cam.data.clip_start, cam.data.clip_end = 1, 5000
    cam.parent = plane  # follows the cut; looks at it from the removed (-X) side
    cam.location = (-600, target[1], target[2])
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    sec.objects.link(cam)
