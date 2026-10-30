# step 17: prong tongues snap (slit-freed side arms, 0.3 mm 45 deg barbs into an end pocket, 1.4% strain; were crush-rib friction only); side keyholes -> one centred Hanger plate in the top clip zone (40x22x3.8, keyhole 9/4.6, 2.2 head room) snapped into 2 top-rail slots, butting the rabbet wall; coupon + Coupon_M/Hanger; slot walls >= 2.72
# Mitered-corner joinery and back features shared by 20_prongs, 25_hangers, 40_sections
# and 45_coupon. Not an NN_ builder: build_all skips it.
#
# Every corner feature is drawn once for the top-right corner (TR) in world mm and
# mirrored to the others with (sx, sy). All of it is symmetric about the miter plane,
# sy*y = sx*x + K: the line through the sight and rabbet corners at 45 deg (both have
# equal margins, so K = (sight_h - sight_w) / 2 for either).
#
# Back key: an L tenon pressed into an L pocket across the miter from the back. Two
# in-plane snap arms (one per leg, on the outer edge) carry barbs that catch under the
# pocket's mouth lip, so the key clicks in and holds the corner closed. The cove profile
# leaves no room for a snap spline in the miter face itself (2026-10-16 fit: at most a
# 7 x 4 mm section, +-5 mm deep, too short for a snap arm); the back strip has the length.
#
# Prong: a flat spring tab. Its tongue pushes into a slot in the rabbet's side wall and
# its arm reaches over the backboard; a bump near the arm's tip presses the stack against
# the glazing lip. The tongue snaps in: two side arms, freed by slits that run back into
# the prong, carry barbs that spring into a wider pocket at the slot's far end. Their 45
# deg retaining faces hold against handling and pull out with a firm tug to change the art.
#
# Hanger: a plate with a keyhole, centred on the top rail. The rail can't hold a keyhole
# itself: its back strip is 8.6 mm wide at mid-span and a keyhole needs ~14. The plate
# sits in the clip zone behind the backboard (z 0-3.8), butts the rabbet wall (the
# frame's weight bears there, not on the tongues) and is held by two snap tongues like
# the prongs'. Hung, the frame drops onto the nail, so the slot runs up (toward the rail)
# from the entry hole. Only HANGER_ROOM is left for the head behind the lip: the stack's
# back is 4 mm from the wall.
import itertools
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
import frame_geo

WALL = 2.4  # min plastic around any recess (6 lines at 0.4 mm)
CLEAR = 0.15  # per side on sliding/snap fits (0.10 slid on the 2026-10-11 coupon)
SEAM_CHAMFER = (
    0.4  # 45 deg relief on the back edge of each miter face (elephant's foot)
)

KEY_GAP = WALL + CLEAR  # key inner edges from the rabbet edges (pocket keeps WALL)
KEY_W = 8.0  # leg width
KEY_LEG = 26.0  # leg length, from the key's outer corner
KEY_T = 5.0  # key thickness (z); the pocket is KEY_T + KEY_ROOF deep
KEY_ROOF = 0.3
KEY_LIP = 0.8  # pocket mouth (z 0..LIP) along the outer edges: the barbs catch under it
ARM_T, ARM_L, SLOT = 1.6, 10.0, 1.2  # snap arm width, length, slot behind it
BARB, BARB_LEN, BARB_RAMP = 0.5, 3.5, 0.9  # barb overlap, length along the arm, lead-in

# Alignment spline: a short loose tenon across the miter at the sight corner, above the
# glazing lip, where the profile is thickest. It keeps the visible miter line flush; the
# key does the holding. Fitted 2026-10-16 (>= WALL from the face, rabbet and key pocket
# at all four corners). u runs along the miter from the sight corner, v across it.
SPLINE_U, SPLINE_Z0 = 6.0, 12.0  # centre along the miter; underside
SPLINE_W, SPLINE_H = 5.0, 5.0  # width (u) and wall height (z) under a 45 deg gable
SPLINE_D = 5.0  # into each piece
SPLINE_CLEAR = 0.10  # per side: the 2026-10-11 coupon's best slide fit
SPLINE_END = 0.5  # extra socket depth at each blind end
SPLINE_CHAMFER = 0.4

