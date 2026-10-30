# step 14: Design review (layout B): center head gets its own lower/narrower muzzle (bridge from the brow), forward nostrils, fangs + tooth row, brow/cheek orbit arches; vision cones angled outward; Side Scale 0.8, necks behind the center ears, right head clear of the right eye (FOV R 65); Center Scale 1.15 (mask <= 200 g); Ref ghost material
"""SDF blob modelling for cerberus-mask: organic forms from Control curves whose per-point
radius is the local thickness (Alt+S in Edit Mode), unioned as one SDF and filleted where
parts meet. Helper module (no NN prefix): the NN builders and live MCP steps import it.

    GN_SDFBlob                 curves (radius = thickness) -> SDF -> fillet/smooth -> mesh
    GN_CerberusMask_Proxy      Ref head-proxy blobs -> HeadProxy mesh
    GN_CerberusMask_Heads      CTL head-part blobs -> center + mirrored side heads + necks

Head-local frame: origin between the pupils, -Y forward (the wearer's view), Z up. The
CTL_Head_* curves and the proxy blobs sit at object location (0, 0, EYE_HEIGHT) so they
overlay the center head; GN_CerberusMask_Heads subtracts Eye Height to get head-local.
"""

import bpy
from kit import control, gn, scene

EYE_HEIGHT = (
    420.0  # mm, pupils above z=0; the proxy's torso (to mid-chest) rests on z=0
)
SNOUT_AUTHORED = 70.0  # mm, snout length the default CTL_Head_Snout curves are drawn at
SNOUT_ROOT_Y = (
    -45.0
)  # mm, face plane where the snout starts (Snout Length is measured from it)
JAW_HINGE = (0.0, 5.0, -35.0)  # head-local, lower-jaw hinge axis (along X)
CRANIUM_C = (0.0, 25.0, 40.0)  # head-local, where a side head's neck starts
# Collar mode: the neck leaves the skull down and back (side-local), toward its shoulder
COLLAR_NECK_DIR = (0.0, 0.287, -0.958)


# --- Control blobs ----------------------------------------------------------------


def _digest(points) -> str:
    """Fingerprint of a blob curve's shape from ((x, y, z), radius) pairs."""
    import hashlib

    h = hashlib.sha1()
    for co, r in points:
        h.update(repr((tuple(round(v, 2) for v in co), round(r, 2))).encode())
    return h.hexdigest()[:12]


def _curve_digest(obj) -> str:
    return _digest(
        (bp.co, bp.radius) for sp in obj.data.splines for bp in sp.bezier_points
    )


def blob(name: str, coll, pts, mirror_x: bool = False, replace: bool = False):
    """A Bezier blob curve through (x, y, z, radius) points, AUTO handles, at the eye
    origin. mirror_x adds the mirrored twin `<name>_R` (and names this one `<name>_L`).

    Control curves are user-owned. Each is stamped with the fingerprint of the default it
    was made from (obj["default_shape"]). While it still matches (untouched), a changed
    default here updates it on the next build; once edited by hand it's kept, with a
    warning when its default has moved on. replace=True always rebuilds from the default."""
    names = [(name + "_L", 1), (name + "_R", -1)] if mirror_x else [(name, 1)]
    out = []
    for n, sx in names:
        default = [((sx * x, y, z), r) for x, y, z, r in pts]
        want = _digest(default)
        obj = bpy.data.objects.get(n)
        rebuild = replace
        if obj is not None and not replace:
            have, stamp = _curve_digest(obj), obj.get("default_shape")
            if stamp is None:  # made before stamping: treat as untouched
                stamp = have
            if have == stamp and have != want:
                rebuild = True
                print(f"blob_geo: {n} updated to its new default")
            elif have != stamp and stamp != want:
                print(
                    f"blob_geo: {n} was edited by hand and its default changed; kept (delete it to take the new one)"
                )
            elif have == want:
                obj["default_shape"] = want
        loc = None
        if obj is not None and rebuild:
            loc = obj.location.copy()
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.curves.remove(data)
            obj = None
        if obj is None:
            obj = control.curve(n, [co for co, _ in default], closed=False, kind="BEZIER",
                                location=(0, 0, EYE_HEIGHT) if loc is None else loc)  # fmt: skip
            for bp, (_, r) in zip(obj.data.splines[0].bezier_points, default):
                bp.radius = r
            obj.data.bevel_depth = 0  # the curve shows as a line; GN draws the volume
            obj["default_shape"] = want
            scene.link(obj, coll)
        out.append(obj)
    return out


EAR_ROOT_Z = 60.0  # head-local, Ear Size scales the ears about this height

