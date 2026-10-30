# step 13: Promoted to builders: 10_proxy (baked, re-bake on blob change), 20_heads (Work/Rig + Mask/Body/Visor groups, each with only its inputs), 30_guides, checks.py; headless 'blend build' (51 s); kit: reset keeps interface, params cover Work + missing() fails the build
# Rig + parts. Control/CTL_Head/* (head blob curves, cutters) and Control/CTL_Collar are
# created once and stay user-owned. Work/Rig (GN_CerberusMask_Rig) poses them into tagged
# world-space curves; the part objects read the Rig, each with only its own inputs, so an
# edit re-evaluates only the parts that use it:
#   Model/Mask   GN_CerberusMask_Mask   the center head as a shell around Ref/HeadProxy
#   Model/Body   GN_CerberusMask_Body   side heads on necks + shoulder yoke
#   Model/Visor  GN_CerberusMask_Visor  eye grille insert glued inside the mask
# Work must stay visible: objects in a hidden collection aren't evaluated, so the parts
# would come out empty.
import importlib
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import blob_geo
from kit import gn, scene

importlib.reload(blob_geo)

colls = blob_geo.head_controls()
colls["Collar"] = blob_geo.collar_controls()

old = bpy.data.node_groups.get("GN_CerberusMask_Heads")  # single tree before the split
if old is not None:
    bpy.data.node_groups.remove(old)

rig = gn.host("Rig", scene.work())
gn.modifier(rig, blob_geo.rig_group(colls))

proxy = bpy.data.objects["HeadProxy"]
for name, group in (
    ("Mask", blob_geo.mask_group()),
    ("Body", blob_geo.body_group()),
    ("Visor", blob_geo.visor_group()),
):
    obj = gn.host(name)
    mod = gn.modifier(obj, group, Rig=rig)
    if gn.has_input(mod, "Face Proxy"):
        gn.set_input(mod, "Face Proxy", proxy)

layer = bpy.context.view_layer.layer_collection.children.get(scene.WORK)
if layer is not None and layer.hide_viewport:
    print("20_heads: Work is hidden in the viewport, so Rig won't evaluate; showing it")
    layer.hide_viewport = False
