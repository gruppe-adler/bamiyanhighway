"""Tunnel test kit (TT_), crouch and prone families plus size transitions. Extension of tunnelkit_build.py (which stays the
standing kit's builder and is not touched); doc: Docs/TunnelKit_CrouchProne.md.

Run (headless):  blender --factory-startup -b --python Docs/blender/tunnelkit_build_cp.py
Environment variables (all optional):
  CP_EXPORT=0      build and verify only, write no FBX (default 1: export to Assets/Tunnels/TT)
  CP_ONLY=a,b      only the pieces whose name contains one of these strings (e.g. CP_ONLY=Trans_,C_Turn90)
  CP_VERIFY=0      skip the verification (default 1: clearance, closedness, sockets, joints, light thickness)
  CP_STATS=path    where the verification numbers go (default Docs/blender/previews/CP_stats.json)
In a live Blender:  TT_EXPORT = False ; exec(open(r"<this file>").read())  builds the pieces into collection CP_Preview.

Construction rules are those of tunnelkit_build.py (closed earth solids with SHELL m of earth round the opening, a sleeve
reaching SLEEVE m past every joint over the neighbour and SLEEVE m back over the piece's own end, timber lining at the
joints, materials TT_Earth / TT_Wood / TT_Ground, triangles only, LOD0 + UTM_ collider, empties "1", "2", ... = sockets).
What is new:
  * three profiles with the same 11 point topology: S (the standing kit's, unchanged numbers), C (crouch) and P (prone);
    the profile decides inside size, shell, sleeve, timber lining, socket height and roughness amplitude
  * the earth's roughness is ONE-SIDED on C and P (it only ever moves the wall away from the void), so the inside never
    gets smaller than the profile: the clear height and width are guaranteed by construction and checked by ray casts
  * the timber lining of C and P sits flush with the wall (2 cm proud), so that it does not eat the clearance
  * sockets (memory points) sit at the CENTRE HEIGHT of the opening: S 1.0 m, C 0.8 m, P 0.475 m above the floor
  * transitions morph the profile along the path through ramps ("funnels") with a timber lining at each end of a ramp
  * every piece is verified after it is built; numbers go to CP_STATS (json) and the log
"""
import bpy, bmesh, math, os, json, random
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
OUT = os.path.join(ADDON, "Assets", "Tunnels", "TT")
EXPORT = globals().get('TT_EXPORT', os.environ.get('CP_EXPORT', '1') != '0')
VERIFY = os.environ.get('CP_VERIFY', '1') != '0'
DEBUG = os.environ.get('CP_DEBUG', '0') == '1'
ONLY = [s for s in os.environ.get('CP_ONLY', '').split(',') if s]
STATS = os.environ.get('CP_STATS', os.path.join(ADDON, "Docs", "blender", "previews", "CP_stats.json"))

# ---------------------------------------------------------------------------------------------------------------------
# Numbers shared by all families (as in tunnelkit_build.py)
SHELL = 0.6          # earth round the opening
SLEEVE = 0.25        # sleeve reach either side of a joint
SLEEVE_IN = 0.1      # how far the sleeve sinks into the shell
SLEEVE_T = 0.3       # sleeve thickness
FRAME_L = 0.15       # timber lining length along the tunnel
TURN_RADIUS = 1.8    # same plan as the standing kit's turn and dogleg, so the generator's grid logic is unchanged
UV_EARTH = 1 / 2.2 / 16
UV_WOOD = 1 / 1.0
EARTH_COL = (1.0, 1.0, 1.0, 1.0)
WOOD_COL = (1.0, 1.0, 1.0, 1.0)
GROUND_COL = (0.0, 1.0, 1.0, 1.0)
MAT_EARTH, MAT_WOOD, MAT_GROUND = 0, 1, 2
MAT_HIDDEN = 3
REFINE = 0.25
FADE_START = 0.4
FADE_END = 1.4
Z = Vector((0, 0, 1))

# Profiles (x across, z up from the floor), counter-clockwise from the floor's left corner: floor, right wall (bulging a
# little), shoulder, roof, and back down the left. The roof is nearly flat within 0.3 m of the middle, so a person's
# shoulders have the same headroom as the head.
S_PTS = [(-0.7, 0.0), (0.7, 0.0), (0.74, 0.8), (0.7, 1.4), (0.56, 1.78), (0.32, 2.02), (0.0, 2.1),
         (-0.32, 2.02), (-0.56, 1.78), (-0.7, 1.4), (-0.74, 0.8)]
C_PTS = [(-0.62, 0.0), (0.62, 0.0), (0.65, 0.62), (0.62, 1.12), (0.52, 1.50), (0.32, 1.63), (0.0, 1.64),
         (-0.32, 1.63), (-0.52, 1.50), (-0.62, 1.12), (-0.65, 0.62)]
P_PTS = [(-0.52, 0.0), (0.52, 0.0), (0.54, 0.36), (0.52, 0.62), (0.45, 0.86), (0.3, 0.96), (0.0, 0.965),
         (-0.3, 0.96), (-0.45, 0.86), (-0.52, 0.62), (-0.54, 0.36)]


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


