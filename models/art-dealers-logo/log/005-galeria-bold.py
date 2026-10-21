# step 5: Galeria Bold 0.2: grow GALERIA outlines per side (median stroke 0.84 -> 1.21 mm, p5 0.53 -> 0.90)
# Logo_Face: the light raised face (filament 2), z = Base Thickness .. + Face Depth.
# Art + GALERIA + (Dealers box minus Dealers letters). Knockout cuts the letters through the box
# to the plate; otherwise they are pocketed Dealers Recess from the top.
from pathlib import Path

import bpy
from kit import gn, materials

GEO = Path(__file__).with_name("logo_geo.py")
ns: dict = {"__file__": str(GEO)}
exec(GEO.read_text(), ns)  # noqa: S102

t = gn.tree("GN_ArtDealers_Face", reset=True)
gn.input(t, "Geometry", "GEOMETRY")
gn.input(t, "Art", "OBJECT", description="CTL_Art outlines")
gn.input(t, "Galeria", "OBJECT", description="CTL_Galeria outlines")
gn.input(t, "Dealers Box", "OBJECT", description="CTL_DealersBox rectangle")
gn.input(
    t, "Dealers Text", "OBJECT", description="CTL_DealersText letters cut from the box"
)
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
    description="Face starts at this height",
)
gn.input(
    t,
    "Face Depth",
    "FLOAT",
    12.0,
    min=0.4,
    subtype="DISTANCE",
    description="Height of the white logo above the floor (tray interior depth)",
)
gn.input(
    t,
    "Galeria Bold",
    "FLOAT",
    0.2,
    min=0.0,
    max=0.25,  # 0.3 folds the smallest counters (non-manifold)
    subtype="DISTANCE",
    description="Grow GALERIA strokes outward by this much per side",
)
gn.input(
    t,
    "Dealers Knockout",
    "BOOL",
    True,
    description="Cut Dealers through the box (else recess)",
)
gn.input(
    t,
    "Dealers Recess",
    "FLOAT",
    1.2,
    min=0.2,
    subtype="DISTANCE",
    description="Pocket depth when not knocked out",
)
gn.output(t, "Geometry")
gin, gout = gn.io(t)
slab_t = ns["slab_group"]()


def solid(name: str, grow=None):
    """Fill the Control curves of input `name` (even-odd: counters become holes) into a slab node.
    grow: optional (node, socket) distance in curve units to push every outline away from the fill.
    The tracer keeps the light side on one side of every loop (outers and counters alike), so one
    sign of tangent x -Z grows strokes and shrinks counters (checked: volume rises with grow)."""
    info = gn.node(t, "GeometryNodeObjectInfo", name)
    gn.link(t, gin, name, info, "Object")
    curve = (info, "Geometry")
    if grow is not None:
        tangent = gn.node(t, "GeometryNodeInputTangent")
        side = gn.node(
            t, "ShaderNodeVectorMath", "Outward", props={"operation": "CROSS_PRODUCT"}
        )
        gn.link(t, tangent, "Tangent", side, 0)
        side.inputs[1].default_value = (0.0, 0.0, -1.0)
        unit = gn.node(t, "ShaderNodeVectorMath", props={"operation": "NORMALIZE"})
        gn.link(t, side, "Vector", unit, 0)
        offset = gn.node(t, "ShaderNodeVectorMath", props={"operation": "SCALE"})
        gn.link(t, unit, "Vector", offset, 0)
        gn.link(t, grow[0], grow[1], offset, "Scale")
        move = gn.node(t, "GeometryNodeSetPosition", f"{name} Bold")
        gn.link(t, info, "Geometry", move, "Geometry")
        gn.link(t, offset, "Vector", move, "Offset")
        curve = (move, "Geometry")
    fill = gn.node(t, "GeometryNodeFillCurve", Mode="N-gons")
    gn.link(t, curve[0], curve[1], fill, "Curve")
    slab = ns["group"](t, slab_t, name)
    gn.link(t, fill, "Mesh", slab, "Mesh")
    return slab


