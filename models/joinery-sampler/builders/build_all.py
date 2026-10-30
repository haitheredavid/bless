# Rebuild the model from scratch. Over MCP (model.blend must be open):
#   exec(open(bpy.path.abspath('//builders/build_all.py')).read(), {'__name__': 'build_all'})
# Runs every builders/NN_*.py in name order (10_base.py, 20_details.py, ...), with the repo's
# lib/ on sys.path and `kit` reloaded so helper edits apply without restarting Blender.
# Model and Work are cleared and rebuilt; Control (user-owned inputs) and Ref are never touched.
# params.toml [base] is applied last, so it wins over defaults set in the builders.
import importlib
import sys
from pathlib import Path

import bpy

HERE = Path(bpy.path.abspath("//builders"))
LIB = HERE.parents[2] / "lib"  # models/<m>/builders -> repo/lib
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
for name in sorted(n for n in sys.modules if n.split(".")[0] in ("kit", "patterns")):
    importlib.reload(sys.modules[name])

from kit import scene

scene.control()  # make sure Control and Notes exist before builders look for them
scene.notes()
scene.clear(scene.model())
scene.clear(scene.work())  # cutters/helpers are rebuilt by the builders too
for step in sorted(HERE.glob("[0-9][0-9]_*.py")):
    exec(step.read_text(), {"__name__": step.stem, "__file__": str(step)})  # noqa: S102
    print(f"build_all: {step.name}")
from kit import params

res = params.apply("base")  # params.toml [base] -> GN inputs (the source of truth)
if res["unused"]:
    print(f"build_all: params with no matching GN input: {res['unused']}")
scene.fit_viewport()  # unit-aware clip range (mm files clip at 1 m otherwise)
scene.purge()
scene.save()
print("build_all ok")
