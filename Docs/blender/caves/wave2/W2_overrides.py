"""W2_overrides: exec'd by W2_v5.py (after the v4/v5 helpers exist, before the build) to turn the generator into one wave-2 asset.
Select with the environment variable W2_ASSET (key in W2_assets.ASSETS).  Built on the same idea as the NR_overrides of the new-rooms
agent (shape = signed distance function, shell = offset surface, openings cut as in build_room), re-written for the W2 shape engine.

PARAMETERS (all in W2_assets.py; everything random is seeded, the same numbers give the same cave)
  grid   sdf sample spacing (m) for the marching-tetrahedra surface;  voxel  remesh voxel of the void and the outer shell (m)
  vox5   v5 merge voxel (m);  budget  triangles of the merged surface;  coll  collider triangles;  fill  small fill formations (before rejects)
  excl   no formations closer than this to a wall (m);  rho_scale  wall distance that counts as 'room centre' for the floor shaping
  crawl_mask  1: roughening is scaled down where the headroom is low (keeps the clearance);  min_clear  the clearance the route must keep
"""
import sys as _sys
_sys.path.insert(0, _HERE5)
import numpy as np
import W2_helpers as WH
import W2_engine as WE
import W2_assets as WA

ASSET_KEY = os.environ['W2_ASSET']
shape, _prm = WA.build(ASSET_KEY)
NAME = shape.name
_base_p = dict(VARIANTS['A'])
_base_p.update(COMMON)
_base_p.update(_prm)
P.clear()
P.update(_base_p)
P['name'] = NAME
P['asset'] = NAME
P['openings'] = [(o['side'], o['along']) for o in shape.openings]
P['_off'] = Vector((random.Random(P['seed']).uniform(-90, 90), random.Random(P['seed'] + 1).uniform(-90, 90), random.Random(P['seed'] + 2).uniform(-90, 90)))
P['_shape'] = shape
P['nr_skip_traverse'] = True
P['nr_nobasinz'] = True
VOX, BUDGET = P['vox5'], P['budget']
COLL_TARGET = P['coll']
HOLE_GROW = VOX * 0.5
FILL_CEIL = P['fill']
FLOOR_EDGE, CEIL_EDGE, WALL_EDGE, GOUR_EDGE = [float(os.environ.get(k, d)) for k, d in
                                               (('CAVE_FLOOR_EDGE', '0.10'), ('CAVE_CEIL_EDGE', '0.12'), ('CAVE_WALL_EDGE', '0.20'), ('CAVE_GOUR_EDGE', '0.07'))]
RENDER = False


# ---------------------------------------------------------------------------------------------------------------------
# fast 2D lookups (bilinear), so per-vertex fields cost microseconds

class Grid2D:
    def __init__(self, fn, x0, x1, y0, y1, h):
        self.x0, self.y0, self.h = x0, y0, h
        xs = np.arange(x0, x1 + h, h, dtype=np.float32)
        ys = np.arange(y0, y1 + h, h, dtype=np.float32)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        self.a = fn(X, Y).astype(np.float64)
        self.nx, self.ny = self.a.shape

    def get(self, x, y):
        u = (x - self.x0) / self.h
        v = (y - self.y0) / self.h
        i = min(max(int(math.floor(u)), 0), self.nx - 2)
        j = min(max(int(math.floor(v)), 0), self.ny - 2)
        fu, fv = min(max(u - i, 0.0), 1.0), min(max(v - j, 0.0), 1.0)
        a = self.a
        return (a[i, j] * (1 - fu) * (1 - fv) + a[i + 1, j] * fu * (1 - fv) + a[i, j + 1] * (1 - fu) * fv + a[i + 1, j + 1] * fu * fv)

    def getv(self, X, Y):
        u = (np.asarray(X) - self.x0) / self.h
        v = (np.asarray(Y) - self.y0) / self.h
        i = np.clip(np.floor(u).astype(int), 0, self.nx - 2)
        j = np.clip(np.floor(v).astype(int), 0, self.ny - 2)
        fu, fv = np.clip(u - i, 0, 1), np.clip(v - j, 0, 1)
        a = self.a
        return a[i, j] * (1 - fu) * (1 - fv) + a[i + 1, j] * fu * (1 - fv) + a[i, j + 1] * (1 - fu) * fv + a[i + 1, j + 1] * fu * fv


