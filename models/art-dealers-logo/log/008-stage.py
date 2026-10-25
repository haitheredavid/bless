# step 8: Stage: backdrop, two suns, world, EEVEE 1600x1000, Cam_hero/front/low/detail fitted from model.toml views
# Stage: render the logo inside this .blend. A grey sweep backdrop, two sun lights (suns don't
# care about the mm scale), a soft world, EEVEE, and one camera per `blend views` shot in
# model.toml. Cameras are fitted to the Logo as built, so rerun build_all after big size changes.
# Look through one: select Cam_<name>, then View > Cameras > Set Active Object as Camera
# (Ctrl+Numpad0). F12 renders the active camera.
import math
import tomllib
from pathlib import Path

import bpy
from kit import materials, scene
from mathutils import Vector

MODEL_TOML = Path(__file__).parents[1] / "model.toml"
VIEWS = tomllib.loads(MODEL_TOML.read_text()).get("views", [])
LENS, FILL = 50.0, 0.8  # mm lens; share of the frame the subject spans

stage = scene.collection("Stage")
for o in list(stage.objects):
    bpy.data.objects.remove(o, do_unlink=True)


def link(name: str, data) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, data)
    stage.objects.link(obj)
    return obj


# --- subject bounds (evaluated Logo) -----------------------------------------
logo = bpy.data.objects["Logo"]
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
pts = [logo.matrix_world @ v.co for v in logo.evaluated_get(dg).data.vertices]
lo = Vector(map(min, zip(*pts)))
hi = Vector(map(max, zip(*pts)))
centre, radius = (lo + hi) / 2, (hi - lo).length / 2

# --- backdrop: floor sweeping up into a wall behind (+Y), sized to the subject ----
s = max(radius, 50.0)
width, front, back, r, height = 8 * s, -4 * s, 1.5 * s, 1.5 * s, 4 * s
profile = [(front, 0.0), (back, 0.0)]
profile += [(back + r * math.sin(math.radians(90 * i / 24)), r * (1 - math.cos(math.radians(90 * i / 24)))) for i in range(1, 25)]  # fmt: skip
profile += [(back + r, height)]
verts = [
    (centre.x + x, centre.y + y, z - 0.05)
    for y, z in profile
    for x in (-width / 2, width / 2)
]
faces = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(len(profile) - 1)]
me = bpy.data.meshes.new("Backdrop")
me.from_pydata(verts, [], faces)
me.shade_smooth()
materials.assign(
    link("Backdrop", me), materials.principled("Backdrop", "#9EA0A4", roughness=0.9)
)

# --- lights + world ----------------------------------------------------------
for name, rot, energy, angle in (
    ("Key Light", (50, 0, -35), 3.5, 8),
    ("Rim Light", (60, 0, 150), 1.5, 15),
):
    sun = bpy.data.lights.new(name, "SUN")
    sun.energy, sun.angle = energy, math.radians(angle)
    link(name, sun).rotation_euler = [math.radians(a) for a in rot]
world = bpy.data.worlds.get("Stage World") or bpy.data.worlds.new("Stage World")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = materials.rgba("#B4B6BA")
bg.inputs["Strength"].default_value = 0.6
sc = bpy.context.scene
sc.world = world

# --- cameras, one per [[views]] ----------------------------------------------
tan_half = math.tan(2 * math.atan(36 / (2 * LENS)) / 2)
for v in VIEWS:
    a, e = math.radians(v["azimuth"]), math.radians(v["elevation"])
    d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    zoom = v.get("zoom", 1.0)
    target = Vector(v["target"]) if "target" in v else centre
    cam_data = bpy.data.cameras.new(f"Cam_{v['name']}")
    cam_data.lens, cam_data.clip_start, cam_data.clip_end = LENS, 1.0, 50 * s
    cam = link(f"Cam_{v['name']}", cam_data)
    cam.location = target + d * (radius / zoom) / (tan_half * FILL)
    # camera up follows world +Z, so the logo's top stays at the top of frame (top-down too)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

# --- render settings ---------------------------------------------------------
for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = engine
        break
    except TypeError:
        continue
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
sc.render.resolution_percentage = 100
try:
    sc.view_settings.view_transform = "AgX"
except TypeError:
    pass
sc.camera = bpy.data.objects.get("Cam_hero") or sc.camera
