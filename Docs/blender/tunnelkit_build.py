"""Tunnel test kit (TT_): builds every piece from a few numbers and exports one FBX per piece to Assets/Tunnels/TT.
Plan: Docs/TunnelKit_Plan.md.

Run in Blender (live or headless --factory-startup):  exec(open(r"<this file>").read())
  TT_EXPORT = False before exec: only build the preview row in the scene (collection TT_Preview), export nothing.

Every piece is a closed solid of earth (inner surface, outer shell SHELL m further out, ends closed), so sunlight has to
pass through geometry from any side. Each opening carries a sleeve reaching SLEEVE m past the joint over the
neighbour's shell and SLEEVE m back over its own: joined pieces' sleeves overlap, there's no straight path from the
earth into the tunnel. A timber frame sits just inside each opening, on the piece's own side of the joint.

Blender space: X right, Y along the tunnel, Z up; floor at Z 0. Corridors start at Y 0 (opening facing -Y).
Memory points (empties "1", "2", ...) at each opening, MP_HEIGHT above the floor, their +Y pointing out.
FBX: <Name>_LOD0 + UTM_<Name> (collider = the same mesh), triangles only, materials TT_Earth / TT_Wood.
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

OUT = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Assets\Tunnels\TT"
EXPORT = globals().get('TT_EXPORT', True)

# The tunnel's inside: flat floor, walls bulging a little, a rounded roof (x across, z up)
INNER = [(-0.7, 0.0), (0.7, 0.0), (0.74, 0.8), (0.7, 1.4), (0.56, 1.78), (0.32, 2.02), (0.0, 2.1),
         (-0.32, 2.02), (-0.56, 1.78), (-0.7, 1.4), (-0.74, 0.8)]
SHELL = 0.6          # earth round it
SLEEVE = 0.25        # sleeve reach either side of a joint
SLEEVE_IN = 0.1      # how far the sleeve sinks into the shell (no gap at all between them)
SLEEVE_T = 0.3       # sleeve thickness
FRAME_T = 0.12       # timber frame depth into the tunnel
FRAME_L = 0.15       # and length along it
MP_HEIGHT = 1.0
TURN_RADIUS = 1.8    # tight: the shell's inner side is 0.5 m from the turn's centre
UV_EARTH = 1 / 2.2 / 16    # metres -> UV for the mud emat (TilingU/V 16, one repeat per 2.2 m)
UV_WOOD = 1 / 1.0
# Materials: 0 TT_Earth, the inside (dark, no sky light), 1 TT_Wood, 2 TT_Ground, the outside (terrain-object
# material, blends on vertex colour R: 1 its own texture, 0 the terrain's; no colour layer at all renders black).
# A terrain-object material can't shut the sky's light out, so it only goes where the sky can be seen from.
EARTH_COL = (1.0, 1.0, 1.0, 1.0)
WOOD_COL = (1.0, 1.0, 1.0, 1.0)
GROUND_COL = (0.0, 1.0, 1.0, 1.0)
MAT_EARTH, MAT_WOOD, MAT_GROUND = 0, 1, 2
MAT_HIDDEN = 3       # while building only: earth buried in earth (sleeves, plugs), left as it is, TT_Earth in the end
# The inside's organic look: edges cut down to REFINE m, then pushed along the surface's normal by noise, WALL_AMP on
# walls and roof, FLOOR_AMP on the floor. Nothing moves within FADE_START of an opening, full from FADE_END: the
# openings keep the exact profile, so pieces still meet perfectly
REFINE = 0.25
WALL_AMP = 0.2
FLOOR_AMP = 0.035
ROOF_IN = 0.5        # the roof bulges in only this much of the walls' amount: headroom
FADE_START = 0.4
FADE_END = 1.4
Z = Vector((0, 0, 1))


# ---------------------------------------------------------------------------------------------------------------------
# Profiles

def offset(profile, d):
    """The closed profile pushed out by d (negative: in), corner by corner along the bisector"""
    n = len(profile)
    pts = [Vector((p[0], p[1])) for p in profile]
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (b - a).normalized()
        e2 = (c - b).normalized()
        n1 = Vector((e1.y, -e1.x))      # counter-clockwise profile: right of the edge is outside
        n2 = Vector((e2.y, -e2.x))
        bis = (n1 + n2)
        if bis.length < 1e-6:
            bis = n1
        bis.normalize()
        k = d / max(bis.dot(n1), 0.2)
        out.append((b.x + bis.x * k, b.y + bis.y * k))
    return out


def ccw(profile):
    area = sum(profile[i - 1][0] * profile[i][1] - profile[i][0] * profile[i - 1][1] for i in range(len(profile)))
    return profile if area > 0 else list(reversed(profile))


INNER = ccw(INNER)
OUTER = offset(INNER, SHELL)
SLEEVE_A = offset(INNER, SHELL - SLEEVE_IN)
SLEEVE_B = offset(INNER, SHELL + SLEEVE_T)


def frame_profiles(profile):
    """Walls and roof of a profile only (no floor), as an open polyline, and the same pulled into the tunnel"""
    # the floor is the edge between the two lowest points; the polyline starts at one and ends at the other
    low = sorted(range(len(profile)), key=lambda i: profile[i][1])[:2]
    n = len(profile)
    start = low[0] if (low[0] + 1) % n != low[1] else low[1]
    line = [profile[(start + k) % n] for k in range(n)]
    pulled = offset(profile, -FRAME_T)
    pulled_line = [pulled[(start + k) % n] for k in range(n)]
    # the ends stay on the floor
    pulled_line[0] = (pulled_line[0][0], line[0][1])
    pulled_line[-1] = (pulled_line[-1][0], line[-1][1])
    outer_line = offset(profile, 0.02)
    outer_line = [outer_line[(start + k) % n] for k in range(n)]
    outer_line[0] = (outer_line[0][0], line[0][1])
    outer_line[-1] = (outer_line[-1][0], line[-1][1])
    return pulled_line, outer_line


# ---------------------------------------------------------------------------------------------------------------------
# Sweeping a pair of profiles along a path into a closed solid

def frame_at(pos, tangent):
    t = Vector((tangent.x, tangent.y, 0)).normalized()
    right = t.cross(Z).normalized()
    return pos, right


def ring(pos, right, profile, scale=(1, 1)):
    return [pos + right * (p[0] * scale[0]) + Z * (p[1] * scale[1]) for p in profile]


def sweep(bm, samples, prof_a, prof_b, closed=True, mat=0, scales=None):
    """samples: [(pos, tangent)]; the solid between profile a (inside) and b (outside), ends closed"""
    rings_a, rings_b = [], []
    for i, (pos, tan) in enumerate(samples):
        p, right = frame_at(pos, tan)
        sc = scales[i] if scales else (1, 1)
        rings_a.append([bm.verts.new(v) for v in ring(p, right, prof_a, sc)])
        rings_b.append([bm.verts.new(v) for v in ring(p, right, prof_b, sc)])
    n = len(prof_a)
    edges = range(n) if closed else range(n - 1)
    faces = []
    for i in range(len(samples) - 1):
        for rings in (rings_a, rings_b):
            for k in edges:
                k2 = (k + 1) % n
                faces.append(bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])))
        if not closed:
            for k in (0, n - 1):
                faces.append(bm.faces.new((rings_a[i][k], rings_b[i][k], rings_b[i + 1][k], rings_a[i + 1][k])))
    for i in (0, len(samples) - 1):
        for k in edges:
            k2 = (k + 1) % n
            faces.append(bm.faces.new((rings_a[i][k], rings_a[i][k2], rings_b[i][k2], rings_b[i][k])))
    for f in faces:
        f.material_index = mat
    return faces


def prism(bm, samples, profile, mat=0):
    """A full solid of a closed profile along a path (a plug)"""
    rings = []
    for pos, tan in samples:
        p, right = frame_at(pos, tan)
        rings.append([bm.verts.new(v) for v in ring(p, right, profile)])
    n = len(profile)
    faces = []
    for i in range(len(samples) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append(bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])))
    faces.append(bm.faces.new(rings[0]))
    faces.append(bm.faces.new(list(reversed(rings[-1]))))
    for f in faces:
        f.material_index = mat
    return faces


def box(bm, lo, hi, mat=0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = Vector((lo[0] if v.co.x < 0 else hi[0], lo[1] if v.co.y < 0 else hi[1], lo[2] if v.co.z < 0 else hi[2]))
    faces = list({f for v in r['verts'] for f in v.link_faces})
    for f in faces:
        f.material_index = mat
    return faces


# ---------------------------------------------------------------------------------------------------------------------
# Paths: lists of (position, horizontal tangent)

def smooth(t):
    return t * t * (3 - 2 * t)


def d_smooth(t):
    return 6 * t * (1 - t)


def path_straight(length, step=0.5, start=Vector((0, 0, 0)), direction=Vector((0, 1, 0))):
    n = max(1, math.ceil(length / step))
    return [(start + direction * (length * i / n), direction.copy()) for i in range(n + 1)]


def path_arc(radius, degrees=90, steps=18):
    """Turning right (towards +X) from heading +Y"""
    out = []
    for i in range(steps + 1):
        a = math.radians(degrees) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    return out


def path_dogleg(length, shift, steps=20):
    out = []
    for i in range(steps + 1):
        t = i / steps
        out.append((Vector((shift * smooth(t), length * t, 0)), Vector((shift * d_smooth(t), length, 0)).normalized()))
    return out


def path_chicane(radius, across, shift_right=True, steps=14):
    """A hard jog sideways: a 90 degree turn, a straight stretch across, a 90 degree turn back to the first heading.
    Moves the tunnel 2 * radius + across sideways, 2 * radius on: no line of sight through it"""
    out = []
    for i in range(steps + 1):                      # turning towards +X
        a = math.radians(90) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    n = max(1, math.ceil(across / 0.5))
    for i in range(1, n + 1):                       # across
        out.append((Vector((radius + across * i / n, radius, 0)), Vector((1, 0, 0))))
    for i in range(1, steps + 1):                   # back to +Y
        b = math.radians(90) * i / steps
        out.append((Vector((radius + across + radius * math.sin(b), 2 * radius - radius * math.cos(b), 0)), Vector((math.cos(b), math.sin(b), 0))))
    if not shift_right:
        out = [(Vector((-p.x, p.y, p.z)), Vector((-t.x, t.y, t.z))) for p, t in out]
    return out


def path_slope(length, rise, steps=16):
    return [(Vector((0, length * i / steps, rise * smooth(i / steps))), Vector((0, 1, 0))) for i in range(steps + 1)]


# ---------------------------------------------------------------------------------------------------------------------
# Joints: a sleeve and a timber frame at an opening

def joint(bm, pos, outward, frame=True):
    """pos: the opening's floor centre; outward: horizontal, pointing out of the piece"""
    out = Vector((outward.x, outward.y, 0)).normalized()
    sleeve = [(pos - out * SLEEVE, out), (pos + out * SLEEVE, out)]
    sweep(bm, sleeve, SLEEVE_A, SLEEVE_B, closed=True, mat=0)
    if not frame:                      # natural cave pieces have no timber
        return
    fa, fb = frame_profiles(INNER)
    frame_path = [(pos - out * FRAME_L, out), (pos - out * 0.005, out)]
    sweep(bm, frame_path, fa, fb, closed=False, mat=1)


