# step 16: 2 keyhole hangers in Rail_L/R backs (x +-122, 244 mm apart; entry 9, shank slot 4.6 x 8 up, 2.4 lip, hip-roofed head cavity; walls >= 2.39): the top rail's 8.6 mm mid strip can't take one; coupon Coupon_R extended to keep a whole keyhole
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
# the glazing lip.
#
# Keyhole: one per side rail near the top, for a screw or nail. The top rail can't take
# one: its back strip is 8.6 mm wide at mid-span and the corner keys fill it near the
# tips. The side rails' strip is 13-15 mm wide between the upper prong (y 110) and the
# key's leg end (y ~137). Hung, the frame drops onto the screws, so each slot runs up
# (+y) from its entry hole and the head sits behind a WALL-thick lip. The head cavity
# gets a 45 deg hip roof, so it prints back-down without supports.
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
PRONG_DEPTH = 4.0  # tongue length into the wall
PRONG_ARM = 14.0  # arm reach past the rabbet edge
PRONG_BUMP = (
    1.5  # bump height on the arm: relaxed reach z 4.9 vs the board's back at 4.0
)
PRONG_RIB = 0.35  # crush ribs on the tongue's sides: 0.2 mm into the slot wall

HANGER_HEAD = 9.0  # entry hole and head cavity width (#8 / 4 mm pan head, ~8 mm)
HANGER_SHANK = 4.6  # slot width through the lip
HANGER_TRAVEL = 8.0  # entry centre to the slot's top end
HANGER_ROOM = 3.6  # cavity height behind the lip (head ~2.5-3 mm)
HANGER_Y = 121.5  # entry centre: clear of the upper prong slot and the key pocket
HANGER_INSET = 7.2  # rabbet edge to the slot centre: the middle of the back strip

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


# --- keyhole hangers ----------------------------------------------------------------


def stadium(cx, y0, y1, r, segs=15) -> list:
    """CCW slot outline: half circles of radius r centred (cx, y0) (bottom) and (cx, y1).
    Odd segs: with 16, Rail_R's section cut left a 3-edge hole at the slot's mouth."""
    bottom = [math.pi + math.pi * i / segs for i in range(segs + 1)]
    top = [math.pi * i / segs for i in range(segs + 1)]
    return [(cx + r * math.cos(a), y0 + r * math.sin(a)) for a in bottom] + [
        (cx + r * math.cos(a), y1 + r * math.sin(a)) for a in top
    ]


def keyhole_shells(sx) -> list:
    """Entry hole + shank slot through the lip (z -1..WALL), and the roofed head cavity
    behind it, in the side rail on side sx. Overlapping shells: union before cutting."""
    cx, y0, y1 = sx * (RX + HANGER_INSET), HANGER_Y, HANGER_Y + HANGER_TRAVEL
    r = HANGER_HEAD / 2
    entry, slot, cavity = bmesh.new(), bmesh.new(), bmesh.new()
    ring_prism(entry, stadium(cx, y0, y0 + 0.01, r), -1.0, WALL + 0.01)
    ring_prism(slot, stadium(cx, y0, y1, HANGER_SHANK / 2), -1.0, WALL + 0.01)
    ring = stadium(cx, y0, y1, r)
    z, rise = WALL + HANGER_ROOM, r - 0.3
    ring_loft(cavity, [(ring, WALL), (ring, z), (inset(ring, rise), z + rise)])
    return [entry, slot, cavity]


def keyhole_span() -> tuple[float, float]:
    """y range a keyhole occupies (the coupon keeps all of it)."""
    return HANGER_Y - HANGER_HEAD / 2, HANGER_Y + HANGER_TRAVEL + HANGER_HEAD / 2


# --- prongs -------------------------------------------------------------------------


def prong_sites() -> list:
    """(rail, along) per prong: 2 on each short rail, 3 on each long one, clear of keys."""
    return [(r, a) for r in "TB" for a in (-75.0, 75.0)] + [
        (r, a) for r in "LR" for a in (-110.0, 0.0, 110.0)
    ]


def prong_xform(rail, along):
    """World point from prong-local (a along the edge, b inward from the rabbet edge, z)."""
    ox, oy = RAILS[rail]
    edge = RX if ox else RY

    def f(a, b, z):
        if ox:
            return Vector((ox * (edge - b), along + a, z))
        return Vector((along + a, oy * (edge - b), z))

    return f


def prong_socket(bm, rail, along) -> None:
    f = prong_xform(rail, along)
    sec = gable(-PRONG_W / 2, PRONG_W / 2, PRONG_Z0, PRONG_Z0 + PRONG_T, CLEAR)
    hull_into(bm, [f(a, b, z) for a, z in sec for b in (1.0, -PRONG_DEPTH - CLEAR)])


def prong_shells(rail, along) -> list:
    """Tongue + arm (one flat bar with crush ribs) and the bump, in the assembled pose."""
    f = prong_xform(rail, along)
    h = PRONG_W / 2
    ribs = [(-PRONG_DEPTH + 0.8, -PRONG_DEPTH + 1.2), (-1.6, -1.2)]
    side = []  # a = +h side, walking b from the tongue tip to the arm tip
    for b0, b1 in ribs:
        side += [(h, b0 - 0.4), (h + PRONG_RIB, b0), (h + PRONG_RIB, b1), (h, b1 + 0.4)]
    plan = (
        [(-h, -PRONG_DEPTH), (h, -PRONG_DEPTH)]
        + side
        + [(h, PRONG_ARM), (-h, PRONG_ARM)]
    )
    plan += [(-a, b) for a, b in side[::-1]]
    bar = bmesh.new()
    pts = [f(a, b, 0).to_2d() for a, b in plan]
    area = sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:] + pts[:1]))
    ring_prism(bar, [tuple(p) for p in (pts if area > 0 else pts[::-1])], PRONG_Z0, PRONG_Z0 + PRONG_T)  # fmt: skip
    top = PRONG_Z0 + PRONG_T
    bump = bmesh.new()
    prof = [(PRONG_ARM - 4.5, top - 0.2), (PRONG_ARM - 3.0, top + PRONG_BUMP),
            (PRONG_ARM - 1.5, top + PRONG_BUMP), (PRONG_ARM - 0.3, top - 0.2)]  # fmt: skip
    hull_into(bump, [f(a, b, z) for b, z in prof for a in (-h + 0.5, h - 0.5)])
    return [bar, bump]


# Hangers: two keyhole slots in the back of the side rails, near the top, for two screws
# (or nails) set level on the wall. Geometry and sizing: joinery.py (keyhole_shells), so
# 45_coupon can keep a whole one. Live boolean on Frame, before 40_sections, so Rail_L/R
# inherit it.
import importlib
import sys
from pathlib import Path

import bpy
from kit import mesh, scene

sys.path.insert(0, str(Path(__file__).parent))
import joinery

importlib.reload(joinery)

frame = bpy.data.objects["Frame"]
shells = joinery.keyhole_shells(1) + joinery.keyhole_shells(-1)
cut = joinery.union("Cut_Hangers", shells, scene.work())
mesh.boolean(frame, cut).solver = joinery.SOLVER
y0, y1 = joinery.keyhole_span()
x = joinery.RX + joinery.HANGER_INSET
print(f"hangers: 2 keyholes at x +-{x:.1f}, y {y0:.1f}-{y1:.1f}, {2 * x:.0f} mm apart")
