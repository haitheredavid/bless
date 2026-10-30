"""GN_JointExplode: pull an assembled display pair apart.

Part A moves -Explode/2 along x, B +Explode/2, the loose part +Explode up z, so a
board can show a joint closed (Explode = 0) or open. Display only: print parts don't
carry it.
"""

from kit import gn

from patterns.joints import _common as c

NAME = "GN_JointExplode"


def build(reset: bool = False):
    t = gn.tree(NAME)
    if gn.current(t, __file__) and not reset:
        return t
    t = gn.tree(NAME, reset=True)
    gn.input(t, "Geometry", "GEOMETRY")
    gn.input(t, "Part", "INT", 0, min=0, max=2, description="0 = A, 1 = B, 2 = Loose")
    gn.input(t, "Explode", "FLOAT", 0.0, min=0.0, max=200.0, subtype="DISTANCE")
    gn.output(t, "Geometry")
    _gin, gout = gn.io(t)
    with gn.stage(t, "1 · Offset by Part"):
        e = c.gin(t, "Explode")
        half = c.mul(t, e, 0.5)
        sx = c.switch(t, "FLOAT", c.is_part(t, c.PART_B), c.mul(t, half, -1.0), half)
        loose = c.is_part(t, c.PART_LOOSE)
        dx = c.switch(t, "FLOAT", loose, sx, 0.0)
        dz = c.switch(t, "FLOAT", loose, 0.0, e)
        moved = c.translate(t, c.gin(t, "Geometry"), c.xyz(t, dx, 0.0, dz))
        t.links.new(moved, gout.inputs[0])
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def apply(obj, **inputs):
    return gn.modifier(obj, build(), **inputs)