_lo, _hi = shape.bounds()
FG = Grid2D(shape.floor2d, _lo[0], _hi[0], _lo[1], _hi[1], 0.1)
WDG = Grid2D(shape.W2, _lo[0], _hi[0], _lo[1], _hi[1], 0.1)
HDG = Grid2D(shape.head2d, _lo[0], _hi[0], _lo[1], _hi[1], 0.1)
FLOORZ = FG.get
FLOORV = FG.getv
RHO = lambda x, y: min(1.2, max(0.0, 1.0 - WDG.get(x, y) / P['rho_scale']))
EXCLUDE = lambda x, y: WDG.get(x, y) < P['excl']


def _dug_zone(c):
    if not shape.dug:
        return False
    d = shape.dug_sd(np.array([c.x]), np.array([c.y]), np.array([c.z]))
    return bool(d[0] > -0.45)


def WMASK(c):
    """scale of the wall/ceiling/floor roughening: smaller where the headroom is low (the crawl clearance must hold) and in a dug tube"""
    m = 1.0
    if P.get('crawl_mask'):
        h = HDG.get(c.x, c.y)
        m = 0.30 + 0.70 * smooth(clamp01((h - 1.7) / 0.9))
        zr = (c.z - FG.get(c.x, c.y)) / max(h, 0.3)                 # the middle of the walls may be rough (the clearance is floor to roof)
        mid = smooth(clamp01((zr - 0.18) / 0.15)) * smooth(clamp01((0.68 - zr) / 0.15))
        m = max(m, 0.85 * mid)
    if shape.dug:
        d = shape.dug_sd(np.array([c.x]), np.array([c.y]), np.array([c.z]))
        if d[0] > -0.35 and d[0] < 0.35:
            m = min(m, 0.22)
    return m


# routes: formations keep clear of them (path_dist), the walkable width is the half width
_RT = [(pts, shape.route_hw.get(k, 1.2)) for k, r in shape.routes.items() for pts in [r['pts']]]


def _pdist(x, y, pts):
    best = 1e9
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2)) if l2 > 0 else 0.0
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def path_dist(x, y):
    if not _RT:
        return 9.0
    return min(max(0.0, _pdist(x, y, pts) - max(0.0, hw - 1.0)) for pts, hw in _RT)


def plan_pools(P, V2):
    P['_basins'] = []


def plan_gours(P):
    gs = []
    for g in shape.gours:
        gs.append(dict(g))
    P['_gours'] = gs


# ---------------------------------------------------------------------------------------------------------------------
# the shell: air from the sdf, rind from the offset sdf, openings cut as in build_room

def probe_opening_w2(tree, side, along, dz, pf):
    out, lat = SIDE[side]
    dists = []
    for dx in (-0.7, 0.0, 0.7):
        for z in (0.25, 1.0, 1.9):
            o = lat * (along + dx) + out * pf
            o = o + Vector((0, 0, z + dz))
            hit = tree.ray_cast(o, out)
            if hit[0] is not None:
                dists.append(hit[3] + pf)
    return min(dists), max(dists)


