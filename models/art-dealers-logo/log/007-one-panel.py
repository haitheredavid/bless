# step 7: Logo object: GN_ArtDealers_Logo wraps base+face, every setting once in Size/Box/Lettering panels; Print bodies driven from it
# Logo: the one object to play with. GN_ArtDealers_Logo runs the base and face groups and joins
# them, so every setting appears once, in labelled panels, on one modifier. The print bodies
# (Logo_Base, Logo_Face in Print) follow it live: each of their inputs is driven from Logo's.
import bpy
from kit import gn, scene

BASE, FACE = (
    bpy.data.node_groups["GN_ArtDealers_Base"],
    bpy.data.node_groups["GN_ArtDealers_Face"],
)
CONTROL = {
    "Art": "CTL_Art",
    "Galeria": "CTL_Galeria",
    "Dealers Box": "CTL_DealersBox",
    "Dealers Text": "CTL_DealersText",
}
PANELS = {  # panel: settings in display order (names are params.toml keys)
    "Size": ["Logo Width"],
    "Box": [
        "Base Shape",
        "Corner Radius",
        "Base Margin",
        "Rim Width",
        "Base Thickness",
        "Face Depth",
    ],
    "Lettering": ["Galeria Bold", "Dealers Knockout", "Dealers Recess"],
}


def socket(name):
    """The input socket `name` of the base or face group (shared ones read from the base)."""
    for group in (BASE, FACE):
        for i in group.interface.items_tree:
            if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == name:
                return i
    raise KeyError(name)


t = gn.tree("GN_ArtDealers_Logo", reset=True)
gn.input(t, "Geometry", "GEOMETRY")
for panel_name, names in PANELS.items():
    panel = t.interface.new_panel(panel_name)
    for name in names:
        src = socket(name)
        kind = {
            "NodeSocketFloat": "FLOAT",
            "NodeSocketInt": "INT",
            "NodeSocketBool": "BOOL",
        }[src.socket_type]
        sock = gn.input(t, name, kind, src.default_value, getattr(src, "min_value", None),
                        getattr(src, "max_value", None), getattr(src, "subtype", None), src.description)  # fmt: skip
        t.interface.move_to_parent(sock, panel, len(panel.interface_items))
gn.output(t, "Geometry")
gin, gout = gn.io(t)
join = gn.node(t, "GeometryNodeJoinGeometry")
for group in (BASE, FACE):
    node = gn.node(
        t,
        "GeometryNodeGroup",
        group.name.removeprefix("GN_ArtDealers_"),
        props={"node_tree": group},
    )
    for s in node.inputs:
        if s.name in CONTROL:
            s.default_value = bpy.data.objects[CONTROL[s.name]]
        elif s.type != "GEOMETRY":
            gn.link(t, gin, s.name, node, s.name)
    gn.link(t, node, "Geometry", join, "Geometry")
gn.link(t, join, "Geometry", gout, "Geometry")
gn.arrange(t)

logo = gn.host("Logo")
mod = gn.modifier(logo, t)

# print bodies follow Logo: drive every non-object input from the matching Logo input
for name in ("Logo_Base", "Logo_Face"):
    part = bpy.data.objects[name]
    pmod = gn.gn_modifiers(part)[0]
    for item in pmod.node_group.interface.items_tree:
        if (
            item.item_type != "SOCKET"
            or item.in_out != "INPUT"
            or item.name in CONTROL
            or item.socket_type == "NodeSocketGeometry"
        ):
            continue
        slot = getattr(pmod.properties.inputs, item.identifier)
        slot.driver_remove("value")
        fc = slot.driver_add("value")
        fc.driver.type = "AVERAGE"
        var = fc.driver.variables.new()
        var.type = "SINGLE_PROP"
        var.targets[0].id = logo
        var.targets[0].data_path = getattr(
            mod.properties.inputs, gn.socket_id(t, item.name)
        ).path_from_id("value")

# Print stays out of the way: not drawn, not rendered (print-pack shows it while packing)
parts = scene.parts()
parts.hide_viewport = True
