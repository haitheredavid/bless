"""Node-building helpers shared by the joint patterns (not a pattern itself).

Values passed to these helpers are either plain floats (set as socket defaults) or
output sockets (linked), so a helper call reads like the formula it builds.

Shapes are convex hulls of "trapezoid boxes": a unit cube whose vertices are moved to
x0..x1, z0..z1 and a half-width h(x) = half + slope * x + grow * sqrt(1 + slope^2).
`grow` is a perpendicular offset of the flanks, which is what clearance is (see
print-fit-and-sectioning.md: adding grow to the half-width under-clears angled edges).
"""

import bpy
from kit import gn

PART_A, PART_B, PART_LOOSE = 0, 1, 2


def feed(t, sock, v) -> None:
    """Link an output socket into sock, or set sock's default to a constant."""
    if isinstance(v, bpy.types.NodeSocket):
        t.links.new(v, sock)
    else:
        sock.default_value = v


def math(t, op: str, a, b=0.0, c=0.0):
    n = t.nodes.new("ShaderNodeMath")
    n.operation = op
    for sock, v in zip(n.inputs, (a, b, c)):
        feed(t, sock, v)
    return n.outputs[0]


def add(t, a, b):
    return math(t, "ADD", a, b)


def sub(t, a, b):
    return math(t, "SUBTRACT", a, b)


def mul(t, a, b):
    return math(t, "MULTIPLY", a, b)


def xyz(t, x=0.0, y=0.0, z=0.0):
    n = t.nodes.new("ShaderNodeCombineXYZ")
    for sock, v in zip(n.inputs, (x, y, z)):
        feed(t, sock, v)
    return n.outputs[0]


def split(t, v):
    """(x, y, z) output sockets of a vector socket."""
    n = t.nodes.new("ShaderNodeSeparateXYZ")
    feed(t, n.inputs[0], v)
    return n.outputs[0], n.outputs[1], n.outputs[2]


def gin(t, name: str):
    """Group-input output socket by name."""
    return gn._socket(gn.io(t)[0].outputs, name)


def is_part(t, part: int):
    """Boolean socket: the Part input equals `part`."""
    n = t.nodes.new("FunctionNodeCompare")
    n.data_type = "INT"
    n.operation = "EQUAL"
    feed(t, gn._socket(n.inputs, "A"), gin(t, "Part"))
    gn._socket(n.inputs, "B").default_value = part
    return n.outputs[0]


def switch(t, kind: str, cond, false, true):
    n = t.nodes.new("GeometryNodeSwitch")
    n.input_type = kind
    feed(t, n.inputs[0], cond)
    for sock, v in ((n.inputs[1], false), (n.inputs[2], true)):
        if v is not None:
            feed(t, sock, v)
    return n.outputs[0]


def by_part(t, a, b, loose):
    """Geometry socket chosen by the Part input (0 = A, 1 = B, 2 = Loose). None = empty."""
    n = t.nodes.new("GeometryNodeIndexSwitch")
    n.data_type = "GEOMETRY"
    n.index_switch_items.new()
    feed(t, n.inputs[0], gin(t, "Part"))
    for i, v in enumerate((a, b, loose), 1):
        if v is not None:
            feed(t, n.inputs[i], v)
    return n.outputs[0]


def join(t, *geos):
    n = t.nodes.new("GeometryNodeJoinGeometry")
    for g in reversed(geos):  # multi-input sockets stack newest on top
        t.links.new(g, n.inputs[0])
    return n.outputs[0]


def hull(t, *geos):
    n = t.nodes.new("GeometryNodeConvexHull")
    feed(t, n.inputs[0], join(t, *geos) if len(geos) > 1 else geos[0])
    return n.outputs[0]


def boolean(t, op: str, base, *cutters):
    """Mesh Boolean (EXACT: 5.x's default mangled simple cuts, gn-patterns.md)."""
    n = t.nodes.new("GeometryNodeMeshBoolean")
    n.operation = op
    n.solver = "EXACT"
    m1, m2 = n.inputs[0], n.inputs[1]
    if op == "DIFFERENCE":
        feed(t, m1, base)
        for c in cutters:
            t.links.new(c, m2)
    else:  # UNION / INTERSECT take every operand in Mesh 2
        for g in (base, *cutters):
            t.links.new(g, m2)
    return n.outputs[0]


def transform(t, geo, matrix):
    n = t.nodes.new("GeometryNodeTransform")
    feed(t, n.inputs["Geometry"], geo)
    n.inputs["Mode"].default_value = "Matrix"
    feed(t, n.inputs["Transform"], matrix)
    return n.outputs[0]


def translate(t, geo, offset):
    n = t.nodes.new("GeometryNodeTransform")
    feed(t, n.inputs["Geometry"], geo)
    feed(t, n.inputs["Translation"], offset)
    return n.outputs[0]


