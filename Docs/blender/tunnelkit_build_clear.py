"""Tunnel test kit (TT_), REDESIGN builder ("clear"): no wood, rounded floor-wall junction, new shared joint rings, variation in
width and height between the joints, three variants per shape. Own copy-and-rewrite of tunnelkit_build.py (standing) and
tunnelkit_build_cp.py (crouch / prone); both stay untouched. Doc: Docs/TunnelKit_Clearance.md, brief: TunnelKit_Redesign_Brief.md.

Run (headless):  blender --factory-startup -b --python Docs/blender/tunnelkit_build_clear.py
Environment (all optional):
  CL_OUT_DIR=<folder>   where the FBX go (default Docs/blender/redesign_staging/full, OUTSIDE Assets; CL_install.py copies them in)
  CL_ONLY=a,b           only pieces whose name contains one of these strings (default: the whole set, 55 pieces)
In a live Blender: CL_NORUN = True ; exec(open(...).read())  gives the functions (preview script does this).

Construction rules kept from the old builders: every piece is a CLOSED solid of earth (inner surface, outer shell SHELL m further
out, ends closed), every opening carries a sleeve reaching SLEEVE m past the joint over the neighbour and SLEEVE m back over the
piece's own end (joined pieces' sleeves overlap), materials TT_Earth (inside) and TT_Ground (outside), triangles only, LOD0 +
UTM_ collider (the same mesh), empties "1", "2", ... = memory points at mp_height above the floor, +Z (the arrow) out of the piece.
What is new:
  * NO WOOD: no timber frames, no TT_Wood material (the FBX has two material slots: TT_Earth, TT_Ground)
  * one profile function mk_profile(hw, H, r): flat floor, a quarter-circle FILLET (r) into straight walls, an elliptical shoulder
    and a flat crown 0.6 m wide (so the clear height holds over the centre +-0.3 m). 24 points whatever the size, so any two
    profiles morph point for point
  * RINGS (the shared opening of every piece of a class): S 1.6 x 2.2 (fillet 0.30), C 1.4 x 1.64 (0.15), P 1.2 x 0.965 (0.10)
  * VARIATION: inside a piece the width and height follow the variant's curve, blended back to the ring over the first 0.5 m (height)
    and 0.5 .. 1.5 m (width) from each end, so the joint zone is exactly the ring. On turns the extra width goes to the OUTSIDE of the
    bend (the inside wall stays where the ring puts it: the tight radius 1.8 holds)
  * NOISE only moves the surface AWAY from the void (the clear size is a guarantee, the lumps only add)
"""
import bpy, bmesh, math, os, json, hashlib
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
OUT = os.environ.get('CL_OUT_DIR', os.path.join(ADDON, 'Docs', 'blender', 'redesign_staging', 'full'))
EXPORT = globals().get('CL_EXPORT', True)
ONLY = [s for s in os.environ.get('CL_ONLY', '').split(',') if s]

SHELL = 0.6          # earth round the opening
SLEEVE = 0.25        # sleeve reach either side of a joint
SLEEVE_IN = 0.1      # how far the sleeve sinks into the shell
SLEEVE_T = 0.3       # sleeve thickness
TURN_RADIUS = 1.8    # plan geometry: unchanged (the generator's grid depends on it)
UV_EARTH = 1 / 2.2 / 16
REFINE = 0.25
FADE_START = 0.4     # nothing moves within this of an opening, full from FADE_END
FADE_END = 1.4
Z = Vector((0, 0, 1))
MAT_EARTH, MAT_GROUND, MAT_HIDDEN, MAT_STEP = 0, 1, 2, 3      # hidden / step: only while building (earth buried in earth; stairs, no noise), TT_Earth in the end
EARTH_COL = (1.0, 1.0, 1.0, 1.0)
GROUND_COL = (0.0, 1.0, 1.0, 1.0)

# ---------------------------------------------------------------------------------------------------------------------
# Size classes: the ring (joint opening) and the earth's roughness. Heights of C and P are the old ones (fixed): the earth
# profile IS the clear size now (no timber lining to subtract).
CLASSES = {
    'S': dict(hw=0.80, H=2.20, r=0.30, mp=1.00, wall_amp=0.12, floor_amp=0.03),
    'C': dict(hw=0.70, H=1.64, r=0.15, mp=0.80, wall_amp=0.10, floor_amp=0.020),
    'P': dict(hw=0.60, H=0.965, r=0.10, mp=0.475, wall_amp=0.05, floor_amp=0.012),
}

# Variants of a shape: width / height in the middle (clear, before the noise adds anything), the wobble about it, which side of a
# bend gets the extra width (1: all to the outside). Standing: standard, A (neck, one player), C (wide, up to 3.0 x 3.2)
VARIANTS = {
    ('S', ''):  dict(w=1.90, ww=0.20, h=2.50, hw_=0.15),
    ('S', 'A'): dict(w=1.32, ww=0.0, h=2.38, hw_=0.05, noise=0.0),     # a TRUE neck: no noise at all (user decision)
    ('S', 'C'): dict(w=2.60, ww=0.25, h=2.85, hw_=0.20),
    ('C', ''):  dict(w=1.55, ww=0.12, h=1.64, hw_=0.0),
    ('P', ''):  dict(w=1.32, ww=0.10, h=0.965, hw_=0.0),
}
W_EASE, W_RAMP = 0.5, 1.0     # width: the ring for the first 0.5 m, then growing over 1.0 m
H_RAMP = 0.5                  # height: reaches the body height at 0.5 m
WOBBLE = 3.1                  # m, wavelength of the slow wobble about the middle value


# ---------------------------------------------------------------------------------------------------------------------
# Profiles

def mk_profile(hw, H, r, nf=4, na=6):
    """Closed counter-clockwise profile (x across, z up from the floor): flat floor, quarter-circle fillet of radius r into the wall,
    straight wall, elliptical shoulder, flat crown. Always 2*(nf+1) + 2*na + 2 = 24 points (nf 4, na 6)"""
    cr = min(0.3, hw * 0.45)                 # half width of the flat crown
    zws = r + 0.55 * (H - r)                 # where the shoulder starts
    right = []
    for k in range(nf + 1):                  # fillet, centre (hw - r, r), from the floor (angle -90) to the wall (0)
        a = math.radians(-90 + 90 * k / nf)
        right.append((hw - r + r * math.cos(a), r + r * math.sin(a)))
    right.append((hw, zws))
    for i in range(1, na + 1):               # shoulder: quarter ellipse from (hw, zws) to the crown edge (cr, H)
        a = math.radians(90 * i / na)
        right.append((cr + (hw - cr) * math.cos(a), zws + (H - zws) * math.sin(a)))
    left = [(-x, z) for x, z in reversed(right)]
    return right + left


