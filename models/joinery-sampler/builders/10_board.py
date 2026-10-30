# Display board (Model): one assembled pair per catalog joint at its `fit` clearance, a
# row per family (+y), joints along +x. Hosts are parented to CTL_Board (Control), so
# moving the empty moves the board. Stack per host, same Part on each:
# GN_JointBar -> GN_Joint_<Kind> -> GN_JointExplode. Sizes come from params.toml [base]
# (build_all applies it last); clearances come from catalog.py.
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import catalog

importlib.reload(catalog)
from kit import control, gn, params
from patterns import joints
from patterns.joints import explode, joint_bar

p = params.load("base")
catalog.validate(p)
board = control.ensure("CTL_Board", lambda n: control.empty(n, size=10.0))
pitch_x = 2 * p["Bar Length"] + 30.0  # an assembled pair plus room to explode
pitch_y = p["Bar Width"] + 30.0

for row, fam in enumerate(catalog.FAMILIES):
    for col, j in enumerate(x for x in catalog.JOINTS if x.family == fam):
        pattern = getattr(joints, j.pattern)
        a_label = catalog.label(j, j.fit if j.loose else None)  # loose: A has sockets
        parts = [(0, "A", a_label), (1, "B", catalog.label(j, j.fit))]
        if j.loose:
            parts.append((2, "K", ""))
        for part, sfx, text in parts:
            obj = gn.host(f"JT_{j.code}_{sfx}")
            obj.parent = board
            obj.location = (col * pitch_x, row * pitch_y, 0.0)
            joint_bar.apply(obj, Part=part, Label=text)
            pattern.apply(obj, Part=part, Clearance=j.fit, **j.inputs)
            explode.apply(obj, Part=part)
            obj["joint"] = j.code
