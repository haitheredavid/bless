# step 6: Collar mode: bust proxy (eye height 260->420, curves raised +160), CTL_Collar shoulder yoke, side heads on necks rising from shoulder anchors (Side From Collar, Shoulder Width/Drop/Forward); variants collar, collar-asym
# Collar mode: raise the rig so a torso proxy fits above z=0, extend the proxy neck, add the
# torso blobs and the CTL_Collar yoke, rebuild heads (Side From Collar) and the proxy.
import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
OLD, NEW = 260.0, 420.0
moved = []
for coll in ("CTL_Head", "Ref_HeadProxy_Blobs"):
    for o in bpy.data.collections[coll].all_objects:
        if abs(o.location.z - OLD) < 1e-3:  # only curves still at the old eye height
            o.location.z = NEW
            moved.append(o.name)
neck = bpy.data.objects.get("Proxy_Neck")
if neck:  # the old neck stopped at z=0 (head-local -202); run it into the chest
    neck.data.splines[0].bezier_points[1].co = (0, 92, -230)
    neck.data.splines[0].bezier_points[1].radius = 60
print("moved", len(moved))

D = bpy.path.abspath("//out/steps/")
exec(open(D + "02_heads.py").read(), {"__name__": "step"})  # noqa: S102, SIM115 - heads tree + CTL_Collar
exec(open(D + "01_proxy.py").read(), {"__name__": "step"})  # noqa: S102, SIM115 - torso blobs + relink