class Piece:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.sockets = []      # (floor centre, outward)
        self.fades = []        # more places to keep exact (a mouth with no socket): (floor centre, outward)
        self.frames = True     # a timber frame at each joint (cave pieces switch it off)

    def socket(self, pos, outward, joint_too=True):
        self.sockets.append((pos.copy(), Vector((outward.x, outward.y, 0)).normalized()))
        if joint_too:
            joint(self.bm, pos, outward, self.frames)


def breathe(samples, wide, high, ease=0.5, ramp=1.2):
    """Per-sample profile scales along a path: the standard profile within ease m of either end (the joints stay
    exact), growing over ramp m to wide x high in the middle"""
    dist = [0.0]
    for i in range(1, len(samples)):
        dist.append(dist[-1] + (samples[i][0] - samples[i - 1][0]).length)
    total = dist[-1]
    out = []
    for d in dist:
        a = smooth(min(max((d - ease) / ramp, 0.0), 1.0))
        b = smooth(min(max((total - d - ease) / ramp, 0.0), 1.0))
        k = a * b
        out.append((1 + (wide - 1) * k, 1 + (high - 1) * k))
    return out


def corridor(piece, samples, scales=None):
    """A tunnel along a path, with an opening (and joint) at each end; scales: see breathe"""
    sweep(piece.bm, samples, INNER, OUTER, closed=True, mat=0, scales=scales)
    piece.socket(samples[0][0], -samples[0][1])
    piece.socket(samples[-1][0], samples[-1][1])