def build_room(P):
    t0 = time.time()
    sh = P['_shape']
    piece = Piece(P['name'])
    piece.frames = False
    lo, hi = sh.bounds()
    h = P['grid']
    S, org = WH.eval_grid(sh.sdf, lo, hi, h)
    Ssh = sh.shell_sdf(S, h)
    vv, tv = WH.mt_surface(S, org, h, 0.0)
    vo, to_ = WH.mt_surface(Ssh, org, h, 0.0)
    P['_sdf'] = (S, org, h)
    print('sdf grid %s: void mesh %d tris, outer mesh %d tris (%.1f s)' % (S.shape, len(tv), len(to_), time.time() - t0))
    bm_v = WH.to_bmesh(vv, tv)
    bm_o = WH.to_bmesh(vo, to_)
    bmesh.ops.recalc_face_normals(bm_v, faces=bm_v.faces[:])
    bmesh.ops.recalc_face_normals(bm_o, faces=bm_o.faces[:])
    V2 = remesh(bm_v, P['voxel'])
    S_out = remesh(bm_o, P['voxel'])
    bm_v.free()
    bm_o.free()
    print('remeshed: void %d faces (vol %.0f), outer %d faces (vol %.0f) (%.1f s)' % (len(V2.faces), V2.calc_volume(), len(S_out.faces), S_out.calc_volume(), time.time() - t0))
    tree = BVHTree.FromBMesh(V2)
    ob_s = to_object(S_out, P['name'] + '_tmp_outer')
    ob_v = to_object(V2.copy(), P['name'] + '_tmp_void')
    cutters = [ob_v]
    collar = bmesh.new()
    stubs, opens = [], []
    for op in sh.openings:
        side, along, dz = op['side'], op['along'], op['dz']
        out, lat = SIDE[side]
        far = max(v.co.dot(out) for v in ob_s.data.vertices)
        wmin, wmax = probe_opening_w2(tree, side, along, dz, op['pf'])
        base = lat * along + out * wmin
        base.z = dz
        start = lat * along + out * (wmax + 0.55)
        end = lat * along + out * max(far + 0.35, wmax + 1.4)
        start.z = dz
        end.z = dz
        hole = bmesh.new()
        hole_end = lat * along + out * (wmax + 2.2)
        hole_end.z = dz
        dug_op = op.get('dug', False)
        prof = WE.RING_S if dug_op else INNER           # a dug opening has the NEW TT dug kit's ring (1.6 x 2.2, fillet 0.3, no timber)
        if dug_op:
            _prism_base(hole, [(base - out * 0.3, out), (hole_end, out)], offset(prof, 0.001 + HOLE_GROW))
        else:
            prism(hole, [(base - out * 0.3, out), (hole_end, out)], offset(INNER, 0.001))
        cutters.append(to_object(hole, P['name'] + '_tmp_hole'))
        prism(collar, [(base - out * 0.3, out), (start + out * 0.3, out)], offset(offset(prof, SHELL), -0.05) if dug_op else offset(OUTER, -0.05))
        stubs.append((start, end, out, dug_op))
        opens.append(dict(side=side, base=base, out=out, lat=lat, wmin=wmin, wmax=wmax, end=end, dz=dz))
        up = tree.ray_cast(base - out * 0.3 + Vector((0, 0, 0.3)), Vector((0, 0, 1)))
        print('opening %s along %.1f dz %.2f: wall at %.2f..%.2f, stub %.2f..%.2f, headroom %.2f' % (side, along, dz, wmin, wmax, wmax + 0.55, far + 0.35, up[3] if up[0] is not None else -1))
    ob_collar = to_object(collar, P['name'] + '_tmp_collar')
    m = ob_s.modifiers.new('collar', 'BOOLEAN')
    m.operation = 'UNION'
    m.solver = 'EXACT'
    m.object = ob_collar
    for c in cutters:
        m = ob_s.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = c
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob_s.evaluated_get(dg))
    for c in cutters + [ob_collar]:
        bpy.data.objects.remove(c)
    bpy.data.objects.remove(ob_s)
    piece.bm.from_mesh(me)
    print('shell after boolean: %d faces, volume %.1f (void %.1f) (%.1f s)' % (len(piece.bm.faces), piece.bm.calc_volume(), V2.calc_volume(), time.time() - t0))
    bpy.data.meshes.remove(me)
    for a, b, out, dug in stubs:
        if dug:
            # the new dug kit's ring: stub = ring .. ring + 0.6 m of earth, sleeve as in tunnelkit_build_clear.py; NO timber frame
            sweep(piece.bm, [(a, out), (b, out)], WE.RING_S, offset(WE.RING_S, SHELL), closed=True, mat=0)
            piece.socket(b, out, joint_too=False)
            sweep(piece.bm, [(b - out * SLEEVE, out), (b + out * SLEEVE, out)], offset(WE.RING_S, SHELL - SLEEVE_IN), offset(WE.RING_S, SHELL + SLEEVE_T), closed=True, mat=0)
        else:
            sweep(piece.bm, [(a, out), (b, out)], INNER, OUTER, closed=True, mat=0)
            piece.frames = False
            piece.socket(b, out)
    piece.frames = False
    P['_open'] = opens
    P['_paths'] = [Vector((o['base'].x, o['base'].y, 0)) for o in opens]
    plan_pools(P, V2)
    print('shell built in %.1f s' % (time.time() - t0))
    return piece, V2


# ---------------------------------------------------------------------------------------------------------------------
# post steps used by W2_v5.py

MAT_DUG = 4          # the inside of a dug tube (TT_EarthDug in the FBX): the TT dug kit's own earth material in the end


