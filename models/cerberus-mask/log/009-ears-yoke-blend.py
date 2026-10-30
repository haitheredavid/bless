# step 9: Broad 3-curve ears, thicker yoke with shoulder caps; Fillet 12 / Smooth 3, Cranium 0.95, Neck Radius 34 / Taper 0.6
# Broad ears (front/fill/back curves), thicker shoulder yoke with shoulder caps, stronger
# SDF blend (Fillet 12, Smooth 3), Cranium Scale 0.95, Neck Radius 34 / Taper 0.6.
import importlib
import sys
from pathlib import Path

import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
sys.path.insert(0, str(Path(bpy.path.abspath("//builders"))))
import blob_geo

importlib.reload(blob_geo)
coll = bpy.data.collections["CTL_Head_Ears"]
for name, pts, mirror in blob_geo.HEAD["Ears"]:
    blob_geo.blob(name, coll, pts, mirror, replace=True)
yoke = bpy.data.collections["CTL_Collar"]
for name, pts, mirror in blob_geo.COLLAR:
    blob_geo.blob(name, yoke, pts, mirror, replace=True)
exec(open(bpy.path.abspath("//out/steps/_rebuild.py")).read(), {"__name__": "step"})  # noqa: S102, SIM115
