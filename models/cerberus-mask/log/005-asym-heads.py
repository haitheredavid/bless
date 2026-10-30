# step 5: Uneven heads + less bulk: per-side Pitch/Tilt about the neck root, Right Yaw/Drop/Back offsets, Cranium Scale; variants asym, asym-lean
# Rebuild GN_CerberusMask_Heads with per-side pose (Left/Right Pitch, Tilt; Right Yaw/Drop/Back
# Offset) and Cranium Scale (blob_geo.py), then compare base / asym / asym-lean live.
import bpy

D = bpy.path.abspath("//out/steps/")
exec(open(D + "02_heads.py").read(), {"__name__": "step"})  # noqa: S102, SIM115 - heads tree (reset)
exec(open(D + "01_proxy.py").read(), {"__name__": "step"})  # noqa: S102, SIM115 - relink proxy
from kit import params

params.apply("base")
params.grid(["base", "asym", "asym-lean"], gap=0.12)
