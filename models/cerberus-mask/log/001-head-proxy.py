# step 1: Ref head proxy from SDF blobs (pupils z=260, neck on z=0); GN_SDFBlob re-bands Points->SDF via mesh so Fillet/Mean stay manifold
import importlib
import sys
from pathlib import Path

import bpy

assert bpy.data.filepath.endswith("models/cerberus-mask/model.blend"), bpy.data.filepath
HERE = Path(bpy.path.abspath("//builders"))
for p in (str(HERE.parents[2] / "lib"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)
for name in sorted(
    n for n in sys.modules if n.split(".")[0] in ("kit", "patterns", "blob_geo")
):
    importlib.reload(sys.modules[name])
import blob_geo
from kit import gn, scene

coll = blob_geo.proxy_controls()
t = blob_geo.proxy_group(coll)
proxy = gn.host("HeadProxy", scene.collection(scene.REF))
gn.modifier(proxy, t)
ev = proxy.evaluated_get(bpy.context.evaluated_depsgraph_get())
bb = [ev.matrix_world @ __import__("mathutils").Vector(c) for c in ev.bound_box]
print(
    {
        "verts": len(ev.data.vertices),
        "min": [round(min(v[i] for v in bb)) for i in range(3)],
        "max": [round(max(v[i] for v in bb)) for i in range(3)],
    }
)