# ---------------------------------------------------------------------------------------------------------------------
# Chambers: a box of earth with tunnel-shaped holes and a short stub at each

def chamber(piece, width, depth, height, doors):
    """doors: (side, offset along the wall): side 'S' (-Y), 'N' (+Y), 'E' (+X), 'W' (-X). Built as an object with booleans,
    then put back into the piece's bmesh"""
    hw, hd = width / 2, depth / 2
    shell = bmesh.new()
    box(shell, (-hw - SHELL, -hd - SHELL, -SHELL), (hw + SHELL, hd + SHELL, height + SHELL))
    obj = to_object(shell, piece.name + '_tmp_room')
    cutters = []
    inner = bmesh.new()
    box(inner, (-hw, -hd, 0), (hw, hd, height))
    cutters.append(to_object(inner, piece.name + '_tmp_inner'))
    stubs = []
    for side, along in doors:
        if side == 'S':
            wall, out, base = -hd, Vector((0, -1, 0)), Vector((along, -hd, 0))
        elif side == 'N':
            wall, out, base = hd, Vector((0, 1, 0)), Vector((along, hd, 0))
        elif side == 'E':
            wall, out, base = hw, Vector((1, 0, 0)), Vector((hw, along, 0))
        else:
            wall, out, base = -hw, Vector((-1, 0, 0)), Vector((-hw, along, 0))
        hole = bmesh.new()
        prism(hole, [(base - out * 0.2, out), (base + out * (SHELL + 0.3), out)], offset(INNER, 0.001))
        cutters.append(to_object(hole, piece.name + '_tmp_hole'))
        # a short tunnel out from the wall, sunk a little into it, and the joint at its end
        stub_start = base + out * (SHELL - 0.1)
        stub_end = base + out * (SHELL + 0.6)
        stubs.append((stub_start, stub_end, out))
    for c in cutters:
        m = obj.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = c
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    for c in cutters:
        bpy.data.objects.remove(c)
    bpy.data.objects.remove(obj)
    piece.bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    for a, b, out in stubs:
        sweep(piece.bm, [(a, out), (b, out)], INNER, OUTER, closed=True, mat=0)
        piece.socket(b, out)