PRONG_W = 8.0  # along the edge
PRONG_T = 1.4  # tongue and arm thickness
PRONG_Z0 = 2.0  # underside of tongue/arm (z up from the back plane): 1.85 mm floor
PRONG_DEPTH = 5.0  # tongue length into the wall
PRONG_ARM = 14.0  # arm reach past the rabbet edge
PRONG_BUMP = (
    1.5  # bump height on the arm: relaxed reach z 4.9 vs the board's back at 4.0
)

# snap tongue (prongs and hanger): side arms SNAP_T wide behind SNAP_SLIT slits, rooted
# SNAP_ROOT past the slot mouth; strain 1.5 * 1.2 * 0.3 / 6.2^2 = 1.4% (PETG, flat)
SNAP_T, SNAP_SLIT, SNAP_ROOT = 1.2, 0.8, 2.5
SNAP_BARB = 0.3  # overlap into the slot's end pocket
SNAP_HOLD = 2.0  # retaining face, from the tongue's tip

HANGER_W, HANGER_H, HANGER_T = 40.0, 22.0, 3.8  # plate along the rail, inward, thick
HANGER_TONGUE_A, HANGER_TONGUE_T = 12.0, 1.6  # tongue centres (+-a) and thickness
HANGER_HEAD = 9.0  # entry hole and head cavity width (nail / screw head <= 8.5)
HANGER_SHANK = 4.6  # slot width through the lip
HANGER_LIP = 1.6  # plastic between the head and the wall
HANGER_ROOM = HANGER_T - HANGER_LIP  # 2.2: head height + 0.2 clearance
HANGER_SLOT_END = 6.0  # slot's top end (centre), inward from the rabbet edge
HANGER_TRAVEL = 8.0  # entry centre to the slot's top end

SW, SH = frame_geo.sight_size()
RW, RH = frame_geo.rabbet_size()
K = (SH - SW) / 2  # miter offset: sy*y = sx*x + K
RX, RY = RW / 2, RH / 2  # rabbet corner (TR)
CORNERS = {"TR": (1, 1), "TL": (-1, 1), "BL": (-1, -1), "BR": (1, -1)}
RAILS = {"T": (0, 1), "B": (0, -1), "L": (-1, 0), "R": (1, 0)}  # outward direction
_SOLVERS = {i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items}  # fmt: skip
SOLVER = "MANIFOLD" if "MANIFOLD" in _SOLVERS else "EXACT"  # frame cuts (Blender 4.5+)


# --- mesh helpers -------------------------------------------------------------------


def mirror(pts, sx, sy):
    """TR points -> corner (sx, sy). Rings stay counter-clockwise."""
    out = [(sx * p[0], sy * p[1], *p[2:]) for p in pts]
    return out[::-1] if sx * sy < 0 and len(pts[0]) == 2 else out


def ring_loft(bm, levels) -> None:
    """Closed shell through CCW rings with equal vertex counts, [(ring, z), ...] bottom
    to top: capped at both ends, quads between consecutive rings."""
    rows = [[bm.verts.new((x, y, z)) for x, y in ring] for ring, z in levels]
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])
    n = len(rows[0])
    for lo, hi in itertools.pairwise(rows):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def ring_prism(bm, ring, z0, z1) -> None:
    """Vertical prism of a simple CCW polygon (may be concave) from z0 to z1."""
    ring_loft(bm, [(ring, z0), (ring, z1)])


def inset(ring, d) -> list:
    """CCW polygon with every edge moved d inward (miter joins)."""
    n = len(ring)
    lines = []
    for i in range(n):
        a, b = Vector(ring[i]), Vector(ring[(i + 1) % n])
        t = (b - a).normalized()
        left = Vector((-t.y, t.x))
        lines.append((a + left * d, t))
    out = []
    for i in range(n):
        (p, u), (q, v) = lines[i - 1], lines[i]
        cross = u.x * v.y - u.y * v.x
        s = ((q - p).x * v.y - (q - p).y * v.x) / cross
        out.append(tuple(p + u * s))
    return out


