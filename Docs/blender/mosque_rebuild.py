"""Mosque_01 rebuild: lower wall, new body windows (photo proportions), clean drum windows, bevel.
Run inside Blender 4.5 (Blender MCP: exec(open(path).read())). Source: mosque_bake.blend -> saves mosque_v4.blend.
"""
import bpy, bmesh, math
from mathutils import Vector, bvhtree, geometry

DIR = r"D:\gronom\Auftraege\2016\GruppeAdler\Modding\bamiyan_highway\blender\mosque"
SRC, OUT = DIR + r"\mosque_bake.blend", DIR + r"\mosque_v4.blend"

# ---- parameters ----
Z_FLOOR = 0.9            # wall base
Z_SILL = 2.9             # window opening bottom (unchanged)
Z_OLD_TOP, Z_TOP = 8.34, 5.65      # wall top (roof slab underside) old -> new
SHIFT = Z_OLD_TOP - Z_TOP          # everything above the wall moves down
K = (Z_TOP - Z_SILL) / (Z_OLD_TOP - Z_SILL)
A_O, A_I = 8.93, 8.43    # octagon apothem outer / inner
WIN_W, WIN_H, WIN_PITCH = 1.20, 2.05, 1.65
SIDE_ANGLES = [90 + 45 * k for k in range(8)]   # side 0 = porch (untouched)
SEG = 12
R_OUT, R_IN = 5.36, 4.96
OLD_D0, OLD_D1 = 8.79, 12.06         # old drum wall z range
D_HEIGHT = 1.90                      # new drum wall height (photo: ~1.9 m)
SHIFT2 = (OLD_D1 - OLD_D0) - D_HEIGHT
DZ0 = OLD_D0 - SHIFT; DZ1 = DZ0 + D_HEIGHT
D_N, D_PHASE = 14, 90.0             # window count, one window on the porch axis (symmetric)
D_W, D_H, D_ZS = 0.75, 1.10, DZ0 + 0.42
DOME_Z0, DOME_Z1, DOME_K = 12.5, 18.0, 1.22   # old z range of the dome shell, vertical stretch (photo: dome h/w ~0.62)
FLATTEN_RIBS = False                           # keep the original raised ribs (slightly raised, like the photo); paint is aligned to them in mosque_bake.py
NOISE_A = 0.025                                # dome hand-made unevenness (m)
def dang(k): return D_PHASE + k * 360.0 / D_N


def fz(z):
    if z <= Z_SILL: return z
    if z < Z_OLD_TOP: return Z_SILL + (z - Z_SILL) * K
    if z <= OLD_D0: return z - SHIFT
    if z < OLD_D1: return DZ0 + (z - OLD_D0) * (D_HEIGHT / (OLD_D1 - OLD_D0))
    if z <= DOME_Z0: return z - SHIFT - SHIFT2
    if z <= DOME_Z1: return DOME_Z0 + (z - DOME_Z0) * DOME_K - SHIFT - SHIFT2
    return z + (DOME_Z1 - DOME_Z0) * (DOME_K - 1) - SHIFT - SHIFT2


def arch_pts(w, h):
    r = w / 2
    pts = [(-r, 0), (r, 0), (r, h - r)]
    for k in range(1, SEG):
        a = math.pi * k / SEG
        pts.append((r * math.cos(a), h - r + r * math.sin(a)))
    pts.append((-r, h - r))
    return pts


def frame(bm, c, zs, inner_wh, outer_wh, yb, yf, sill_w, sill_y0, sill_y1):
    t = Vector((-math.sin(c), math.cos(c), 0)); rad = Vector((math.cos(c), math.sin(c), 0))
    def P(x, y, z): return bm.verts.new(rad * y + t * x + Vector((0, 0, zs + z)))
    inner, outer = arch_pts(*inner_wh), arch_pts(*outer_wh)
    n = len(inner)
    iF = [P(x, yf, z) for x, z in inner]; oF = [P(x, yf, z) for x, z in outer]
    iB = [P(x, yb, z) for x, z in inner]; oB = [P(x, yb, z) for x, z in outer]
    fs = []
    for i in range(1, n):
        j = (i + 1) % n
        fs.append(bm.faces.new((iF[i], iF[j], oF[j], oF[i])))
        fs.append(bm.faces.new((oB[i], oB[j], oF[j], oF[i])))
        fs.append(bm.faces.new((iB[j], iB[i], iF[i], iF[j])))
    fs.append(bm.faces.new((iF[0], oF[0], oB[0], iB[0])))
    sv = [bm.verts.new(rad * y + t * x + Vector((0, 0, zs + z)))
          for z in (-0.09, 0.0) for (x, y) in ((-sill_w, sill_y0), (sill_w, sill_y0), (sill_w, sill_y1), (-sill_w, sill_y1))]
    for q in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        fs.append(bm.faces.new([sv[i] for i in q]))
    return fs


