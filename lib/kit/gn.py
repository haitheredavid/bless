"""Geometry Nodes: build node groups in code, attach them as modifiers, read/write inputs.

Everything addresses sockets by their *name* ("Depth"), never by identifier ("Socket_2"):
identifiers depend on creation order and break as soon as a group is edited by hand.
Blender 5 moved modifier inputs from ID properties (mod["Socket_2"]) to
mod.properties.inputs.Socket_2.value; set_input/get_input handle both.

    t = gn.tree("GN_Thing")                       # get or create (is_modifier)
    gn.input(t, "Depth", "FLOAT", 40.0, min=0)    # idempotent by name
    gin, gout = gn.io(t)
    ext = gn.node(t, "GeometryNodeExtrudeMesh", Offset_Scale=...)
    gn.link(t, gin, "Geometry", ext, "Mesh")
    gn.arrange(t)
    mod = gn.modifier(obj, t, Depth=60.0)
    gn.set_input(mod, "Depth", 55.0)
"""

from contextlib import contextmanager

import bpy

SOCKET_TYPES = {
    "GEOMETRY": "NodeSocketGeometry",
    "FLOAT": "NodeSocketFloat",
    "INT": "NodeSocketInt",
    "BOOL": "NodeSocketBool",
    "VECTOR": "NodeSocketVector",
    "OBJECT": "NodeSocketObject",
    "COLLECTION": "NodeSocketCollection",
    "MATERIAL": "NodeSocketMaterial",
    "STRING": "NodeSocketString",
    "COLOR": "NodeSocketColor",
}


_DECLARED: dict[
    str, set[str]
] = {}  # interface items declared since each tree's last reset


def tree(name: str, reset: bool = False) -> bpy.types.GeometryNodeTree:
    """Get or create a modifier node group. reset=True clears its nodes for a clean
    rebuild but keeps the interface: inputs/outputs/panels are re-declared by name
    (input/output/panel), so group nodes elsewhere stay linked and modifier input values
    survive. Clearing the interface used to unlink every tree using the group and zero
    modifier inputs not covered by params.toml. prune() drops items not re-declared."""
    t = bpy.data.node_groups.get(name)
    if t is None:
        t = bpy.data.node_groups.new(name, "GeometryNodeTree")
    elif reset:
        t.nodes.clear()
    if reset or name not in _DECLARED:
        _DECLARED[name] = set()
    t.is_modifier = True
    return t


def prune(t) -> list[str]:
    """Remove interface items not declared since the last tree(reset=True): inputs a
    builder no longer creates. Call at the end of a rebuild; returns the removed names."""
    keep = _DECLARED.get(t.name, set())
    gone = [i for i in t.interface.items_tree if i.name not in keep]
    names = [i.name for i in gone]
    for i in gone:
        t.interface.remove(i)
    return names


def panel(t, name: str):
    """Get or create an interface panel by name."""
    _DECLARED.setdefault(t.name, set()).add(name)
    for i in t.interface.items_tree:
        if i.item_type == "PANEL" and i.name == name:
            return i
    return t.interface.new_panel(name)


def current(t, source: str) -> bool:
    """True if group t was built from this exact source file (see stamp()). Pattern
    builders use it so editing a pattern rebuilds its group in every .blend that runs it."""
    return bool(t.nodes) and t.get("source_hash") == _hash(source)


def stamp(t, source: str) -> None:
    t["source_hash"] = _hash(source)


def _hash(source: str) -> str:
    import hashlib

    with open(source, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:12]


def _items(t, in_out: str) -> dict:
    return {
        i.name: i
        for i in t.interface.items_tree
        if i.item_type == "SOCKET" and i.in_out == in_out
    }


def input(
    t,
    name: str,
    kind: str = "FLOAT",
    default=None,
    min=None,
    max=None,
    subtype: str | None = None,
    description: str = "",
):
    """Get or create a group input socket by name; set default/min/max when given.
    An existing socket of another type is replaced."""
    _DECLARED.setdefault(t.name, set()).add(name)
    sock = _items(t, "INPUT").get(name)
    if sock is not None and sock.socket_type != SOCKET_TYPES[kind]:
        t.interface.remove(sock)
        sock = None
    if sock is None:
        sock = t.interface.new_socket(
            name, in_out="INPUT", socket_type=SOCKET_TYPES[kind]
        )
    if description:
        sock.description = description
    if subtype and hasattr(sock, "subtype"):
        sock.subtype = subtype
    if min is not None and hasattr(sock, "min_value"):
        sock.min_value = min
    if max is not None and hasattr(sock, "max_value"):
        sock.max_value = max
    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default
    return sock