# Default head parts (head-local mm, last value = radius). Drawn at Snout Length 70.
# Dog skull: long braincase with a sagittal crest, brow ridge, flared cheekbones,
# a narrow muzzle with a nasal bridge, solid lower jaw, broad triangular ears.
HEAD = {
    "Cranium": [
        ("CTL_Head_Dome", [(0, -5, 28, 46), (0, 55, 30, 50)], False),
        ("CTL_Head_Crest", [(0, -10, 62, 6), (0, 40, 78, 9), (0, 85, 62, 6)], False),
        (
            "CTL_Head_Brow",
            [(-48, -30, 14, 12), (0, -40, 12, 13), (48, -30, 14, 12)],
            False,
        ),
        (
            "CTL_Head_Cheek",
            [(-58, 10, -8, 12), (-55, -22, -10, 11), (-38, -48, -14, 10)],
            True,
        ),
    ],
    "Snout": [
        (
            # root radius < 27 / Center Scale keeps the wearer's sightline (pupils at x ±31)
            # beside the center muzzle instead of through it
            "CTL_Head_Muzzle",
            [(0, -45, -6, 22), (0, -85, -12, 20), (0, -112, -18, 16)],
            False,
        ),
        (
            "CTL_Head_Bridge",
            [(0, -38, 10, 14), (0, -80, 2, 11), (0, -108, -6, 9)],
            False,
        ),
        ("CTL_Head_Nose", [(0, -116, -10, 10), (0, -121, -12, 9)], False),
        ("CTL_Head_Fang", [(-21, -98, -32, 4.5), (-22, -100, -52, 1.2)], True),
    ],
    "Ears": [  # front edge, fill, back edge meet at the tip: one broad triangle
        (
            "CTL_Head_Ear",
            [(-38, 0, 58, 14), (-50, 10, 118, 9), (-58, 18, 158, 3)],
            True,
        ),
        (
            "CTL_Head_EarFill",
            [(-51, 19, 56, 15), (-55, 19, 117, 10), (-58, 18, 152, 3.5)],
            True,
        ),
        (
            "CTL_Head_EarBack",
            [(-64, 38, 54, 13), (-62, 28, 116, 9), (-58, 18, 158, 3)],
            True,
        ),
    ],
    "Jaw": [  # mandibles from the hinge to the chin, plus a floor so the jaw is solid
        (
            "CTL_Head_Mandible",
            [(-40, 8, -30, 11), (-30, -45, -44, 9), (-12, -92, -50, 7)],
            True,
        ),
        (
            "CTL_Head_Jaw",
            [(0, -20, -40, 14), (0, -60, -45, 11), (0, -88, -49, 8)],
            False,
        ),
        ("CTL_Head_LowFang", [(-17, -82, -46, 3.5), (-18, -84, -30, 1.0)], True),
    ],
    # Cutters (subtracted, not added). "Cuts" = the center head's eye openings for the
    # wearer: cones ~25 mm at the eye, flared forward, toward the temple and down, angled
    # outward so they don't open the muzzle (checked by builders/checks.py).
    # "CutsSide" = the side heads' dark sockets.
    "Cuts": [
        # inner edge stays beyond x -15: closer in, it cuts the hollow bridge apart and
        # the center muzzle comes loose (checks.py: Mask 2 pieces)
        ("CTL_Cut_Socket", [(-42, -95, -4, 22), (-27, -12, 0, 12)], True),
        ("CTL_Cut_SocketOuter", [(-75, -65, 0, 24), (-37, -12, 1, 12)], True),
        ("CTL_Cut_SocketLow", [(-36, -70, -26, 16), (-31, -12, -6, 10)], True),
    ],
    "CutsSide": [
        ("CTL_Cut_SideSocket", [(-36, -50, 4, 12), (-30, -18, 2, 9)], True),
    ],
    "CutsSnout": [  # stretched with the snout
        ("CTL_Cut_Nostril", [(-7, -135, -12, 4), (-6, -110, -14, 3.5)], True),
    ],
    # Center head only (the side skulls keep Snout/CutsSnout). Its muzzle sits lower and
    # narrower so head-on the nose reads below the sockets and the vision cones pass
    # beside it; scaled by Center Scale and stretched with Snout Length like Snout.
    "CenterSnout": [
        (
            "CTL_Center_Muzzle",
            [(0, -55, -24, 15), (0, -90, -28, 16), (0, -118, -31, 13)],
            False,
        ),
        (
            # starts inside the brow ridge (y -42): further back, the face cut (proxy +
            # Face Clear) removes it over the wearer's nose and the muzzle comes loose
            "CTL_Center_Bridge",
            [(0, -42, 10, 12), (0, -75, -12, 9), (0, -110, -22, 8)],
            False,
        ),
        ("CTL_Center_Nose", [(0, -122, -27, 9), (0, -127, -30, 8)], False),
        ("CTL_Center_Fang", [(-13, -105, -40, 4.5), (-14, -107, -58, 1.5)], True),
        (
            "CTL_Center_Teeth",
            [
                (-15, -85, -42, 3),
                (-12, -100, -44, 3),
                (-7, -112, -44, 2.5),
                (0, -116, -44, 2.5),
                (7, -112, -44, 2.5),
                (12, -100, -44, 3),
                (15, -85, -42, 3),
            ],
            False,
        ),
    ],
    "CenterCutsSnout": [  # nostrils of the center muzzle, forward and down
        ("CTL_Center_Nostril", [(-6, -142, -34, 4), (-5, -118, -28, 3.5)], True),
    ],
    # Bone frame around the center's eye openings (unscaled, like the cutters: it stays on
    # the pupils). Brow arch above; the cheekbone arch only frames the outer-lower corner
    # (x <= -46): under the pupil it would block the downward view (checks.py: 30 deg).
    # Open toward the temple like a real canine orbit, so the outer cone keeps the side view.
    "CenterOrbits": [
        (
            "CTL_Center_BrowArch",
            [(-6, -50, 22, 6), (-24, -58, 27, 7), (-46, -52, 25, 6), (-60, -36, 17, 5)],
            True,
        ),
        (
            "CTL_Center_CheekArch",
            [(-46, -58, -32, 6), (-60, -44, -28, 6), (-72, -22, -16, 6)],
            True,
        ),
    ],
}

# Shoulder yoke the collar-mounted side heads grow from: one closed loop around the neck
# base, over the trapezius and shoulder tips (head-local mm, last value = radius).
COLLAR = [
    (
        "CTL_Collar_Yoke",
        [
            (0, 18, -210, 24),
            (-80, 28, -200, 26),
            (-150, 75, -192, 32),
            (-180, 112, -200, 36),  # shoulder cap: where the neck roots sit
            (-120, 165, -186, 26),
            (0, 182, -182, 22),
            (120, 165, -186, 26),
            (180, 112, -200, 36),
            (150, 75, -192, 32),
            (80, 28, -200, 26),
            (0, 18, -210, 24),
        ],
        False,
    ),
]

PROXY = [  # generic adult bust, head-local mm; head ~165 wide, ~220 long, eye-to-chin ~125
    ("Proxy_Cranium", [(0, 70, 40, 78), (0, 110, 35, 76)], False),
    ("Proxy_Face", [(-18, 42, 0, 50), (-15, 40, -60, 42)], True),
    ("Proxy_Nose", [(0, -4, -8, 7), (0, -24, -40, 11)], False),
    ("Proxy_Jaw", [(-42, 62, -62, 24), (0, 14, -108, 20), (42, 62, -62, 24)], False),
    ("Proxy_Neck", [(0, 90, -100, 52), (0, 92, -230, 60)], False),
    ("Proxy_Ear", [(-74, 85, 2, 11), (-77, 90, -38, 9)], True),
    # torso to mid-chest: ~400 across the deltoids, ~320 chest, bottom on z=0
    (
        "Proxy_Shoulder",
        [(-30, 95, -235, 70), (-150, 100, -245, 58), (-195, 105, -275, 48)],
        True,
    ),
    ("Proxy_Chest", [(-60, 75, -280, 100), (-60, 85, -318, 100)], True),
]


def head_controls() -> dict:
    """Control/CTL_Head/CTL_Head_<Part> collections with the default blobs (once)."""
    root = scene.collection("CTL_Head", scene.control())
    colls = {}
    for part, blobs in HEAD.items():
        coll = scene.collection(f"CTL_Head_{part}", root)
        for name, pts, mirror in blobs:
            blob(name, coll, pts, mirror)
        colls[part] = coll
    return colls


def proxy_controls():
    """Ref/Ref_HeadProxy blobs (once). Ref is user-owned: created if missing, never cleared."""
    ref = scene.collection(scene.REF)
    coll = scene.collection("Ref_HeadProxy_Blobs", ref)
    for name, pts, mirror in PROXY:
        blob(name, coll, pts, mirror)
    return coll


def collar_controls():
    """Control/CTL_Collar: the shoulder yoke curve (once)."""
    coll = scene.collection("CTL_Collar", scene.control())
    for name, pts, mirror in COLLAR:
        blob(name, coll, pts, mirror)
    return coll


# --- node helpers -------------------------------------------------------------------


def _math(t, op, a=None, b=None, label=""):
    n = gn.node(t, "ShaderNodeMath", label, props={"operation": op})
    for i, v in ((0, a), (1, b)):
        if isinstance(v, tuple):
            gn.link(t, v[0], v[1], n, i)
        elif v is not None:
            n.inputs[i].default_value = v
    return n


