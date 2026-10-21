# Logo_Base: the dark tray (filament 1). Floor z = 0 .. Base Thickness; a Rim Width wall around
# the plate edge rises to Base Thickness + Face Depth, level with the top of the white logo.
# Plate shape: 0 rectangle / 1 rounded rectangle around the logo bounds + margin; 2 the logo's
# convex silhouette grown by the margin (Minkowski with a circle: hull -> circle per corner -> hull).
# Tray = outer slab minus the inner pocket (the same outline grown Rim Width less), one boolean.
from pathlib import Path

import bpy
from kit import gn, materials

GEO = Path(__file__).with_name("logo_geo.py")
ns: dict = {"__file__": str(GEO)}
exec(GEO.read_text(), ns)  # noqa: S102


def outline_group():
    """GN_ArtDealers_Outline: plate face (z=0) around Logo, grown by Grow; Shape/Corner Radius as above."""
    t = gn.tree("GN_ArtDealers_Outline", reset=True)
    gn.input(t, "Logo", "GEOMETRY")
    gn.input(t, "Grow", "FLOAT", 8.0, min=0.0, subtype="DISTANCE")
    gn.input(t, "Shape", "INT", 0, min=0, max=2)
    gn.input(t, "Corner Radius", "FLOAT", 4.0, min=0.0, subtype="DISTANCE")
    gn.output(t, "Mesh")
    gin, gout = gn.io(t)

    with gn.stage(t, "1 Rectangle"):
        bbox = gn.node(t, "GeometryNodeBoundBox")
        gn.link(t, gin, "Logo", bbox, "Geometry")
        size = gn.node(
            t, "ShaderNodeVectorMath", "Size", props={"operation": "SUBTRACT"}
        )
        gn.link(t, bbox, "Max", size, 0)
        gn.link(t, bbox, "Min", size, 1)
        split = gn.node(t, "ShaderNodeSeparateXYZ")
        gn.link(t, size, "Vector", split, "Vector")
        two_g = gn.node(
            t, "ShaderNodeMath", "2 x Grow", props={"operation": "MULTIPLY"}
        )
        gn.link(t, gin, "Grow", two_g, 0)
        two_g.inputs[1].default_value = 2.0
        quad = gn.node(
            t, "GeometryNodeCurvePrimitiveQuadrilateral", props={"mode": "RECTANGLE"}
        )
        for axis, sock in (("X", "Width"), ("Y", "Height")):
            add = gn.node(t, "ShaderNodeMath", sock, props={"operation": "ADD"})
            gn.link(t, split, axis, add, 0)
            gn.link(t, two_g, "Value", add, 1)
            gn.link(t, add, "Value", quad, sock)
        fillet = gn.node(
            t, "GeometryNodeFilletCurve", Mode="Poly", Count=8, Limit_Radius=True
        )
        gn.link(t, quad, "Curve", fillet, "Curve")
        gn.link(t, gin, "Corner Radius", fillet, "Radius")
        is_round = gn.node(
            t,
            "FunctionNodeCompare",
            "Shape = 1",
            props={"data_type": "INT", "operation": "EQUAL"},
            B=1,
        )
        gn.link(t, gin, "Shape", is_round, "A")
        pick = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
        gn.link(t, is_round, "Result", pick, "Switch")
        gn.link(t, quad, "Curve", pick, "False")
        gn.link(t, fillet, "Curve", pick, "True")
        centre = gn.node(
            t, "ShaderNodeVectorMath", "Min + Max", props={"operation": "ADD"}
        )
        gn.link(t, bbox, "Min", centre, 0)
        gn.link(t, bbox, "Max", centre, 1)
        half = gn.node(
            t, "ShaderNodeVectorMath", "Centre", props={"operation": "SCALE"}
        )
        gn.link(t, centre, "Vector", half, 0)
        half.inputs["Scale"].default_value = 0.5
        place = gn.node(t, "GeometryNodeTransform")
        gn.link(t, pick, "Output", place, "Geometry")
        gn.link(t, half, "Vector", place, "Translation")
        rect = gn.node(t, "GeometryNodeFillCurve", Mode="N-gons")
        gn.link(t, place, "Geometry", rect, "Curve")

    with gn.stage(t, "2 Silhouette"):
        hull = gn.node(t, "GeometryNodeConvexHull")
        gn.link(t, gin, "Logo", hull, "Geometry")
        circle = gn.node(t, "GeometryNodeCurvePrimitiveCircle", Resolution=32)
        gn.link(t, gin, "Grow", circle, "Radius")
        inst = gn.node(t, "GeometryNodeInstanceOnPoints")
        gn.link(t, hull, "Convex Hull", inst, "Points")
        gn.link(t, circle, "Curve", inst, "Instance")
        real = gn.node(t, "GeometryNodeRealizeInstances")
        gn.link(t, inst, "Instances", real, "Geometry")
        grown = gn.node(t, "GeometryNodeConvexHull")
        gn.link(t, real, "Geometry", grown, "Geometry")

    with gn.stage(t, "3 Pick"):
        is_sil = gn.node(
            t,
            "FunctionNodeCompare",
            "Shape = 2",
            props={"data_type": "INT", "operation": "EQUAL"},
            B=2,
        )
        gn.link(t, gin, "Shape", is_sil, "A")
        shape = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
        gn.link(t, is_sil, "Result", shape, "Switch")
        gn.link(t, rect, "Mesh", shape, "False")
        gn.link(t, grown, "Convex Hull", shape, "True")
        gn.link(t, shape, "Output", gout, "Mesh")
    gn.arrange(t)
    return t


