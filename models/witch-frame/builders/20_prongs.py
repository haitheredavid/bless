# Flex prongs: 10 spring tabs that hold the art stack from the back, no screws or tools.
#
# Stack (z up from the wall/back plane), all cut to the 9x12" art size: glazing z 7-9
# against the lip, art on its 3 mm backboard z 4-7. Each prong's tongue pushes 5 mm into a
# slot in the rabbet's side wall (a live boolean on Frame, gable-roofed so it prints
# without bridging) and snaps: barbs on its two slit-freed side arms spring into a wider
# pocket at the slot's end (joinery.tongue_path). Its arm reaches 14 mm over the
# backboard and a bump near the tip presses the stack forward. Relaxed, the bump reaches
# z 4.9, so the board's back (z 4) deflects it 0.9 mm: about 1.3% strain in a 1.4 mm PETG
# arm printed flat, and up to 2.5% for a stack 0.8 mm thicker. Prongs live in Model
# (40_sections links them to Print).
import importlib
import sys
from pathlib import Path

import bpy
from kit import materials, mesh, scene

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

frame = bpy.data.objects["Frame"]
shells = [s for rail, along in joinery.prong_sites() for s in joinery.prong_socket_shells(rail, along)]  # fmt: skip
cut = joinery.union("Cut_ProngSockets", shells, scene.work())
mesh.boolean(frame, cut).solver = joinery.SOLVER  # live: the frame stays parametric

pla = materials.principled("PLA_Matte", "#8A8496", roughness=0.65)
for i, (rail, along) in enumerate(joinery.prong_sites(), 1):
    prong = joinery.union(
        f"Prong_{i:02d}", joinery.prong_shells(rail, along), scene.model()
    )
    mesh.clean(prong)
    for p in prong.data.polygons:
        p.use_smooth = False
    materials.assign(prong, pla)
    prong["rail"], prong["along"] = rail, along  # 70_assembly slides each one in
print(f"prongs: {len(joinery.prong_sites())} sockets + prongs")
