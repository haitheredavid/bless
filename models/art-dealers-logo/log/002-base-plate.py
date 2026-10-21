# step 2: Logo_Base: GN_ArtDealers_Base plate (rect/rounded/silhouette) 3 mm, dark
# Logo_Base: the dark plate (filament 1), z = 0 .. Base Thickness.
# Shape 0 rectangle / 1 rounded rectangle around the logo bounds + margin; 2 the logo's convex
# silhouette grown by the margin (Minkowski with a circle: hull -> circle per corner -> hull).
from pathlib import Path

from kit import gn, materials

GEO = Path(__file__).with_name("logo_geo.py")
ns: dict = {"__file__": str(GEO)}
exec(GEO.read_text(), ns)  # noqa: S102

t = gn.tree("GN_ArtDealers_Base", reset=True)
gn.input(t, "Geometry", "GEOMETRY")
gn.input(t, "Art", "OBJECT", description="CTL_Art outlines")
gn.input(t, "Galeria", "OBJECT", description="CTL_Galeria outlines")
gn.input(t, "Dealers Box", "OBJECT", description="CTL_DealersBox rectangle")
gn.input(t, "Logo Width", "FLOAT", 150.0, min=20.0, subtype="DISTANCE", description="Overall logo width")
gn.input(t, "Base Thickness", "FLOAT", 3.0, min=0.6, subtype="DISTANCE", description="Plate thickness; colour change height")
gn.input(t, "Base Margin", "FLOAT", 8.0, min=0.5, subtype="DISTANCE", description="Plate border around the logo")
gn.input(t, "Base Shape", "INT", 0, min=0, max=2, description="0 rectangle, 1 rounded rectangle, 2 silhouette")
gn.input(t, "Corner Radius", "FLOAT", 4.0, min=0.1, subtype="DISTANCE", description="Rounded rectangle corner radius")
gn.output(t, "Geometry")
gin, gout = gn.io(t)

with gn.stage(t, "1 Logo outline"):
    join = gn.node(t, "GeometryNodeJoinGeometry")
    for name in ("Art", "Galeria", "Dealers Box"):
        info = gn.node(t, "GeometryNodeObjectInfo", name)
        gn.link(t, gin, name, info, "Object")
        gn.link(t, info, "Geometry", join, "Geometry")
    logo = gn.node(t, "GeometryNodeTransform")
    gn.link(t, join, "Geometry", logo, "Geometry")
    gn.link(t, ns["logo_scale"](t, gin), "Vector", logo, "Scale")

with gn.stage(t, "2 Rectangle"):
    bbox = gn.node(t, "GeometryNodeBoundBox")
    gn.link(t, logo, "Geometry", bbox, "Geometry")
    size = gn.node(t, "ShaderNodeVectorMath", "Size", props={"operation": "SUBTRACT"})
    gn.link(t, bbox, "Max", size, 0)
    gn.link(t, bbox, "Min", size, 1)
    split = gn.node(t, "ShaderNodeSeparateXYZ")
    gn.link(t, size, "Vector", split, "Vector")
    two_m = gn.node(t, "ShaderNodeMath", "2 x Margin", props={"operation": "MULTIPLY"})
    gn.link(t, gin, "Base Margin", two_m, 0)
    two_m.inputs[1].default_value = 2.0
    quad = gn.node(t, "GeometryNodeCurvePrimitiveQuadrilateral", props={"mode": "RECTANGLE"})
    for axis, sock in (("X", "Width"), ("Y", "Height")):
        add = gn.node(t, "ShaderNodeMath", sock, props={"operation": "ADD"})
        gn.link(t, split, axis, add, 0)
        gn.link(t, two_m, "Value", add, 1)
        gn.link(t, add, "Value", quad, sock)
    fillet = gn.node(t, "GeometryNodeFilletCurve", Mode="Poly", Count=8, Limit_Radius=True)
    gn.link(t, quad, "Curve", fillet, "Curve")
    gn.link(t, gin, "Corner Radius", fillet, "Radius")
    is_round = gn.node(t, "FunctionNodeCompare", "Shape = 1", props={"data_type": "INT", "operation": "EQUAL"}, B=1)
    gn.link(t, gin, "Base Shape", is_round, "A")
    pick = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
    gn.link(t, is_round, "Result", pick, "Switch")
    gn.link(t, quad, "Curve", pick, "False")
    gn.link(t, fillet, "Curve", pick, "True")
    centre = gn.node(t, "ShaderNodeVectorMath", "Min + Max", props={"operation": "ADD"})
    gn.link(t, bbox, "Min", centre, 0)
    gn.link(t, bbox, "Max", centre, 1)
    half = gn.node(t, "ShaderNodeVectorMath", "Centre", props={"operation": "SCALE"})
    gn.link(t, centre, "Vector", half, 0)
    half.inputs["Scale"].default_value = 0.5
    place = gn.node(t, "GeometryNodeTransform")
    gn.link(t, pick, "Output", place, "Geometry")
    gn.link(t, half, "Vector", place, "Translation")
    rect = gn.node(t, "GeometryNodeFillCurve", Mode="N-gons")
    gn.link(t, place, "Geometry", rect, "Curve")

with gn.stage(t, "3 Silhouette"):
    hull = gn.node(t, "GeometryNodeConvexHull")
    gn.link(t, logo, "Geometry", hull, "Geometry")
    circle = gn.node(t, "GeometryNodeCurvePrimitiveCircle", Resolution=32)
    gn.link(t, gin, "Base Margin", circle, "Radius")
    inst = gn.node(t, "GeometryNodeInstanceOnPoints")
    gn.link(t, hull, "Convex Hull", inst, "Points")
    gn.link(t, circle, "Curve", inst, "Instance")
    real = gn.node(t, "GeometryNodeRealizeInstances")
    gn.link(t, inst, "Instances", real, "Geometry")
    grown = gn.node(t, "GeometryNodeConvexHull")
    gn.link(t, real, "Geometry", grown, "Geometry")

with gn.stage(t, "4 Plate"):
    is_sil = gn.node(t, "FunctionNodeCompare", "Shape = 2", props={"data_type": "INT", "operation": "EQUAL"}, B=2)
    gn.link(t, gin, "Base Shape", is_sil, "A")
    shape = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
    gn.link(t, is_sil, "Result", shape, "Switch")
    gn.link(t, rect, "Mesh", shape, "False")
    gn.link(t, grown, "Convex Hull", shape, "True")
    slab = ns["group"](t, ns["slab_group"](), "Slab")
    gn.link(t, shape, "Output", slab, "Mesh")
    gn.link(t, gin, "Base Thickness", slab, "Height")
    mat = gn.node(t, "GeometryNodeSetMaterial")
    mat.inputs["Material"].default_value = ns["base_material"]()
    gn.link(t, slab, "Mesh", mat, "Geometry")
    gn.link(t, mat, "Geometry", gout, "Geometry")

gn.arrange(t)

obj = gn.host("Logo_Base")
materials.assign(obj, ns["base_material"]())
gn.modifier(obj, t, Art="CTL_Art", Galeria="CTL_Galeria", Dealers_Box="CTL_DealersBox")
