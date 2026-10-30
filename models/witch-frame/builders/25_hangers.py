# Hanger: one keyhole plate centred on the top rail, for a single nail or screw.
# Geometry and sizing: joinery.py (hanger_shells). The plate lives in the clip zone
# behind the backboard, butts the top rabbet wall and snaps into two slots cut in it (a
# live boolean on Frame, before 40_sections, so Rail_T inherits them). Like the prongs,
# it's in Model and 40_sections links it to Print.
import importlib
import sys
from pathlib import Path

import bpy
from kit import materials, mesh, scene

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

frame = bpy.data.objects["Frame"]
cut = joinery.union("Cut_HangerSlots", joinery.hanger_socket_shells(), scene.work())
mesh.boolean(frame, cut).solver = joinery.SOLVER

plate, keyhole = joinery.hanger_shells()
hanger = joinery.union("Hanger", plate, scene.model())
joinery.difference(hanger, joinery.union("_Keyhole", keyhole, scene.work()))
mesh.clean(hanger)
for p in hanger.data.polygons:
    p.use_smooth = False
materials.assign(hanger, materials.principled("PLA_Matte", "#8A8496", roughness=0.65))
hanger["rail"], hanger["along"] = "T", 0.0  # 70_assembly slides it in like a prong
print(
    f"hanger: {joinery.HANGER_W:.0f} x {joinery.HANGER_H:.0f} x {joinery.HANGER_T} plate, "
    f"keyhole {joinery.HANGER_HEAD:.0f} mm entry, head room {joinery.HANGER_ROOM:.1f} mm"
)