def math(op: str, a, b, label: str = ""):
    """Math node; a/b are (node, socket) pairs or constants."""
    n = gn.node(t, "ShaderNodeMath", label, props={"operation": op})
    for i, v in enumerate((a, b)):
        if isinstance(v, tuple):
            gn.link(t, v[0], v[1], n, i)
        else:
            n.inputs[i].default_value = v
    return n


def switch(label: str, false, true):
    """Float switch on Dealers Knockout; false/true are (node, socket) pairs or constants."""
    n = gn.node(t, "GeometryNodeSwitch", label, props={"input_type": "FLOAT"})
    gn.link(t, gin, "Dealers Knockout", n, "Switch")
    for key, v in (("False", false), ("True", true)):
        if isinstance(v, tuple):
            gn.link(t, v[0], v[1], n, key)
        else:
            n.inputs[key].default_value = v
    return n


with gn.stage(t, "1 Letters"):
    # Galeria Bold is in mm at the final size; the curves are scaled by Logo Width / TRACE_WIDTH later
    bold = math("MULTIPLY", (gin, "Galeria Bold"), ns["TRACE_WIDTH"], "Bold x Trace")
    bold = math("DIVIDE", (bold, "Value"), (gin, "Logo Width"), "Bold (curve units)")
    parts = [solid("Art"), solid("Galeria", (bold, "Value"))]
    for s in parts:
        gn.link(t, gin, "Face Depth", s, "Height")

with gn.stage(t, "2 Dealers box"):
    box = solid("Dealers Box")
    gn.link(t, gin, "Face Depth", box, "Height")
    text = solid("Dealers Text")
    # knockout: z -1 .. depth + 1 (clean through); recess: depth - recess .. depth + 1
    through = math("ADD", (gin, "Face Depth"), 2.0, "Depth + 2")
    pocket = math("ADD", (gin, "Dealers Recess"), 1.0, "Recess + 1")
    floor = math(
        "SUBTRACT", (gin, "Face Depth"), (gin, "Dealers Recess"), "Pocket Floor"
    )
    height = switch("Cutter Height", (pocket, "Value"), (through, "Value"))
    bottom = switch("Cutter Bottom", (floor, "Value"), -1.0)
    gn.link(t, height, "Output", text, "Height")
    gn.link(t, bottom, "Output", text, "Bottom")
    solvers = [
        i.identifier
        for i in bpy.types.GeometryNodeMeshBoolean.bl_rna.properties[
            "solver"
        ].enum_items
    ]
    cut = gn.node(
        t,
        "GeometryNodeMeshBoolean",
        props={
            "operation": "DIFFERENCE",
            "solver": "MANIFOLD" if "MANIFOLD" in solvers else "EXACT",
        },
    )
    gn.link(t, box, "Mesh", cut, "Mesh 1")
    gn.link(t, text, "Mesh", cut, "Mesh 2")

with gn.stage(t, "3 Place"):
    join = gn.node(t, "GeometryNodeJoinGeometry")
    for s in parts:
        gn.link(t, s, "Mesh", join, "Geometry")
    gn.link(t, cut, "Mesh", join, "Geometry")
    lift = gn.node(t, "ShaderNodeCombineXYZ")
    gn.link(t, gin, "Base Thickness", lift, "Z")
    place = gn.node(t, "GeometryNodeTransform")
    gn.link(t, join, "Geometry", place, "Geometry")
    gn.link(t, ns["logo_scale"](t, gin), "Vector", place, "Scale")
    gn.link(t, lift, "Vector", place, "Translation")
    mat = gn.node(t, "GeometryNodeSetMaterial")
    mat.inputs["Material"].default_value = ns["face_material"]()
    gn.link(t, place, "Geometry", mat, "Geometry")
    gn.link(t, mat, "Geometry", gout, "Geometry")

gn.arrange(t)

obj = gn.host("Logo_Face")
materials.assign(obj, ns["face_material"]())
gn.modifier(
    obj,
    t,
    Art="CTL_Art",
    Galeria="CTL_Galeria",
    Dealers_Box="CTL_DealersBox",
    Dealers_Text="CTL_DealersText",
)