def trap_box(t, x0, x1, z0, z1, half, slope=0.0, grow=0.0):
    """Prism with a symmetric trapezoid section in XY: half-width at x is
    half + slope * x + grow * sqrt(1 + slope^2); spans x0..x1 and z0..z1."""
    cube = t.nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (1.0, 1.0, 1.0)
    px, py, pz = split(t, t.nodes.new("GeometryNodeInputPosition").outputs[0])
    x = math(t, "MULTIPLY_ADD", add(t, px, 0.5), sub(t, x1, x0), x0)
    z = math(t, "MULTIPLY_ADD", add(t, pz, 0.5), sub(t, z1, z0), z0)
    sec = math(t, "SQRT", math(t, "MULTIPLY_ADD", slope, slope, 1.0))
    h = math(t, "MULTIPLY_ADD", grow, sec, math(t, "MULTIPLY_ADD", slope, x, half))
    y = mul(t, math(t, "SIGN", py), h)
    sp = t.nodes.new("GeometryNodeSetPosition")
    t.links.new(cube.outputs["Mesh"], sp.inputs["Geometry"])
    t.links.new(xyz(t, x, y, z), sp.inputs["Position"])
    return sp.outputs[0]


def chamfered_trap(t, x0, x1, z0, z1, half, slope, grow, ch):
    """trap_box with its top and bottom edges chamfered 45 deg by ch (flanks and the
    x1 end; x0 is the root, buried in the host)."""
    tall = trap_box(t, x0, x1, add(t, z0, ch), sub(t, z1, ch), half, slope, grow)
    wide = trap_box(t, x0, sub(t, x1, ch), z0, z1, half, slope, sub(t, grow, ch))
    return hull(t, tall, wide)


def flare(t, x0, x1, z_face, half, slope, grow, f, up: bool):
    """45 deg mouth flare of a socket at the face z_face: grow + f at the face, grow at
    depth f inside, ends pushed out by f. up=True for a mouth on a top face."""
    inner = sub(t, z_face, f) if up else add(t, z_face, f)
    outer = add(t, z_face, 1.0) if up else sub(t, z_face, 1.0)
    mz = (z_face, outer) if up else (outer, z_face)
    nz = (inner, z_face) if up else (z_face, inner)
    mouth = trap_box(t, sub(t, x0, f), add(t, x1, f), *mz, half, slope, add(t, grow, f))
    neck = trap_box(t, x0, x1, *nz, half, slope, grow)
    return hull(t, mouth, neck)


def mirror_x(t, convex):
    """Mirror a convex piece across x = 0. Re-hulled: a negative scale flips winding."""
    n = t.nodes.new("GeometryNodeTransform")
    feed(t, n.inputs["Geometry"], convex)
    n.inputs["Scale"].default_value = (-1.0, 1.0, 1.0)
    return hull(t, n.outputs[0])


def joint_inputs(t) -> None:
    """The contract every GN_Joint_* group shares."""
    gn.input(t, "Geometry", "GEOMETRY")
    gn.input(t, "Part", "INT", 0, min=0, max=2,
             description="0 = A (nominal), 1 = B (carries Clearance), 2 = Loose part only")  # fmt: skip
    gn.input(t, "Clearance", "FLOAT", 0.2, min=-0.3, max=1.0, subtype="DISTANCE",
             description="Gap per mating face on B and on sockets; negative = interference")  # fmt: skip
    gn.input(t, "Joint Origin", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION",
             description="Host-local point on the joint face")  # fmt: skip
    gn.input(t, "Joint Rotation", "VECTOR", (0.0, 0.0, 0.0), subtype="EULER",
             description="Joint frame: mating axis +X, up +Z")  # fmt: skip
    gn.input(t, "Joint Chamfer", "FLOAT", 0.4, min=0.0, max=2.0, subtype="DISTANCE",
             description="45 deg chamfer on male edges and flare on socket mouths")  # fmt: skip
    gn.output(t, "Geometry")


def joint_frame(t):
    """(matrix, zmin, zmax): the joint frame and the host's z extent inside it. Joints
    span the host's full height at the joint (a through socket, a key on the top face)."""
    ct = t.nodes.new("FunctionNodeCombineTransform")
    feed(t, ct.inputs["Translation"], gin(t, "Joint Origin"))
    e2r = t.nodes.new("FunctionNodeEulerToRotation")
    feed(t, e2r.inputs[0], gin(t, "Joint Rotation"))
    t.links.new(e2r.outputs[0], ct.inputs["Rotation"])
    inv = t.nodes.new("FunctionNodeInvertMatrix")
    t.links.new(ct.outputs[0], inv.inputs[0])
    local = transform(t, gin(t, "Geometry"), inv.outputs[0])
    bb = t.nodes.new("GeometryNodeBoundBox")
    t.links.new(local, bb.inputs[0])
    zmin = split(t, bb.outputs["Min"])[2]
    zmax = split(t, bb.outputs["Max"])[2]
    return ct.outputs[0], zmin, zmax