def _xyz(t, x=0.0, y=0.0, z=0.0, label=""):
    n = gn.node(t, "ShaderNodeCombineXYZ", label)
    for i, v in enumerate((x, y, z)):
        if isinstance(v, tuple):
            gn.link(t, v[0], v[1], n, i)
        else:
            n.inputs[i].default_value = v
    return n


def _transform(t, geo, translation=None, rotation=None, scale=None, label=""):
    """Transform Geometry; each arg is a constant tuple or a (node, socket) pair."""
    n = gn.node(t, "GeometryNodeTransform", label)
    gn.link(t, geo[0], geo[1], n, "Geometry")
    for key, v in (
        ("Translation", translation),
        ("Rotation", rotation),
        ("Scale", scale),
    ):
        if v is None:
            continue
        if isinstance(v[0], bpy.types.Node):
            gn.link(t, v[0], v[1], n, key)
        else:
            n.inputs[key].default_value = v
    return n


def _scale_radius(t, geo, factor):
    """Multiply curve radius by factor (a (node, socket) pair): Transform leaves it alone."""
    rad = gn.node(t, "GeometryNodeInputRadius")
    mul = _math(t, "MULTIPLY", (rad, 0), factor)
    n = gn.node(t, "GeometryNodeSetCurveRadius")
    gn.link(t, geo[0], geo[1], n, "Curve")
    gn.link(t, mul, 0, n, "Radius")
    return n


def _collection(t, coll, label):
    ci = gn.node(
        t, "GeometryNodeCollectionInfo", label, props={"transform_space": "ORIGINAL"}
    )
    ci.inputs["Collection"].default_value = coll
    real = gn.node(t, "GeometryNodeRealizeInstances")
    gn.link(t, ci, "Instances", real, "Geometry")
    return real


def _join(t, *geos):
    j = gn.node(t, "GeometryNodeJoinGeometry")
    for g in geos:
        gn.link(t, g[0], g[1], j, "Geometry")
    return j


def _tag(t, geo, name, label=""):
    """Store a True boolean point attribute `name` (Join fills it False elsewhere)."""
    n = gn.node(t, "GeometryNodeStoreNamedAttribute", label or f"tag: {name}",
                props={"data_type": "BOOLEAN", "domain": "POINT"}, Name=name, Value=True)  # fmt: skip
    gn.link(t, geo[0], geo[1], n, "Geometry")
    return n


def _separate(t, geo, name):
    """Split geometry by boolean point attribute `name`: outputs Selection / Inverted."""
    attr = gn.node(
        t, "GeometryNodeInputNamedAttribute", props={"data_type": "BOOLEAN"}, Name=name
    )
    sep = gn.node(
        t, "GeometryNodeSeparateGeometry", f"split: {name}", props={"domain": "POINT"}
    )
    gn.link(t, geo[0], geo[1], sep, "Geometry")
    gn.link(t, attr, "Attribute", sep, "Selection")
    return sep


def _sdf(t, geo, gin):
    """Closed mesh -> SDF grid at the tree's Voxel Size (6-voxel band)."""
    n = gn.node(t, "GeometryNodeMeshToSDFGrid", Band_Width=6)
    gn.link(t, geo[0], geo[1], n, "Mesh")
    gn.link(t, gin, "Voxel Size", n, "Voxel Size")
    return n


# --- groups ------------------------------------------------------------------------


def blob_group() -> bpy.types.GeometryNodeTree:
    """GN_SDFBlob: curves (radius = thickness) -> points -> SDF -> fillet -> smooth -> mesh."""
    t = gn.tree("GN_SDFBlob")
    if gn.current(t, __file__):
        return t
    t = gn.tree("GN_SDFBlob", reset=True)  # keeps the interface: users stay linked
    gn.input(t, "Geometry", "GEOMETRY")
    gn.input(
        t,
        "Voxel Size",
        "FLOAT",
        2.0,
        min=0.5,
        max=10.0,
        description="SDF resolution, mm",
    )
    gn.input(
        t,
        "Fillet",
        "INT",
        4,
        min=0,
        max=40,
        description="Fillet iterations: fills creases where blobs meet",
    )
    gn.input(t, "Smooth", "INT", 1, min=0, max=10, description="Mean-filter iterations")
    gn.output(t, "Geometry")
    gin, gout = gn.io(t)
    with gn.stage(t, "1 · Curves to radius points"):
        step = _math(
            t, "MULTIPLY", (gin, "Voxel Size"), 0.5, "point spacing = voxel / 2"
        )
        pts = gn.node(t, "GeometryNodeCurveToPoints", props={"mode": "LENGTH"})
        gn.link(t, gin, "Geometry", pts, "Curve")
        gn.link(t, step, 0, pts, "Length")
        rad = gn.node(
            t,
            "GeometryNodeInputNamedAttribute",
            props={"data_type": "FLOAT"},
            Name="radius",
        )
    with gn.stage(t, "2 · SDF union, re-banded, fillet, smooth"):
        sdf = gn.node(t, "GeometryNodePointsToSDFGrid")
        gn.link(t, pts, "Points", sdf, "Points")
        gn.link(t, rad, "Attribute", sdf, "Radius")
        gn.link(t, gin, "Voxel Size", sdf, "Voxel Size")
        # Points to SDF leaves a narrow band too thin for Fillet/Mean (they tear holes:
        # 8.9k non-manifold edges on the proxy). Meshing and re-voxelising rebuilds it.
        raw = gn.node(t, "GeometryNodeGridToMesh")
        gn.link(t, sdf, "SDF Grid", raw, "Grid")
        band = gn.node(t, "GeometryNodeMeshToSDFGrid", Band_Width=6)
        gn.link(t, raw, "Mesh", band, "Mesh")
        gn.link(t, gin, "Voxel Size", band, "Voxel Size")
        fil = gn.node(t, "GeometryNodeSDFGridFillet")
        gn.link(t, band, "SDF Grid", fil, "Grid")
        gn.link(t, gin, "Fillet", fil, "Iterations")
        mean = gn.node(t, "GeometryNodeSDFGridMean", Width=1)
        gn.link(t, fil, "Grid", mean, "Grid")
        gn.link(t, gin, "Smooth", mean, "Iterations")
    with gn.stage(t, "3 · Mesh"):
        mesh = gn.node(t, "GeometryNodeGridToMesh")
        gn.link(t, mean, "Grid", mesh, "Grid")
        smooth = gn.node(t, "GeometryNodeSetShadeSmooth")
        gn.link(t, mesh, "Mesh", smooth, "Geometry")
        gn.link(t, smooth, "Geometry", gout, "Geometry")
    gn.arrange(t)
    gn.stamp(t, __file__)
    return t


def _blob_node(t, geo, gin=None):
    g = gn.node(t, "GeometryNodeGroup")
    g.node_tree = blob_group()
    gn.link(t, geo[0], geo[1], g, "Geometry")
    if gin is not None:
        for k in ("Voxel Size", "Fillet", "Smooth"):
            gn.link(t, gin, k, g, k)
    return g


