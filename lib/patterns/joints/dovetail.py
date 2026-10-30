"""GN_Joint_Dovetail: sliding (through) dovetail across a butt joint.

Part A grows a tail out of the joint face (x = 0 in the joint frame): a trapezoid
Dovetail Neck wide at the face, widening by Dovetail Angle per flank to Dovetail Depth,
through the host's full height, top and bottom edges chamfered by Joint Chamfer. Part B
gets the matching socket: the tail section offset by Clearance on every face (flanks
perpendicular, end + Clearance), open top and bottom with a 45 deg Joint Chamfer flare
at both mouths (first-layer squish can't close it; lead-in from the top). Assemble by
sliding the tail down into the socket along z. No loose part.

Print as modelled (z up): the trapezoid lies in the layer plane, so there is no
overhang; the slide runs across the layer lines, which the clearance sweep absorbs.
"""

from kit import gn

from patterns.joints import _common as c

NAME = "GN_Joint_Dovetail"


def build(reset: bool = False):
    t = gn.tree(NAME)
    if gn.current(t, __file__) and not reset:
        return t
    t = gn.tree(NAME, reset=True)
    c.joint_inputs(t)
    gn.input(t, "Dovetail Angle", "FLOAT", 15.0, min=3.0, max=35.0,
             description="Flank angle from the mating axis, degrees")  # fmt: skip
    gn.input(t, "Dovetail Neck", "FLOAT", 8.0, min=1.0, max=100.0, subtype="DISTANCE")
    gn.input(t, "Dovetail Depth", "FLOAT", 6.0, min=1.0, max=100.0, subtype="DISTANCE")
    _gin, gout = gn.io(t)
    geo, cl, ch = c.gin(t, "Geometry"), c.gin(t, "Clearance"), c.gin(t, "Joint Chamfer")
    depth = c.gin(t, "Dovetail Depth")

    with gn.stage(t, "1 · Joint frame + host height"):
        frame, zmin, zmax = c.joint_frame(t)
        slope = c.math(t, "TANGENT", c.math(t, "RADIANS", c.gin(t, "Dovetail Angle")))
        half = c.mul(t, c.gin(t, "Dovetail Neck"), 0.5)
    with gn.stage(t, "2 · A: tail (chamfered)"):
        tail = c.chamfered_trap(t, -0.5, depth, zmin, zmax, half, slope, 0.0, ch)
        a = c.boolean(t, "UNION", geo, c.transform(t, tail, frame))
    with gn.stage(t, "3 · B: socket (tail + Clearance, flared mouths)"):
        end = c.add(t, depth, cl)
        core = c.trap_box(
            t, -1.0, end, c.sub(t, zmin, 1.0), c.add(t, zmax, 1.0), half, slope, cl
        )
        low = c.flare(t, -1.0, end, zmin, half, slope, cl, ch, up=False)
        high = c.flare(t, -1.0, end, zmax, half, slope, cl, ch, up=True)
        cutters = [c.transform(t, p, frame) for p in (core, low, high)]
        b = c.boolean(t, "DIFFERENCE", geo, *cutters)
    with gn.stage(t, "4 · Part"):
        t.links.new(c.by_part(t, a, b, None), gout.inputs[0])
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def apply(obj, **inputs):
    return gn.modifier(obj, build(), **inputs)
