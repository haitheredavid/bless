"""GN_SectionPiece: one printable piece of a larger source object, kept live.

Takes the Source object's evaluated geometry (e.g. the GN Frame with its booleans),
keeps what lies inside an axis box (Box Min..Box Max, host-local), and subtracts an
optional Cutter object (joinery recesses, pin holes). Edit the source and every piece
follows. Put pieces in the Print collection (kit.scene.parts()). Source vertices or
cutter vertices that lie exactly on a cut plane (a miter through a loft's corner ridge)
leave coincident duplicates and zero-area faces; the last stage welds them.
"""

from kit import gn

NAME = "GN_SectionPiece"


def build(reset: bool = False):
    t = gn.tree(NAME)
    if gn.current(t, __file__) and not reset:
        return t
    t = gn.tree(NAME, reset=True)
    gn.input(t, "Geometry", "GEOMETRY")
    gn.input(t, "Source", "OBJECT", description="Object to cut a piece from")
    gn.input(t, "Box Min", "VECTOR", (-1.0, -1.0, -1.0), subtype="TRANSLATION")
    gn.input(t, "Box Max", "VECTOR", (1.0, 1.0, 1.0), subtype="TRANSLATION")
    gn.input(t, "Cutter", "OBJECT", description="Optional: subtracted from the piece")
    gn.input(t, "Weld Distance", "FLOAT", 1e-4, min=0.0, max=0.1,
             description="Merge coincident vertices the cuts leave behind")  # fmt: skip
    gn.output(t, "Geometry")
    gin, gout = gn.io(t)

    with gn.stage(t, "1 · Source geometry"):
        src = gn.node(t, "GeometryNodeObjectInfo", "Source")
        gn.link(t, gin, "Source", src, "Object")
        real = gn.node(t, "GeometryNodeRealizeInstances")
        gn.link(t, src, "Geometry", real, "Geometry")
    with gn.stage(t, "2 · Quadrant box"):
        size = gn.node(t, "ShaderNodeVectorMath", props={"operation": "SUBTRACT"})
        gn.link(t, gin, "Box Max", size, 0)
        gn.link(t, gin, "Box Min", size, 1)
        mid = gn.node(t, "ShaderNodeVectorMath", props={"operation": "ADD"})
        gn.link(t, gin, "Box Max", mid, 0)
        gn.link(t, gin, "Box Min", mid, 1)
        half = gn.node(t, "ShaderNodeVectorMath", props={"operation": "SCALE"})
        gn.link(t, mid, 0, half, 0)
        half.inputs["Scale"].default_value = 0.5
        cube = gn.node(t, "GeometryNodeMeshCube")
        gn.link(t, size, 0, cube, "Size")
        box = gn.node(t, "GeometryNodeTransform")
        gn.link(t, cube, "Mesh", box, "Geometry")
        gn.link(t, half, 0, box, "Translation")
    with gn.stage(t, "3 · Keep inside box (intersect)"):
        keep = gn.node(
            t,
            "GeometryNodeMeshBoolean",
            props={"operation": "INTERSECT", "solver": "EXACT"},
        )
        gn.link(
            t, real, "Geometry", keep, "Mesh 2"
        )  # INTERSECT takes all inputs in Mesh 2
        gn.link(t, box, "Geometry", keep, "Mesh 2")
    with gn.stage(t, "4 · Subtract cutter (joinery)"):
        cut = gn.node(t, "GeometryNodeObjectInfo", "Cutter")
        gn.link(t, gin, "Cutter", cut, "Object")
        sub = gn.node(
            t,
            "GeometryNodeMeshBoolean",
            props={"operation": "DIFFERENCE", "solver": "EXACT"},
        )
        gn.link(t, keep, "Mesh", sub, "Mesh 1")
        gn.link(t, cut, "Geometry", sub, "Mesh 2")
    with gn.stage(t, "5 · Weld coincident vertices"):
        weld = gn.node(t, "GeometryNodeMergeByDistance")
        gn.link(t, sub, "Mesh", weld, "Geometry")
        gn.link(t, gin, "Weld Distance", weld, "Distance")
        gn.link(t, weld, "Geometry", gout, "Geometry")
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def apply(obj, **inputs):
    return gn.modifier(obj, build(), **inputs)