def to_object(bm, name):
    # the exact boolean needs every solid's faces turned outwards
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------------------------------------------------------------
# The pieces

def build_straight():
    p = Piece('TT_Straight_4')
    samples = path_straight(4.0, step=0.25)
    corridor(p, samples, breathe(samples, 1.15, 1.05))
    return p


def build_straight_wide():
    """A gallery: swells to about 3 m across and a little higher, then back"""
    p = Piece('TT_Straight_Wide')
    samples = path_straight(5.0, step=0.25)
    corridor(p, samples, breathe(samples, 2.1, 1.3, ramp=1.5))
    return p


def build_straight_narrow():
    """A squeeze: down to about 1.1 m across and a little lower"""
    p = Piece('TT_Straight_Narrow')
    samples = path_straight(4.0, step=0.25)
    corridor(p, samples, breathe(samples, 0.78, 0.9))
    return p


def build_curve(angle):
    """A very gentle bend of `angle` degrees (to the right; entered from the other end it bends left), 4 m long like
    Straight_4, so the joints stay exact: for fitting things together (headings in small steps, small sideways shifts)"""
    p = Piece('TT_Curve_%d' % angle)
    samples = path_arc(4.0 / math.radians(angle), degrees=angle, steps=16)
    corridor(p, samples, breathe(samples, 1.08, 1.0))
    return p


def build_straight_short(length):
    """1 m and 2 m straights: they take up the last bit of a length that doesn't come out in 4 m steps"""
    p = Piece('TT_Straight_%d' % length)
    corridor(p, path_straight(float(length), step=0.25))
    return p


def build_turn():
    p = Piece('TT_Turn90')
    samples = path_arc(TURN_RADIUS, steps=24)
    corridor(p, samples, breathe(samples, 1.12, 1.0))
    return p


def build_turn_wide():
    """A turn that opens out into a small cave on the way round (wider radius, so the shell clears the centre)"""
    p = Piece('TT_Turn90_Wide')
    samples = path_arc(3.0, steps=30)
    corridor(p, samples, breathe(samples, 1.8, 1.25, ramp=1.3))
    return p