def proxy_group(coll) -> bpy.types.GeometryNodeTree:
    t = gn.tree("GN_CerberusMask_Proxy", reset=True)
    gn.output(t, "Geometry")
    _, gout = gn.io(t)
    with gn.stage(t, "1 · Proxy blobs"):
        src = _collection(t, coll, "Ref_HeadProxy_Blobs")
        g = _blob_node(t, (src, "Geometry"))
        g.inputs["Voxel Size"].default_value = 3.0
        g.inputs["Fillet"].default_value = 8
        g.inputs["Smooth"].default_value = 2
        gn.link(t, g, "Geometry", gout, "Geometry")
    gn.arrange(t)
    return t


def rig_group(colls: dict) -> bpy.types.GeometryNodeTree:
    """GN_CerberusMask_Rig: CTL_Head_* parts -> posed blob curves in world space (center
    head, side heads on necks, yoke, cutters). Cheap: curves only. Points carry tags the
    part groups split on: `center` (the face mask), `cut` (subtract), `vision` (the
    center's eye openings, which also shape the visor)."""
    t = gn.tree("GN_CerberusMask_Rig", reset=True)
    I = lambda *a, **k: gn.input(t, *a, **k)
    I(
        "Eye Height",
        "FLOAT",
        EYE_HEIGHT,
        min=0,
        description="Pupils above z=0; where the CTL_Head curves sit",
    )
    I(
        "Full Mask",
        "BOOL",
        False,
        description="Center head gets its lower jaw (and later the collar)",
    )
    I(
        "Snout Length",
        "FLOAT",
        SNOUT_AUTHORED,
        min=20,
        max=160,
        description="Nose tip forward of the face plane, mm",
    )
    I(
        "Jaw Open",
        "FLOAT",
        12.0,
        min=0,
        max=45,
        description="Lower-jaw opening, degrees",
    )
    I("Ear Size", "FLOAT", 1.0, min=0, max=2)
    I(
        "Side Yaw",
        "FLOAT",
        15.0,
        min=-30,
        max=80,
        description="Side snouts swing forward from straight out, degrees",
    )
    I(
        "Side Spread",
        "FLOAT",
        176.0,
        min=80,
        max=400,
        description="Distance between the temple anchors, mm",
    )
    I(
        "Side Back",
        "FLOAT",
        30.0,
        min=-60,
        max=120,
        description="Side heads behind the eye plane, mm",
    )
    I(
        "Side Drop",
        "FLOAT",
        10.0,
        min=-80,
        max=120,
        description="Side heads below the eye line, mm",
    )
    I("Side Scale", "FLOAT", 0.8, min=0.3, max=1.5)
    I(
        "Cranium Scale",
        "FLOAT",
        1.0,
        min=0.4,
        max=1.5,
        description="Thickness of dome, brow and cheeks: the mask's bulk",
    )
    for s in ("Left", "Right"):
        I(
            f"{s} Pitch",
            "FLOAT",
            0.0,
            min=-60,
            max=60,
            description=f"{s} head snout up (+) or down (-) about its neck root, degrees",
        )
        I(
            f"{s} Tilt",
            "FLOAT",
            0.0,
            min=-45,
            max=45,
            description=f"{s} head cocked: top leans forward (+) or back (-), degrees",
        )
    I(
        "Right Yaw Offset",
        "FLOAT",
        0.0,
        min=-60,
        max=60,
        description="Added to Side Yaw for the right head, degrees",
    )
    I(
        "Right Drop Offset",
        "FLOAT",
        0.0,
        min=-100,
        max=100,
        description="Added to Side Drop for the right head, mm",
    )
    I(
        "Right Back Offset",
        "FLOAT",
        0.0,
        min=-80,
        max=80,
        description="Added to Side Back for the right head, mm",
    )
    I(
        "Neck Extrude",
        "FLOAT",
        20.0,
        min=0,
        max=200,
        description="Side head pushed out from its temple anchor on a neck, mm",
    )
    I("Neck Radius", "FLOAT", 38.0, min=5, max=80)
    I(
        "Neck Curve",
        "FLOAT",
        0.0,
        min=-150,
        max=150,
        description="Neck bow, mm: collar necks arch forward (+), temple necks bow up (+)",
    )
    I(
        "Neck Taper",
        "FLOAT",
        0.0,
        min=0,
        max=1.5,
        description="Neck thicker at the root than at the skull: 0 = even, 1 = root 3x the skull end",
    )
    I(
        "Side From Collar",
        "BOOL",
        False,
        description="Side heads rise on necks from the CTL_Collar shoulder yoke instead of the temples",
    )
    I(
        "Shoulder Width",
        "FLOAT",
        330.0,
        min=150,
        max=520,
        description="Collar mode: distance between the two neck roots, mm",
    )
    I(
        "Shoulder Drop",
        "FLOAT",
        205.0,
        min=100,
        max=350,
        description="Collar mode: neck roots below the eye line, mm",
    )
    I(
        "Shoulder Forward",
        "FLOAT",
        105.0,
        min=-50,
        max=200,
        description="Collar mode: neck roots behind the eye plane (+Y), mm",
    )
    I(
        "Center Scale",
        "FLOAT",
        1.0,
        min=0.6,
        max=1.6,
        description="Center head size about the pupils (its eye openings stay put)",
    )
    gn.output(t, "Geometry")
    gin, gout = gn.io(t)
    neg_eye = _math(t, "MULTIPLY", (gin, "Eye Height"), -1.0)
    to_local = _xyz(t, z=(neg_eye, 0))

    def part(name):
        src = _collection(t, colls[name], f"CTL_Head_{name}")
        return _transform(
            t,
            (src, "Geometry"),
            translation=(to_local, 0),
            label=f"{name} → head-local",
        )

    with gn.stage(t, "1 · Head parts (head-local)"):
        cranium = _scale_radius(
            t, (part("Cranium"), "Geometry"), (gin, "Cranium Scale")
        )
        # Snout: stretch along Y about the face plane so the tip lands at Snout Length
        sy = _math(t, "DIVIDE", (gin, "Snout Length"), SNOUT_AUTHORED, "snout stretch")
        stretch = _xyz(t, 1.0, (sy, 0), 1.0)

        def stretched(geo, label):
            a = _transform(t, geo, translation=(0, -SNOUT_ROOT_Y, 0))
            b = _transform(t, (a, "Geometry"), scale=(stretch, 0))
            return _transform(
                t, (b, "Geometry"), translation=(0, SNOUT_ROOT_Y, 0), label=label
            )

        snout = stretched((part("Snout"), "Geometry"), "snout stretched")
        # Cutters ride along with their head, tagged so stage 4 subtracts them:
        # vision openings on the center head, small dark sockets on the side heads
        socket_cuts = _tag(
            t, (part("Cuts"), "Geometry"), "cut", label="tag: vision cuts (center)"
        )
        socket_cuts = _tag(t, (socket_cuts, "Geometry"), "vision", label="tag: vision")
        nostril_cuts = _tag(t, (stretched((part("CutsSnout"), "Geometry"), "nostrils stretched"), "Geometry"), "cut",
                            label="tag: nostril cuts")  # fmt: skip
        side_sockets = _tag(
            t, (part("CutsSide"), "Geometry"), "cut", label="tag: side sockets"
        )
        cuts = _join(t, (side_sockets, "Geometry"), (nostril_cuts, "Geometry"))
        ears = _scale_radius(t, (part("Ears"), "Geometry"), (gin, "Ear Size"))
        # Ear Size also scales ear length about the ear roots
        e1 = _transform(t, (ears, "Curve"), translation=(0, 0, -EAR_ROOT_Z))
        es = _xyz(t, (gin, "Ear Size"), (gin, "Ear Size"), (gin, "Ear Size"))
        e2 = _transform(t, (e1, "Geometry"), scale=(es, 0))
        ears = _transform(
            t, (e2, "Geometry"), translation=(0, 0, EAR_ROOT_Z), label="ears sized"
        )
        # Jaw: rotate about the hinge axis (X) by Jaw Open
        jaw = part("Jaw")
        j1 = _transform(t, (jaw, "Geometry"), translation=tuple(-v for v in JAW_HINGE))
        ang = _math(t, "RADIANS", (gin, "Jaw Open"))
        rot = gn.node(t, "FunctionNodeEulerToRotation")
        gn.link(t, _xyz(t, (ang, 0)), 0, rot, "Euler")
        j2 = _transform(t, (j1, "Geometry"), rotation=(rot, "Rotation"))
        jaw = _transform(t, (j2, "Geometry"), translation=JAW_HINGE, label="jaw open")
    with gn.stage(t, "2 · Center head (the face mask) + collar yoke"):
        cjaw = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
        gn.link(t, gin, "Full Mask", cjaw, "Switch")
        gn.link(t, jaw, "Geometry", cjaw, "True")
        yoke = gn.node(t, "GeometryNodeSwitch", props={"input_type": "GEOMETRY"})
        gn.link(t, gin, "Side From Collar", yoke, "Switch")
        gn.link(t, part("Collar"), "Geometry", yoke, "True")
        center_snout = stretched(
            (part("CenterSnout"), "Geometry"), "center snout stretched"
        )
        center_nostrils = _tag(t, (stretched((part("CenterCutsSnout"), "Geometry"), "center nostrils stretched"),
                                   "Geometry"), "cut", label="tag: center nostril cuts")  # fmt: skip
        body = _join(t, (cranium, "Curve"), (center_snout, "Geometry"), (ears, "Geometry"), (cjaw, "Output"),
                     (center_nostrils, "Geometry"))  # fmt: skip
        cs = _xyz(
            t, (gin, "Center Scale"), (gin, "Center Scale"), (gin, "Center Scale")
        )
        body = _scale_radius(
            t,
            (_transform(t, (body, "Geometry"), scale=(cs, 0)), "Geometry"),
            (gin, "Center Scale"),
        )
        # its eye-socket cutters stay unscaled: the openings sit on the wearer's pupils
        center = _tag(
            t,
            (
                _join(
                    t,
                    (body, "Curve"),
                    (socket_cuts, "Geometry"),
                    (part("CenterOrbits"), "Geometry"),
                ),
                "Geometry",
            ),
            "center",
            label="tag: center",
        )
    with gn.stage(t, "3 · Side heads on necks (temple or collar): own pose each"):
        inv = _math(t, "DIVIDE", 1.0, (gin, "Side Scale"))
        length = _math(
            t, "ADD", (gin, "Neck Extrude"), 30.0, "neck overlaps its anchor by 30 mm"
        )
        llocal = _math(t, "MULTIPLY", (length, 0), (inv, 0), "neck length, side-local")
        nr = _math(
            t, "MULTIPLY", (gin, "Neck Radius"), (inv, 0), "neck radius, side-local"
        )
        sc = _xyz(t, (gin, "Side Scale"), (gin, "Side Scale"), (gin, "Side Scale"))
        half = _math(t, "MULTIPLY", (gin, "Side Spread"), 0.5)
        out_x = _math(t, "ADD", (half, 0), (gin, "Neck Extrude"), "temple anchor |x|")
        shoulder_x = _math(
            t, "MULTIPLY", (gin, "Shoulder Width"), 0.5, "shoulder anchor |x|"
        )

        def side_head(direction, bow, label):
            """Side-local head (snout -Y) with a neck from the skull along `direction`,
            bowed along `bow` by Neck Curve and tapered (thick at the root) by Neck Taper;
            returns (geometry, neck root, -neck root)."""
            comps = [(_math(t, "MULTIPLY_ADD", (llocal, 0), d), 0) for d in direction]
            for (n, _), c in zip(comps, CRANIUM_C):
                n.inputs[2].default_value = c
            pivot = _xyz(t, *comps, label=f"{label} neck root")
            # middle control point = midpoint + bow * Neck Curve (side-local mm)
            bow_mm = _math(t, "MULTIPLY", (gin, "Neck Curve"), (inv, 0))
            mids = [(_math(t, "MULTIPLY_ADD", (bow_mm, 0), b), 0) for b in bow]
            for (n, _), c, d in zip(mids, CRANIUM_C, direction):
                n.inputs[2].default_value = 0.0
                half_len = _math(t, "MULTIPLY_ADD", (llocal, 0), d * 0.5)
                half_len.inputs[2].default_value = c
                gn.link(t, half_len, 0, n, 2)
            middle = _xyz(t, *mids, label=f"{label} neck bow")
            line = gn.node(
                t, "GeometryNodeCurveQuadraticBezier", Resolution=16, Start=CRANIUM_C
            )
            gn.link(t, middle, 0, line, "Middle")
            gn.link(t, pivot, 0, line, "End")
            # radius = Neck Radius * (1 + Taper * (factor - 0.5)): factor 0 at the skull, 1 at the root
            fac = gn.node(t, "GeometryNodeSplineParameter")
            centred = _math(t, "SUBTRACT", (fac, "Factor"), 0.5)
            k = _math(t, "MULTIPLY_ADD", (centred, 0), (gin, "Neck Taper"))
            k.inputs[2].default_value = 1.0
            rad = _math(
                t, "MULTIPLY", (k, 0), (nr, 0), f"{label} neck radius (tapered)"
            )
            neck = gn.node(t, "GeometryNodeSetCurveRadius")
            gn.link(t, line, "Curve", neck, "Curve")
            gn.link(t, rad, 0, neck, "Radius")
            geo = _join(
                t,
                (cranium, "Curve"),
                (snout, "Geometry"),
                (ears, "Geometry"),
                (jaw, "Geometry"),
                (neck, "Curve"),
                (cuts, "Geometry"),
            )
            geo = _scale_radius(t, (geo, "Geometry"), (gin, "Side Scale"))
            neg = gn.node(t, "ShaderNodeVectorMath", props={"operation": "SCALE"})
            gn.link(t, pivot, 0, neg, 0)
            neg.inputs["Scale"].default_value = -1.0
            return geo, pivot, neg

        heads = {  # temple necks bow up; collar necks arch forward (swan neck)
            False: side_head((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), "temple"),
            True: side_head(COLLAR_NECK_DIR, (0.0, -1.0, 0.0), "collar"),
        }

        def place(sgn: int, name: str, collar: bool):
            """Mirror for the right, pose about the neck root, yaw out to its side, then
            move to the temple anchor or put the neck root on the shoulder anchor."""
            side, pivot, neg_pivot = heads[collar]
            mode = "collar" if collar else "temple"
            geo = (side, "Curve")
            if sgn > 0:
                geo = (
                    _transform(t, geo, scale=(-1.0, 1.0, 1.0), label="right: mirror"),
                    "Geometry",
                )
            a = _transform(t, geo, translation=(neg_pivot, 0))
            # Euler X = -pitch (snout up for +), Y = tilt (sign flipped for the mirrored right)
            pitch = _math(
                t, "RADIANS", (_math(t, "MULTIPLY", (gin, f"{name} Pitch"), -1.0), 0)
            )
            tilt = _math(
                t,
                "RADIANS",
                (_math(t, "MULTIPLY", (gin, f"{name} Tilt"), float(-sgn)), 0),
            )
            pose = gn.node(t, "FunctionNodeEulerToRotation")
            gn.link(t, _xyz(t, (pitch, 0), (tilt, 0), 0.0), 0, pose, "Euler")
            c = _transform(
                t,
                (a, "Geometry"),
                rotation=(pose, "Rotation"),
                label=f"{name.lower()} {mode}: pitch, tilt",
            )
            if not collar:  # temple mode keeps its original anchoring (skull-relative)
                c = _transform(t, (c, "Geometry"), translation=(pivot, 0))
            yaw_deg = (gin, "Side Yaw")
            if sgn > 0:
                yaw_deg = (
                    _math(t, "ADD", (gin, "Side Yaw"), (gin, "Right Yaw Offset")),
                    0,
                )
            # snout (-Y) swings out to sgn·X, then forward by yaw: rotate Z by sgn·(90 - yaw)
            z = _math(
                t, "MULTIPLY", (_math(t, "SUBTRACT", 90.0, yaw_deg), 0), float(sgn)
            )
            yrot = gn.node(t, "FunctionNodeEulerToRotation")
            gn.link(
                t, _xyz(t, 0.0, 0.0, (_math(t, "RADIANS", (z, 0)), 0)), 0, yrot, "Euler"
            )
            d = _transform(
                t,
                (c, "Geometry"),
                rotation=(yrot, "Rotation"),
                scale=(sc, 0),
                label=f"{name.lower()} {mode}: yaw, scale",
            )
            if collar:
                x = _math(t, "MULTIPLY", (shoulder_x, 0), float(sgn))
                back, drop = (gin, "Shoulder Forward"), (gin, "Shoulder Drop")
            else:
                x = _math(t, "MULTIPLY", (out_x, 0), float(sgn))
                back, drop = (gin, "Side Back"), (gin, "Side Drop")
            if sgn > 0:
                back = (_math(t, "ADD", back, (gin, "Right Back Offset")), 0)
                drop = (_math(t, "ADD", drop, (gin, "Right Drop Offset")), 0)
            sz = _math(t, "MULTIPLY", drop, -1.0)
            return _transform(t, (d, "Geometry"), translation=(_xyz(t, (x, 0), back, (sz, 0)), 0),
                              label=f"{name.lower()}: to {mode} anchor")  # fmt: skip

        def either(sgn, name):
            sw = gn.node(
                t,
                "GeometryNodeSwitch",
                f"{name}: temple / collar",
                props={"input_type": "GEOMETRY"},
            )
            gn.link(t, gin, "Side From Collar", sw, "Switch")
            gn.link(t, place(sgn, name, False), "Geometry", sw, "False")
            gn.link(t, place(sgn, name, True), "Geometry", sw, "True")
            return sw

        left, right = either(-1, "Left"), either(1, "Right")
    with gn.stage(t, "4 · World placement"):
        allh = _join(
            t,
            (center, "Geometry"),
            (left, "Output"),
            (right, "Output"),
            (yoke, "Output"),
        )
        world = _transform(
            t, (allh, "Geometry"), translation=(_xyz(t, z=(gin, "Eye Height")), 0)
        )
        gn.link(t, world, "Geometry", gout, "Geometry")
    gn.arrange(t)
    return t