def hull_into(bm, pts, chamfer=0.0) -> None:
    tmp = bmesh.new()
    for co in pts:
        tmp.verts.new(co)
    bmesh.ops.convex_hull(tmp, input=tmp.verts[:])
    bmesh.ops.dissolve_limit(
        tmp, angle_limit=0.001, verts=tmp.verts[:], edges=tmp.edges[:]
    )
    if chamfer:
        bmesh.ops.bevel(
            tmp, geom=tmp.edges[:], offset=chamfer, segments=1, affect="EDGES"
        )
    me = bpy.data.meshes.new("_hull")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def gable(u0, u1, z0, z1, grow=0.0) -> list:
    """Section u0..u1 wide, walls z0..z1, 45 deg roof to an apex (u1-u0)/2 above z1,
    offset outward by `grow` (walls and floor by grow, apex by grow * sqrt 2)."""
    m, a = (u0 + u1) / 2, (u1 - u0) / 2 + grow
    apex = z1 + (u1 - u0) / 2 + grow * math.sqrt(2)
    return [(m - a, z0 - grow), (m + a, z0 - grow), (m + a, apex - a), (m, apex), (m - a, apex - a)]  # fmt: skip


def union(name, shells, coll):
    """One manifold object from overlapping closed bmesh shells (EXACT union). Frees them."""
    objs = []
    for i, bm in enumerate(shells):
        me = bpy.data.meshes.new(f"_{name}_{i}")
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        objs.append(bpy.data.objects.new(me.name, me))
        bpy.context.scene.collection.objects.link(objs[-1])
    base = objs[0]
    for o in objs[1:]:
        mod = base.modifiers.new(o.name, "BOOLEAN")
        mod.operation, mod.solver, mod.use_self, mod.object = "UNION", "EXACT", True, o
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(base.evaluated_get(dg), depsgraph=dg)
    me.name = name
    for o in objs:
        old = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(old)
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    return obj


# --- miter --------------------------------------------------------------------------


def miter_wedges(bm, corner, keep, top=80.0, big=600.0) -> None:
    """Cutter removing the far side of `corner`'s miter from a piece: keep="H" keeps the
    horizontal rail (Top/Bottom) side, "V" the vertical one. Its section (w = depth into
    the removed side, z) is the half-plane plus a SEAM_CHAMFER notch into the kept side
    at the back face, extruded along the miter. It stops short of the frame's centre
    lines, so the two wedges cutting one rail never overlap."""
    sx, sy = CORNERS[corner]
    o = Vector((SW / 2, SH / 2, 0))  # TR sight corner, on the miter
    u_dir = Vector((1, 1, 0)) / math.sqrt(2)
    into_h = Vector((-1, 1, 0)) / math.sqrt(2)  # across the miter, into the top rail
    if keep == "H":  # the vertical rail's part with y >= 0 starts at u = -SH/2/sqrt2
        w_dir, u0 = -into_h, -SH / 2 / math.sqrt(2) - 5
    else:  # the horizontal rail's part with x >= 0 starts at u = -SW/2/sqrt2
        w_dir, u0 = into_h, -SW / 2 / math.sqrt(2) - 5
    c = SEAM_CHAMFER
    prof = [(big, -1), (big, top), (0, top), (0, c), (-(c + 1), -1)]
    tmp = bmesh.new()
    rings = []
    for u in (u0, 80.0):
        pts = [o + u_dir * u + w_dir * w + Vector((0, 0, z)) for w, z in prof]
        rings.append([tmp.verts.new((sx * p.x, sy * p.y, p.z)) for p in pts])
    tmp.faces.new(rings[0])
    tmp.faces.new(rings[1][::-1])
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        tmp.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
    me = bpy.data.meshes.new("_wedge")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


# --- back key -----------------------------------------------------------------------