def offset(profile, d):
    """The closed profile pushed out by d (negative: in), corner by corner along the bisector"""
    n = len(profile)
    pts = [Vector((p[0], p[1])) for p in profile]
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (b - a).normalized()
        e2 = (c - b).normalized()
        n1 = Vector((e1.y, -e1.x))
        n2 = Vector((e2.y, -e2.x))
        bis = n1 + n2
        if bis.length < 1e-6:
            bis = n1
        bis.normalize()
        k = d / max(bis.dot(n1), 0.2)
        out.append((b.x + bis.x * k, b.y + bis.y * k))
    return out


def ring_profile(cls):
    c = CLASSES[cls]
    return mk_profile(c['hw'], c['H'], c['r'])


def smooth(t):
    return t * t * (3 - 2 * t)


def d_smooth(t):
    return 6 * t * (1 - t)


def clamp01(t):
    return min(max(t, 0.0), 1.0)


# ---------------------------------------------------------------------------------------------------------------------
# Sweeping per-sample profiles along a path into a closed solid

def frame_at(pos, tangent):
    t = Vector((tangent.x, tangent.y, 0)).normalized()
    return pos, t.cross(Z).normalized()


def ring(pos, right, profile):
    return [pos + right * p[0] + Z * p[1] for p in profile]