def _rig_input(t, gin):
    """The Rig object's posed, tagged curves (world space; Rig sits at the origin)."""
    rig = gn.node(
        t, "GeometryNodeObjectInfo", "Rig", props={"transform_space": "ORIGINAL"}
    )
    gn.link(t, gin, "Rig", rig, "Object")
    return rig


def _blend_inputs(t):
    gn.input(
        t,
        "Voxel Size",
        "FLOAT",
        2.0,
        min=0.5,
        max=10.0,
        description="SDF resolution, mm",
    )
    gn.input(
        t,
        "Fillet",
        "INT",
        4,
        min=0,
        max=40,
        description="How much the parts melt together",
    )
    gn.input(t, "Smooth", "INT", 1, min=0, max=10)


def _cutter_sdf(t, geo, gin):
    """Cutter curves -> SDF (no fillet: cuts keep their shape)."""
    m = _blob_node(t, geo)
    gn.link(t, gin, "Voxel Size", m, "Voxel Size")
    m.inputs["Fillet"].default_value = 0
    m.inputs["Smooth"].default_value = 0
    return _sdf(t, (m, "Geometry"), gin)


def _drop_fragments(t, mesh):
    """Delete mesh islands under 25% of the biggest one's area (unprintable loose bits)."""
    island = gn.node(t, "GeometryNodeInputMeshIsland")
    area = gn.node(t, "GeometryNodeInputMeshFaceArea")
    acc = gn.node(
        t,
        "GeometryNodeAccumulateField",
        "area per piece",
        props={"data_type": "FLOAT", "domain": "FACE"},
    )
    gn.link(t, area, "Area", acc, "Value")
    gn.link(t, island, "Island Index", acc, "Group ID")
    stat = gn.node(
        t,
        "GeometryNodeAttributeStatistic",
        props={"data_type": "FLOAT", "domain": "FACE"},
    )
    gn.link(t, mesh[0], mesh[1], stat, "Geometry")
    gn.link(t, acc, "Total", stat, "Attribute")
    quarter = _math(t, "MULTIPLY", (stat, "Max"), 0.25)
    small = gn.node(
        t, "FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "LESS_THAN"}
    )
    gn.link(t, acc, "Total", small, "A")
    gn.link(t, quarter, 0, small, "B")
    drop = gn.node(
        t,
        "GeometryNodeDeleteGeometry",
        "drop loose fragments",
        props={"domain": "FACE"},
    )
    gn.link(t, mesh[0], mesh[1], drop, "Geometry")
    gn.link(t, small, "Result", drop, "Selection")
    return drop


