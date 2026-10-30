# Cameras matching the `blend views` shots in session.toml, so they can be viewed in
# Blender: select Cam_<name> and press Ctrl+Numpad0 (or set it as the scene camera).
# The renders stand the frame up (+Z face -> -Y); here the frame lies flat, so each view
# direction is rotated back and the camera's up is +Y (the art's top) for upright shots.
import math

import bpy
from kit import scene
from mathutils import Matrix, Vector

# name: (azimuth, elevation, upright, target in model coords, distance mm)
VIEWS = {
    "hero": (-62, 12, True, (0, 0, 20), 820),
    "front": (-90, 0, True, (0, 0, 20), 770),
    "profile": (-14, 0, True, (0, 0, 20), 770),
    "plan": (-90, 89, False, (0, 0, 20), 770),
    "back": (118, 14, True, (0, 0, 20), 820),
    "corner": (-55, 18, True, (127, 163, 20), 220),
    "key": (110, 35, True, (119, 157, 3), 130),
    "prong": (105, 30, True, (75, 150, 3), 110),
}

views = scene.collection("Views")
views.hide_render = True
for name, (az, el, upright, target, dist) in VIEWS.items():
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    up = Vector((0, 0, 1))
    if upright:
        d, up = Vector((d.x, d.z, -d.y)), Vector((0, 1, 0))
    elif el > 80:  # looking straight down: keep the art's top at the top of frame
        up = Vector((0, 1, 0))
    z = d.normalized()
    x = up.cross(z).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = Vector(target) + z * dist
    cam_name = f"Cam_{name}"
    cam = bpy.data.objects.get(cam_name)
    if cam is None:
        cam = bpy.data.objects.new(cam_name, bpy.data.cameras.new(cam_name))
        views.objects.link(cam)
    cam.matrix_world = m
    cam.data.lens, cam.data.clip_start, cam.data.clip_end = 50, 1, 10000

sc = bpy.context.scene
sc.render.resolution_x = sc.render.resolution_y = 1200  # square, like the renders
sc.camera = bpy.data.objects["Cam_hero"]