def cutter(cb, c, zs, w, h, y0, y1):
    t = Vector((-math.sin(c), math.cos(c), 0)); rad = Vector((math.cos(c), math.sin(c), 0))
    pts = arch_pts(w, h)
    a = [cb.verts.new(rad * y0 + t * x + Vector((0, 0, zs + z))) for x, z in pts]
    b = [cb.verts.new(rad * y1 + t * x + Vector((0, 0, zs + z))) for x, z in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n; cb.faces.new((a[i], a[j], b[j], b[i]))
    cb.faces.new(a[::-1]); cb.faces.new(b)


def fix_orient(nb):
    """make every face of a closed solid point outwards (ray parity test); exact boolean + recalc left some faces inverted"""
    nb.normal_update(); nb.faces.ensure_lookup_table()
    tree = bvhtree.BVHTree.FromBMesh(nb); flip = []
    for f in nb.faces:
        n = f.normal
        if n.length < 1e-6: continue
        o = f.calc_center_median() + n * 1e-4; cnt = 0
        while cnt < 60:
            loc, nrm, idx, dist = tree.ray_cast(o, n)
            if idx is None: break
            cnt += 1; o = loc + n * 1e-4
        if cnt % 2 == 1: flip.append(f)
    bmesh.ops.reverse_faces(nb, faces=flip)
    return len(flip)


def boolean_cut(tb, cb, name):
    tm = bpy.data.meshes.new(name + '_t'); tb.to_mesh(tm); tb.free()
    cm = bpy.data.meshes.new(name + '_c'); cb.to_mesh(cm); cb.free()
    to = bpy.data.objects.new(name + '_t', tm); co = bpy.data.objects.new(name + '_c', cm)
    bpy.context.collection.objects.link(to); bpy.context.collection.objects.link(co)
    m = to.modifiers.new('b', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = co; m.solver = 'EXACT'
    ev = to.evaluated_get(bpy.context.evaluated_depsgraph_get())
    res = bpy.data.meshes.new_from_object(ev)
    nb = bmesh.new(); nb.from_mesh(res)
    print(name, 'faces re-oriented', fix_orient(nb))     # exact boolean returns mixed winding -> backface-culled holes
    bpy.data.objects.remove(to); bpy.data.objects.remove(co)
    return nb


def chk(bm, label):
    """debug: count wall-plane faces (sides 1-7, outer/inner plane) that face the wrong way"""
    bm.normal_update(); bad = 0
    for f in bm.faces:
        if f.calc_area() < 0.05: continue
        c = f.calc_center_median()
        if not (0.95 < c.z < 5.7): continue
        side = int(round((math.degrees(math.atan2(c.y, c.x)) - 90) / 45)) % 8
        if side == 0: continue
        a = math.radians(90 + 45 * side); n = Vector((math.cos(a), math.sin(a), 0)); d = c.dot(n); fo = f.normal.dot(n)
        if abs(abs(fo) - 1) < 0.01 and ((abs(d - 8.93) < 0.05 and fo < 0) or (abs(d - 8.43) < 0.05 and fo > 0)): bad += 1
    print('flipped wall faces', label, bad)


def merge_into(bm, nb):
    vs = [bm.verts.new(v.co) for v in nb.verts]
    for f in nb.faces:
        bm.faces.new([vs[v.index] for v in f.verts]).material_index = 0
    nb.free()


# ============ 0. load + height remap ============
bpy.ops.wm.open_mainfile(filepath=SRC)
o = bpy.data.objects['Mosque_LOD0']
old_raw = o.data.copy(); old_raw.name = 'tmp_old_raw'          # un-squashed original: UV source for the new body walls (keeps texel density)
for v in o.data.vertices: v.co.z = fz(v.co.z)
old_mesh = o.data.copy(); old_mesh.name = 'tmp_old_uv'
bm = bmesh.new(); bm.from_mesh(o.data)

# ============ 1. delete old wall of sides 1..7 and drum wall ============
def ang(c): return math.degrees(math.atan2(c.y, c.x))
def in_side0(c): return abs((ang(c) - 90 + 180) % 360 - 180) < 22.5
dele = []
for f in bm.faces:
    c = f.calc_center_median(); r = math.hypot(c.x, c.y)
    if Z_FLOOR + 0.05 < c.z < Z_TOP - 0.05 and 8.2 < r < 10.2 and not in_side0(c) and not (c.y > 9.2 and abs(c.x) < 7.0): dele.append(f)   # keep porch columns
    elif DZ0 + 0.06 < c.z < DZ1 - 0.01 and r < 6.1: dele.append(f)
bmesh.ops.delete(bm, geom=dele, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)

# porch: remove the solid side wall panel on -x (not in the reference photo, porch is open there)
pan = [f for f in bm.faces if -3.46 < f.calc_center_median().x < -2.88 and 9.3 < f.calc_center_median().y < 12.8 and 0.9 < f.calc_center_median().z < 4.4]
print('porch panel faces removed', len(pan))
bmesh.ops.delete(bm, geom=pan, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
# porch: explicit front columns on both sides (one was missing in game)
col_f = []
for sx in (-1, 1):
    x0, x1 = sorted((sx * 2.905, sx * 3.445)); y0, y1 = 12.835, 13.445; z0, z1 = 0.9, 4.3
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        col_f.append(bm.faces.new([vs[i] for i in q]))
bmesh.ops.recalc_face_normals(bm, faces=col_f)

# drum: subdivide boundary rings to 96 and snap
bnd = [e for e in bm.edges if e.is_boundary and DZ0 - 0.05 < e.verts[0].co.z < DZ1 + 0.05 and DZ0 - 0.05 < e.verts[1].co.z < DZ1 + 0.05 and math.hypot(*e.verts[0].co.xy) < 6.2]
res = bmesh.ops.subdivide_edges(bm, edges=bnd, cuts=1, use_grid_fill=False)
for g in res['geom_inner']:
    if isinstance(g, bmesh.types.BMVert):
        r = math.hypot(g.co.x, g.co.y); tr = R_OUT if abs(r - R_OUT) < 0.1 else R_IN
        g.co.x *= tr / r; g.co.y *= tr / r

# ============ 2. new octagon wall with arched openings ============
prof = [(A_I, Z_FLOOR), (A_O, Z_FLOOR), (A_O, 1.9), (A_O + 0.07, 1.9), (A_O + 0.07, 2.5), (A_O, 2.5),
        (A_O, Z_TOP - 0.30), (A_O + 0.22, Z_TOP - 0.30), (A_O + 0.22, Z_TOP), (A_I, Z_TOP)]
tb = bmesh.new(); k22 = 1 / math.cos(math.radians(22.5))
rings = []
for pa, pz in prof:
    rings.append([tb.verts.new((pa * k22 * math.cos(math.radians(45 * i + 67.5)), pa * k22 * math.sin(math.radians(45 * i + 67.5)), pz)) for i in range(8)])
for p in range(len(prof)):
    q = (p + 1) % len(prof)
    for i in range(8):
        j = (i + 1) % 8
        tb.faces.new((rings[p][i], rings[p][j], rings[q][j], rings[q][i]))
tb.faces.new(rings[0][::-1]) if False else None
# profile closed: bottom edge (0->1) and top edge (9->0 closes) are the cap faces already (quads between rings)
bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
cb = bmesh.new()
for k in range(1, 8):
    c = math.radians(SIDE_ANGLES[k]); t = Vector((-math.sin(c), math.cos(c), 0)); rad = Vector((math.cos(c), math.sin(c), 0))
    for j in (-1, 0, 1):
        cc = rad * 0 + t * (j * WIN_PITCH)
        # cutter placed via offset along tangent: shift by moving centre angle projection
        pts = arch_pts(WIN_W, WIN_H)
        a = [cb.verts.new(rad * 8.2 + t * (x + j * WIN_PITCH) + Vector((0, 0, Z_SILL + z))) for x, z in pts]
        b = [cb.verts.new(rad * 9.6 + t * (x + j * WIN_PITCH) + Vector((0, 0, Z_SILL + z))) for x, z in pts]
        n = len(pts)
        for i in range(n):
            jj = (i + 1) % n; cb.faces.new((a[i], a[jj], b[jj], b[i]))
        cb.faces.new(a[::-1]); cb.faces.new(b)
bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
nb = boolean_cut(tb, cb, 'wall')
rm = []
for f in nb.faces:
    c = f.calc_center_median()
    if abs(f.normal.z) > 0.99 and (abs(c.z - Z_FLOOR) < 1e-3 or abs(c.z - Z_TOP) < 1e-3): rm.append(f)
    elif in_side0(c): rm.append(f)
bmesh.ops.delete(nb, geom=rm, context='FACES')
print('wall faces', len(nb.faces))
merge_into(bm, nb)

# window frames + sills (outer arch ring)
new_f = []
for k in range(1, 8):
    c = math.radians(SIDE_ANGLES[k]); t = Vector((-math.sin(c), math.cos(c), 0)); rad = Vector((math.cos(c), math.sin(c), 0))
    for j in (-1, 0, 1):
        ctr = t * (j * WIN_PITCH)
        cc = math.atan2(rad.y * 1 + 0, rad.x)  # side normal angle
        # frame builder works around a centre angle; emulate lateral offset by building at offset origin
        # (use local copy of builder with offset)
        w, h = WIN_W, WIN_H
        inner, outer = arch_pts(w, h), arch_pts(w + 0.28, h + 0.14)
        def P(x, y, z): return bm.verts.new(rad * y + t * (x + j * WIN_PITCH) + Vector((0, 0, Z_SILL + z)))
        n = len(inner)
        iF = [P(x, A_O + 0.07, z) for x, z in inner]; oF = [P(x, A_O + 0.07, z) for x, z in outer]
        iB = [P(x, A_O - 0.04, z) for x, z in inner]; oB = [P(x, A_O - 0.04, z) for x, z in outer]
        for i in range(1, n):
            jj = (i + 1) % n
            new_f.append(bm.faces.new((iF[i], iF[jj], oF[jj], oF[i])))
            new_f.append(bm.faces.new((oB[i], oB[jj], oF[jj], oF[i])))
            new_f.append(bm.faces.new((iB[jj], iB[i], iF[i], iF[jj])))
        new_f.append(bm.faces.new((iF[0], oF[0], oB[0], iB[0])))
        sv = [bm.verts.new(rad * y + t * (x + j * WIN_PITCH) + Vector((0, 0, Z_SILL + z)))
              for z in (-0.16, 0.0) for (x, y) in ((-0.78, A_O - 0.05), (0.78, A_O - 0.05), (0.78, A_O + 0.30), (-0.78, A_O + 0.30))]
        for q in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            new_f.append(bm.faces.new([sv[i] for i in q]))


# carpets live in their own mesh now (Mosque_01_CarpetFloor, see mosque_carpet.py): drop the old carpet box from the main mesh
old_carpet = [f for f in bm.faces if f.material_index == 5]
bmesh.ops.delete(bm, geom=old_carpet, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
print('old carpet faces removed', len(old_carpet))

# ============ 2b. roof slab: old mesh had duplicated overlapping roof layers (z-fight, bevel failed) -> rebuild clean + bevelled ============
ROOF_A, ROOF_R = 9.53, R_IN                  # slab apothem, hole radius (= drum inner radius)
def is_roof_face(f):
    zs = [v.co.z for v in f.verts]
    if min(zs) < Z_TOP - 0.01 or max(zs) > DZ0 + 0.01: return False
    if max(math.hypot(v.co.x, v.co.y) for v in f.verts) < 4.8: return False
    if all(v.co.y > 8.6 and abs(v.co.x) < 4.3 for v in f.verts): return False      # porch roof slab stays
    return True
old_roof = [f for f in bm.faces if is_roof_face(f)]
print('old roof faces removed', len(old_roof))
bmesh.ops.delete(bm, geom=old_roof, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
# old porch fascia (y=9.53) would sit exactly on the new roof rim -> z-fighting; remove it before building the new slab
fas = [f for f in bm.faces if all(abs(v.co.y - 9.53) < 0.03 and Z_TOP - 0.03 < v.co.z < DZ0 + 0.03 and abs(v.co.x) < 4.1 for v in f.verts)]
bmesh.ops.delete(bm, geom=fas, context='FACES')
print('old porch fascia removed', len(fas))
# the old porch roof slab overlaps the main roof (z-fight): cut it at y=9.56 BEFORE the new main roof exists, so only the old slab is affected
slab = [f for f in bm.faces if all(v.co.y > 8.6 and abs(v.co.x) < 4.3 and Z_TOP - 0.03 < v.co.z < DZ0 + 0.03 for v in f.verts)]
geom = list(set(slab + [e for f in slab for e in f.edges] + [v for f in slab for v in f.verts]))
bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 9.56, 0), plane_no=(0, 1, 0), clear_inner=True, use_snap_center=False)
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
print('porch slab cut at y=9.56')
rb = bmesh.new(); NR = 96
def oct_r(a_deg):
    d = (a_deg - 90 + 22.5) % 45 - 22.5
    return ROOF_A / math.cos(math.radians(d))
rows = {}
for name, r_fn, z in (('ot', oct_r, DZ0), ('ob', oct_r, Z_TOP), ('ct', None, DZ0), ('cb', None, Z_TOP)):
    rows[name] = [rb.verts.new(((r_fn(360.0 * i / NR) if r_fn else ROOF_R) * math.cos(2 * math.pi * i / NR),
                                (r_fn(360.0 * i / NR) if r_fn else ROOF_R) * math.sin(2 * math.pi * i / NR), z)) for i in range(NR)]
for i in range(NR):
    j = (i + 1) % NR
    rb.faces.new((rows['ct'][i], rows['ct'][j], rows['ot'][j], rows['ot'][i]))       # top
    rb.faces.new((rows['ob'][i], rows['ob'][j], rows['cb'][j], rows['cb'][i]))       # underside (faces down after recalc)
    rb.faces.new((rows['ot'][i], rows['ot'][j], rows['ob'][j], rows['ob'][i]))       # rim
    rb.faces.new((rows['cb'][i], rows['cb'][j], rows['ct'][j], rows['ct'][i]))       # hole wall
bmesh.ops.recalc_face_normals(rb, faces=rb.faces)
rim_edges = [e for e in rb.edges if (all(abs(v.co.z - DZ0) < 1e-6 and math.hypot(v.co.x, v.co.y) > 9 for v in e.verts)
                                      or all(abs(v.co.z - Z_TOP) < 1e-6 and math.hypot(v.co.x, v.co.y) > 9 for v in e.verts)
                                      or (math.hypot(e.verts[0].co.x, e.verts[0].co.y) > 9 and abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6
                                          and abs(abs(math.degrees(math.atan2(e.verts[0].co.y, e.verts[0].co.x)) - 90) % 45 - 22.5) < 0.01 + 22.5 * 0 and False))]
# corner (vertical) edges of the octagon: sharp ones only
for e in rb.edges:
    if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(20) and e not in rim_edges and math.hypot(e.verts[0].co.x, e.verts[0].co.y) > 9: rim_edges.append(e)
rb.normal_update()
bmesh.ops.bevel(rb, geom=rim_edges, offset=0.025, offset_type='OFFSET', segments=2, profile=0.5, affect='EDGES', clamp_overlap=True)
roof_new = merge_into(bm, rb) if False else None
vs = [bm.verts.new(v.co) for v in rb.verts]
for f in rb.faces:
    nf = bm.faces.new([vs[v.index] for v in f.verts]); nf.material_index = 0; nf.smooth = False
rb.free()
print('roof rebuilt')

# ============ 2c. stairs: close open side faces ============
st_edges = [e for e in bm.edges if e.is_boundary and e.verts[0].co.y > 9.9 and e.verts[1].co.y > 9.9 and e.verts[0].co.z < 0.95 and e.verts[1].co.z < 0.95]
print('stair boundary edges', len(st_edges))
if st_edges:
    r = bmesh.ops.holes_fill(bm, edges=st_edges, sides=24)
    for f in r['faces']: f.material_index = 1
    print('stair side faces added', len(r['faces']))

# ---- z-fighting above the entrance: old porch fascia sits exactly on the new roof rim (y=9.53) and the porch slab overlaps the main roof ----

# ---- stairs: remove internal duplicate faces (opposite normals on the same spot) and degenerate faces ----
st = [f for f in bm.faces if f.calc_center_median().y > 9.9 and f.calc_center_median().z < 0.96]
seen = {}; dup = []
for f in st:
    c = f.calc_center_median(); k = (round(c.x, 2), round(c.y, 2), round(c.z, 2))
    for g in seen.get(k, []):
        if f.normal.dot(g.normal) < -0.9 and abs(f.calc_area() - g.calc_area()) < 0.01: dup += [f, g]
    seen.setdefault(k, []).append(f)
tiny = [f for f in st if f.calc_area() < 1e-5]
bmesh.ops.delete(bm, geom=list(set(dup + tiny)), context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
stray = [f for f in bm.faces if f.calc_center_median().x > 3.3 and 11.0 < f.calc_center_median().y < 11.3 and 0.88 < f.calc_center_median().z < 0.96 and abs(f.normal.x) > 0.8]   # only the right porch side has this sliver
bmesh.ops.delete(bm, geom=stray, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
print('stray side faces removed', len(stray))
print('stairs: duplicate-pair faces', len(set(dup)), 'degenerate faces', len(tiny))
# ---- wooden door leaves of the old model are replaced by the vanilla church door prefabs ----
wood = [f for f in bm.faces if f.material_index == 3 and abs(f.calc_center_median().x) < 1.6 and 7.4 < f.calc_center_median().y < 8.8]
bmesh.ops.delete(bm, geom=wood, context='FACES')
for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
print('old door leaf faces removed', len(wood))

# ============ 3. drum wall with arched openings ============
tb = bmesh.new(); N = 96
def ring(r, z): return [tb.verts.new((r * math.cos(2 * math.pi * i / N), r * math.sin(2 * math.pi * i / N), z)) for i in range(N)]
ro0, ro1, ri0, ri1 = ring(R_OUT, DZ0), ring(R_OUT, DZ1), ring(R_IN, DZ0), ring(R_IN, DZ1)
for i in range(N):
    j = (i + 1) % N
    tb.faces.new((ro0[i], ro0[j], ro1[j], ro1[i])); tb.faces.new((ri0[j], ri0[i], ri1[i], ri1[j]))
    tb.faces.new((ro0[j], ro0[i], ri0[i], ri0[j])); tb.faces.new((ro1[i], ro1[j], ri1[j], ri1[i]))
bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
cb = bmesh.new()
for k in range(D_N): cutter(cb, math.radians(dang(k)), D_ZS, D_W, D_H, 4.7, 5.6)
bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
nb = boolean_cut(tb, cb, 'drum')
caps = [f for f in nb.faces if abs(f.normal.z) > 0.99 and (abs(f.calc_center_median().z - DZ0) < 1e-3 or abs(f.calc_center_median().z - DZ1) < 1e-3)]
bmesh.ops.delete(nb, geom=caps, context='FACES')
merge_into(bm, nb)
for k in range(D_N):
    c = math.radians(dang(k))
    new_f += frame(bm, c, D_ZS, (D_W, D_H), (D_W + 0.20, D_H + 0.10), 5.29, 5.40, 0.55, 5.28, 5.47)

chk(bm, 'before weld')
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.003)
chk(bm, 'after weld')
new_f = [f for f in new_f if f.is_valid]
bmesh.ops.recalc_face_normals(bm, faces=new_f)
for f in new_f: f.material_index = 0; f.smooth = False

# ============ 4. UVs from nearest old surface ============
uv = bm.loops.layers.uv.active
todo = [f for f in bm.faces if all(abs(l[uv].uv.x) < 1e-6 and abs(l[uv].uv.y) < 1e-6 for l in f.loops)]
def prep(me):
    b = bmesh.new(); b.from_mesh(me); b.faces.ensure_lookup_table()
    return b, b.loops.layers.uv.active, bvhtree.BVHTree.FromBMesh(b)
ob, ouv, tree = prep(old_mesh)
ob2, ouv2, tree2 = prep(old_raw)
def tri_frame(face, lay):
    """per-triangle affine UV frames of a source face: (A, uvA, G_u, G_v, N, tri area) for all non-degenerate triangles"""
    out = []; ls = face.loops
    for i in range(1, len(ls) - 1):
        a, b, c = ls[0], ls[i], ls[i + 1]
        e1 = b.vert.co - a.vert.co; e2 = c.vert.co - a.vert.co; nn = e1.cross(e2)
        if nn.length < 1e-8: continue
        N = nn.normalized()
        du1, du2 = b[lay].uv.x - a[lay].uv.x, c[lay].uv.x - a[lay].uv.x
        dv1, dv2 = b[lay].uv.y - a[lay].uv.y, c[lay].uv.y - a[lay].uv.y
        den = e1.dot(e2.cross(N))
        if abs(den) < 1e-9: continue
        Gu = (e2.cross(N) * du1 + N.cross(e1) * du2) / den; Gv = (e2.cross(N) * dv1 + N.cross(e1) * dv2) / den
        out.append((a.vert.co.copy(), Vector((a[lay].uv.x, a[lay].uv.y)), Gu, Gv, N, (a.vert.co, b.vert.co, c.vert.co)))
    return out


def uv_area(f, uvl):
    p = [l[uvl].uv for l in f.loops]; return abs(sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y for i in range(len(p)))) / 2


def project_uv(f, tree, bmx, lay, nrm_f):
    """UV for a new face from the nearest well-defined source triangle with similar orientation (affine extrapolation).
    Faces perpendicular to the source plane are unfolded along u or v so they never collapse to zero UV area."""
    c = f.calc_center_median(); best = None
    for rad, need in ((0.4, 0.5), (1.5, 0.5), (4.0, 0.5), (4.0, -2.0)):
        for loc, nrm, idx, dist in tree.find_nearest_range(c, rad):
            sf = bmx.faces[idx]
            if sf.normal.dot(nrm_f) < need or sf.calc_area() < 1e-4: continue
            for fr in tri_frame(sf, lay):
                if (fr[2].length + fr[3].length) < 1e-6: continue
                d = (geometry.closest_point_on_tri(c, *fr[5]) - c).length
                if best is None or d < best[0]: best = (d, fr)
        if best: break
    if best is None: return False
    A, uvA, Gu, Gv, N, _ = best[1]; s = max(Gu.length, Gv.length)
    variants = [(Gu, Gv), (Gu + N * s, Gv), (Gu - N * s, Gv), (Gu, Gv + N * s), (Gu, Gv - N * s)]
    bestv = None
    for gu, gv in variants:
        for l in f.loops:
            d = l.vert.co - A; l[uv].uv = (uvA.x + gu.dot(d), uvA.y + gv.dot(d))
        ar = uv_area(f, uv)
        if bestv is None or ar > bestv[0] * 1.5: bestv = (ar, gu, gv)
        if ar > 1e-9 and gu is Gu: break
    for l in f.loops:
        d = l.vert.co - A; l[uv].uv = (uvA.x + bestv[1].dot(d), uvA.y + bestv[2].dot(d))
    return True
def is_body_wall(c):
    r = math.hypot(c.x, c.y)
    return Z_FLOOR <= c.z <= Z_TOP and 8.2 < r < 9.6 and not in_side0(c) and not (c.y > 9.2 and abs(c.x) < 7.0)
nbody = 0; nfail = 0
bm.normal_update()
for f in todo:
    c = f.calc_center_median(); body = is_body_wall(c); nbody += body
    ok = project_uv(f, tree2 if body else tree, ob2 if body else ob, ouv2 if body else ouv, f.normal)
    if not ok: nfail += 1
ob.free(); ob2.free(); bpy.data.meshes.remove(old_mesh); bpy.data.meshes.remove(old_raw)
bad = sum(1 for f in bm.faces for l in f.loops if l[uv].uv.x != l[uv].uv.x or l[uv].uv.y != l[uv].uv.y)
print('uv faces', len(todo), 'body-wall (undistorted)', nbody, 'failed', nfail, 'NaN loops', bad)

# dome: flatten the old raised 3D ribs (they floated / were misaligned with the painted ribs), then low-amplitude hand-made unevenness
from mathutils import noise
bm.normal_update()
dz0 = fz(DOME_Z0); cen = Vector((0, 0, dz0))
def outer_vert(v):
    fs = v.link_faces
    return bool(fs) and any(f.normal.dot(f.calc_center_median() - cen) > 0.3 for f in fs) and not any(f.normal.dot(f.calc_center_median() - cen) < -0.3 for f in fs)
dome_v = [v for v in bm.verts if v.co.z > dz0 + 0.3 and v.co.z < fz(DOME_Z1) - 0.4 and outer_vert(v)]
rings = {}
for v in dome_v: rings.setdefault(round(v.co.z / 0.1), []).append(v)
nflat = 0
for vs in rings.values():
    rs = sorted(math.hypot(v.co.x, v.co.y) for v in vs); med = rs[len(rs) // 2]
    for v in vs:
        r = math.hypot(v.co.x, v.co.y)
        if FLATTEN_RIBS and r - med > 0.012 and r > 1.0: v.co.x *= med / r; v.co.y *= med / r; nflat += 1
for v in dome_v:                                   # radial displacement: same direction -> same value, so nothing tears
    d = v.co - cen; dn = d.normalized()
    v.co += dn * (noise.fractal(dn * 3.0, 0.5, 2.0, 4) * NOISE_A + noise.noise(dn * 14.0) * 0.004)
print('dome: ribs flattened', nflat, 'noise verts', len(dome_v))
for f in bm.faces:
    for l in f.loops:
        l[uv].uv.x = min(1.0, max(0.0, l[uv].uv.x)); l[uv].uv.y = min(1.0, max(0.0, l[uv].uv.y))

# smooth round drum wall
for f in bm.faces:
    c = f.calc_center_median()
    if DZ0 <= c.z <= DZ1 and 4.9 < math.hypot(c.x, c.y) < 5.5 and not f.smooth:
        rad = Vector((c.x, c.y, 0)).normalized()
        if abs(abs(f.normal.dot(rad)) - 1) < 0.02 and abs(f.normal.z) < 0.05: f.smooth = True

# ============ 5. bevel body edges ============
def ok(e):
    if len(e.link_faces) != 2 or e.calc_face_angle(0) < math.radians(50) or e.calc_length() < 0.4: return False
    zs = [v.co.z for v in e.verts]
    if max(zs) > DZ0 + 0.02 and max(math.hypot(*v.co.xy) for v in e.verts) < 6.6: return False   # drum / dome
    return max(zs) <= DZ0 + 0.02
edges = [e for e in bm.edges if ok(e)]
chk(bm, 'before bevel')
bmesh.ops.bevel(bm, geom=edges, offset=0.03, offset_type='OFFSET', segments=2, profile=0.5, affect='EDGES', clamp_overlap=True, loop_slide=True)
chk(bm, 'after bevel')
print('bevelled', len(edges))
bm.to_mesh(o.data); bm.free()

# ============ 6. panes ============
for me in {p.data for p in bpy.data.objects if p.name.startswith('Pane_Drum_')}:
    for v in me.vertices:
        x, y, z = v.co
        pr = D_W / 2 + 0.02; rect = D_H + 0.02 - pr
        v.co = (x * 2 * pr, y, z * (rect / 0.88) if z <= 0.88 else rect + (z - 0.88) * 2 * pr)
for i in range(D_N, 64):
    if f'Pane_Drum_{i}' in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[f'Pane_Drum_{i}'])
for i in range(D_N):
    p = bpy.data.objects[f'Pane_Drum_{i}']; a = math.radians(dang(i))
    p.location = (5.16 * math.cos(a), 5.16 * math.sin(a), D_ZS - 0.02); p.rotation_euler.z = a - math.pi / 2
pw, ph = WIN_W + 0.04, WIN_H + 0.04
for me in {p.data for p in bpy.data.objects if p.name.startswith('Pane_Body_')}:
    sx, r0 = (pw / 2) / 0.755, 0.755
    for v in me.vertices:
        x, y, z = v.co
        z2 = z * ((ph - pw / 2) / (3.115 - r0)) if z <= 3.115 - r0 else (ph - pw / 2) + (z - (3.115 - r0)) * ((pw / 2) / r0)
        v.co = (x * sx, y, z2)
for k in range(1, 8):
    c = math.radians(SIDE_ANGLES[k]); t = Vector((-math.sin(c), math.cos(c), 0)); rad = Vector((math.cos(c), math.sin(c), 0))
    for j in range(3):
        p = bpy.data.objects[f'Pane_Body_{k}_{j}']
        p.location = rad * 8.71 + t * ((j - 1) * WIN_PITCH * (1 if k not in () else 1)) + Vector((0, 0, Z_SILL - 0.02))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT, 'tris', sum(len(p.vertices) - 2 for p in o.data.polygons))