def key_outline(grow=0.0, undercut=0.0) -> list:
    """L key outline, TR, CCW: legs along -x (top) and -y (right) from the outer corner.
    `grow` offsets every edge; `undercut` pushes only the two outer edges further out."""
    g, w = KEY_GAP - grow, KEY_W + 2 * grow
    e = KEY_GAP + KEY_W - KEY_LEG - grow  # leg ends (relative to the rabbet corner)
    o = g + w + undercut
    pts = [(e, g), (g, g), (g, e), (o, e), (o, o), (e, o)]
    return [(RX + x, RY + y) for x, y in pts]


def key_pocket_shells(corner) -> list:
    """Mouth (z -1..LIP) and the wider cavity above it, whose 45 deg hip roof leaves a
    0.6 mm ridge so the pocket prints back-down without supports. Two overlapping
    shells: union them (joinery.union) before cutting."""
    sx, sy = CORNERS[corner]
    mouth, cavity = bmesh.new(), bmesh.new()
    ring_prism(mouth, mirror(key_outline(CLEAR), sx, sy), -1.0, KEY_LIP + 0.01)
    wide = mirror(key_outline(CLEAR, BARB + CLEAR), sx, sy)
    rise = (KEY_W + 2 * CLEAR + BARB + CLEAR) / 2 - 0.3
    z = KEY_T + KEY_ROOF
    ring_loft(cavity, [(wide, KEY_LIP), (wide, z), (inset(wide, rise), z + rise)])
    return [mouth, cavity]


def key_shells(corner) -> list:
    """Key body (L with a slot behind each snap arm) + two barbs, as shells for union."""
    g, o = KEY_GAP, KEY_GAP + KEY_W
    e = o - KEY_LEG
    s0, s1 = o - ARM_T - SLOT, o - ARM_T  # slot band across the leg
    r = SLOT / 2
    tip = e + ARM_L  # slot's rounded inner end (centre)
    arc = [
        (tip + r * math.sin(a), (s0 + s1) / 2 - r * math.cos(a))
        for a in (math.pi * i / 6 for i in range(7))
    ]
    # top leg end, walked north from the inner edge: up to the slot, around its rounded
    # end, back out, then the arm's end
    top = [(e, g), (e, s0)] + arc + [(e, s1), (e, o)]
    # the right leg's end is its mirror about the miter (x <-> y), walked east
    right = [(y, x) for x, y in top]
    # CCW: inner corner, right leg end (east), outer corner, top leg end (south)
    ring = [(g, g)] + right + [(o, o)] + top[::-1]
    body = bmesh.new()
    sx, sy = CORNERS[corner]
    ring_w = [(RX + x, RY + y) for x, y in ring]
    ring_prism(body, mirror(ring_w, sx, sy), 0.0, KEY_T)
    shells = [body]
    zr = KEY_LIP + CLEAR  # retaining face, just past the lip
    for leg in ("top", "right"):
        a0, a1 = e + 0.5, e + 0.5 + BARB_LEN
        pts = []
        for z, b in ((zr, BARB), (KEY_T - BARB_RAMP, BARB), (KEY_T, 0.02)):
            for a in (a0, a1):
                for d in (-0.3, b):  # 0.3 into the arm so the union is solid
                    x, y = (a, o + d) if leg == "top" else (o + d, a)
                    pts.append(Vector((sx * (RX + x), sy * (RY + y), z)))
        bm = bmesh.new()
        hull_into(bm, pts)
        shells.append(bm)
    return shells


# --- alignment spline ---------------------------------------------------------------


def spline_into(bm, corner, half, grow=0.0, chamfer=0.0) -> None:
    """Spline section (grown by `grow`), from v = -half to +half across the miter."""
    sx, sy = CORNERS[corner]
    o = Vector((sx * SW / 2, sy * SH / 2, 0))
    u_dir = Vector((sx, sy, 0)) / math.sqrt(2)
    v_dir = Vector((-sx, sy, 0)) / math.sqrt(2)
    sec = gable(SPLINE_U - SPLINE_W / 2, SPLINE_U + SPLINE_W / 2, SPLINE_Z0,
                SPLINE_Z0 + SPLINE_H, grow)  # fmt: skip
    pts = [o + u_dir * u + v_dir * v + Vector((0, 0, z)) for u, z in sec for v in (-half, half)]  # fmt: skip
    hull_into(bm, pts, chamfer)


