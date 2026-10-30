"""GN_JointBar: the standard specimen bar a joint is cut into.

A bar Bar Length long (x) with a Bar Width x Bar Height section, z = 0..Height, every
edge chamfered (Edge Chamfer: 45 deg, beats elephant's foot on the bed edges and leaves
a small V at the seam). The joint face is x = 0: Part A's bar runs x = -Length..0,
Part B's 0..Length, so A and B hosts at the same location are assembled. Part 2
(Loose) gets A's bar: the joint pattern only reads its frame and outputs the loose
part alone.

Label is engraved Label Depth deep in the front (-y) face, centred, reading left to
right from the front (e.g. "DT .15"). Empty Label = no engraving.
"""

from kit import gn

from patterns.joints import _common as c

NAME = "GN_JointBar"


def build(reset: bool = False):
    t = gn.tree(NAME)
    if gn.current(t, __file__) and not reset:
        return t
    t = gn.tree(NAME, reset=True)
    gn.input(t, "Geometry", "GEOMETRY")
    gn.input(t, "Part", "INT", 0, min=0, max=2,
             description="0 = A (bar on -x), 1 = B (bar on +x), 2 = Loose (A's bar)")  # fmt: skip
    gn.input(t, "Bar Width", "FLOAT", 18.0, min=4.0, max=200.0, subtype="DISTANCE")
    gn.input(t, "Bar Height", "FLOAT", 18.0, min=2.0, max=200.0, subtype="DISTANCE")
    gn.input(t, "Bar Length", "FLOAT", 25.0, min=4.0, max=250.0, subtype="DISTANCE")
    gn.input(t, "Edge Chamfer", "FLOAT", 0.4, min=0.0, max=3.0, subtype="DISTANCE")
    gn.input(t, "Label", "STRING", "", description="Engraved on the front (-y) face")
    gn.input(t, "Label Size", "FLOAT", 4.5, min=1.0, max=30.0, subtype="DISTANCE")
    gn.input(t, "Label Depth", "FLOAT", 0.4, min=0.0, max=3.0, subtype="DISTANCE")
    gn.output(t, "Geometry")
    _gin, gout = gn.io(t)
    L, W, H = c.gin(t, "Bar Length"), c.gin(t, "Bar Width"), c.gin(t, "Bar Height")
    ch = c.gin(t, "Edge Chamfer")

    with gn.stage(t, "1 · Side (A on -x, B on +x)"):
        sign = c.switch(t, "FLOAT", c.is_part(t, c.PART_B), -1.0, 1.0)
        cx = c.mul(t, sign, c.mul(t, L, 0.5))
        centre = c.xyz(t, cx, 0.0, c.mul(t, H, 0.5))
    with gn.stage(t, "2 · Chamfered bar (hull of three boxes)"):
        ch2 = c.mul(t, ch, 2.0)
        boxes = []
        for size in (
            (L, c.sub(t, W, ch2), c.sub(t, H, ch2)),
            (c.sub(t, L, ch2), W, c.sub(t, H, ch2)),
            (c.sub(t, L, ch2), c.sub(t, W, ch2), H),
        ):
            cube = t.nodes.new("GeometryNodeMeshCube")
            c.feed(t, cube.inputs["Size"], c.xyz(t, *size))
            boxes.append(c.translate(t, cube.outputs["Mesh"], centre))
        bar = c.hull(t, *boxes)
    with gn.stage(t, "3 · Label cutter (front face)"):
        s2c = t.nodes.new("GeometryNodeStringToCurves")
        c.feed(t, s2c.inputs["String"], c.gin(t, "Label"))
        c.feed(t, s2c.inputs["Size"], c.gin(t, "Label Size"))
        s2c.inputs["Pivot Point"].default_value = "Midpoint"
        real = t.nodes.new("GeometryNodeRealizeInstances")
        t.links.new(s2c.outputs["Curve Instances"], real.inputs[0])
        fill = t.nodes.new("GeometryNodeFillCurve")
        t.links.new(real.outputs[0], fill.inputs["Curve"])
        # Triangles: N-gons can't hold a glyph's counter (D, A, 0) and cuts it as a
        # self-touching ngon. Individual off, or every triangle extrudes its own walls.
        fill.inputs["Mode"].default_value = "Triangles"
        ext = t.nodes.new("GeometryNodeExtrudeMesh")
        t.links.new(fill.outputs[0], ext.inputs["Mesh"])
        ext.inputs["Offset"].default_value = (0.0, 0.0, 1.0)
        ext.inputs["Individual"].default_value = False
        c.feed(t, ext.inputs["Offset Scale"], c.add(t, c.gin(t, "Label Depth"), 1.0))
        base = t.nodes.new("GeometryNodeFlipFaces")
        t.links.new(fill.outputs[0], base.inputs[0])
        glyphs = c.join(t, ext.outputs["Mesh"], base.outputs[0])
        weld = t.nodes.new("GeometryNodeMergeByDistance")
        t.links.new(glyphs, weld.inputs[0])
        weld.inputs["Distance"].default_value = 1e-4
        # lay the glyphs into the front face: text +y -> +z, extrusion +z -> -y
        rot = t.nodes.new("GeometryNodeTransform")
        t.links.new(weld.outputs[0], rot.inputs["Geometry"])
        rot.inputs["Rotation"].default_value = (1.5707963, 0.0, 0.0)
        y0 = c.add(t, c.mul(t, W, -0.5), c.gin(t, "Label Depth"))
        label = c.translate(t, rot.outputs[0], c.xyz(t, cx, y0, c.mul(t, H, 0.5)))
    with gn.stage(t, "4 · Engrave"):
        cut = c.boolean(t, "DIFFERENCE", bar, label)
        t.links.new(cut, gout.inputs[0])
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def apply(obj, **inputs):
    return gn.modifier(obj, build(), **inputs)