def frame_profiles(profile, lip, back=0.05):
    """Walls and roof of a profile only (no floor), as an open polyline: the lining's inner face (the profile pulled
    into the tunnel by lip) and its outer face (the profile pushed back into the earth by back)"""
    low = sorted(range(len(profile)), key=lambda i: profile[i][1])[:2]
    n = len(profile)
    start = low[0] if (low[0] + 1) % n != low[1] else low[1]
    line = [profile[(start + k) % n] for k in range(n)]
    pulled = offset(profile, -lip)
    pulled_line = [pulled[(start + k) % n] for k in range(n)]
    pulled_line[0] = (pulled_line[0][0], line[0][1])
    pulled_line[-1] = (pulled_line[-1][0], line[-1][1])
    outer = offset(profile, back)
    outer_line = [outer[(start + k) % n] for k in range(n)]
    outer_line[0] = (outer_line[0][0], line[0][1])
    outer_line[-1] = (outer_line[-1][0], line[-1][1])
    return pulled_line, outer_line


class Prof:
    """One opening size: its profile and everything derived from it"""

    def __init__(self, key, pts, lip, back, mp_height, wall_amp, floor_amp, one_sided, roof_in=1.0):
        self.key = key
        self.inner = ccw(pts)
        self.outer = offset(self.inner, SHELL)
        self.sleeve_a = offset(self.inner, SHELL - SLEEVE_IN)
        self.sleeve_b = offset(self.inner, SHELL + SLEEVE_T)
        self.lip = lip
        self.frame = frame_profiles(self.inner, lip, back)
        self.mp_height = mp_height          # socket height above the floor: the centre of the opening
        self.wall_amp = wall_amp
        self.floor_amp = floor_amp
        self.one_sided = one_sided
        self.roof_in = roof_in
        self.height = max(p[1] for p in self.inner)
        self.half_width = max(p[0] for p in self.inner)


# S: exactly the standing kit (frame 0.12 deep, noise both ways 0.2 / 0.035, roof 0.5 of the walls' amount)
PROF = {
    'S': Prof('S', S_PTS, 0.12, 0.02, 1.0, 0.2, 0.035, False, 0.5),
    # C: earth 1.24 wide (1.30 at the bulge) x 1.64 high, lined 1.20 x 1.62 at the joints; roof >= 1.63 within 0.3 m of the middle
    'C': Prof('C', C_PTS, 0.02, 0.05, 0.8, 0.10, 0.02, True),
    # P: earth 1.04 wide (1.08 at the bulge) x 0.965 high, lined 1.00 x 0.945 at the joints; roof >= 0.96 within 0.3 m of the middle
    'P': Prof('P', P_PTS, 0.02, 0.05, 0.475, 0.05, 0.012, True),
}
assert all(len(p.inner) == 11 for p in PROF.values())


# ---------------------------------------------------------------------------------------------------------------------
# Sweeping profiles along a path into a closed solid

def frame_at(pos, tangent):
    t = Vector((tangent.x, tangent.y, 0)).normalized()
    right = t.cross(Z).normalized()
    return pos, right


def ring(pos, right, profile, scale=(1, 1)):
    return [pos + right * (p[0] * scale[0]) + Z * (p[1] * scale[1]) for p in profile]


def sweep(bm, samples, prof_a, prof_b, closed=True, mat=0, scales=None):
    """samples: [(pos, tangent)]; the solid between profile a (inside) and b (outside), ends closed. prof_a / prof_b may
    also be lists with one profile per sample (a morph)"""
    rings_a, rings_b = [], []
    per = isinstance(prof_a[0], list)
    for i, (pos, tan) in enumerate(samples):
        p, right = frame_at(pos, tan)
        sc = scales[i] if scales else (1, 1)
        rings_a.append([bm.verts.new(v) for v in ring(p, right, prof_a[i] if per else prof_a, sc)])
        rings_b.append([bm.verts.new(v) for v in ring(p, right, prof_b[i] if per else prof_b, sc)])
    n = len(rings_a[0])
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
    out = []
    for i in range(steps + 1):
        a = math.radians(degrees) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    return out


def path_chicane(radius, across, shift_right=True, steps=14):
    """A hard jog sideways: 90 degree turn, a straight stretch across, 90 degree turn back to the first heading"""
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


def densify(samples, step=0.1):
    """A route for the verification: the path every `step` m (position and horizontal tangent), width measurable"""
    route = []
    for (a, ta), (b, tb) in zip(samples[:-1], samples[1:]):
        n = max(1, math.ceil((b - a).length / step))
        for k in range(n):
            t = k / n
            tan = (ta * (1 - t) + tb * t)
            route.append((a + (b - a) * t, Vector((tan.x, tan.y, 0)).normalized(), True))
    route.append((samples[-1][0].copy(), Vector((samples[-1][1].x, samples[-1][1].y, 0)).normalized(), True))
    return route


# ---------------------------------------------------------------------------------------------------------------------
# Pieces

def joint(bm, pos, outward, prof, frame=True, frame_len=FRAME_L):
    """pos: the opening's floor centre; outward: horizontal, pointing out of the piece"""
    out = Vector((outward.x, outward.y, 0)).normalized()
    sleeve = [(pos - out * SLEEVE, out), (pos + out * SLEEVE, out)]
    sweep(bm, sleeve, prof.sleeve_a, prof.sleeve_b, closed=True, mat=0)
    if frame:
        fa, fb = prof.frame
        sweep(bm, [(pos - out * frame_len, out), (pos - out * 0.005, out)], fa, fb, closed=False, mat=1)