def spline_socket(bm, corner) -> None:
    spline_into(bm, corner, SPLINE_D + SPLINE_END, SPLINE_CLEAR)


def spline_part(bm, corner) -> None:
    spline_into(bm, corner, SPLINE_D, 0.0, SPLINE_CHAMFER)


# --- snap tongues: prongs and hanger -------------------------------------------------


def rail_xform(rail, along):
    """World point from rail-local (a along the edge, b inward from the rabbet edge, z)."""
    ox, oy = RAILS[rail]
    edge = RX if ox else RY

    def f(a, b, z):
        if ox:
            return Vector((ox * (edge - b), along + a, z))
        return Vector((along + a, oy * (edge - b), z))

    return f


def world_ring(f, plan) -> list:
    """A rail-local (a, b) outline as a CCW world XY ring."""
    pts = [f(a, b, 0).to_2d() for a, b in plan]
    area = sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:] + pts[:1]))
    return [tuple(p) for p in (pts if area > 0 else pts[::-1])]


def tongue_path(u, w, depth, relief) -> list:
    """Snap tongue centred at a = u, in (a, b): from its +a side at the slot mouth (b 0)
    out to the tip (b = -depth) and back to its -a side. Slits behind each side arm run
    back to b = SNAP_ROOT; `relief` adds one outside each arm too (tongue on a wider body).
    Barbs: 30 deg lead-in at the tip, 45 deg retaining face SNAP_HOLD from the tip."""
    h, t, s, bb = w / 2, SNAP_T, SNAP_SLIT, SNAP_BARB
    hold, crest = -depth + SNAP_HOLD, -depth + 0.9
    lead = crest - bb / math.tan(math.radians(30))
    start = [(u + h + s, 0.0), (u + h + s, SNAP_ROOT), (u + h, SNAP_ROOT)] if relief else [(u + h, 0.0)]  # fmt: skip
    right = start + [
        (u + h, hold), (u + h + bb, hold - bb), (u + h + bb, crest), (u + h, lead),
        (u + h, -depth), (u + h - t, -depth), (u + h - t, SNAP_ROOT),
        (u + h - t - s, SNAP_ROOT), (u + h - t - s, -depth),
    ]  # fmt: skip
    return right + [(2 * u - a, b) for a, b in reversed(right)]


def slit_path(u, w, relief) -> list:
    """The b = 0 edge of a body under a snap tongue at a = u, dipping into its slits."""
    h, t, s, r = w / 2, SNAP_T, SNAP_SLIT, SNAP_ROOT
    start = [(u + h + s, 0.0), (u + h + s, r), (u + h, r), (u + h, 0.0)] if relief else [(u + h, 0.0)]  # fmt: skip
    right = start + [(u + h - t, 0.0), (u + h - t, r), (u + h - t - s, r), (u + h - t - s, 0.0)]  # fmt: skip
    return right + [(2 * u - a, b) for a, b in reversed(right)]


def snap_socket_shells(rail, along, w, z0, t, depth=PRONG_DEPTH) -> list:
    """Gable-roofed slot for a snap tongue (w wide, z0..z0+t), plus the wider pocket at its
    far end that the barbs spring into. Overlapping shells: union before cutting."""
    f = rail_xform(rail, along)
    h, bb = w / 2, SNAP_BARB
    slot = gable(-h, h, z0, z0 + t, CLEAR)
    pocket = gable(-h - bb - CLEAR, h + bb + CLEAR, z0, z0 + t, CLEAR)
    end = -depth - CLEAR
    shells = []
    for sec, b0 in ((slot, 1.0), (pocket, -depth + SNAP_HOLD + CLEAR)):
        bm = bmesh.new()
        hull_into(bm, [f(a, b, z) for a, z in sec for b in (b0, end)])
        shells.append(bm)
    return shells