def _smooth_out(t, geo, gout):
    s = gn.node(t, "GeometryNodeSetShadeSmooth")
    gn.link(t, geo[0], geo[1], s, "Geometry")
    gn.link(t, s, "Geometry", gout, "Geometry")


def mask_group() -> bpy.types.GeometryNodeTree:
    """GN_CerberusMask_Mask: the center head as a wearable shell around the face proxy."""
    t = gn.tree("GN_CerberusMask_Mask", reset=True)
    gn.input(t, "Rig", "OBJECT", description="Rig object (GN_CerberusMask_Rig)")
    gn.input(
        t, "Face Proxy", "OBJECT", description="Head proxy the mask is hollowed around"
    )
    gn.input(t, "Eye Height", "FLOAT", EYE_HEIGHT, min=0)
    gn.input(
        t,
        "Face Clear",
        "FLOAT",
        6.0,
        min=0,
        max=30,
        description="Gap from the face proxy to the mask's inside (foam + air), mm",
    )
    gn.input(
        t, "Wall", "FLOAT", 2.4, min=0.8, max=10, description="Mask shell thickness, mm"
    )
    gn.input(
        t,
        "Mask Back",
        "FLOAT",
        40.0,
        min=-40,
        max=150,
        description="Mask is clipped behind this plane (head-local Y, mm)",
    )
    _blend_inputs(t)
    gn.output(t, "Geometry")
    gn.prune(t)
    gin, gout = gn.io(t)
    with gn.stage(t, "1 · Center head from the rig: body / cutters"):
        center = _separate(t, (_rig_input(t, gin), "Geometry"), "center")
        cut = _separate(t, (center, "Selection"), "cut")
        cut_sdf = _cutter_sdf(t, (cut, "Selection"), gin)
        mask_sdf = _sdf(t, (_blob_node(t, (cut, "Inverted"), gin), "Geometry"), gin)
    with gn.stage(
        t,
        "2 · Shell: minus inside (Wall), face (+Face Clear), behind Mask Back, cutters",
    ):
        neg_wall = _math(t, "MULTIPLY", (gin, "Wall"), -1.0)
        inner = gn.node(t, "GeometryNodeSDFGridOffset", "mask inside")
        gn.link(t, mask_sdf, "SDF Grid", inner, "Grid")
        gn.link(t, neg_wall, 0, inner, "Distance")
        proxy = gn.node(
            t,
            "GeometryNodeObjectInfo",
            "Face Proxy",
            props={"transform_space": "ORIGINAL"},
        )
        gn.link(t, gin, "Face Proxy", proxy, "Object")
        face = gn.node(t, "GeometryNodeSDFGridOffset", "face + clearance")
        gn.link(t, _sdf(t, (proxy, "Geometry"), gin), "SDF Grid", face, "Grid")
        gn.link(t, gin, "Face Clear", face, "Distance")
        box = gn.node(
            t, "GeometryNodeMeshCube", "behind Mask Back", Size=(1000.0, 600.0, 1000.0)
        )
        by = _math(t, "ADD", (gin, "Mask Back"), 300.0)
        back = _transform(
            t,
            (box, "Mesh"),
            translation=(_xyz(t, 0.0, (by, 0), (gin, "Eye Height")), 0),
        )
        shell = gn.node(
            t,
            "GeometryNodeSDFGridBoolean",
            "mask shell",
            props={"operation": "DIFFERENCE"},
        )
        gn.link(t, mask_sdf, "SDF Grid", shell, "Grid 1")
        for g, s in (
            (cut_sdf, "SDF Grid"),
            (_sdf(t, (back, "Geometry"), gin), "SDF Grid"),
            (face, "Grid"),
            (inner, "Grid"),
        ):
            gn.link(t, g, s, shell, "Grid 2")
    with gn.stage(t, "3 · Mesh; drop loose fragments (< 25% of the biggest piece)"):
        mesh = gn.node(t, "GeometryNodeGridToMesh")
        gn.link(t, shell, "Grid", mesh, "Grid")
        _smooth_out(t, (_drop_fragments(t, (mesh, "Mesh")), "Geometry"), gout)
    gn.arrange(t)
    return t


