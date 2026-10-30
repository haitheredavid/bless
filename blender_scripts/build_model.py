"""Rebuild a model headless: run its builders/build_all.py (which saves model.blend).

Usage: blender -b models/<m>/model.blend -P build_model.py -- [--variant preview] [--allow-fail] --result r.json

Result: {"ok", "seconds", "variant", "error", "report"} where report is what the model's
builders/checks.py left in bpy.app.driver_namespace["build_report"] (or null).
"""

import argparse
import contextlib
import io
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy
from _common import parse, write_result

parser = argparse.ArgumentParser()
parser.add_argument("--variant", default="base")
parser.add_argument(
    "--allow-fail", action="store_true", help="save even if checks.py fails"
)
opts = parse(parser)

build_all = Path(bpy.path.abspath("//builders/build_all.py"))
bpy.app.driver_namespace["build_variant"] = opts.variant
bpy.app.driver_namespace["build_allow_fail"] = opts.allow_fail
bpy.app.driver_namespace.pop("build_report", None)
t0 = time.time()
error = None
log = io.StringIO()  # builders' notes (updated curves, warnings) go to the CLI
source, ns = (
    build_all.read_text(),
    {"__name__": "build_all", "__file__": str(build_all)},
)
try:
    with contextlib.redirect_stdout(log):
        exec(source, ns)  # noqa: S102
except Exception:  # noqa: BLE001 - any builder error is reported to the CLI with its traceback
    error = traceback.format_exc(limit=6)
sys.stdout.write(log.getvalue())
write_result(
    opts.result,
    {
        "ok": error is None,
        "seconds": round(time.time() - t0, 1),
        "variant": opts.variant,
        "error": error,
        "log": log.getvalue().splitlines(),
        "report": bpy.app.driver_namespace.get("build_report"),
    },
)
