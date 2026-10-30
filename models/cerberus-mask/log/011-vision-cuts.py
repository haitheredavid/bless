# step 11: Vision cones on the center only (FOV per eye: out 104 L / 34 R (right side head blocks), down 86, up 16), side heads small sockets, muzzle root r22, drop loose mask fragments, Center Scale 1.15
# Center head = wearer's mask with vision cones (CTL_Head_Cuts, center only), side heads get
# small sockets (CTL_Head_CutsSide); muzzle root narrowed to r22 so the sightline passes
# beside it; mask drops fragments < 25% of its biggest piece; Center Scale 1.15.
import sys
from pathlib import Path

import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
sys.path.insert(0, str(Path(bpy.path.abspath("//builders"))))
import importlib

import blob_geo

importlib.reload(blob_geo)
for part, names in (("Cuts", None), ("Snout", {"CTL_Head_Muzzle"})):
    for name, pts, mirror in blob_geo.HEAD[part]:
        if names is None or name in names:
            blob_geo.blob(
                name,
                bpy.data.collections[f"CTL_Head_{part}"],
                pts,
                mirror,
                replace=True,
            )
exec(open(bpy.path.abspath("//out/steps/_rebuild.py")).read(), {"__name__": "step"})  # noqa: S102, SIM115
exec(open(bpy.path.abspath("//out/steps/fov_check.py")).read(), {"__name__": "chk"})  # noqa: S102, SIM115