def body_group() -> bpy.types.GeometryNodeTree:
    """GN_CerberusMask_Body: side heads, necks and yoke, minus their sockets/nostrils."""
    t = gn.tree("GN_CerberusMask_Body", reset=True)
    gn.input(t, "Rig", "OBJECT", description="Rig object (GN_CerberusMask_Rig)")
    _blend_inputs(t)
    gn.output(t, "Geometry")
    gn.prune(t)
    gin, gout = gn.io(t)
    with gn.stage(t, "1 · Side heads + yoke from the rig: body / cutters"):
        side = _separate(t, (_rig_input(t, gin), "Geometry"), "center")
        cut = _separate(t, (side, "Inverted"), "cut")
        body = gn.node(
            t,
            "GeometryNodeSDFGridBoolean",
            "body minus cutters",
            props={"operation": "DIFFERENCE"},
        )
        gn.link(
            t,
            _sdf(t, (_blob_node(t, (cut, "Inverted"), gin), "Geometry"), gin),
            "SDF Grid",
            body,
            "Grid 1",
        )
        gn.link(t, _cutter_sdf(t, (cut, "Selection"), gin), "SDF Grid", body, "Grid 2")
    with gn.stage(t, "2 · Mesh; drop loose fragments (fang tips thinner than a voxel)"):
        mesh = gn.node(t, "GeometryNodeGridToMesh")
        gn.link(t, body, "Grid", mesh, "Grid")
        _smooth_out(t, (_drop_fragments(t, (mesh, "Mesh")), "Geometry"), gout)
    gn.arrange(t)
    return t