def build_dogleg(side):
    p = Piece('TT_Dogleg_' + side)
    corridor(p, path_chicane(TURN_RADIUS, 1.0, side == 'R'))
    return p


def build_slope():
    p = Piece('TT_Slope')
    samples = path_slope(4.0, 1.2)
    corridor(p, samples, breathe(samples, 1.12, 1.0))
    return p


def build_end():
    p = Piece('TT_End')
    samples = path_straight(1.2, step=0.6)
    sweep(p.bm, samples, INNER, OUTER, closed=True, mat=0)
    prism(p.bm, path_straight(0.6, step=0.6, start=Vector((0, 0.8, 0))), offset(INNER, SHELL - 0.05), mat=0)
    p.socket(samples[0][0], -samples[0][1])
    return p


def build_junction():
    p = Piece('TT_Junction')
    chamber(p, 3.2, 3.2, 2.4, [('S', 0.0), ('E', 0.6), ('W', -0.7)])
    return p


def build_room():
    p = Piece('TT_Room')
    chamber(p, 6.0, 6.0, 2.6, [('S', -1.5), ('E', 1.5), ('N', 1.8)])
    return p


def build_entry_horizontal():
    """A mouth into a hillside: the opening flares out over its first 1.2 m; pivot at the mouth's floor centre"""
    p = Piece('TT_Entry_Horizontal')
    samples = path_straight(5.0, step=0.25)
    scales = []
    for pos, _ in samples:
        t = min(pos.y / 1.2, 1.0)
        inner = smooth(min(max((5.0 - pos.y - 0.5) / 1.5, 0.0), 1.0))     # 0 at the joint
        f = max(1.0 + 0.5 * (1 - smooth(t)), 1.0 + 0.12 * inner)
        scales.append((f, max(1.0 + 0.2 * (1 - smooth(t)), 1.0 + 0.15 * inner)))
    sweep(p.bm, samples, INNER, OUTER, closed=True, mat=0, scales=scales)
    # a heavy timber frame round the mouth
    fa, fb = frame_profiles(INNER)
    sweep(p.bm, [(Vector((0, 0.0, 0)), Vector((0, 1, 0))), (Vector((0, 0.25, 0)), Vector((0, 1, 0)))], fa, fb, closed=False, mat=1,
          scales=[scales[0], scales[0]])
    # The mouth gets no memory point: nothing attaches there, but its frame needs the wall left exact
    p.fades.append((Vector((0, 0, 0)), Vector((0, -1, 0))))
    p.socket(samples[-1][0], samples[-1][1])
    return p


SHAFT_H = 1.55
SHAFT_W = 1.25


