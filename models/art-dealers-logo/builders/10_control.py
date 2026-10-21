# Control curves from the trace (builders/logo_trace.json, made by trace_logo.py).
# Created only if missing: once they exist they are the user's to reshape.
import json
from pathlib import Path

import bpy
from kit import control

TRACE = json.loads(Path(__file__).with_name("logo_trace.json").read_text())


def outlines(name: str, loops) -> bpy.types.Object:
    """One curve object with a closed POLY spline per traced loop (Fill Curve nests the holes)."""
    obj = control.curve(name, loops[0])
    cu = obj.data
    assert isinstance(cu, bpy.types.Curve)
    for loop in loops[1:]:
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for p, (x, y) in zip(sp.points, loop):
            p.co = (x, y, 0.0, 1.0)
        sp.use_cyclic_u = True
    return obj


control.ensure("CTL_Art", lambda n: outlines(n, TRACE["art"]))
control.ensure("CTL_Galeria", lambda n: outlines(n, TRACE["galeria"]))
control.ensure("CTL_DealersText", lambda n: outlines(n, TRACE["dealers_text"]))
x0, y0, x1, y1 = TRACE["dealers_box"]
control.ensure(
    "CTL_DealersBox",
    lambda n: control.curve(n, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]),
)