def output(t, name: str = "Geometry", kind: str = "GEOMETRY"):
    _DECLARED.setdefault(t.name, set()).add(name)
    sock = _items(t, "OUTPUT").get(name)
    if sock is not None and sock.socket_type != SOCKET_TYPES[kind]:
        t.interface.remove(sock)
        sock = None
    if sock is None:
        sock = t.interface.new_socket(
            name, in_out="OUTPUT", socket_type=SOCKET_TYPES[kind]
        )
    return sock


def io(t) -> tuple[bpy.types.Node, bpy.types.Node]:
    """The group input and output nodes (created if missing)."""
    gin = next((n for n in t.nodes if n.bl_idname == "NodeGroupInput"), None)
    gout = next((n for n in t.nodes if n.bl_idname == "NodeGroupOutput"), None)
    gin = gin or t.nodes.new("NodeGroupInput")
    gout = gout or t.nodes.new("NodeGroupOutput")
    return gin, gout


def _socket(sockets, key):
    """A node socket by index or by name (first enabled match; Math has three 'Value's)."""
    if isinstance(key, int):
        return sockets[key]
    for s in sockets:
        if s.name == key and s.enabled:
            return s
    for s in sockets:
        if s.identifier == key:
            return s
    raise KeyError(f"no socket {key!r} in {[s.name for s in sockets]}")


def node(t, idname: str, label: str = "", props: dict | None = None, **inputs):
    """Add a node. props sets node properties (e.g. operation, transform_space); kwargs
    set input defaults by socket name, with spaces written as underscores."""
    n = t.nodes.new(idname)
    if label:
        n.label = label
    for k, v in (props or {}).items():
        setattr(n, k, v)
    for k, v in inputs.items():
        _socket(n.inputs, k.replace("_", " ")).default_value = v
    return n


def link(t, a, a_out, b, b_in):
    """Link a.outputs[a_out] -> b.inputs[b_in] (names or indices)."""
    return t.links.new(_socket(a.outputs, a_out), _socket(b.inputs, b_in))


_STAGES: dict[str, list[tuple[str, list[str]]]] = {}
COLORS = [  # muted frame tints, cycled per stage
    (0.30, 0.38, 0.50), (0.42, 0.33, 0.50), (0.30, 0.45, 0.38),
    (0.50, 0.40, 0.28), (0.45, 0.30, 0.33), (0.30, 0.43, 0.48),
]  # fmt: skip


@contextmanager
def stage(t, label: str):
    """Group the nodes created inside the block under a labelled Frame box; arrange()
    lays stages out left to right in the order they were declared.

        with gn.stage(t, "1 · Outline ring"):
            ...nodes...
    """
    before = {n.name for n in t.nodes}
    yield
    new = [
        n.name for n in t.nodes if n.name not in before and n.bl_idname != "NodeFrame"
    ]
    _STAGES.setdefault(t.name, []).append((label, new))


def _depths(t) -> dict:
    depth = {n.name: 0 for n in t.nodes if n.bl_idname != "NodeFrame"}
    for _ in range(len(depth)):
        changed = False
        for lk in t.links:
            d = depth[lk.from_node.name] + 1
            if d > depth[lk.to_node.name]:
                depth[lk.to_node.name], changed = d, True
        if not changed:
            break
    return depth


def _place(n, x: float, y: float) -> None:
    if hasattr(n, "location_absolute"):  # Blender 4.4+: location is parent-relative
        n.location_absolute = (x, y)
    else:
        n.location = (x, y)