def prong_sites() -> list:
    """(rail, along) per prong: 2 on each short rail, 3 on each long one, clear of keys."""
    return [(r, a) for r in "TB" for a in (-75.0, 75.0)] + [
        (r, a) for r in "LR" for a in (-110.0, 0.0, 110.0)
    ]


def prong_socket_shells(rail, along) -> list:
    return snap_socket_shells(rail, along, PRONG_W, PRONG_Z0, PRONG_T)


def prong_shells(rail, along) -> list:
    """Snap tongue + spring arm (one flat bar) and the bump, in the assembled pose."""
    f = rail_xform(rail, along)
    h = PRONG_W / 2
    plan = tongue_path(0.0, PRONG_W, PRONG_DEPTH, False) + [
        (-h, PRONG_ARM),
        (h, PRONG_ARM),
    ]
    bar = bmesh.new()
    ring_prism(bar, world_ring(f, plan), PRONG_Z0, PRONG_Z0 + PRONG_T)
    top = PRONG_Z0 + PRONG_T
    bump = bmesh.new()
    prof = [(PRONG_ARM - 4.5, top - 0.2), (PRONG_ARM - 3.0, top + PRONG_BUMP),
            (PRONG_ARM - 1.5, top + PRONG_BUMP), (PRONG_ARM - 0.3, top - 0.2)]  # fmt: skip
    hull_into(bump, [f(a, b, z) for b, z in prof for a in (-h + 0.5, h - 0.5)])
    return [bar, bump]


def stadium(a, b0, b1, r, segs=15) -> list:
    """Slot outline in (a, b): half circles of radius r centred (a, b0) and (a, b1)."""
    lo = [math.pi + math.pi * i / segs for i in range(segs + 1)]
    hi = [math.pi * i / segs for i in range(segs + 1)]
    return [(a + r * math.cos(t), b0 + r * math.sin(t)) for t in lo] + [
        (a + r * math.cos(t), b1 + r * math.sin(t)) for t in hi
    ]


def hanger_tongue_z0() -> float:
    return HANGER_T - HANGER_TONGUE_T  # tongues flush with the plate's board side


def hanger_socket_shells() -> list:
    return [
        s
        for u in (-HANGER_TONGUE_A, HANGER_TONGUE_A)
        for s in snap_socket_shells(
            "T", u, PRONG_W, hanger_tongue_z0(), HANGER_TONGUE_T
        )
    ]


def hanger_shells() -> tuple[list, list]:
    """(plate shells, keyhole shells) for the hanger, in place on the top rail. The plate
    is a full-thickness body with its tongue slits, plus a top layer carrying the tongues;
    the keyhole (entry + shank slot through the lip, head cavity open on the board side)
    is cut from their union."""
    f = rail_xform("T", 0.0)
    hw, u, z1 = HANGER_W / 2, HANGER_TONGUE_A, hanger_tongue_z0()
    tail = [(-hw, 0.0), (-hw, HANGER_H), (hw, HANGER_H)]
    thin = [(hw, 0.0)] + tongue_path(u, PRONG_W, PRONG_DEPTH, True) + tongue_path(-u, PRONG_W, PRONG_DEPTH, True) + tail  # fmt: skip
    thick = [(hw, 0.0)] + slit_path(u, PRONG_W, True) + slit_path(-u, PRONG_W, True) + tail  # fmt: skip
    body, tongues = bmesh.new(), bmesh.new()
    ring_prism(body, world_ring(f, thick), 0.0, z1 + 0.01)
    ring_prism(tongues, world_ring(f, thin), z1, HANGER_T)
    b0, b1 = HANGER_SLOT_END, HANGER_SLOT_END + HANGER_TRAVEL
    entry, slot, cavity = bmesh.new(), bmesh.new(), bmesh.new()
    ring_prism(entry, world_ring(f, stadium(0.0, b1, b1 + 0.01, HANGER_HEAD / 2)), -1.0, HANGER_LIP + 0.01)  # fmt: skip
    ring_prism(slot, world_ring(f, stadium(0.0, b0, b1, HANGER_SHANK / 2)), -1.0, HANGER_LIP + 0.01)  # fmt: skip
    ring_prism(cavity, world_ring(f, stadium(0.0, b0, b1, HANGER_HEAD / 2)), HANGER_LIP, HANGER_T + 1.0)  # fmt: skip
    return [body, tongues], [entry, slot, cavity]


