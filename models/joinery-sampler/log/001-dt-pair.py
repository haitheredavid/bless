# step 1: joint library: GN_JointBar (chamfered bar, engraved label) + GN_Joint_Dovetail (tail on A, clearance socket with flared mouths on B); test pair at 0.20
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
from patterns.joints import dovetail, joint_bar

out = {}
for part, suffix, label in ((0, "A", "DT A"), (1, "B", "DT .20")):
    old = bpy.data.objects.get(f"JT_DT_{suffix}")
    if old:  # a rebuilt group leaves stale (zero) inputs on existing modifiers
        bpy.data.objects.remove(old)
    obj = gn.host(f"JT_DT_{suffix}")
    joint_bar.apply(obj, Part=part, Label=label)
    dovetail.apply(obj, Part=part, Clearance=0.20)
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    out[obj.name] = (
        len(ev.vertices),
        len(ev.polygons),
        [round(v, 2) for v in obj.dimensions],
    )
print(out)