def sweep(bm, samples, prof_a, prof_b, mat=0, shifts=None):
    """samples: [(pos, tangent)]; the solid between profile a (inside) and b (outside), ends closed. prof_a / prof_b: one profile
    (a list of points) or one per sample. shifts: sideways offset of every ring (along 'right')"""
    rings_a, rings_b = [], []
    per = isinstance(prof_a[0], list)
    for i, (pos, tan) in enumerate(samples):
        p, right = frame_at(pos, tan)
        if shifts:
            p = p + right * shifts[i]
        rings_a.append([bm.verts.new(v) for v in ring(p, right, prof_a[i] if per else prof_a)])
        rings_b.append([bm.verts.new(v) for v in ring(p, right, prof_b[i] if per else prof_b)])
    n = len(rings_a[0])
    faces = []
    for i in range(len(samples) - 1):
        for rings in (rings_a, rings_b):
            for k in range(n):
                k2 = (k + 1) % n
                faces.append(bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])))
    for i in (0, len(samples) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append(bm.faces.new((rings_a[i][k], rings_a[i][k2], rings_b[i][k2], rings_b[i][k])))
    for f in faces:
        f.material_index = mat
    return faces


def prism(bm, samples, profile, mat=0):
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
# Paths: lists of (position, horizontal tangent). Same plan geometry as tunnelkit_build.py

def path_straight(length, step=0.25, start=Vector((0, 0, 0)), direction=Vector((0, 1, 0))):
    n = max(1, math.ceil(length / step))
    return [(start + direction * (length * i / n), direction.copy()) for i in range(n + 1)]


def path_arc(radius, degrees=90, steps=18):
    out = []
    for i in range(steps + 1):
        a = math.radians(degrees) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    return out


def path_chicane(radius, across, shift_right=True, steps=14):
    out = []
    for i in range(steps + 1):
        a = math.radians(90) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    n = max(1, math.ceil(across / 0.5))
    for i in range(1, n + 1):
        out.append((Vector((radius + across * i / n, radius, 0)), Vector((1, 0, 0))))
    for i in range(1, steps + 1):
        b = math.radians(90) * i / steps
        out.append((Vector((radius + across + radius * math.sin(b), 2 * radius - radius * math.cos(b), 0)), Vector((math.cos(b), math.sin(b), 0))))
    if not shift_right:
        out = [(Vector((-p.x, p.y, p.z)), Vector((-t.x, t.y, t.z))) for p, t in out]
    return out


def path_slope(length, rise, steps=16):
    return [(Vector((0, length * i / steps, rise * smooth(i / steps))), Vector((0, 1, 0))) for i in range(steps + 1)]


# ---------------------------------------------------------------------------------------------------------------------
# Pieces

class Piece:
    def __init__(self, name, cls):
        self.name = name
        self.cls = cls
        self.bm = bmesh.new()
        self.sockets = []      # (floor centre, outward, class)
        self.fades = []
        self.noise = 1.0       # 0: smooth walls (the _A necks)
        self.sculpt = None     # entries: shapes the finished mesh (bm) further, after the inside's noise
        self.smooth_ground = False     # entries: the outside is smooth-shaded too

    def socket(self, pos, outward, cls=None):
        cls = cls or self.cls
        self.sockets.append((pos.copy(), Vector((outward.x, outward.y, 0)).normalized(), cls))
        out = Vector((outward.x, outward.y, 0)).normalized()
        inner = ring_profile(cls)
        sleeve = [(pos - out * SLEEVE, out), (pos + out * SLEEVE, out)]
        sweep(self.bm, sleeve, offset(inner, SHELL - SLEEVE_IN), offset(inner, SHELL + SLEEVE_T), mat=MAT_EARTH)


def seed_of(name):
    return int(hashlib.md5(name.encode()).hexdigest()[:6], 16) / 0xFFFFFF


def arc_lengths(samples):
    d = [0.0]
    for i in range(1, len(samples)):
        d.append(d[-1] + (samples[i][0] - samples[i - 1][0]).length)
    return d


def variation(piece, samples, variant, bend_bias=0.0):
    """Per-sample (hw, H, shift): the ring at both ends, the variant's curve inside"""
    c = CLASSES[piece.cls]
    v = VARIANTS[(piece.cls, variant)]
    dist = arc_lengths(samples)
    L = dist[-1]
    ramp = max(0.25, min(W_RAMP, L / 2 - W_EASE))
    ph = seed_of(piece.name) * 2 * math.pi
    # sign of the bend at each sample (+1 turning left, -1 right), smoothed over ~0.8 m: the extra width goes to the outside
    sig = []
    for i in range(len(samples)):
        j0, j1 = max(0, i - 1), min(len(samples) - 1, i + 1)
        t0, t1 = samples[j0][1], samples[j1][1]
        sig.append(t0.x * t1.y - t0.y * t1.x)
    sig = [max(-1.0, min(1.0, x * 12)) for x in sig]
    out = []
    for i, s in enumerate(dist):
        e = min(s, L - s)
        kw = smooth(clamp01((e - W_EASE) / ramp))
        kh = smooth(clamp01(e / H_RAMP))
        w_t = v['w'] + v['ww'] * math.sin(2 * math.pi * s / WOBBLE + ph)
        h_t = v['h'] + v['hw_'] * math.sin(2 * math.pi * s / WOBBLE + ph + 2.1)
        hw = c['hw'] + kw * (w_t / 2 - c['hw'])
        # height: up to the body minimum (2.32) within the first 0.5 m (the hard rule), the rest of the way over the width's ramp
        hb = min(2.32, v['h'] - v['hw_']) if c['H'] > 2.0 else h_t
        H = c['H'] + kh * (hb - c['H']) + kw * (h_t - hb)
        # extra width to the outside of a bend: shift the section by bias * (hw - ring hw), away from the centre of the bend
        k = 0
        if bend_bias:
            lo, hi = max(0, i - 3), min(len(samples) - 1, i + 3)
            k = sum(sig[lo:hi + 1]) / (hi - lo + 1)
        out.append((hw, H, k * bend_bias * (hw - c['hw'])))
    return out


def corridor(piece, samples, variant='', bend_bias=0.0):
    c = CLASSES[piece.cls]
    piece.noise = VARIANTS[(piece.cls, variant)].get('noise', 1.0)
    var = variation(piece, samples, variant, bend_bias)
    inners = [mk_profile(hw, H, c['r']) for hw, H, _ in var]
    outers = [offset(p, SHELL) for p in inners]
    # shift along 'right'. k is negative in a right-hand bend (whose inside is on the right), so the section moves LEFT = outwards
    sweep(piece.bm, samples, inners, outers, mat=MAT_EARTH, shifts=[sh for _, _, sh in var])
    piece.socket(samples[0][0], -samples[0][1])
    piece.socket(samples[-1][0], samples[-1][1])
    return var


def name_for(base, cls, variant):
    n = 'TT_' + ({'S': '', 'C': 'C_', 'P': 'P_'}[cls]) + base
    return n + ('_' + variant if variant else '')


def build_straight(length, cls='S', variant='', name=None):
    p = Piece(name or name_for('Straight_%d' % length, cls, variant), cls)
    corridor(p, path_straight(float(length)), variant)
    return p


def build_curve(angle, cls='S', variant=''):
    p = Piece(name_for('Curve_%d' % angle, cls, variant), cls)
    corridor(p, path_arc(4.0 / math.radians(angle), degrees=angle, steps=16), variant, bend_bias=1.0)
    return p


def build_turn(cls='S', variant=''):
    p = Piece(name_for('Turn90', cls, variant), cls)
    corridor(p, path_arc(TURN_RADIUS, steps=24), variant, bend_bias=1.0)
    return p


def build_turn_wide():
    """TT_Turn90_Wide (the old name stays): radius 3.0 like before, the C variant's dimensions. TT_Turn90_C is the tight radius 1.8"""
    p = Piece('TT_Turn90_Wide', 'S')
    corridor(p, path_arc(3.0, steps=30), 'C', bend_bias=1.0)
    return p


def build_dogleg(side, cls='S', variant=''):
    p = Piece(name_for('Dogleg_' + side, cls, variant), cls)
    corridor(p, path_chicane(TURN_RADIUS, 1.0, side == 'R'), variant, bend_bias=1.0)
    return p


def build_slope(cls='S', variant=''):
    rise = {'S': 1.2, 'C': 1.0, 'P': 0.8}[cls]
    p = Piece(name_for('Slope', cls, variant), cls)
    corridor(p, path_slope(4.0, rise), variant)
    return p


def build_end(cls='S'):
    """Dead end: the ring tunnel, then a plug. Walk: 0.8 m deep as before; crouch / prone 1.6 m"""
    p = Piece(name_for('End', cls, ''), cls)
    void = 0.8 if cls == 'S' else 1.6
    ring_in = ring_profile(cls)
    samples = path_straight(void + 0.4, step=0.6 if cls == 'S' else 0.5)
    sweep(p.bm, samples, ring_in, offset(ring_in, SHELL), mat=MAT_EARTH)
    prism(p.bm, path_straight(0.6, step=0.6, start=Vector((0, void, 0))), offset(ring_in, SHELL - 0.05), mat=MAT_EARTH)
    p.socket(samples[0][0], -samples[0][1])
    return p


# Mouth flare (extra width, extra height at the mouth) and how much the inside swells away from the joint (width, height)
ENTRY = {'S': (0.5, 0.2, 0.12, 0.15), 'C': (0.5, 0.30, 0.10, 0.04), 'P': (0.6, 0.50, 0.10, 0.04)}


# ---------------------------------------------------------------------------------------------------------------------
# Rounded, terrain-friendly mouths (the entries)
LIP_R = 0.25          # radius of the mouth's rim (the shell is 0.6 thick: what is left flat at the very front is 0.10)
SKIRT = 0.45          # how much wider the outside gets towards its foot: sloped sides, no vertical wall standing on the ground
RAKE_TOP = 0.5        # the mouth leans back: its top this far behind the floor's front edge
RAKE_LEN = 2.5        # the lean has faded out this far in
LUMP = 0.16           # lumps on the outside (only ever outwards)
GROUND_REFINE = 0.28
SIDE_OUTER = 1        # face layer 'side': an entry's outside, always TT_Ground
SIDE_INNER = 2        # and a mouth's inside, always TT_Earth (split_inside would zigzag along the open rim)
SIDE_COLLAR = 3       # the incline's rock collar, always TT_Ground


def refine_ground(bm, near, size=None):
    """The outside's edges halved until none inside 'near' is longer than size (GROUND_REFINE), so it can take a shape"""
    size = size or GROUND_REFINE
    side = bm.faces.layers.int.get('side')
    for _ in range(8):
        long = [e for e in bm.edges if e.calc_length() > size and any(f.material_index == MAT_GROUND for f in e.link_faces)
                and not (side and any(f[side] == SIDE_COLLAR for f in e.link_faces))      # the collar is built fine enough
                and near((e.verts[0].co + e.verts[1].co) * 0.5)]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')


def mark_outer(bm, samples, n, front_cap=False, inner=False):
    """Tags a fresh sweep's outer faces (face layer 'side'). TT_Ground alone doesn't tell them apart: the inside of an open shaft
    is TT_Ground too. sweep's face order: per segment the inner ring then the outer ring, then the two end caps"""
    side = bm.faces.layers.int.new('side')
    bm.faces.ensure_lookup_table()
    segs = len(samples) - 1
    for i in range(segs):
        for k in range(n):
            bm.faces[i * 2 * n + n + k][side] = SIDE_OUTER
            if inner:
                bm.faces[i * 2 * n + k][side] = SIDE_INNER
    if front_cap:
        for k in range(n):
            bm.faces[segs * 2 * n + k][side] = SIDE_OUTER


def lumps(bm, weight):
    """Noise on the outside, outwards only (it only adds earth). weight(co): 0 .. 1. Only verts whose faces are all tagged outer"""
    side = bm.faces.layers.int.get('side')
    bm.normal_update()
    moves = []
    for v in bm.verts:
        if not v.link_faces or any(f.material_index != MAT_GROUND or f[side] != SIDE_OUTER for f in v.link_faces):
            continue
        w = weight(v.co)
        if w <= 0:
            continue
        co = v.co
        h = 0.65 * noise.noise(co * 0.9 + Vector((3.1, 8.2, 1.4))) + 0.35 * noise.noise(co * 2.3 + Vector((7.4, 0.6, 4.8)))
        moves.append((v, v.normal * (clamp01(0.5 + 0.5 * h / 0.6) * LUMP * w)))
    for v, d in moves:
        v.co += d
    bm.normal_update()


# The horizontal entries' mound: a rounded mass of rock round the opening, to cover the terrain hole and bed into the ground.
# Radius per class: about 1.5 x the piece's own height, so the mound is about 3 x it across. It ends before the joint: past it
# the next piece's tunnel starts (turns, doglegs), which a mass there would block
MOUND_R = {'S': 6.4, 'C': 5.5, 'P': 4.5}
MOUND_MID = 2.2       # the mound is widest this far in from the mouth
MOUND_END = 4.7       # and back to the plain shell here
MOUND_ROUND = 2.8     # its profile along the tunnel: (1 - d^p)^(1/p), 2 an ellipse, more: fuller
MOUND_ARC = 8.0       # degrees: the profile's points are no further apart than this, seen from the mound's centre
MOUND_REFINE = 0.36
MOUND_UNEVEN = 0.2    # the radius wanders this much (share of it) round the outline: not a clean ball


def mound_shape(y):
    """0 .. 1: how far out towards the mound's radius the outside is at y"""
    d = (MOUND_MID - y) / MOUND_MID if y < MOUND_MID else (y - MOUND_MID) / (MOUND_END - MOUND_MID)
    return (1 - clamp01(d) ** MOUND_ROUND) ** (1 / MOUND_ROUND)


def edge_cuts(profile, zc):
    """How many pieces each edge of the profile needs for MOUND_ARC"""
    ang = [math.atan2(z - zc, x) for x, z in profile]
    out = []
    for i in range(len(profile)):
        d = abs((ang[(i + 1) % len(ang)] - ang[i] + math.pi) % (2 * math.pi) - math.pi)
        out.append(max(1, math.ceil(math.degrees(d) / MOUND_ARC)))
    return out


def densify(profile, cuts):
    out = []
    for i, n in enumerate(cuts):
        a, b = profile[i], profile[(i + 1) % len(profile)]
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    return out


def rock_bumps(bm, mouth_hw, mouth_h, seed):
    """The mound's surface: warped swells, rounded blocks with creases between them, grit. It starts small right by the rim, only
    adds earth where the mound is thin, and stops before the joint, so it can't break into the tunnel"""
    side = bm.faces.layers.int.get('side')
    bm.normal_update()
    off = Vector((seed * 37.1, seed * 11.3, seed * 71.9))
    moves = []
    for v in bm.verts:
        if not v.link_faces or any(f.material_index != MAT_GROUND or f[side] != SIDE_OUTER for f in v.link_faces):
            continue
        co = v.co
        away = math.hypot(max(0.0, abs(co.x) - mouth_hw), max(0.0, co.z - mouth_h, -co.z))      # from the opening
        w = smooth(clamp01((away - 0.08) / 0.55)) * (1 - smooth(clamp01((co.y - 4.1) / 0.6)))
        if w <= 0:
            continue
        p = co + off
        q = p + Vector((noise.noise(p * 0.35), noise.noise(p * 0.35 + Vector((19.1, 3.3, 7.7))), noise.noise(p * 0.35 + Vector((4.2, 27.5, 13.9))))) * 0.9
        cell = noise.voronoi(q * 0.8)[0]
        block = min(cell[1] - cell[0], 0.5) / 0.5 - 0.6                 # rounded tops, sharp creases
        h = (0.55 * noise.noise(q * 0.33) + 0.22 * block + 0.17 * noise.noise(q * 1.4) + 0.06 * noise.noise(p * 3.6) + 0.08) * w
        thin = 1 - smooth(clamp01((away - 0.5) / 0.8))                   # by the opening the mound is thin: only ever add there
        add = max(0.0, 0.2 + 0.28 * noise.noise(q * 1.4 + Vector((8.1, 2.2, 6.4))) + 0.2 * block) * w
        h = h + (add - h) * thin
        moves.append((v, v.normal * h))
    for v, d in moves:
        v.co += d
    bm.normal_update()


def make_mouth_sculpt(mouth_hw, mouth_h, seed):
    def sculpt(bm):
        refine_ground(bm, lambda c: c.y < MOUND_END + 0.1, MOUND_REFINE)
        rock_bumps(bm, mouth_hw, mouth_h, seed)
        for v in bm.verts:                     # the front leans back: the top behind the floor's front edge
            c = v.co
            fall = 1 - smooth(clamp01(c.y / RAKE_LEN))
            if fall > 0:
                c.y += RAKE_TOP * clamp01(c.z / 2.9) ** 1.3 * fall
        bm.normal_update()
    return sculpt


def build_entry_horizontal(cls='S'):
    """A mouth into a hillside: the opening flares out over its first 1.2 m; pivot at the mouth's floor centre; no timber.
    A rounded rim, a mouth leaning back and a big bumpy mound of rock round it (see MOUND_R)"""
    p = Piece(name_for('Entry_Horizontal', cls, ''), cls)
    c = CLASSES[cls]
    fw, fh, sw, sh = ENTRY[cls]
    R = MOUND_R[cls]

    def size(y):
        """The nominal opening at y (without the rim's rounding)"""
        t = min(y / 1.2, 1.0)
        inner = smooth(clamp01((5.0 - y - 0.5) / 1.5))
        hw = c['hw'] * max(1.0 + fw * (1 - smooth(t)), 1.0 + sw * inner)
        H = c['H'] * max(1.0 + fh * (1 - smooth(t)), 1.0 + sh * inner)
        if cls == 'S':                                    # the walk height rule near the joint: 2.32 within 0.5 m
            H = max(H, c['H'] + smooth(clamp01((5.0 - y) / H_RAMP)) * (2.32 - c['H']))
        return hw, H

    # stations: every 0.25 m, finer through the rim and where the mound curves in at its two ends
    ys = [s[0].y for s in path_straight(5.0, step=0.25)]
    ys += [LIP_R * (1 - math.cos(math.radians(a))) for a in (15, 30, 45, 60, 75, 90)]
    ys += [MOUND_MID * (1 - math.cos(math.radians(a))) for a in range(10, 90, 10)]
    ys += [MOUND_MID + (MOUND_END - MOUND_MID) * math.sin(math.radians(a)) for a in range(10, 91, 10)]
    stations = []
    for y in sorted(ys):
        if not stations or y - stations[-1] > 0.008:
            stations.append(y)
    stations[-1] = 5.0

    mouth_h = size(0.0)[1]
    zc = mouth_h / 2                                      # the mound's centre: the middle of the opening
    cuts = edge_cuts(mk_profile(*size(0.0), c['r']), zc)
    seed = seed_of(p.name)
    samples, inners, outers = [], [], []
    for y in stations:
        hw, H = size(y)
        s = math.sin(math.acos(1 - min(y / LIP_R, 1.0)))  # through the rim a quarter circle (0 .. 1)
        flare_in = LIP_R * (1 - s)
        nominal = densify(mk_profile(hw, H, c['r']), cuts)
        inner = densify(mk_profile(hw + flare_in, H + flare_in, c['r']), cuts)       # the floor stays flat
        # through the rim the outside is measured from the flared inside, so the two can never cross
        shell = offset(inner, SHELL - 2 * flare_in) if flare_in > 0 else offset(nominal, SHELL)
        k = mound_shape(y)
        outer = []
        for (x, z), (ox, oz) in zip(nominal, shell):
            a = math.atan2(z - zc, x)
            r = R * (1.06 + MOUND_UNEVEN * noise.noise(Vector((math.cos(a) * 1.6 + seed * 31, math.sin(a) * 1.6 + seed * 17, y * 0.3))))
            outer.append((ox + (r * math.cos(a) - ox) * k, oz + (zc + r * math.sin(a) - oz) * k))
        samples.append((Vector((0, y, 0)), Vector((0, 1, 0))))
        inners.append(inner)
        outers.append(outer)
    sweep(p.bm, samples, inners, outers, mat=MAT_EARTH)
    mark_outer(p.bm, samples, len(inners[0]), front_cap=True, inner=True)      # the front cap: the rim's flat
    p.sculpt = make_mouth_sculpt(size(0.0)[0] + LIP_R, mouth_h + LIP_R, seed)
    p.smooth_ground = True
    p.fades.append((Vector((0, 0, 0)), Vector((0, -1, 0))))       # the mouth gets no memory point, but its wall stays exact
    p.socket(samples[-1][0], samples[-1][1])
    return p


SHAFT_H = 1.55
SHAFT_W = 1.25


# The incline's rock collar: the horizontal entries' rugged mass, laid flat round the hole. About 3 x the piece's depth across.
# In the piece's own space: ground at z 0, the open hole x +-1, y -1.85 .. 1.65, the stairs come out towards +y
COLLAR_R = 7.2        # from the hole's middle to the collar's rim (wanders by MOUND_UNEVEN)
COLLAR_RISE = 1.35    # how high the rock stands round the hole, before the lumps (it wanders 0.5 .. 1.5 times this)
COLLAR_IN = (1.3, -2.5, 1.75)     # the inner edge: half width, back end, front end (the shaft's void stays inside it)


def collar_noise(p):
    """The same warped swells, rounded blocks and grit as the mounds'"""
    q = p + Vector((noise.noise(p * 0.35), noise.noise(p * 0.35 + Vector((19.1, 3.3, 7.7))), noise.noise(p * 0.35 + Vector((4.2, 27.5, 13.9))))) * 0.9
    cell = noise.voronoi(q * 0.8)[0]
    block = min(cell[1] - cell[0], 0.5) / 0.5 - 0.6
    return 0.75 * noise.noise(q * 0.33) + 0.38 * block + 0.22 * noise.noise(q * 1.4) + 0.08 * noise.noise(p * 3.6) + 0.12


def incline_collar(bm, seed, around=112, rings=24):
    """A closed ring of rock: a height field on top, a flat-ish underside. Flat where the stairs come out; shallow behind the
    hole, where the next piece's tunnel runs underneath (its roof is at about z -0.55)"""
    side = bm.faces.layers.int.get('side') or bm.faces.layers.int.new('side')
    half, back_y, front_y = COLLAR_IN
    cy = (back_y + front_y) / 2
    hh = (front_y - back_y) / 2
    off = Vector((seed * 37.1, seed * 11.3, seed * 71.9))
    top, bottom = [], []
    for i in range(around):
        a = 2 * math.pi * i / around
        ca, sa = math.cos(a), math.sin(a)
        r_in = (abs(ca / half) ** 6 + abs(sa / hh) ** 6) ** (-1 / 6)          # a rounded rectangle round the hole
        r_out = COLLAR_R * (1.04 + MOUND_UNEVEN * noise.noise(Vector((ca * 1.6 + seed * 31, sa * 1.6 + seed * 17, 0.5))))
        rise = COLLAR_RISE * (1.0 + 0.9 * noise.noise(Vector((ca * 2.1 + seed * 5, sa * 2.1 + seed * 9, 3.3))))
        rise = max(0.5 * COLLAR_RISE, min(1.5 * COLLAR_RISE, rise))
        column_top, column_bottom = [], []
        for j in range(rings + 1):
            s = (j / rings) ** 1.15
            r = r_in + (r_out - r_in) * s
            x, y = r * ca, cy + r * sa
            way_out = smooth(clamp01((y - 0.4) / 1.4)) * (1 - smooth(clamp01((abs(x) - 1.5) / 1.8)))
            behind = smooth(clamp01((-0.5 - y) / 1.5))
            hump = math.sin(math.pi * clamp01(s / 0.8)) ** 0.8
            sink = -1.1 + 0.9 * behind                                      # where the rim ends up: buried
            z = 0.05 + rise * hump * (1 - way_out) + sink * smooth(clamp01((s - 0.62) / 0.38))
            w = smooth(clamp01(s / 0.16)) * (1 - way_out) * (1 - 0.7 * smooth(clamp01((s - 0.85) / 0.15)))
            z += collar_noise(Vector((x, y, 0)) + off) * w
            z += 0.07 * noise.noise(Vector((x * 1.7, y * 1.7, 4.2)) + off) * way_out * smooth(clamp01(s / 0.2))      # not a floor
            z = max(z, -1.4 + 1.2 * behind)                                 # behind: never deep (the tunnel runs underneath)
            low = -1.4 + 0.95 * smooth(clamp01((-0.3 - y) / 1.4))           # the underside: shallow behind
            column_top.append(bm.verts.new((x, y, z)))
            column_bottom.append(bm.verts.new((x, y, min(low, z - 0.25))))
        top.append(column_top)
        bottom.append(column_bottom)
    faces = []
    for i in range(around):
        n = (i + 1) % around
        for j in range(rings):
            faces.append(bm.faces.new((top[i][j], top[i][j + 1], top[n][j + 1], top[n][j])))
            faces.append(bm.faces.new((bottom[i][j], bottom[n][j], bottom[n][j + 1], bottom[i][j + 1])))
        faces.append(bm.faces.new((top[i][0], top[n][0], bottom[n][0], bottom[i][0])))
        faces.append(bm.faces.new((top[i][rings], bottom[i][rings], bottom[n][rings], top[n][rings])))
    for f in faces:
        f.material_index = MAT_GROUND
        f[side] = SIDE_COLLAR


def sculpt_incline(bm):
    """The shaft under the rock collar: sloped lumpy sides, for where the terrain falls away. In the piece's own space: ground
    at z 0"""
    refine_ground(bm, lambda c: c.z > -2.2)
    # the sides slope: wider below the collar, back to the plain shell further down
    bm.normal_update()
    moves = []
    for v in bm.verts:
        c = v.co
        if not v.link_faces or any(f.material_index != MAT_GROUND for f in v.link_faces) or abs(c.x) < 1.3:
            continue
        depth = -c.z
        k = smooth(clamp01((depth - 0.2) / 0.8)) * (1 - smooth(clamp01((depth - 1.4) / 0.9)))
        moves.append((v, math.copysign(SKIRT * k * clamp01((abs(c.x) - 1.3) / 0.25), c.x)))
    for v, dx in moves:
        v.co.x += dx
    lumps(bm, lambda c: (1 - smooth(clamp01((-c.z - 1.8) / 0.8))) * (0.3 + 0.7 * smooth(clamp01(-c.z / 0.4))))
    bm.normal_update()


def build_entry_incline():
    """A 45 degree stair shaft up to the surface, cut level with the ground at RISE; pivot at the hole's centre on the ground. The steps are EARTH now"""
    rise = 4.0
    p = Piece('TT_Entry_Incline', 'S')
    c = CLASSES['S']
    path = path_straight(1.0, step=0.5)
    up = []
    steps = 16
    for i in range(1, steps + 1):
        t = i / steps
        d = (rise + 2.6) * t
        up.append((Vector((0, 1.0 + d, d)), Vector((0, 1, 0))))
    samples = path + up
    profs = []
    for pos, _ in samples:
        k = smooth(clamp01((pos.y - 0.4) / 1.2))
        profs.append(mk_profile(c['hw'] * (1 + (SHAFT_W - 1) * k), c['H'] * (1 + (SHAFT_H - 1) * k), c['r']))
    shell = bmesh.new()
    sweep(shell, samples, profs, [offset(q, SHELL) for q in profs], mat=MAT_EARTH)
    mark_outer(shell, samples, len(profs[0]))
    stairs = bmesh.new()
    n = int(rise / 0.25) + 2
    outline = [(1.0, -0.4)]
    for i in range(n):
        outline.append((1.0 + 0.25 * i, 0.25 * (i + 1)))
        outline.append((1.0 + 0.25 * (i + 1), 0.25 * (i + 1)))
    outline.append((1.0 + 0.25 * n, 0.25 * n - 0.65))
    half = c['hw'] * SHAFT_W - 0.02
    side = [stairs.verts.new((-half, y, z)) for y, z in outline]
    face = stairs.faces.new(side)
    face.material_index = MAT_STEP         # earth steps: keep their edges, the earth's noise isn't for them
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
    hole = Vector((0, 1.0 + rise - 2.1 * SHAFT_H / 2, rise))          # as the old piece: the pivot / sockets stay where they were
    bmesh.ops.translate(p.bm, verts=p.bm.verts[:], vec=-hole)
    p.sockets = [(pos - hole, out, cl) for pos, out, cl in p.sockets]
    incline_collar(p.bm, seed_of(p.name))
    p.sculpt = sculpt_incline
    p.smooth_ground = True
    return p


# ---------------------------------------------------------------------------------------------------------------------
# Chambers (Junction, Room): a box of earth with rounded edges, tunnel holes and a short stub at each door

def to_object(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def chamber(piece, width, depth, height, doors, round_r=0.3):
    """doors: (side, offset along the wall): 'S' (-Y), 'N' (+Y), 'E' (+X), 'W' (-X). The chamber's inner space has all its edges
    rounded (floor to wall too); the door holes start well inside it so the rounded floor edge can't leave a lip across a door"""
    hw, hd = width / 2, depth / 2
    ring_in = ring_profile(piece.cls)
    shell = bmesh.new()
    box(shell, (-hw - SHELL, -hd - SHELL, -SHELL), (hw + SHELL, hd + SHELL, height + SHELL))
    obj = to_object(shell, piece.name + '_tmp_room')
    cutters = []
    inner = bmesh.new()
    box(inner, (-hw, -hd, 0), (hw, hd, height))
    bmesh.ops.bevel(inner, geom=inner.edges[:], offset=round_r, segments=3, profile=0.5, affect='EDGES')
    cutters.append(to_object(inner, piece.name + '_tmp_inner'))
    stubs = []
    for side, along in doors:
        if side == 'S':
            out, base = Vector((0, -1, 0)), Vector((along, -hd, 0))
        elif side == 'N':
            out, base = Vector((0, 1, 0)), Vector((along, hd, 0))
        elif side == 'E':
            out, base = Vector((1, 0, 0)), Vector((hw, along, 0))
        else:
            out, base = Vector((-1, 0, 0)), Vector((-hw, along, 0))
        hole = bmesh.new()
        cut_profile = [(x, max(z, 0.0)) for x, z in offset(ring_in, 0.04)]
        prism(hole, [(base - out * (round_r + 0.25), out), (base + out * (SHELL + 0.3), out)], cut_profile)
        cutters.append(to_object(hole, piece.name + '_tmp_hole'))
        stubs.append((base + out * (SHELL - 0.1), base + out * (SHELL + 0.6), out))
    for cu in cutters:
        m = obj.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = cu
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    for cu in cutters:
        bpy.data.objects.remove(cu)
    bpy.data.objects.remove(obj)
    piece.bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    outer = offset(ring_in, SHELL)
    for a, b, out in stubs:
        sweep(piece.bm, [(a, out), (b, out)], ring_in, outer, mat=MAT_EARTH)
        piece.socket(b, out)


# Junction: chamber width, depth, height, rounding radius, doors. The E and W doors are STAGGERED (their openings do not overlap in
# y, so there is no straight view from one to the other): walk E +1.0 [0.2 .. 1.8] and W -0.9 [-1.7 .. -0.1]. Old walk junction: 3.2 x 3.2 x 2.4,
# doors S 0, E +0.6, W -0.7. The chamber is deeper (y) so the doors stay clear of the rounded corners.
JUNCTION = {
    'S': (3.2, 4.2, 2.8, 0.30, [('S', 0.0), ('E', 1.0), ('W', -0.9)]),
    'C': (2.8, 3.8, 1.9, 0.20, [('S', 0.0), ('E', 0.9), ('W', -0.8)]),
    'P': (2.4, 3.2, 1.15, 0.12, [('S', 0.0), ('E', 0.75), ('W', -0.7)]),
}


def build_junction(cls='S', variant=''):
    p = Piece(name_for('Junction', cls, variant), cls)
    w, d, h, r, doors = JUNCTION[cls]
    chamber(p, w, d, h, doors, r)
    return p


def build_room():
    """6 x 6 m, three staggered doors as before (S -1.5, E +1.5, N +1.8), now 3.0 m high, rounded"""
    p = Piece('TT_Room', 'S')
    chamber(p, 6.0, 6.0, 3.0, [('S', -1.5), ('E', 1.5), ('N', 1.8)], 0.30)
    return p


# Transitions: keys (profile, y where that profile starts to hold); between two different keys the profile morphs (smoothstep).
TRANS_LEN = 3.0
TRANS_KEYS = {
    ('S', 'C'): [('S', 0.0), ('S', 0.9), ('C', 1.8), ('C', 3.0)],
    ('C', 'P'): [('C', 0.0), ('C', 1.0), ('P', 1.8), ('P', 3.0)],
    ('S', 'P'): [('S', 0.0), ('S', 0.55), ('C', 1.25), ('C', 1.75), ('P', 2.45), ('P', 3.0)],
}


def lerp_profile(a, b, t):
    return [(pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t) for pa, pb in zip(a, b)]


def build_trans(a, b):
    keys = TRANS_KEYS[(a, b)]
    small = min((k for k, _ in keys), key=lambda k: CLASSES[k]['H'])      # the noise and the roughness of the smallest class
    p = Piece('TT_Trans_%s_%s' % (a, b), small)
    ys = []
    for (k0, y0), (k1, y1) in zip(keys[:-1], keys[1:]):
        if k0 == k1:
            ys += [y0, y1]
        else:
            n = max(2, int(round((y1 - y0) / 0.1)))
            ys += [y0 + (y1 - y0) * i / n for i in range(n + 1)]
    ys = sorted(set(round(y, 4) for y in ys))
    samples, inners, outers = [], [], []
    for y in ys:
        for (k0, y0), (k1, y1) in zip(keys[:-1], keys[1:]):
            if y0 - 1e-6 <= y <= y1 + 1e-6:
                t = 0.0 if k0 == k1 else smooth((y - y0) / (y1 - y0))
                inner = ring_profile(k0) if k0 == k1 else lerp_profile(ring_profile(k0), ring_profile(k1), t)
                break
        samples.append((Vector((0, y, 0)), Vector((0, 1, 0))))
        inners.append(inner)
        # a steep ramp cuts the earth's thickness by the cosine of its slope: the shell swells over the ramp's middle (0 on the plateaus)
        outers.append(offset(inner, SHELL + 0.25 * 4 * t * (1 - t)))
    sweep(p.bm, samples, inners, outers, mat=MAT_EARTH)
    p.socket(Vector((0, 0, 0)), Vector((0, -1, 0)), a)
    p.socket(Vector((0, TRANS_LEN, 0)), Vector((0, 1, 0)), b)
    return p


# ---------------------------------------------------------------------------------------------------------------------
# Objects, UVs, export

def materials():
    mats = []
    for name, col in (('TT_Earth', (0.46, 0.35, 0.24, 1)), ('TT_Ground', (0.3, 0.45, 0.2, 1))):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = col
        mats.append(m)
    return mats


def split_inside(bm):
    """Earth the sky can see becomes TT_Ground (outside); inside earth that looks at the back of a surface is buried: hidden"""
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
    for _ in range(8):
        long = [e for e in bm.edges if e.calc_length() > REFINE and any(f.material_index == MAT_EARTH for f in e.link_faces)]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')


def keep_exact(v, keep):
    w = 1.0
    for pos, out in keep:
        rel = v - pos
        along = rel.dot(out)
        side = (rel - out * along).length
        if side > 3.5 or along > 0.5:
            continue
        w = min(w, smooth(clamp01((-along - FADE_START) / (FADE_END - FADE_START))))
    return w


def roughen(bm, keep, cls, scale=1.0):
    """The inside pushed along its normal by noise, ONLY away from the void (never into it), the floor much less, the openings not at
    all: the clear size of the profile is a guarantee"""
    c = CLASSES[cls]
    bm.normal_update()
    moves = []
    for v in bm.verts:
        inside = [f for f in v.link_faces if f.material_index == MAT_EARTH]
        if not inside:
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
        amp = (c['wall_amp'] + (c['floor_amp'] - c['wall_amp']) * max(0.0, n.z)) * scale
        co = v.co
        h = (0.55 * noise.noise(co * 0.55) + 0.3 * noise.noise(co * 1.5 + Vector((5.3, 1.7, 9.1)))
             + 0.15 * noise.noise(co * 4.0 + Vector((2.9, 7.7, 3.1))))
        t = clamp01(0.5 + 0.5 * h / 0.7)                 # 0..1, mostly mid
        moves.append((v, -n * (t * amp * w)))              # n points into the void: minus = into the earth
    for v, d in moves:
        v.co += d
    bm.normal_update()


def finish(piece, at=Vector((0, 0, 0)), collection=None):
    bm = piece.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    split_inside(bm)
    side = bm.faces.layers.int.get('side')
    if side:
        for f in bm.faces:
            if f[side] == SIDE_OUTER:
                f.material_index = MAT_GROUND
            elif f[side] == SIDE_INNER:
                f.material_index = MAT_EARTH
            elif f[side] == SIDE_COLLAR:
                f.material_index = MAT_GROUND
    refine(bm)
    if piece.noise > 0:
        roughen(bm, [(s[0], s[1]) for s in piece.sockets] + piece.fades, piece.cls, piece.noise)
    if piece.sculpt:
        piece.sculpt(bm)
        bmesh.ops.dissolve_degenerate(bm, dist=0.001, edges=bm.edges[:])
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')
    for f in bm.faces:
        if f.material_index in (MAT_HIDDEN, MAT_STEP):
            f.material_index = MAT_EARTH
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co[u_ax] * UV_EARTH, co[v_ax] * UV_EARTH)
    col = bm.loops.layers.color.new('Col')
    for f in bm.faces:
        c = EARTH_COL if f.material_index == MAT_EARTH else GROUND_COL
        for l in f.loops:
            l[col] = c
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(60))
    me = bpy.data.meshes.new(piece.name + '_LOD0')
    bm.to_mesh(me)
    bm.free()
    for m in materials():
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = p.material_index == MAT_EARTH or piece.smooth_ground
    coll = collection or bpy.context.scene.collection
    lod = bpy.data.objects.new(piece.name + '_LOD0', me)
    utm = bpy.data.objects.new('UTM_' + piece.name, me.copy())
    utm.data.name = 'UTM_' + piece.name
    objs = [lod, utm]
    for o in objs:
        coll.objects.link(o)
        o.location = at
    for i, (pos, out, cls) in enumerate(piece.sockets):
        e = bpy.data.objects.new(str(i + 1) if collection is None else f'{piece.name}.{i + 1}', None)
        e.empty_display_type = 'SINGLE_ARROW'
        e.empty_display_size = 0.5
        e.location = at + pos + Z * CLASSES[cls]['mp']
        e.rotation_euler = (math.radians(-90), 0, math.atan2(-out.x, out.y))
        coll.objects.link(e)
        objs.append(e)
    return objs


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
    print(f'{piece.name}: {tris} triangles, {len(piece.sockets)} openings -> {path}', flush=True)