def build_entry_incline():
    """A 45 degree stair shaft up to the surface, cut level with the ground at RISE; pivot at the hole's centre on the ground"""
    rise = 4.0
    p = Piece('TT_Entry_Incline')
    # a short level stub at the bottom (where the tunnel joins), then up at 45 degrees and on past the ground
    path = path_straight(1.0, step=0.5)
    up = []
    steps = 16
    for i in range(1, steps + 1):
        t = i / steps
        d = (rise + 2.6) * t
        up.append((Vector((0, 1.0 + d, d)), Vector((0, 1, 0))))
    samples = path + up
    # Tall enough to stand on the stairs: up the slope the head moves into the roof, so the shaft is SHAFT_H times the
    # standard height (straight up), SHAFT_W as wide, from just past the joint (which keeps the standard profile)
    scales = []
    for pos, _ in samples:
        k = smooth(min(max((pos.y - 0.4) / 1.2, 0.0), 1.0))
        scales.append((1 + (SHAFT_W - 1) * k, 1 + (SHAFT_H - 1) * k))
    shell = bmesh.new()
    sweep(shell, samples, INNER, OUTER, closed=True, mat=0, scales=scales)
    # steps, 0.25 m each, up to the ground: one solid each, overlapping the shell's floor (cut on their own, as the
    # boolean leaves holes where overlapping solids are cut together)
    stairs = bmesh.new()
    n = int(rise / 0.25) + 2
    outline = [(1.0, -0.4)]
    for i in range(n):
        outline.append((1.0 + 0.25 * i, 0.25 * (i + 1)))
        outline.append((1.0 + 0.25 * (i + 1), 0.25 * (i + 1)))
    outline.append((1.0 + 0.25 * n, 0.25 * n - 0.65))
    half = 0.7 * SHAFT_W
    side = [stairs.verts.new((-half, y, z)) for y, z in outline]
    face = stairs.faces.new(side)
    face.material_index = MAT_WOOD     # timber steps: they keep their edges, the earth's noise isn't for them
    grown = bmesh.ops.extrude_face_region(stairs, geom=[face])
    moved = [g for g in grown['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(stairs, verts=moved, vec=(2 * half, 0, 0))

    cut = bmesh.new()
    box(cut, (-10, -10, rise), (10, 20, rise + 20))
    cutter = to_object(cut, p.name + '_tmp_cut')
    for part, label in ((shell, '_tmp_shaft'), (stairs, '_tmp_stairs')):
        obj = to_object(part, p.name + label)
        m = obj.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = cutter
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        bpy.data.objects.remove(obj)
        p.bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    bpy.data.objects.remove(cutter)
    p.socket(samples[0][0], -samples[0][1])
    # pivot: the middle of the hole, on the ground (the floor reaches the ground at 1 + rise, the roof shaft height before)
    hole = Vector((0, 1.0 + rise - 2.1 * SHAFT_H / 2, rise))
    bmesh.ops.translate(p.bm, verts=p.bm.verts[:], vec=-hole)
    p.sockets = [(pos - hole, out) for pos, out in p.sockets]
    return p


# ---------------------------------------------------------------------------------------------------------------------
# Objects, UVs, export

def materials():
    mats = []
    for name, col in (('TT_Earth', (0.46, 0.35, 0.24, 1)), ('TT_Wood', (0.35, 0.25, 0.15, 1)), ('TT_Ground', (0.3, 0.45, 0.2, 1))):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = col
        mats.append(m)
    return mats


def finish(piece, at=Vector((0, 0, 0)), collection=None):
    """The piece's LOD0, collider and memory points as objects; returns them"""
    bm = piece.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    split_inside(bm)
    refine(bm)
    roughen(bm, piece.sockets + piece.fades)
    for f in bm.faces:
        if f.material_index == MAT_HIDDEN:
            f.material_index = MAT_EARTH
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        s = UV_WOOD if f.material_index == MAT_WOOD else UV_EARTH
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co[u_ax] * s, co[v_ax] * s)
    col = bm.loops.layers.color.new('Col')
    for f in bm.faces:
        c = {MAT_EARTH: EARTH_COL, MAT_WOOD: WOOD_COL}.get(f.material_index, GROUND_COL)
        for l in f.loops:
            l[col] = c
    # smooth over the earth's lumps, sharp at real corners (floor into wall, timber), or the shading smears round them
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(60))
    me = bpy.data.meshes.new(piece.name + '_LOD0')
    bm.to_mesh(me)
    bm.free()
    for m in materials():
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = p.material_index == MAT_EARTH
    col = collection or bpy.context.scene.collection
    lod = bpy.data.objects.new(piece.name + '_LOD0', me)
    utm = bpy.data.objects.new('UTM_' + piece.name, me.copy())
    utm.data.name = 'UTM_' + piece.name
    objs = [lod, utm]
    for o in objs:
        col.objects.link(o)
        o.location = at
    for i, (pos, out) in enumerate(piece.sockets):
        e = bpy.data.objects.new(str(i + 1) if collection is None else f'{piece.name}.{i + 1}', None)
        e.empty_display_type = 'SINGLE_ARROW'
        e.empty_display_size = 0.6
        e.location = at + pos + Z * MP_HEIGHT
        e.rotation_euler = (math.radians(-90), 0, math.atan2(-out.x, out.y))    # the arrow (local +Z) laid along +Y, then turned out
        col.objects.link(e)
        objs.append(e)
    return objs


def split_inside(bm):
    """Earth facing a closed-in space (geometry straight above and below a point just off it) stays TT_Earth, the
    inside; earth the sky can see becomes TT_Ground, the outside. Inside earth that looks at the back of a surface
    is buried in other earth: MAT_HIDDEN"""
    tree = BVHTree.FromBMesh(bm)
    for f in bm.faces:
        if f.material_index != MAT_EARTH:
            continue
        p = f.calc_center_median() + f.normal * 0.02
        up = tree.ray_cast(p, Z, 30.0)[0]
        down = tree.ray_cast(p, -Z, 30.0)[0]
        if up is None or down is None:
            f.material_index = MAT_GROUND
            continue
        hit = tree.ray_cast(p, f.normal, 30.0)
        if hit[0] is not None and hit[1].dot(f.normal) > 0:
            f.material_index = MAT_HIDDEN