def difference(obj, cutter) -> None:
    """Bake obj minus cutter into obj's mesh, then delete the cutter."""
    mod = obj.modifiers.new("_cut", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", SOLVER, cutter
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)
    old, cut_me = obj.data, cutter.data
    obj.modifiers.remove(mod)
    obj.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(cut_me)


# Flex prongs: 10 spring tabs that hold the art stack from the back, no screws or tools.
#
# Stack (z up from the wall/back plane), all cut to the 9x12" art size: glazing z 7-9
# against the lip, art on its 3 mm backboard z 4-7. Each prong's tongue pushes 5 mm into a
# slot in the rabbet's side wall (a live boolean on Frame, gable-roofed so it prints
# without bridging) and snaps: barbs on its two slit-freed side arms spring into a wider
# pocket at the slot's end (joinery.tongue_path). Its arm reaches 14 mm over the
# backboard and a bump near the tip presses the stack forward. Relaxed, the bump reaches
# z 4.9, so the board's back (z 4) deflects it 0.9 mm: about 1.3% strain in a 1.4 mm PETG
# arm printed flat, and up to 2.5% for a stack 0.8 mm thicker. Prongs live in Model
# (40_sections links them to Print).
import importlib
import sys
from pathlib import Path

import bpy
from kit import materials, mesh, scene

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

frame = bpy.data.objects["Frame"]
shells = [s for rail, along in joinery.prong_sites() for s in joinery.prong_socket_shells(rail, along)]  # fmt: skip
cut = joinery.union("Cut_ProngSockets", shells, scene.work())
mesh.boolean(frame, cut).solver = joinery.SOLVER  # live: the frame stays parametric

pla = materials.principled("PLA_Matte", "#8A8496", roughness=0.65)
for i, (rail, along) in enumerate(joinery.prong_sites(), 1):
    prong = joinery.union(
        f"Prong_{i:02d}", joinery.prong_shells(rail, along), scene.model()
    )
    mesh.clean(prong)
    for p in prong.data.polygons:
        p.use_smooth = False
    materials.assign(prong, pla)
    prong["rail"], prong["along"] = rail, along  # 70_assembly slides each one in
print(f"prongs: {len(joinery.prong_sites())} sockets + prongs")
# Hanger: one keyhole plate centred on the top rail, for a single nail or screw.
# Geometry and sizing: joinery.py (hanger_shells). The plate lives in the clip zone
# behind the backboard, butts the top rabbet wall and snaps into two slots cut in it (a
# live boolean on Frame, before 40_sections, so Rail_T inherits them). Like the prongs,
# it's in Model and 40_sections links it to Print.
import importlib
import sys
from pathlib import Path

import bpy
from kit import materials, mesh, scene

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

frame = bpy.data.objects["Frame"]
cut = joinery.union("Cut_HangerSlots", joinery.hanger_socket_shells(), scene.work())
mesh.boolean(frame, cut).solver = joinery.SOLVER

plate, keyhole = joinery.hanger_shells()
hanger = joinery.union("Hanger", plate, scene.model())
joinery.difference(hanger, joinery.union("_Keyhole", keyhole, scene.work()))
mesh.clean(hanger)
for p in hanger.data.polygons:
    p.use_smooth = False
materials.assign(hanger, materials.principled("PLA_Matte", "#8A8496", roughness=0.65))
hanger["rail"], hanger["along"] = "T", 0.0  # 70_assembly slides it in like a prong
print(
    f"hanger: {joinery.HANGER_W:.0f} x {joinery.HANGER_H:.0f} x {joinery.HANGER_T} plate, "
    f"keyhole {joinery.HANGER_HEAD:.0f} mm entry, head room {joinery.HANGER_ROOM:.1f} mm"
)