t = gn.tree("GN_ArtDealers_Base", reset=True)
gn.input(t, "Geometry", "GEOMETRY")
gn.input(t, "Art", "OBJECT", description="CTL_Art outlines")
gn.input(t, "Galeria", "OBJECT", description="CTL_Galeria outlines")
gn.input(t, "Dealers Box", "OBJECT", description="CTL_DealersBox rectangle")
gn.input(
    t,
    "Logo Width",
    "FLOAT",
    150.0,
    min=20.0,
    subtype="DISTANCE",
    description="Overall logo width",
)
gn.input(
    t,
    "Base Thickness",
    "FLOAT",
    3.0,
    min=0.6,
    subtype="DISTANCE",
    description="Tray floor thickness",
)
gn.input(
    t,
    "Face Depth",
    "FLOAT",
    12.0,
    min=0.4,
    subtype="DISTANCE",
    description="Interior depth: rim and logo height above the floor",
)
gn.input(
    t,
    "Base Margin",
    "FLOAT",
    8.0,
    min=0.5,
    subtype="DISTANCE",
    description="Plate border around the logo (rim included)",
)
gn.input(
    t,
    "Rim Width",
    "FLOAT",
    4.0,
    min=0.8,
    subtype="DISTANCE",
    description="Tray wall thickness; must be less than Base Margin",
)
gn.input(
    t,
    "Base Shape",
    "INT",
    0,
    min=0,
    max=2,
    description="0 rectangle, 1 rounded rectangle, 2 silhouette",
)
gn.input(
    t,
    "Corner Radius",
    "FLOAT",
    4.0,
    min=0.1,
    subtype="DISTANCE",
    description="Rounded rectangle outer corner radius",
)
gn.output(t, "Geometry")
gin, gout = gn.io(t)
outline_t = outline_group()
slab_t = ns["slab_group"]()


def math(op: str, a, b, label: str = ""):
    """Math node; a/b are (node, socket) pairs or constants."""
    n = gn.node(t, "ShaderNodeMath", label, props={"operation": op})
    for i, v in enumerate((a, b)):
        if isinstance(v, tuple):
            gn.link(t, v[0], v[1], n, i)
        else:
            n.inputs[i].default_value = v
    return n


with gn.stage(t, "1 Logo outline"):
    join = gn.node(t, "GeometryNodeJoinGeometry")
    for name in ("Art", "Galeria", "Dealers Box"):
        info = gn.node(t, "GeometryNodeObjectInfo", name)
        gn.link(t, gin, name, info, "Object")
        gn.link(t, info, "Geometry", join, "Geometry")
    logo = gn.node(t, "GeometryNodeTransform")
    gn.link(t, join, "Geometry", logo, "Geometry")
    gn.link(t, ns["logo_scale"](t, gin), "Vector", logo, "Scale")

with gn.stage(t, "2 Outer slab"):
    outer = ns["group"](t, outline_t, "Outer")
    gn.link(t, logo, "Geometry", outer, "Logo")
    gn.link(t, gin, "Base Margin", outer, "Grow")
    gn.link(t, gin, "Base Shape", outer, "Shape")
    gn.link(t, gin, "Corner Radius", outer, "Corner Radius")
    top = math("ADD", (gin, "Base Thickness"), (gin, "Face Depth"), "Rim Top")
    body = ns["group"](t, slab_t, "Body")
    gn.link(t, outer, "Mesh", body, "Mesh")
    gn.link(t, top, "Value", body, "Height")

with gn.stage(t, "3 Pocket"):
    # inner outline: grown Rim Width less (kept >= 0.1 mm off the logo), corners shrink by the rim
    gap = math("SUBTRACT", (gin, "Base Margin"), (gin, "Rim Width"), "Margin - Rim")
    grow = math("MAXIMUM", (gap, "Value"), 0.1, "Pocket Grow")
    shrunk = math(
        "SUBTRACT", (gin, "Corner Radius"), (gin, "Rim Width"), "Radius - Rim"
    )
    radius = math("MAXIMUM", (shrunk, "Value"), 0.1, "Pocket Radius")
    inner = ns["group"](t, outline_t, "Inner")
    gn.link(t, logo, "Geometry", inner, "Logo")
    gn.link(t, grow, "Value", inner, "Grow")
    gn.link(t, gin, "Base Shape", inner, "Shape")
    gn.link(t, radius, "Value", inner, "Corner Radius")
    depth = math("ADD", (gin, "Face Depth"), 1.0, "Depth + 1")
    pocket = ns["group"](t, slab_t, "Pocket")
    gn.link(t, inner, "Mesh", pocket, "Mesh")
    gn.link(t, depth, "Value", pocket, "Height")
    gn.link(t, gin, "Base Thickness", pocket, "Bottom")
    solvers = [
        i.identifier
        for i in bpy.types.GeometryNodeMeshBoolean.bl_rna.properties[
            "solver"
        ].enum_items
    ]  # ty: ignore[unresolved-attribute]
    cut = gn.node(
        t,
        "GeometryNodeMeshBoolean",
        props={
            "operation": "DIFFERENCE",
            "solver": "MANIFOLD" if "MANIFOLD" in solvers else "EXACT",
        },
    )
    gn.link(t, body, "Mesh", cut, "Mesh 1")
    gn.link(t, pocket, "Mesh", cut, "Mesh 2")
    mat = gn.node(t, "GeometryNodeSetMaterial")
    mat.inputs["Material"].default_value = ns["base_material"]()
    gn.link(t, cut, "Mesh", mat, "Geometry")
    gn.link(t, mat, "Geometry", gout, "Geometry")

gn.arrange(t)

obj = gn.host("Logo_Base")
materials.assign(obj, ns["base_material"]())
gn.modifier(obj, t, Art="CTL_Art", Galeria="CTL_Galeria", Dealers_Box="CTL_DealersBox")
