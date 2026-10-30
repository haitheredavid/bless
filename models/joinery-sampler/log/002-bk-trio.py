# step 2: GN_Joint_Butterfly: bowtie key (loose, chamfered) and clearance pockets with flared mouths in both bars; test trio at 0.10
import importlib
import sys
from pathlib import Path

import bpy

assert bpy.data.filepath.endswith("models/joinery-sampler/model.blend"), (
    bpy.data.filepath
)
LIB = str(Path(bpy.path.abspath("//")).parents[1] / "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
for name in sorted(n for n in sys.modules if n.split(".")[0] in ("kit", "patterns")):
    importlib.reload(sys.modules[name])
from kit import gn
from patterns.joints import butterfly, joint_bar

out = {}
for part, suffix, label in ((0, "A", "BK .10"), (1, "B", "BK .10"), (2, "K", "")):
    old = bpy.data.objects.get(f"JT_BK_{suffix}")
    if old:  # a rebuilt group leaves stale (zero) inputs on existing modifiers
        bpy.data.objects.remove(old)
    obj = gn.host(f"JT_BK_{suffix}")
    obj.location.y = 30.0
    joint_bar.apply(obj, Part=part, Label=label)
    butterfly.apply(obj, Part=part, Clearance=0.10)
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    out[obj.name] = (
        len(ev.vertices),
        len(ev.polygons),
        [round(v, 2) for v in obj.dimensions],
    )
print(out)
