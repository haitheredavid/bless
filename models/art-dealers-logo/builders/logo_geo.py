# Shared GN pieces for the base and face builders (not run by build_all; builders exec it).
#   ns = {"__file__": str(path)}; exec(path.read_text(), ns)
from kit import gn, materials

TRACE_WIDTH = (
    150.0  # mm; width the Control curves were traced at (trace_logo.py LOGO_WIDTH)
)
BASE_COLOR = "#111111"  # filament 1
FACE_COLOR = "#EEEEEE"  # filament 2


def slab_group():
    """GN_ArtDealers_Slab: flat faces (z=0) extruded up Height into a closed solid, moved to Bottom.
    Rebuilt only when this file changes: resetting it would unlink the group nodes already using it."""
    t = gn.tree("GN_ArtDealers_Slab")
    if gn.current(t, __file__):
        return t
    t = gn.tree("GN_ArtDealers_Slab", reset=True)
    gn.input(t, "Mesh", "GEOMETRY")
    gn.input(t, "Height", "FLOAT", 1.0, min=0.0, subtype="DISTANCE")
    gn.input(t, "Bottom", "FLOAT", 0.0, subtype="DISTANCE")
    gn.output(t, "Mesh")
    gin, gout = gn.io(t)
    up = gn.node(t, "ShaderNodeCombineXYZ")
    ext = gn.node(
        t,
        "GeometryNodeExtrudeMesh",
        props={"mode": "FACES"},
        Offset_Scale=1.0,
        Individual=False,
    )
    floor = gn.node(t, "GeometryNodeFlipFaces")
    join = gn.node(t, "GeometryNodeJoinGeometry")
    merge = gn.node(t, "GeometryNodeMergeByDistance", Distance=1e-4)
    at = gn.node(t, "ShaderNodeCombineXYZ")
    move = gn.node(t, "GeometryNodeTransform")
    gn.link(t, gin, "Height", up, "Z")
    gn.link(t, gin, "Mesh", ext, "Mesh")
    gn.link(t, up, "Vector", ext, "Offset")
    gn.link(t, gin, "Mesh", floor, "Mesh")
    gn.link(t, ext, "Mesh", join, "Geometry")
    gn.link(t, floor, "Mesh", join, "Geometry")
    gn.link(t, join, "Geometry", merge, "Geometry")
    gn.link(t, gin, "Bottom", at, "Z")
    gn.link(t, merge, "Geometry", move, "Geometry")
    gn.link(t, at, "Vector", move, "Translation")
    gn.link(t, move, "Geometry", gout, "Mesh")
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def group(t, sub, label: str = ""):
    """A group node running node group `sub` inside t."""
    return gn.node(t, "GeometryNodeGroup", label, props={"node_tree": sub})


def logo_scale(t, gin):
    """Vector (k, k, 1) with k = Logo Width / TRACE_WIDTH: scales the traced curves in XY only."""
    k = gn.node(t, "ShaderNodeMath", "Logo Scale", props={"operation": "DIVIDE"})
    gn.link(t, gin, "Logo Width", k, 0)
    k.inputs[1].default_value = TRACE_WIDTH
    v = gn.node(t, "ShaderNodeCombineXYZ", Z=1.0)
    gn.link(t, k, "Value", v, "X")
    gn.link(t, k, "Value", v, "Y")
    return v


def _material(name: str, color: str, roughness: float):
    """Created once with the default colour; after that the colour is the user's (rebuilds keep it)."""
    import bpy

    return bpy.data.materials.get(name) or materials.principled(
        name, color, roughness=roughness
    )


def base_material():
    return _material("Box Colour", BASE_COLOR, 0.6)


def face_material():
    return _material("Letters Colour", FACE_COLOR, 0.5)
