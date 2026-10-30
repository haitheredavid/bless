# step 2: SDF blockout: CTL_Head_{Cranium,Snout,Ears,Jaw} blob curves -> center head + yawed/mirrored side heads on necks (GN_CerberusMask_Heads)
import importlib
import sys
from pathlib import Path

import bmesh
import bpy
import mathutils

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

colls = blob_geo.head_controls()
t = blob_geo.heads_group(colls)
heads = gn.host("Heads", scene.model())
gn.modifier(heads, t)
bpy.context.view_layer.update()
ev = heads.evaluated_get(bpy.context.evaluated_depsgraph_get())
bb = [ev.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
bm = bmesh.new()
bm.from_mesh(ev.data)
print(
    {
        "faces": len(bm.faces),
        "nonmanifold": sum(1 for e in bm.edges if not e.is_manifold),
        "min": [round(min(v[i] for v in bb)) for i in range(3)],
        "max": [round(max(v[i] for v in bb)) for i in range(3)],
    }
)