def arrange(t, dx: float = 220.0, dy: float = 180.0, gap: float = 160.0) -> None:
    """Lay nodes out left-to-right by link depth so the tree reads in the node editor.
    With stage() blocks, each stage gets its own column band (in declaration order) and
    a labelled, tinted Frame box; group input sits left, group output right."""
    for n in [n for n in t.nodes if n.bl_idname == "NodeFrame"]:
        t.nodes.remove(n)
    depth = _depths(t)
    stages = _STAGES.pop(t.name, [])
    if not stages:
        columns: dict[int, list] = {}
        for name, d in depth.items():
            columns.setdefault(d, []).append(t.nodes[name])
        for d, nodes in columns.items():
            for i, n in enumerate(nodes):
                _place(n, d * dx, -i * dy)
        return
    staged = {name for _, names in stages for name in names}
    x = 0.0
    loose = [t.nodes[n] for n in depth if n not in staged]
    gin = [n for n in loose if n.bl_idname == "NodeGroupInput"]
    gout = [n for n in loose if n.bl_idname == "NodeGroupOutput"]
    for i, n in enumerate(gin):
        _place(n, x, -i * dy)
    x += dx + gap
    for k, (label, names) in enumerate(stages):
        if not names:
            continue
        lo = min(depth[n] for n in names)
        cols: dict[int, list] = {}
        for name in names:
            cols.setdefault(depth[name] - lo, []).append(t.nodes[name])
        frame = t.nodes.new("NodeFrame")
        frame.label = label
        frame.label_size = 28
        frame.use_custom_color = True
        frame.color = COLORS[k % len(COLORS)]
        for c, nodes in sorted(cols.items()):
            for i, n in enumerate(nodes):
                n.parent = frame
                _place(n, x + c * dx, -i * dy)
        x += (max(cols) + 1) * dx + gap
    for i, n in enumerate(n for n in loose if n not in gin and n not in gout):
        _place(n, x, -i * dy)
    for i, n in enumerate(gout):
        _place(n, x + dx, -i * dy)


# --- modifiers -----------------------------------------------------------------


def host(name: str, coll=None) -> bpy.types.Object:
    """Get or create an empty-mesh object (in Model by default) to carry GN modifiers."""
    from kit import scene

    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        (coll or scene.model()).objects.link(obj)
    return obj


def modifier(obj, t, name: str | None = None, **inputs) -> bpy.types.Modifier:
    """Get or add a NODES modifier running group t; kwargs set inputs by socket name
    (underscores stand for spaces)."""
    name = name or t.name
    mod = obj.modifiers.get(name)
    if mod is None:
        mod = obj.modifiers.new(name, "NODES")
    mod.node_group = t
    for k, v in inputs.items():
        set_input(mod, k.replace("_", " "), v)
    return mod


def socket_id(t, name: str) -> str:
    sock = _items(t, "INPUT").get(name)
    if sock is None:
        raise KeyError(
            f"{t.name} has no input {name!r}; has {list(_items(t, 'INPUT'))}"
        )
    return sock.identifier


def has_input(mod, name: str) -> bool:
    return mod.node_group is not None and name in _items(mod.node_group, "INPUT")


def _read(mod, ident: str):
    """Current value of input `ident`. Blender 5 keeps modifier inputs in
    mod.properties.inputs.<id>.value; older versions used ID properties (mod[id])."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        return getattr(props.inputs, ident).value
    return mod.get(ident)


def _write(mod, ident: str, value) -> None:
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        getattr(props.inputs, ident).value = value
    else:
        mod[ident] = value


def set_input(mod, name: str, value) -> None:
    """Set a modifier input by socket name and re-evaluate. Coerces to the socket's type
    (60 -> 60.0 for a float, "CTL_Path" -> the object) so the input never turns red."""
    sock = _items(mod.node_group, "INPUT").get(name)
    if sock is None:
        raise KeyError(f"{mod.node_group.name} has no input {name!r}")
    kind = sock.socket_type
    if kind == "NodeSocketFloat":
        value = float(value)
    elif kind == "NodeSocketInt":
        value = int(value)
    elif kind == "NodeSocketBool":
        value = bool(value)
    elif kind == "NodeSocketObject" and isinstance(value, str):
        value = bpy.data.objects[value]
    elif kind == "NodeSocketMaterial" and isinstance(value, str):
        value = bpy.data.materials[value]
    _write(mod, sock.identifier, value)
    mod.id_data.update_tag()


def _plain(v):
    if hasattr(v, "name") and hasattr(v, "users"):  # ID (object, material, ...)
        return v.name
    if hasattr(v, "__len__") and not isinstance(v, str):
        return list(v)
    return v


def get_input(mod, name: str):
    """A modifier input by socket name (IDs as their name, vectors as lists)."""
    return _plain(_read(mod, socket_id(mod.node_group, name)))


def inputs(mod) -> dict:
    """All non-geometry inputs of a GN modifier as {name: value}."""
    return {
        name: _plain(_read(mod, sock.identifier))
        for name, sock in _items(mod.node_group, "INPUT").items()
        if sock.socket_type != "NodeSocketGeometry"
    }


def gn_modifiers(obj) -> list[bpy.types.Modifier]:
    return [m for m in obj.modifiers if m.type == "NODES" and m.node_group]