def refine(bm):
    """The inside's edges halved until none is longer than REFINE"""
    for _ in range(8):
        long = [e for e in bm.edges if e.calc_length() > REFINE and any(f.material_index == MAT_EARTH for f in e.link_faces)]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')


def keep_exact(v, keep):
    """0 at an opening (and up to FADE_START in from it), 1 from FADE_END in"""
    w = 1.0
    for pos, out in keep:
        rel = v - pos
        along = rel.dot(out)
        side = (rel - out * along).length
        if side > 3.5 or along > 0.5:
            continue
        w = min(w, smooth(min(max((-along - FADE_START) / (FADE_END - FADE_START), 0.0), 1.0)))
    return w


def roughen(bm, keep):
    """The inside pushed along its normal by noise; the floor much less, the openings not at all"""
    bm.normal_update()
    moves = []
    for v in bm.verts:
        inside = [f for f in v.link_faces if f.material_index == MAT_EARTH]
        if not inside or any(f.material_index == MAT_WOOD for f in v.link_faces):
            continue
        w = keep_exact(v.co, keep)
        if w <= 0:
            continue
        n = Vector()
        for f in inside:
            n += f.normal * f.calc_area()
        if n.length < 1e-9:
            continue
        n.normalize()
        amp = WALL_AMP + (FLOOR_AMP - WALL_AMP) * max(0.0, n.z)
        c = v.co
        # big swells, lumps, and grit
        h = (0.55 * noise.noise(c * 0.55) + 0.3 * noise.noise(c * 1.5 + Vector((5.3, 1.7, 9.1)))
             + 0.15 * noise.noise(c * 4.0 + Vector((2.9, 7.7, 3.1))))
        if n.z < -0.3 and h < 0:
            h *= ROOF_IN
        moves.append((v, n * (h * amp * w)))
    for v, d in moves:
        v.co += d
    bm.normal_update()


def export(piece):
    objs = finish(piece)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, piece.name + '.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'}, use_mesh_modifiers=True,
                             mesh_smooth_type='EDGE', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
    tris = len(objs[0].data.polygons)
    for o in objs:
        data = o.data
        bpy.data.objects.remove(o)
        if data and data.users == 0:
            bpy.data.meshes.remove(data)
    print(f'{piece.name}: {tris} triangles, {len(piece.sockets)} openings -> {path}')


FINE = [lambda: build_curve(5), lambda: build_curve(10), lambda: build_curve(15), lambda: build_straight_short(1), lambda: build_straight_short(2)]

BUILDERS = [build_straight, build_straight_wide, build_straight_narrow, build_turn, build_turn_wide, lambda: build_dogleg('L'), lambda: build_dogleg('R'), build_slope, build_end,
            build_junction, build_room, build_entry_horizontal, build_entry_incline]


def preview():
    """Every piece in a row in collection TT_Preview, for looking at"""
    col = bpy.data.collections.get('TT_Preview')
    if col:
        for o in list(col.objects):
            bpy.data.objects.remove(o)
    else:
        col = bpy.data.collections.new('TT_Preview')
        bpy.context.scene.collection.children.link(col)
    x = 0.0
    for build in FINE + BUILDERS:
        piece = build()
        objs = finish(piece, Vector((x, 0, 0)), col)
        for o in objs:
            if o.name.startswith('UTM_'):
                o.hide_set(True)
        width = objs[0].dimensions.x
        x += width + 4.0
    print('preview built')


if EXPORT:
    # The preview's objects carry the same names; left in place, the exported ones would come out as "..._LOD0.001"
    old = bpy.data.collections.get('TT_Preview')
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(old)
    # TT_ONLY=fine exports only the fine-adjustment pieces (curves, short straights): the others are already imported
    import os
    only = os.environ.get('TT_ONLY', '')
    for build in (FINE if only == 'fine' else FINE + BUILDERS):
        export(build())
    print('exported')
else:
    preview()
