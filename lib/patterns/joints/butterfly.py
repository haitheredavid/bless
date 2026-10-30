"""GN_Joint_Butterfly: butterfly (bowtie) key across a butt joint, from the top face.

The loose key is two trapezoids meeting at Key Waist on the joint face (x = 0),
widening by Key Angle per flank to Key Length overall, Key Depth thick, top and bottom
edges chamfered by Joint Chamfer (lead-in, elephant's foot). A and B both get the
pocket: the key offset by Clearance on every face, Key Depth + Key Floor Gap deep from
the host's top, mouth flared by Joint Chamfer. The key seats Key Floor Gap below the
surface (one layer: a floor that prints a hair high can't leave it proud).

Print the bars as modelled (pocket open upward, no overhang) and the key flat.
"""

from kit import gn

from patterns.joints import _common as c

NAME = "GN_Joint_Butterfly"


def build(reset: bool = False):
    t = gn.tree(NAME)
    if gn.current(t, __file__) and not reset:
        return t
    t = gn.tree(NAME, reset=True)
    c.joint_inputs(t)
    gn.input(t, "Key Length", "FLOAT", 20.0, min=2.0, max=200.0, subtype="DISTANCE")
    gn.input(t, "Key Waist", "FLOAT", 6.0, min=1.0, max=100.0, subtype="DISTANCE")
    gn.input(t, "Key Angle", "FLOAT", 15.0, min=3.0, max=35.0,
             description="Flank angle from the mating axis, degrees")  # fmt: skip
    gn.input(t, "Key Depth", "FLOAT", 5.0, min=1.0, max=100.0, subtype="DISTANCE")
    gn.input(t, "Key Floor Gap", "FLOAT", 0.2, min=0.0, max=2.0, subtype="DISTANCE")
    _gin, gout = gn.io(t)
    geo, cl, ch = c.gin(t, "Geometry"), c.gin(t, "Clearance"), c.gin(t, "Joint Chamfer")

    with gn.stage(t, "1 · Joint frame + key levels"):
        frame, _zmin, zmax = c.joint_frame(t)
        slope = c.math(t, "TANGENT", c.math(t, "RADIANS", c.gin(t, "Key Angle")))
        half = c.mul(t, c.gin(t, "Key Waist"), 0.5)
        reach = c.mul(t, c.gin(t, "Key Length"), 0.5)
        top = c.sub(t, zmax, c.gin(t, "Key Floor Gap"))
        floor = c.sub(t, top, c.gin(t, "Key Depth"))
    with gn.stage(t, "2 · Loose: key (two chamfered halves)"):
        right = c.chamfered_trap(t, -0.5, reach, floor, top, half, slope, 0.0, ch)
        key = c.boolean(t, "UNION", right, c.mirror_x(t, right))
        loose = c.transform(t, key, frame)
    with gn.stage(t, "3 · A and B: pocket (key + Clearance, flared mouth)"):
        end = c.add(t, reach, cl)
        core = c.trap_box(t, -0.5, end, floor, c.add(t, zmax, 1.0), half, slope, cl)
        mouth = c.flare(t, -0.5, end, zmax, half, slope, cl, ch, up=True)
        pieces = (core, mouth, c.mirror_x(t, core), c.mirror_x(t, mouth))
        cut = c.boolean(
            t, "DIFFERENCE", geo, *(c.transform(t, p, frame) for p in pieces)
        )
    with gn.stage(t, "4 · Part"):
        t.links.new(c.by_part(t, cut, cut, loose), gout.inputs[0])
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def apply(obj, **inputs):
    return gn.modifier(obj, build(), **inputs)