def w2_retag(fbm):
    """faces of the merged surface that lie on a dug tube become MAT_DUG"""
    if not shape.dug:
        return 0
    faces = [f for f in fbm.faces if f.material_index == MAT_EARTH]
    if not faces:
        return 0
    C = np.array([tuple(f.calc_center_median()) for f in faces], dtype=np.float32)
    dd = shape.dug_sd(C[:, 0], C[:, 1], C[:, 2])
    cs = shape.sdf(C[:, 0], C[:, 1], C[:, 2], with_dug=False)
    sel = (np.abs(dd) < 0.09) & (cs > -0.02)
    n = 0
    for f, k in zip(faces, sel):
        if k:
            f.material_index = MAT_DUG
            n += 1
    print('dug tube faces: %d of %d inside faces' % (n, len(faces)))
    return n


# collision: the inner surface only (the outer skin is the terrain's business), decimated
def w2_collider(final_bm, utm, ob_lod):
    cb = final_bm.copy()
    cl = cb.faces.layers.int.get('collide')
    # collide == 0 only drops the separate small formations kept out of the remesh (fid > 0). The remeshed surface got its collide flag from the
    # nearest face before the remesh (transfer), so the rock round a small stalactite's root inherited collide 0: a HOLE in the collider's roof
    # (or floor, round a small stalagmite). Found with W2_check (columns with no air interval); not an issue the older rooms ever tested.
    fl = cb.faces.layers.int.get('fid')
    drop = [f for f in cb.faces if (cl is not None and fl is not None and f[cl] == 0 and f[fl] > 0) or f.material_index == MAT_GROUND]
    bmesh.ops.delete(cb, geom=drop, context='FACES')
    # buried faces: a face whose normal ray runs through solid rock (hits the BACK of a surface) is inside the rock (the stubs' outer skins
    # that split_inside called 'earth in earth'): not part of the walkable inner surface
    cb.faces.ensure_lookup_table()
    nowood = cb.copy()                                  # the timber frames are open ribbons just in front of the wall: they must not count as 'rock' for the test
    bmesh.ops.delete(nowood, geom=[f for f in nowood.faces if f.material_index == MAT_WOOD], context='FACES')
    tr = BVHTree.FromBMesh(nowood)
    buried = []
    for f in cb.faces:
        if f.material_index == MAT_WOOD:
            continue
        n = f.normal
        h = tr.ray_cast(f.calc_center_median() + n * 0.02, n, 3.0)
        if h[0] is not None and h[1].dot(n) > 0.0:
            buried.append(f)
    bmesh.ops.delete(cb, geom=buried, context='FACES')
    nowood.free()
    print('collider: %d buried faces dropped' % len(buried))
    utm.data.clear_geometry()
    cb.to_mesh(utm.data)
    cb.free()
    n_full = len(utm.data.polygons)
    if n_full > COLL_TARGET:
        md = utm.modifiers.new('dec', 'DECIMATE')
        md.ratio = COLL_TARGET / n_full
        md.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        me_c = bpy.data.meshes.new_from_object(utm.evaluated_get(dg))
        utm.modifiers.clear()
        old = utm.data
        utm.data = me_c
        bpy.data.meshes.remove(old)
    return n_full, len(utm.data.polygons)


def verify(piece, lod):
    """W2: every opening's end ring still has all its profile points (INNER, 11 for a cave opening; the dug kit's ring, 24, for a dug one), no open edges"""
    me_ = lod.data
    ok_ = []
    for (pos, out), op in zip(piece.sockets, shape.openings):
        prof = WE.RING_S if op.get('dug') else INNER
        lat = out.cross(Z).normalized()
        found = 0
        for (px, pz) in prof:
            target = pos + lat * px + Z * pz
            if any((v.co - target).length < 2e-3 for v in me_.vertices):
                found += 1
        ok_.append('%d/%d' % (found, len(prof)))
    bm_ = bmesh.new()
    bm_.from_mesh(me_)
    open_edges = sum(1 for e in bm_.edges if len(e.link_faces) != 2)
    bm_.free()
    xs = [v.co.x for v in me_.vertices]
    ys = [v.co.y for v in me_.vertices]
    lo_, hi_ = Vector((min(xs), min(ys), 0)), Vector((max(xs), max(ys), 0))
    facing = []
    for pos, out in piece.sockets:
        gaps = {(1, 0): hi_.x - pos.x, (-1, 0): pos.x - lo_.x, (0, 1): hi_.y - pos.y, (0, -1): pos.y - lo_.y}
        best = min(gaps, key=gaps.get)
        facing.append(best == (round(out.x), round(out.y)))
    return ok_, open_edges, facing
