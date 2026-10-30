# step 8: Dog-skull head curves: braincase+crest, cheekbones, nasal bridge, solid mandibles + lower fangs (replaces the U jaw)
# Replace the blockout head curves with dog-skull shapes (blob_geo.HEAD): braincase + crest,
# cheekbones, nasal bridge, solid mandibles + lower fangs, broad two-edge ears. Overwrites
# CTL_Head_* curves (keeps their object location), then rebuilds.
import importlib
import sys
from pathlib import Path

import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
sys.path.insert(0, str(Path(bpy.path.abspath("//builders"))))
import blob_geo

importlib.reload(blob_geo)
root = bpy.data.collections["CTL_Head"]
keep = {
    n
    for blobs in blob_geo.HEAD.values()
    for n, _, m in blobs
    for n in ([n + "_L", n + "_R"] if m else [n])
}
for o in list(root.all_objects):  # drop curves the new head set no longer has
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
for part, blobs in blob_geo.HEAD.items():
    coll = bpy.data.collections[f"CTL_Head_{part}"]
    for name, pts, mirror in blobs:
        blob_geo.blob(name, coll, pts, mirror, replace=True)
exec(open(bpy.path.abspath("//out/steps/_rebuild.py")).read(), {"__name__": "step"})  # noqa: S102, SIM115