class Piece:
    def __init__(self, name, prof):
        self.name = name
        self.prof = prof                 # the profile that sets the noise and the clearance the piece must keep
        self.bm = bmesh.new()
        self.sockets = []                # (floor centre, outward, profile)
        self.fades = []
        self.routes = []                 # [(position, tangent, width measurable)] polylines for the clearance check
        self.mid = prof.mp_height        # height of the measuring rays above the floor (inside every profile of the piece)
        self.box = None                  # a chamber's inner footprint (hw, hd): routes inside it measure no width

    def socket(self, pos, outward, prof=None, joint_too=True):
        prof = prof or self.prof
        self.sockets.append((pos.copy(), Vector((outward.x, outward.y, 0)).normalized(), prof))
        if joint_too:
            joint(self.bm, pos, outward, prof)


def breathe(samples, wide, high, ease=0.5, ramp=1.2):
    """Per-sample profile scales: the standard profile within ease m of either end (the joints stay exact), growing over
    ramp m to wide x high in the middle. Only ever >= 1: the inside only gets bigger"""
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
    sweep(piece.bm, samples, piece.prof.inner, piece.prof.outer, closed=True, mat=0, scales=scales)
    piece.socket(samples[0][0], -samples[0][1])
    piece.socket(samples[-1][0], samples[-1][1])
    piece.routes.append(densify(samples))


