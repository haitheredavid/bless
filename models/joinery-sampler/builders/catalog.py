# Joint catalog: one entry per joint, the single source for 10_board (display) and
# 20_print (sweep parts) and the [[print.coupon]] entries in model.toml. Not an NN_
# builder: build_all skips it.
#
# `fit` is the clearance the board shows and later models should use: the coupon's
# pick replaces it (model.toml [[print.coupon]] param = "builders/catalog.py:<CODE>.fit").
# `sweep` is what the coupon prints: B (and, for loose joints, both bars' sockets) at
# each value; A and loose parts stay nominal.
import math
from dataclasses import dataclass, field

WALL = 2.4  # min plastic around any recess (6 lines at 0.4 mm)


@dataclass(frozen=True)
class Joint:
    code: str
    name: str
    family: str  # key of FAMILIES
    pattern: str  # module in patterns.joints
    fit: float  # clearance per face for the board / reuse
    sweep: tuple[float, ...]
    kind: str  # print-spec joints[].kind
    loose: bool = False  # a loose part (key, pin, tenon); sockets in both bars
    why: str = ""  # print orientation and the FDM rule it follows
    inputs: dict = field(default_factory=dict)  # per-joint GN overrides over params


FAMILIES = {"Interlock": "Print_Interlock", "Pins": "Print_Pins", "Snap": "Print_Snap"}

DT = Joint(
    "DT", "Sliding dovetail", "Interlock", "dovetail", 0.20, (0.15, 0.20, 0.30),
    kind="dovetail",
    why="as modelled, z up: the trapezoid lies in the layer plane (no overhang); the slide crosses the layers, which the sweep absorbs",
)  # fmt: skip
BK = Joint(
    "BK", "Butterfly key", "Interlock", "butterfly", 0.10, (0.05, 0.10, 0.15),
    kind="key", loose=True,
    why="bars as modelled, pockets open upward; key flat, chamfered both faces",
)  # fmt: skip

JOINTS = (DT, BK)


def label(j: Joint, c: float | None) -> str:
    """Engraved text: 'DT A' for a nominal A, 'DT .15' / 'PF -.05' with a clearance."""
    if c is None:
        return f"{j.code} A"
    s = f"{c:.2f}".replace("0.", ".")
    return f"{j.code} {s}"


def tag(c: float) -> str:
    """Name suffix for a clearance: 0.15 -> '15', -0.05 -> 'm05'."""
    return ("m" if c < 0 else "") + f"{round(abs(c) * 100):02d}"


# --- checks -------------------------------------------------------------------------


def _sec(deg: float) -> float:
    return 1 / math.cos(math.radians(deg))


def check(j: Joint, p: dict, c: float) -> list[str]:
    """Wall and shape problems for joint j at clearance c with params p ([] = ok)."""
    w, h, length = p["Bar Width"], p["Bar Height"], p["Bar Length"]
    f = p["Joint Chamfer"]
    bad = []
    if j.code == "DT":
        a, neck, d = p["Dovetail Angle"], p["Dovetail Neck"], p["Dovetail Depth"]
        half = neck / 2 + (d + c) * math.tan(math.radians(a)) + c * _sec(a) + f
        if w / 2 - half < WALL:
            bad.append(f"DT side wall {w / 2 - half:.2f} < {WALL} at c={c}")
        if length - d - c - f < WALL:
            bad.append(f"DT end wall {length - d - c - f:.2f} < {WALL}")
        if neck < 2 * WALL:
            bad.append(f"DT neck {neck} < {2 * WALL}")
    elif j.code == "BK":
        a, kl, kw = p["Key Angle"], p["Key Length"], p["Key Waist"]
        kd, gap = p["Key Depth"], p["Key Floor Gap"]
        half = kw / 2 + (kl / 2 + c) * math.tan(math.radians(a)) + c * _sec(a) + f
        if w / 2 - half < WALL:
            bad.append(f"BK side wall {w / 2 - half:.2f} < {WALL} at c={c}")
        if h - kd - gap < WALL:
            bad.append(f"BK floor {h - kd - gap:.2f} < {WALL}")
        if length - kl / 2 - c - f < WALL:
            bad.append(f"BK end wall {length - kl / 2 - c - f:.2f} < {WALL}")
    return bad


def validate(p: dict) -> None:
    """Assert every joint holds WALL at every clearance it prints or shows."""
    bad = [m for j in JOINTS for c in {*j.sweep, j.fit} for m in check(j, p, c)]
    assert not bad, "; ".join(bad)