# ---------------------------------------------------------------------------------------------------------------------
# What gets built

def full_set():
    """55 pieces: walk (std, A, C for Straight_4, Curve_5/10/15, Turn90, Dogleg_L/R, Slope; std only for Straight_1, 2), Narrow / Wide /
    Turn90_Wide, Junction, Room, End, Entry_Horizontal, Entry_Incline; crouch and prone families (9 each); the three transitions"""
    out = [lambda: build_straight(1), lambda: build_straight(2)]
    for var in ('', 'A', 'C'):
        out.append(lambda var=var: build_straight(4, 'S', var))
        for a in (5, 10, 15):
            out.append(lambda a=a, var=var: build_curve(a, 'S', var))
        out.append(lambda var=var: build_turn('S', var))
        out.append(lambda var=var: build_dogleg('L', 'S', var))
        out.append(lambda var=var: build_dogleg('R', 'S', var))
        out.append(lambda var=var: build_slope('S', var))
    out.append(lambda: build_straight(4, 'S', 'A', name='TT_Straight_Narrow'))
    out.append(lambda: build_straight(5, 'S', 'C', name='TT_Straight_Wide'))
    out.append(build_turn_wide)
    out += [build_junction, build_room, build_end, build_entry_horizontal, build_entry_incline]
    for cls in ('C', 'P'):
        out.append(lambda cls=cls: build_straight(4, cls))
        out.append(lambda cls=cls: build_straight(2, cls))
        out.append(lambda cls=cls: build_turn(cls))
        out.append(lambda cls=cls: build_dogleg('L', cls))
        out.append(lambda cls=cls: build_dogleg('R', cls))
        out.append(lambda cls=cls: build_slope(cls))
        out.append(lambda cls=cls: build_junction(cls))
        out.append(lambda cls=cls: build_end(cls))
        out.append(lambda cls=cls: build_entry_horizontal(cls))
    for a, b in (('S', 'C'), ('C', 'P'), ('S', 'P')):
        out.append(lambda a=a, b=b: build_trans(a, b))
    return out


def run():
    for b in full_set():
        piece = b()
        if ONLY and not any(s_ in piece.name for s_ in ONLY):
            piece.bm.free()
            continue
        export(piece)
    print('exported', flush=True)


if globals().get('CL_NORUN'):
    pass
else:
    run()