def to_object(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def chamber(piece, width, depth, height, doors):
    """doors: (side, offset along the wall): side 'S' (-Y), 'N' (+Y), 'E' (+X), 'W' (-X). A box of earth with a tunnel hole
    and a short stub at each door (booleans)"""
    prof = piece.prof
    hw, hd = width / 2, depth / 2
    piece.box = (hw, hd)
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
            out, base = Vector((0, -1, 0)), Vector((along, -hd, 0))
        elif side == 'N':
            out, base = Vector((0, 1, 0)), Vector((along, hd, 0))
        elif side == 'E':
            out, base = Vector((1, 0, 0)), Vector((hw, along, 0))
        else:
            out, base = Vector((-1, 0, 0)), Vector((-hw, along, 0))
        hole = bmesh.new()
        # the cutter's floor stays AT the floor (offset(profile, 0.001) would dip 1 mm below it and carve a sliver pit into the
        # chamber's floor, whose noise folds over). The hole is 4 cm bigger than the stub's profile: in the 10 cm where the stub
        # overlaps the wall the stub's inner surface is the visible one and the two don't fight
        cut_profile = [(x, max(z, 0.0)) for x, z in offset(prof.inner, 0.04)]
        prism(hole, [(base - out * 0.2, out), (base + out * (SHELL + 0.3), out)], cut_profile)
        cutters.append(to_object(hole, piece.name + '_tmp_hole'))
        stubs.append((base + out * (SHELL - 0.1), base + out * (SHELL + 0.6), out, base))
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
    bases = []
    for a, b, out, base in stubs:
        sweep(piece.bm, [(a, out), (b, out)], prof.inner, prof.outer, closed=True, mat=0)
        piece.socket(b, out)
        bases.append((b, base))
    # routes: from each door through the middle to every other door
    centre = Vector((0, 0, 0))
    for i in range(len(bases)):
        for j in range(i + 1, len(bases)):
            pts = [bases[i][0], bases[i][1], centre, bases[j][1], bases[j][0]]
            route = []
            for a, b in zip(pts[:-1], pts[1:]):
                n = max(1, math.ceil((b - a).length / 0.1))
                tan = (b - a).normalized()
                for k in range(n):
                    route.append((a + (b - a) * (k / n), tan, True))
            route.append((pts[-1], (pts[-1] - pts[-2]).normalized(), True))
            piece.routes.append(route)


# ---------------------------------------------------------------------------------------------------------------------
# The families

def build_straight(fam, length):
    p = Piece('TT_%s_Straight_%d' % (fam, length), PROF[fam])
    samples = path_straight(float(length), step=0.25)
    if length >= 4:
        wide = {'C': 1.12, 'P': 1.10}[fam]
        high = {'C': 1.03, 'P': 1.0}[fam]
        corridor(p, samples, breathe(samples, wide, high))
    else:
        corridor(p, samples)
    return p


def build_turn(fam):
    p = Piece('TT_%s_Turn90' % fam, PROF[fam])
    samples = path_arc(TURN_RADIUS, steps=24)
    corridor(p, samples, breathe(samples, {'C': 1.12, 'P': 1.10}[fam], 1.0))
    return p


def build_dogleg(fam, side):
    p = Piece('TT_%s_Dogleg_%s' % (fam, side), PROF[fam])
    corridor(p, path_chicane(TURN_RADIUS, 1.0, side == 'R'))
    return p


SLOPE_RISE = {'C': 1.0, 'P': 0.8}      # over 4 m, eased at both ends: steepest 21 degrees (C) and 17 degrees (P)


def build_slope(fam):
    p = Piece('TT_%s_Slope' % fam, PROF[fam])
    samples = path_slope(4.0, SLOPE_RISE[fam])
    corridor(p, samples, breathe(samples, {'C': 1.10, 'P': 1.08}[fam], 1.0))
    return p


END_VOID = 1.6          # the dead end: 1.6 m deep, then the plug


def build_end(fam):
    p = Piece('TT_%s_End' % fam, PROF[fam])
    samples = path_straight(END_VOID + 0.4, step=0.5)
    sweep(p.bm, samples, p.prof.inner, p.prof.outer, closed=True, mat=0)
    prism(p.bm, path_straight(0.6, step=0.6, start=Vector((0, END_VOID, 0))), offset(p.prof.inner, SHELL - 0.05), mat=0)
    p.socket(samples[0][0], -samples[0][1])
    p.routes.append(densify(path_straight(END_VOID - 0.1, step=0.5)))
    return p


JUNCTION = {   # chamber width, depth, height, doors (E and W staggered so no opening looks straight into another)
    'C': (2.8, 2.8, 1.9, [('S', 0.0), ('E', 0.6), ('W', -0.7)]),
    'P': (2.4, 2.4, 1.15, [('S', 0.0), ('E', 0.5), ('W', -0.6)]),
}


def build_junction(fam):
    p = Piece('TT_%s_Junction' % fam, PROF[fam])
    w, d, h, doors = JUNCTION[fam]
    chamber(p, w, d, h, doors)
    return p


# Mouth flare (extra width, extra height at the mouth) and how much the inside swells away from the joint
ENTRY = {'C': (0.5, 0.30, 1.10, 1.04), 'P': (0.6, 0.50, 1.10, 1.04)}


def build_entry(fam):
    """A mouth into a hillside: the opening flares out over its first 1.2 m; pivot at the mouth's floor centre"""
    p = Piece('TT_%s_Entry_Horizontal' % fam, PROF[fam])
    flare_w, flare_h, swell_w, swell_h = ENTRY[fam]
    samples = path_straight(5.0, step=0.25)
    scales = []
    for pos, _ in samples:
        t = min(pos.y / 1.2, 1.0)
        inner = smooth(min(max((5.0 - pos.y - 0.5) / 1.5, 0.0), 1.0))
        scales.append((max(1.0 + flare_w * (1 - smooth(t)), 1.0 + (swell_w - 1) * inner),
                       max(1.0 + flare_h * (1 - smooth(t)), 1.0 + (swell_h - 1) * inner)))
    sweep(p.bm, samples, p.prof.inner, p.prof.outer, closed=True, mat=0, scales=scales)
    fa, fb = p.prof.frame
    sweep(p.bm, [(Vector((0, 0.0, 0)), Vector((0, 1, 0))), (Vector((0, 0.25, 0)), Vector((0, 1, 0)))], fa, fb, closed=False, mat=1,
          scales=[scales[0], scales[0]])
    p.fades.append((Vector((0, 0, 0)), Vector((0, -1, 0))))
    p.socket(samples[-1][0], samples[-1][1])
    p.routes.append(densify(samples))
    return p


# Transitions: keys (profile, y where that profile starts to hold); between two different keys the profile morphs
# (smoothstep). A plateau is exact; the timber lining sits on the plateau side of each ramp end.
TRANS_LEN = 3.0
TRANS_KEYS = {
    ('S', 'C'): [('S', 0.0), ('S', 0.9), ('C', 1.8), ('C', 3.0)],
    ('C', 'P'): [('C', 0.0), ('C', 1.0), ('P', 1.8), ('P', 3.0)],
    ('S', 'P'): [('S', 0.0), ('S', 0.55), ('C', 1.25), ('C', 1.75), ('P', 2.45), ('P', 3.0)],
}
TRANS_LINING = 0.15


def lerp_profile(a, b, t):
    return [(pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t) for pa, pb in zip(a, b)]


def build_trans(a, b):
    keys = TRANS_KEYS[(a, b)]
    # the piece keeps the noise settings and clearance of its smallest profile
    small = min((PROF[k] for k, _ in keys), key=lambda pr: pr.height)
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
                inner = PROF[k0].inner if k0 == k1 else lerp_profile(PROF[k0].inner, PROF[k1].inner, t)
                break
        samples.append((Vector((0, y, 0)), Vector((0, 1, 0))))
        inners.append(inner)
        # a steep ramp cuts the earth's thickness (measured square to the ramp) by the cosine of its slope: the shell
        # swells over the ramp's middle to make up for it (0 on the plateaus, so the joints stay exact)
        outers.append(offset(inner, SHELL + 0.25 * 4 * t * (1 - t)))
    sweep(p.bm, samples, inners, outers, closed=True, mat=0)
    fwd = Vector((0, 1, 0))
    for (k0, y0), (k1, y1) in zip(keys[:-1], keys[1:]):
        if k0 != k1:
            for prof, y_in, y_out in ((PROF[k0], y0 - TRANS_LINING, y0), (PROF[k1], y1, y1 + TRANS_LINING)):
                fa, fb = prof.frame
                sweep(p.bm, [(Vector((0, y_in, 0)), fwd), (Vector((0, y_out, 0)), fwd)], fa, fb, closed=False, mat=1)
    p.socket(Vector((0, 0, 0)), Vector((0, -1, 0)), PROF[a])
    p.socket(Vector((0, TRANS_LEN, 0)), Vector((0, 1, 0)), PROF[b])
    p.mid = min(PROF[a].mp_height, PROF[b].mp_height, small.mp_height)
    p.routes.append(densify(path_straight(TRANS_LEN, step=0.5)))
    return p


def build_s_partner():
    """The standing kit's 2 m straight (as tunnelkit_build.py builds it), for the joint tests only; never exported"""
    p = Piece('S_Straight_2', PROF['S'])
    corridor(p, path_straight(2.0, step=0.25))
    return p


FAMILY = [lambda f: build_straight(f, 4), lambda f: build_straight(f, 2), build_turn, lambda f: build_dogleg(f, 'L'),
          lambda f: build_dogleg(f, 'R'), build_slope, build_junction, build_end]


def all_builders():
    out = []
    for fam in ('C', 'P'):
        for b in FAMILY:
            out.append(lambda b=b, fam=fam: b(fam))
    for a, b in (('S', 'C'), ('C', 'P'), ('S', 'P')):
        out.append(lambda a=a, b=b: build_trans(a, b))
    for fam in ('C', 'P'):
        out.append(lambda fam=fam: build_entry(fam))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Objects, UVs, export (as tunnelkit_build.py)

def materials():
    mats = []
    for name, col in (('TT_Earth', (0.46, 0.35, 0.24, 1)), ('TT_Wood', (0.35, 0.25, 0.15, 1)), ('TT_Ground', (0.3, 0.45, 0.2, 1))):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = col
        mats.append(m)
    return mats


def split_inside(bm):
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
        w = min(w, smooth(min(max((-along - FADE_START) / (FADE_END - FADE_START), 0.0), 1.0)))
    return w


def roughen(bm, keep, prof):
    """The inside pushed along its normal by noise; the openings not at all. One-sided profiles (C, P) only ever push the
    wall, roof and floor AWAY from the void, so the clearance of the profile can't be lost"""
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
        amp = prof.wall_amp + (prof.floor_amp - prof.wall_amp) * max(0.0, n.z)
        c = v.co
        h = (0.55 * noise.noise(c * 0.55) + 0.3 * noise.noise(c * 1.5 + Vector((5.3, 1.7, 9.1)))
             + 0.15 * noise.noise(c * 4.0 + Vector((2.9, 7.7, 3.1))))
        if prof.one_sided:
            t = min(max(0.5 + 0.5 * h / 0.7, 0.0), 1.0)       # 0..1, mostly mid
            moves.append((v, -n * (t * amp * w)))              # n points into the void: minus = into the earth
        else:
            if n.z < -0.3 and h < 0:
                h *= prof.roof_in
            moves.append((v, n * (h * amp * w)))
    for v, d in moves:
        v.co += d
    bm.normal_update()


def finish(piece, at=Vector((0, 0, 0)), collection=None):
    """The piece's LOD0, collider and memory points as objects; returns them"""
    bm = piece.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    split_inside(bm)
    refine(bm)
    roughen(bm, [(s[0], s[1]) for s in piece.sockets] + piece.fades, piece.prof)
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
    for i, (pos, out, prof) in enumerate(piece.sockets):
        e = bpy.data.objects.new(str(i + 1) if collection is None else f'{piece.name}.{i + 1}', None)
        e.empty_display_type = 'SINGLE_ARROW'
        e.empty_display_size = 0.4
        e.location = at + pos + Z * prof.mp_height
        e.rotation_euler = (math.radians(-90), 0, math.atan2(-out.x, out.y))
        col.objects.link(e)
        objs.append(e)
    return objs


# ---------------------------------------------------------------------------------------------------------------------
# Verification

def tris_bm(obj, matrix=None):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if matrix is not None:
        bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    return bm


def closedness(obj):
    bm = tris_bm(obj)
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    multi = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    loose = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    # connected solids: each must be closed; volume sign check (outward normals) by signed volume of the whole mesh
    vol = 0.0
    for f in bm.faces:
        a, b, c = [v.co for v in f.verts]
        vol += a.dot(b.cross(c)) / 6.0
    ngons = sum(1 for f in bm.faces if len(f.verts) != 3)
    tris = len(bm.faces)
    bm.free()
    return dict(tris=tris, open_edges=open_edges, multi_edges=multi, loose_edges=loose, non_tris=ngons, signed_volume=round(vol, 3))


def bvh_of(obj, matrix=None):
    bm = tris_bm(obj, matrix)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def measure_route(tree, piece):
    """Clearance along the routes by ray casts against the LOD0 mesh: height from the floor to the roof straight up at the
    route and 0.3 m to either side, width between the walls at several heights. Returns the minima"""
    hmin_c, hmin_b, wmin = 1e9, 1e9, 1e9
    where = {}
    for route in piece.routes:
        for pos, tan, wok in route:
            right = tan.cross(Z).normalized()
            for off in (0.0, -0.3, 0.3):
                q = pos + right * off + Z * piece.mid
                up = tree.ray_cast(q, Z, 20.0)
                dn = tree.ray_cast(q, -Z, 20.0)
                if up[0] is None or dn[0] is None:
                    h = 0.0
                else:
                    h = up[0].z - dn[0].z
                if off == 0.0:
                    if h < hmin_c:
                        hmin_c, where['hc'] = h, tuple(round(x, 2) for x in pos)
                else:
                    if h < hmin_b:
                        hmin_b, where['hb'] = h, tuple(round(x, 2) for x in pos)
            inside_box = piece.box is not None and abs(pos.x) < piece.box[0] + 0.01 and abs(pos.y) < piece.box[1] + 0.01
            if wok and not inside_box:
                for zf in (0.12, 0.3, 0.5, 0.62):
                    zz = pos.z + zf * piece.prof_h_narrow
                    q = Vector((pos.x, pos.y, zz))
                    r = tree.ray_cast(q, right, 5.0)
                    l = tree.ray_cast(q, -right, 5.0)
                    if r[0] is None or l[0] is None:
                        w = 0.0
                    else:
                        w = (r[0] - l[0]).length
                    if w < wmin:
                        wmin, where['w'] = w, tuple(round(x, 2) for x in pos)
    return dict(min_height_centre=round(hmin_c, 3), min_height_band=round(hmin_b, 3), min_width=round(wmin, 3), where=where)


def socket_check(piece, objs, tree):
    out = []
    for i, (pos, direction, prof) in enumerate(piece.sockets):
        empty = [o for o in objs if o.type == 'EMPTY'][i]
        mw = empty.matrix_world
        fwd = mw.to_3x3() @ Vector((0, 0, 1))        # the arrow: local +Z
        err = math.degrees(fwd.angle(direction))
        p = mw.translation
        pin = p - direction * 0.05          # just inside: on the end plane itself the rays graze the joint's rings
        up = tree.ray_cast(pin, Z, 10.0)
        dn = tree.ray_cast(pin, -Z, 10.0)
        floor = dn[0].z if dn[0] else None
        roof = up[0].z if up[0] else None
        # outward: nothing in the way (as the catalog's Escapes trace: from the socket along the axis)
        free_out = tree.ray_cast(p + direction * 0.05, direction, 40.0)[0] is None
        out.append(dict(socket=i + 1, pos=[round(x, 3) for x in p], out=[round(x, 3) for x in direction], size=prof.key,
                        height_above_floor=round(p.z - pos.z, 3), floor_under=None if floor is None else round(p.z - floor, 3),
                        roof_over=None if roof is None else round(roof - p.z, 3), angle_error_deg=round(err, 4),
                        free_outward=free_out))
    return out


def join_matrix(pos_a, out_a, pos_b, out_b):
    """Moves copy B so that its socket b sits on socket a and faces the other way"""
    # rotate by theta about Z so that R(out_b) = -out_a
    th = math.atan2(-out_a.y, -out_a.x) - math.atan2(out_b.y, out_b.x)
    R = Matrix.Rotation(th, 4, 'Z')
    T = Matrix.Translation(pos_a - R @ pos_b)
    return T @ R


def mouth_ok(o, d, sockets, tol=1.15):
    """A ray that escaped: does it leave through an opening (the plane at a socket, inside the opening's box)?"""
    for pos, out, prof in sockets:
        dn = d.dot(out)
        if dn <= 1e-6:
            continue
        t = (pos - o).dot(out) / dn
        if t < -1e-6:
            continue
        hit = o + d * t
        right = out.cross(Z).normalized()
        lat = (hit - pos).dot(right)
        z = hit.z - pos.z
        if abs(lat) <= prof.half_width * tol + 0.05 and -0.05 <= z <= prof.height * tol + 0.05:
            return True
    return False


def thickness_test(tree, origins, sockets, rng, n_dirs, seams=(), hmax=40.0, tol=1.15):
    """Rays from points in the void in random directions: the thickness of earth before the open air (min), and rays that
    got out some way that is not an opening (leaks). seams: (position, outward) of joint planes: the two coincident end
    faces of joined pieces lie there and are skipped, as the solids continue across them"""
    tmin, leaks, rays = 1e9, 0, 0
    kinds = {'escaped': 0, 'fold_or_ambiguous': 0}
    dirs = []
    for _ in range(n_dirs):
        v = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
        dirs.append(v.normalized())

    def on_seam(hit):
        for sp, so in seams:
            if abs((hit[0] - sp).dot(so)) < 2e-3 and abs(hit[1].dot(so)) > 0.99:
                return True
        return False

    def cluster(hit, d):
        """+1 per face entered, -1 per face left at this spot: coplanar faces of overlapping solids (a stub's floor and the
        chamber's floor at the same height) hit together"""
        delta = 0
        for loc, n, idx, dist in tree.find_nearest_range(hit[0], 1e-5):
            if abs(n.dot(hit[1])) > 0.98:
                delta += 1 if n.dot(d) < 0 else -1
        return delta or (1 if hit[1].dot(d) < 0 else -1)

    def cast(pos, d):
        for _ in range(8):
            hit = tree.ray_cast(pos, d, hmax)
            if hit[0] is None or not on_seam(hit):
                return hit
            pos = hit[0] + d * 1e-4
        return hit

    def one(o, d):
        """('ok', thickness or None) or ('leak', why)"""
        hit = cast(o, d)
        if hit[0] is None:
            return ('ok', None) if mouth_ok(o, d, sockets, tol) else ('leak', 'escaped')
        if hit[1].dot(d) > 0:       # first thing seen is the back of a face: the origin isn't in the void
            return ('leak', 'origin not in the void')
        if any(-0.7 < (hit[0] - sp).dot(so) < 0.4 and ((hit[0] - sp) - so * (hit[0] - sp).dot(so)).length < 2.5 for sp, so, _ in sockets):
            return ('ok', None)     # grazing the lining at an opening that is open (a single piece): not measured
        start = hit[0]
        depth = cluster(hit, d)
        pos = hit[0]
        for _ in range(60):
            nxt = cast(pos + d * 1e-4, d)
            if nxt[0] is None:
                break
            depth += cluster(nxt, d)
            if depth <= 0:
                q = nxt[0] + d * 2e-3
                if tree.ray_cast(q, Z, 40.0)[0] is not None and tree.ray_cast(q, -Z, 40.0)[0] is not None:
                    return ('ok', None)   # came out into the void again (grazing a lining's corner): not an exit
                return ('ok', (nxt[0] - start).length)
            pos = nxt[0]
        return ('leak', 'never left the earth')

    for o in origins:
        for d0 in dirs:
            rays += 1
            res = None
            for attempt in range(5):     # a ray along an edge counts faces twice or not at all: nudge it and try again
                d = d0 if attempt == 0 else (d0 + Vector((rng.gauss(0, 4e-3), rng.gauss(0, 4e-3), rng.gauss(0, 4e-3)))).normalized()
                res = one(o, d)
                if res[0] == 'ok':
                    break
            if res[0] == 'leak':
                leaks += 1
                kinds['escaped' if res[1] == 'escaped' else 'fold_or_ambiguous'] += 1
                if DEBUG and leaks < 4:
                    print('  LEAK', res[1], tuple(round(x, 2) for x in o), 'dir', tuple(round(x, 3) for x in d0))
                    pp = o
                    for _ in range(8):
                        hh = tree.ray_cast(pp, d0, hmax)
                        if hh[0] is None:
                            print('     end'); break
                        print('     hit', tuple(round(x, 3) for x in hh[0]), 'n', tuple(round(x, 2) for x in hh[1]), 'face', hh[2])
                        pp = hh[0] + d0 * 1e-4
            elif res[1] is not None:
                if res[1] < tmin and DEBUG:
                    print('  thinnest so far %.3f from' % res[1], tuple(round(x, 2) for x in o), 'dir', tuple(round(x, 3) for x in d))
                tmin = min(tmin, res[1])
    return tmin, kinds, rays


def void_points(piece, per_route=14):
    pts = []
    for route in piece.routes:
        step = max(1, len(route) // per_route)
        for pos, tan, _ in route[::step]:
            pts.append(pos + Z * piece.mid)
    return pts


def verify_piece(piece, objs, rng):
    bpy.context.view_layer.update()
    lod = objs[0]
    res = dict(name=piece.name)
    res.update(closedness(lod))
    tree = bvh_of(lod)
    piece.prof_h_narrow = min(pr.height for pr in ([piece.prof] + [s[2] for s in piece.sockets]))
    res['clearance'] = measure_route(tree, piece)
    res['sockets'] = socket_check(piece, objs, tree)
    bb = [lod.matrix_world @ Vector(c) for c in lod.bound_box]
    res['bbox_min'] = [round(min(v[i] for v in bb), 3) for i in range(3)]
    res['bbox_max'] = [round(max(v[i] for v in bb), 3) for i in range(3)]
    tmin, kinds, rays = thickness_test(tree, void_points(piece), piece.sockets + [(m[0], m[1], piece.prof) for m in piece.fades], rng, 40, tol=1.8)
    res['earth_thickness_min'] = round(tmin, 3)
    res['rays_escaped_not_through_opening'] = kinds['escaped']
    res['rays_fold_or_ambiguous'] = kinds['fold_or_ambiguous']
    res['rays'] = rays
    return res


def make_partner(builder, name):
    """A straight to join pieces to in the tests (own names: the real pieces' empties must stay called "1", "2", ...)"""
    piece = builder()
    piece.name = name
    objs = finish(piece, Vector((0, 0, 0)), bpy.context.scene.collection)
    for o in objs:
        o.hide_set(True)
    return piece, objs


def joint_test(piece, objs, sock_index, partner, partner_objs, partner_sock, rng):
    """Piece joined to a partner at the given sockets (partner's socket faces back). Ring match at the joint plane, how far
    each sleeve reaches past the plane, and the light thickness of earth round the joint"""
    pos_a, out_a, prof_a = piece.sockets[sock_index]
    pos_b, out_b, prof_b = partner.sockets[partner_sock]
    M = join_matrix(pos_a, out_a, pos_b, out_b)
    bm1 = tris_bm(objs[0])
    bm2 = tris_bm(partner_objs[0], M)
    right = out_a.cross(Z).normalized()

    def near(bm):
        return [v.co.copy() for v in bm.verts if abs((v.co - pos_a).dot(out_a)) < 1.0 and ((v.co - pos_a) - out_a * (v.co - pos_a).dot(out_a)).length < 2.0]

    na, nb = near(bm1), near(bm2)

    def lateral(v):
        rel = v - pos_a
        return Vector((rel.dot(right), rel.z))

    def on_profile(v, poly):
        p = lateral(v)
        best = 1e9
        for i in range(len(poly)):
            a, b = Vector(poly[i - 1]), Vector(poly[i])
            ab = b - a
            t = min(max((p - a).dot(ab) / ab.length_squared, 0.0), 1.0)
            best = min(best, (p - (a + ab * t)).length)
        return best < 2e-4

    # the opening's two outlines (void profile and shell profile): every vertex of one piece on them has a twin in the other
    va = [v for v in na if abs((v - pos_a).dot(out_a)) < 0.002 and (on_profile(v, prof_a.inner) or on_profile(v, prof_a.outer))]
    vb = [v for v in nb if abs((v - pos_a).dot(out_a)) < 0.002 and (on_profile(v, prof_a.inner) or on_profile(v, prof_a.outer))]
    worst = 0.0
    for v in va:
        worst = max(worst, min(((v - w).length for w in vb), default=99.0))
    for w in vb:
        worst = max(worst, min(((v - w).length for v in va), default=99.0))
    reach_a = max(((v - pos_a).dot(out_a) for v in na), default=0.0)          # own sleeve, into the partner
    reach_b = -min(((v - pos_a).dot(out_a) for v in nb), default=0.0)         # partner's sleeve, into the piece
    me2 = bpy.data.meshes.new('CP_tmp_pair_b')
    bm2.to_mesh(me2)
    bm1.from_mesh(me2)
    bpy.data.meshes.remove(me2)
    tree = BVHTree.FromBMesh(bm1)
    bm1.free()
    bm2.free()
    sock_world = [(p, o, pr) for i, (p, o, pr) in enumerate(piece.sockets) if i != sock_index]
    sock_world += [(M @ p, (M.to_3x3() @ o).normalized(), pr) for i, (p, o, pr) in enumerate(partner.sockets) if i != partner_sock]
    sock_world += [(f[0], f[1], piece.prof) for f in piece.fades]
    origins = []
    for a in [x * 0.15 for x in range(-6, 7)]:
        for lat in (-0.15, 0.0, 0.15):
            origins.append(pos_a + out_a * a + right * lat + Z * min(prof_a.mp_height, prof_b.mp_height))
    tmin, kinds, rays = thickness_test(tree, origins, sock_world, rng, 120, seams=[(pos_a, out_a)], tol=1.8 if piece.fades else 1.15)
    return dict(piece=piece.name, socket=sock_index + 1, partner=partner.name, partner_socket=partner_sock + 1,
                ring_mismatch_m=round(worst, 6), ring_verts=[len(va), len(vb)],
                sleeve_reach_into_partner_m=round(reach_a, 3), partner_sleeve_reach_into_piece_m=round(reach_b, 3),
                earth_thickness_min=round(tmin, 3), rays=rays, rays_escaped_not_through_opening=kinds['escaped'],
                rays_fold_or_ambiguous=kinds['fold_or_ambiguous'])


# ---------------------------------------------------------------------------------------------------------------------
# Export

def export(piece, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, piece.name + '.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'}, use_mesh_modifiers=True,
                             mesh_smooth_type='EDGE', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
    print(f'{piece.name}: {len(objs[0].data.polygons)} triangles, {len(piece.sockets)} openings -> {path}')


def remove(objs):
    for o in objs:
        data = o.data
        bpy.data.objects.remove(o)
        if data and data.users == 0:
            bpy.data.meshes.remove(data)


def check_standing_profile():
    """The S profile used here against the real exported standing kit (TT_Straight_2.fbx): its opening ring must contain
    all 11 inner and 11 outer points of S"""
    path = os.path.join(OUT, 'TT_Straight_2.fbx')
    if not os.path.exists(path):
        return dict(checked=False)
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path)
    new = [bpy.data.objects[k] for k in bpy.data.objects.keys() if k not in before]
    lod = [o for o in new if o.type == 'MESH' and 'LOD0' in o.name][0]
    bm = tris_bm(lod)
    mat = lod.matrix_world
    ring_pts = [(mat @ v.co) for v in bm.verts if abs((mat @ v.co).y) < 0.002]
    bm.free()
    def worst(profile):
        w = 0.0
        for x, z in profile:
            w = max(w, min(((v.x - x) ** 2 + (v.z - z) ** 2) ** 0.5 for v in ring_pts))
        return w
    res = dict(checked=True, ring_verts=len(ring_pts), inner_worst_m=round(worst(PROF['S'].inner), 5),
               outer_worst_m=round(worst(PROF['S'].outer), 5))
    for o in new:
        data = o.data
        bpy.data.objects.remove(o)
        if data and data.users == 0 and hasattr(data, 'vertices'):
            bpy.data.meshes.remove(data)
    return res


def run():
    rng = random.Random(1234)
    stats = dict(pieces=[], joints=[])
    stats['standing_profile_vs_exported_kit'] = check_standing_profile() if VERIFY else None
    partners = {}
    if VERIFY:
        partners['S'] = make_partner(build_s_partner, 'CP_partner_S')
        for fam in ('C', 'P'):
            partners[fam] = make_partner(lambda fam=fam: build_straight(fam, 2), 'CP_partner_' + fam)
    for build in all_builders():
        piece = build()
        if ONLY and not any(s in piece.name for s in ONLY):
            piece.bm.free()
            continue
        objs = finish(piece)
        if VERIFY:
            res = verify_piece(piece, objs, rng)
            stats['pieces'].append(res)
            print(json.dumps({k: res[k] for k in ('name', 'tris', 'open_edges', 'multi_edges', 'clearance', 'earth_thickness_min',
                                                  'rays_escaped_not_through_opening', 'rays_fold_or_ambiguous')}))
            # every socket against a straight of its own size, and (two-socket pieces) a copy of the piece itself
            for i, (pos, out, prof) in enumerate(piece.sockets):
                part, part_objs = partners[prof.key]
                stats['joints'].append(joint_test(piece, objs, i, part, part_objs, 0, rng))
            if len(piece.sockets) == 2 and piece.sockets[0][2].key == piece.sockets[1][2].key:
                stats['joints'].append(joint_test(piece, objs, 1, piece, objs, 0, rng))
                stats['joints'][-1]['partner'] = piece.name + ' (second copy)'
        if EXPORT:
            export(piece, objs)
        remove(objs)
    for key, (pp, po) in partners.items():
        remove(po)
    if VERIFY:
        os.makedirs(os.path.dirname(STATS), exist_ok=True)
        with open(STATS, 'w') as f:
            json.dump(stats, f, indent=1)
        print('stats ->', STATS)
    print('done')


def preview():
    col = bpy.data.collections.get('CP_Preview')
    if col:
        for o in list(col.objects):
            bpy.data.objects.remove(o)
    else:
        col = bpy.data.collections.new('CP_Preview')
        bpy.context.scene.collection.children.link(col)
    x = 0.0
    for build in all_builders():
        piece = build()
        objs = finish(piece, Vector((x, 0, 0)), col)
        for o in objs:
            if o.name.startswith('UTM_'):
                o.hide_set(True)
        x += objs[0].dimensions.x + 4.0
    print('preview built')


if globals().get('TT_NORUN'):
    pass                      # imported by the preview script: only the functions
elif globals().get('TT_EXPORT', None) is False:
    preview()
else:
    run()
