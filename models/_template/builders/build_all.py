# Rebuild the model from scratch. Over MCP (model.blend must be open):
#   exec(open(bpy.path.abspath('//builders/build_all.py')).read(), {'__name__': 'build_all'})
# Headless (no MCP timeout; saves model.blend): `just build <model>` / `blend build <model>`.
# Runs every builders/NN_*.py in name order (10_base.py, 20_details.py, ...), with the repo's
# lib/ on sys.path and `kit` reloaded so helper edits apply without restarting Blender.
# Model and Work are cleared and rebuilt; Control (user-owned inputs) and Ref are never touched.
# params.toml [base] (plus the variant `blend build --variant` asks for) is applied after the
# builders, so it wins over their defaults. Every value input must have a params key:
# a rebuild resets uncovered inputs to their socket defaults. builders/checks.py, if
# present, runs last and fails the build on unmet requirements.
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

variant = bpy.app.driver_namespace.get("build_variant", "base")
res = params.apply(
    params.load(variant)
)  # params.toml -> GN inputs (the source of truth)
if res["unused"]:
    print(f"build_all: params with no matching GN input: {res['unused']}")
if missing := params.missing(variant):
    raise AssertionError(f"build_all: GN inputs with no params.toml key: {missing}")
bpy.context.view_layer.update()
checks = HERE / "checks.py"
failed = None
if checks.exists():
    try:
        exec(checks.read_text(), {"__name__": "checks", "__file__": str(checks)})  # noqa: S102
    except (
        AssertionError
    ) as e:  # `blend build --allow-fail` saves anyway, to inspect the failure
        if not bpy.app.driver_namespace.get("build_allow_fail"):
            raise
        failed = e
scene.fit_viewport()  # unit-aware clip range (mm files clip at 1 m otherwise)
scene.purge()
scene.save()
if failed is not None:
    raise failed
print(f"build_all ok ({variant})")