def visor_group() -> bpy.types.GeometryNodeTree:
    """GN_CerberusMask_Visor: eye grille insert glued inside the mask behind the openings."""
    t = gn.tree("GN_CerberusMask_Visor", reset=True)
    gn.input(t, "Rig", "OBJECT", description="Rig object (GN_CerberusMask_Rig)")
    gn.input(
        t, "Face Proxy", "OBJECT", description="Head proxy the mask is hollowed around"
    )
    gn.input(t, "Eye Height", "FLOAT", EYE_HEIGHT, min=0)
    gn.input(t, "Face Clear", "FLOAT", 6.0, min=0, max=30)
    gn.input(
        t,
        "Visor Thick",
        "FLOAT",
        1.2,
        min=0.6,
        max=3.0,
        description="Plate thickness, mm (sits flush on the mask's inside)",
    )
    gn.input(
        t,
        "Visor Margin",
        "FLOAT",
        8.0,
        min=2.0,
        max=20.0,
        description="Overlap past the eye openings for gluing, mm",
    )
    gn.input(
        t,
        "Grille Hole",
        "FLOAT",
        3.0,
        min=1.0,
        max=8.0,
        description="Grille hole diameter, mm",
    )
    gn.input(
        t,
        "Grille Bar",
        "FLOAT",
        0.9,
        min=0.4,
        max=3.0,
        description="Grille bar width between holes, mm",
    )
    gn.input(
        t,
        "Visor Voxel",
        "FLOAT",
        0.5,
        min=0.2,
        max=2.0,
        description="SDF resolution of the visor, mm",
    )
    gn.output(t, "Geometry")
    gn.prune(t)
    gin, gout = gn.io(t)
    vv = (gin, "Visor Voxel")

    def fine_sdf(
        geo,
    ):  # band 24 voxels: Face Clear / Visor Margin offsets must stay inside it
        n = gn.node(t, "GeometryNodeMeshToSDFGrid", Band_Width=24)
        gn.link(t, geo[0], geo[1], n, "Mesh")
        gn.link(t, *vv, n, "Voxel Size")
        return n

    with gn.stage(
        t, "1 · Plate: face proxy (eye region) + Face Clear, Visor Thick inward"
    ):
        eye = _xyz(t, 0.0, -10.0, (gin, "Eye Height"))
        clip = gn.node(
            t, "GeometryNodeMeshCube", "eye region", Size=(200.0, 120.0, 90.0)
        )
        clip_box = _transform(t, (clip, "Mesh"), translation=(eye, 0))
        proxy = gn.node(
            t,
            "GeometryNodeObjectInfo",
            "Face Proxy",
            props={"transform_space": "ORIGINAL"},
        )
        gn.link(t, gin, "Face Proxy", proxy, "Object")
        near_face = gn.node(t, "GeometryNodeMeshBoolean", "face proxy, eye region only",
                            props={"operation": "INTERSECT", "solver": "MANIFOLD"})  # fmt: skip
        gn.link(t, proxy, "Geometry", near_face, "Mesh 2")
        gn.link(t, clip_box, "Geometry", near_face, "Mesh 2")
        face_f = fine_sdf((near_face, "Mesh"))
        outer = gn.node(t, "GeometryNodeSDFGridOffset", "visor outside = mask inside")
        gn.link(t, face_f, "SDF Grid", outer, "Grid")
        gn.link(t, gin, "Face Clear", outer, "Distance")
        inner_v = gn.node(t, "GeometryNodeSDFGridOffset", "visor inside")
        gn.link(t, face_f, "SDF Grid", inner_v, "Grid")
        gn.link(
            t,
            _math(t, "SUBTRACT", (gin, "Face Clear"), (gin, "Visor Thick")),
            0,
            inner_v,
            "Distance",
        )
        plate = gn.node(
            t,
            "GeometryNodeSDFGridBoolean",
            "visor plate",
            props={"operation": "DIFFERENCE"},
        )
        gn.link(t, outer, "Grid", plate, "Grid 1")
        gn.link(t, inner_v, "Grid", plate, "Grid 2")
    with gn.stage(t, "2 · Region: the center's vision cutters grown by Visor Margin"):
        vision = _separate(t, (_rig_input(t, gin), "Geometry"), "vision")
        region_mesh = _blob_node(t, (vision, "Selection"))
        gn.link(t, *vv, region_mesh, "Voxel Size")
        region_mesh.inputs["Fillet"].default_value = 0
        region_mesh.inputs["Smooth"].default_value = 0
        region = gn.node(t, "GeometryNodeSDFGridOffset", "openings + margin")
        gn.link(t, fine_sdf((region_mesh, "Geometry")), "SDF Grid", region, "Grid")
        gn.link(t, gin, "Visor Margin", region, "Distance")
    with gn.stage(t, "3 · Trim plate to region (mesh boolean)"):
        # An SDF Intersect here returned ~half the region (565 cm3) instead of the thin
        # plate; both meshes are closed, so Manifold is exact.
        plate_mesh = gn.node(t, "GeometryNodeGridToMesh", "plate mesh")
        gn.link(t, plate, "Grid", plate_mesh, "Grid")
        region_m = gn.node(t, "GeometryNodeGridToMesh", "region mesh")
        gn.link(t, region, "Grid", region_m, "Grid")
        visor_mesh = gn.node(t, "GeometryNodeMeshBoolean", "visor = plate ∩ region",
                             props={"operation": "INTERSECT", "solver": "MANIFOLD"})  # fmt: skip
        gn.link(t, plate_mesh, "Mesh", visor_mesh, "Mesh 2")
        gn.link(t, region_m, "Mesh", visor_mesh, "Mesh 2")
    with gn.stage(t, "4 · Hex grille: staggered point grids in XZ, holes along Y"):
        pitch = _math(t, "ADD", (gin, "Grille Hole"), (gin, "Grille Bar"), "hole pitch")
        row = _math(t, "MULTIPLY", (pitch, 0), 1.7320508, "row pitch (x2 rows)")
        grids = []
        for dx, dz in ((0.0, 0.0), (0.5, 0.8660254)):
            nx = _math(t, "ADD", (_math(t, "DIVIDE", 200.0, (pitch, 0)), 0), 1.0)
            nz = _math(t, "ADD", (_math(t, "DIVIDE", 90.0, (row, 0)), 0), 1.0)
            g = gn.node(t, "GeometryNodeMeshGrid")
            gn.link(t, nx, 0, g, "Vertices X")
            gn.link(t, nz, 0, g, "Vertices Y")
            gn.link(
                t,
                _math(
                    t, "MULTIPLY", (_math(t, "SUBTRACT", (nx, 0), 1.0), 0), (pitch, 0)
                ),
                0,
                g,
                "Size X",
            )
            gn.link(
                t,
                _math(t, "MULTIPLY", (_math(t, "SUBTRACT", (nz, 0), 1.0), 0), (row, 0)),
                0,
                g,
                "Size Y",
            )
            off = _xyz(
                t,
                (_math(t, "MULTIPLY", (pitch, 0), dx), 0),
                (_math(t, "MULTIPLY", (pitch, 0), dz), 0),
                0.0,
            )
            grids.append((_transform(t, (g, "Mesh"), translation=(off, 0)), "Geometry"))
        to_xz = gn.node(t, "FunctionNodeEulerToRotation")
        to_xz.inputs["Euler"].default_value = (1.5707963, 0.0, 0.0)
        pts = _transform(
            t, (_join(t, *grids), "Geometry"), rotation=(to_xz, "Rotation")
        )
        pts = _transform(
            t,
            (pts, "Geometry"),
            translation=(eye, 0),
            label="grille points at the eyes",
        )
        hole = gn.node(
            t, "GeometryNodeMeshCylinder", "grille hole", Vertices=10, Depth=200.0
        )
        gn.link(t, _math(t, "MULTIPLY", (gin, "Grille Hole"), 0.5), 0, hole, "Radius")
        inst = gn.node(t, "GeometryNodeInstanceOnPoints")
        gn.link(t, pts, "Geometry", inst, "Points")
        gn.link(t, hole, "Mesh", inst, "Instance")
        gn.link(t, to_xz, "Rotation", inst, "Rotation")
        holes = gn.node(t, "GeometryNodeRealizeInstances")
        gn.link(t, inst, "Instances", holes, "Geometry")
        grille = gn.node(t, "GeometryNodeMeshBoolean", "visor minus grille holes",
                         props={"operation": "DIFFERENCE", "solver": "MANIFOLD"})  # fmt: skip
        gn.link(t, visor_mesh, "Mesh", grille, "Mesh 1")
        gn.link(t, holes, "Geometry", grille, "Mesh 2")
        gn.link(t, grille, "Mesh", gout, "Geometry")
    gn.arrange(t)
    return t
