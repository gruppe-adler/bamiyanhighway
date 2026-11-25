"""NR_overrides: exec'd by NR_v5.py (after the v4/v5 helpers exist, before the build) to turn the generator into the
two new rooms.  Select with the environment variable NR_ROOM = hall | swim.

PARAMETERS (everything random is seeded; same numbers -> same rooms)
  hall  TT_Cave_Hall_TwoLevel (HallShape in NR_shapes.py)
        HX/HY half width/length of the footprint (7.0 / 28.6 m), RC corner radius, HC roof height (10.8 m above the lower floor),
        U gallery floor height (5.4 m), WW/PA arch shoulder width/sharpness. ramp = the cascade down the west wall
        (control points in HallShape.__init__, slope <= 22 deg, 4.0 m wide), talus = the steeper rubble slope (<= 28 deg).
        voxel 0.07 / budget 190k triangles / collider 40k.
  swim  TT_Cave_Room_SwimThrough (SwimShape)
        WL water level (-1.0 m, entrance floor = 0), YA0..YB1 chamber extents, bore_r bore radius (1.18 m, 2.36 m diameter, varies +-7%),
        the bore curve is in SwimShape.__init__.  voxel 0.05 / budget 150k / collider 40k.
  Common: CAVE_OUT output folder (blend, stats), CAVE_FILL number of small fill stalactites, NR_GRID sdf grid spacing.
"""
import sys as _sys
_sys.path.insert(0, _HERE5)
import numpy as np
import importlib
import NR_shapes as NS
importlib.reload(NS)

ROOM = os.environ.get('NR_ROOM', 'hall')
shape = NS.HallShape() if ROOM == 'hall' else NS.SwimShape()
NAME = shape.name

_base_p = dict(VARIANTS['E'])
_base_p.update(COMMON)
_base_p.update(EXTRA['E'])

if ROOM == 'hall':
    _mine = dict(label='TwoLevelHall', asset=NAME, seed=211, rx=7.0, ry=27.0, h=11.0, voxel=0.3, probe_from=24.4, pools=0, gours=0,
                 talus=0.45, relief=0.10, ribs=0.15, wall_amp=0.26, stalactites=80, stalagmites=16, columns=9, pairs=12, straws=0,
                 len_st=(0.6, 3.2), cracks=6, crack_len=(4.0, 8.0), crack_density=4.0, hero=10, curtains=4, boulders=8, candles=3,
                 col_span=11.8, len_scale=1.7, floor_big=0.26, boulder_big=1.3, bank=0.5, swell=0.3, vault=1.0, cluster_scale=2.0,
                 nr_grid=0.25, nr_nobasinz=True, nr_skip_traverse=True, nr_no_plug=True)
    FILL_CEIL = 130
    VOX, BUDGET = 0.07, 130000
    COLL_TARGET = 40000
else:
    _mine = dict(label='SwimThrough', asset=NAME, seed=307, rx=6.2, ry=11.8, h=6.5, voxel=0.25, probe_from=9.0, pools=0, gours=0,
                 talus=0.25, relief=0.08, ribs=0.2, wall_amp=0.32, bulge_amp=0.4, stalactites=60, stalagmites=10, columns=3, pairs=8, straws=0,
                 len_st=(0.4, 2.2), cracks=7, crack_len=(3.0, 6.0), crack_density=9.0, hero=6, curtains=2, boulders=4, candles=3,
                 col_span=7.0, len_scale=1.2, floor_big=0.10, bank=0.3, swell=0.15, vault=0.8, cluster_scale=1.4,
                 nr_grid=0.2, nr_nobasinz=True, nr_skip_traverse=True, nr_no_plug=True)
    FILL_CEIL = 330
    VOX, BUDGET = 0.05, 150000
    COLL_TARGET = 40000
_mine['nr_grid'] = float(os.environ.get('NR_GRID', _mine['nr_grid']))
P.clear()
P.update(_base_p)
P.update(_mine)
P['name'] = NAME
P['_off'] = Vector((random.Random(P['seed']).uniform(-90, 90), random.Random(P['seed'] + 1).uniform(-90, 90), random.Random(P['seed'] + 2).uniform(-90, 90)))
P['_shape'] = shape
HOLE_GROW = VOX * 0.5
FLOOR_EDGE, CEIL_EDGE, WALL_EDGE, GOUR_EDGE = [float(os.environ.get(k, d)) for k, d in
                                               (('CAVE_FLOOR_EDGE', '0.10'), ('CAVE_CEIL_EDGE', '0.16'), ('CAVE_WALL_EDGE', '0.24'), ('CAVE_GOUR_EDGE', '0.07'))]


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
        i = int(math.floor(u))
        j = int(math.floor(v))
        i = min(max(i, 0), self.nx - 2)
        j = min(max(j, 0), self.ny - 2)
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


if ROOM == 'hall':
    _lo, _hi = (-16.0, -36.0), (16.0, 36.0)
    FG = Grid2D(shape.floor2d, _lo[0], _hi[0], _lo[1], _hi[1], 0.2)
    WDG = Grid2D(shape.W2, _lo[0], _hi[0], _lo[1], _hi[1], 0.25)
    WL_ = None
else:
    _lo, _hi = (-12.0, -16.0), (12.0, 16.0)

    def _swim_floor(X, Y):
        return np.where(Y < 0.0, shape.floor_lobe(X, Y, shape.lobe('A')), shape.floor_lobe(X, Y, shape.lobe('B')))

    def _swim_wd(X, Y):
        return np.where(Y < 0.0, shape.W2(X, Y, shape.lobe('A')), shape.W2(X, Y, shape.lobe('B')))
    FG = Grid2D(_swim_floor, _lo[0], _hi[0], _lo[1], _hi[1], 0.2)
    WDG = Grid2D(_swim_wd, _lo[0], _hi[0], _lo[1], _hi[1], 0.25)
    WL_ = shape.WL

FLOORZ = FG.get
FLOORV = FG.getv
RHO = lambda x, y: min(1.2, max(0.0, 1.0 - WDG.get(x, y) / (7.0 if ROOM == 'hall' else 5.5)))
if ROOM == 'swim':
    SEPT = 4.9                                                      # no formations inside the rock between the basins
    EXCLUDE = lambda x, y: abs(y) < SEPT or WDG.get(x, y) < 0.6
    WATERMASK = lambda x, y: FG.get(x, y) < WL_ + 0.35
    _B = shape.bore

    def WMASK(c):
        d2 = (_B[:, 0] - c.x) ** 2 + (_B[:, 1] - c.y) ** 2 + (_B[:, 2] - c.z) ** 2
        d = math.sqrt(float(d2.min()))
        return 0.12 + 0.88 * smooth(clamp01((d - (shape.p['bore_r'] + 0.15)) / 1.2))
else:
    EXCLUDE = lambda x, y: WDG.get(x, y) < 0.8

# routes: formations keep clear of them (path_dist), the walkable width is the half width
_RT = []
for _k, _pts in shape.routes.items():
    _RT.append((_pts, getattr(shape, 'route_hw', {}).get(_k, 1.2)))


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
    return min(max(0.0, _pdist(x, y, pts) - max(0.0, hw - 1.0)) for pts, hw in _RT)


# ---------------------------------------------------------------------------------------------------------------------
# water / pools / terraces

def plan_pools(P, V2):
    P['_basins'] = []


def plan_gours(P):
    gs = []
    if ROOM == 'hall':
        rng = random.Random(P['seed'] * 13 + 5)
        for (x, y, R, d) in ((3.6, -8.0, 2.6, (-0.8, -0.6)), (3.4, 2.5, 2.3, (-0.3, -1.0)), (-4.3, 18.0, 2.4, (0.9, -0.4)), (-3.5, 25.0, 1.8, (0.6, -0.8))):
            n = math.hypot(*d)
            steps = 6
            gs.append(dict(x=x, y=y, R=R, dx=d[0] / n, dy=d[1] / n, steps=steps, ds=2 * R / steps, h=P['gour_h'] * rng.uniform(0.8, 1.1),
                           lip=P['gour_lip'] * rng.uniform(0.8, 1.2), seed=rng.uniform(0, 100)))
    P['_gours'] = gs


# ---------------------------------------------------------------------------------------------------------------------
# the shell: air from the sdf, rind from the offset sdf, openings cut as in build_room

def probe_opening_nr(tree, side, along, dz):
    out, lat = SIDE[side]
    pf = P.get('probe_from', 0.0)
    dists = []
    for dx in (-0.7, 0.0, 0.7):
        for z in (0.25, 1.0, 1.9):
            o = lat * (along + dx) + out * pf
            o = o + Vector((0, 0, z + dz))
            hit = tree.ray_cast(o, out)
            if hit[0] is not None:
                dists.append(hit[3] + pf)
    return min(dists), max(dists)


def shell_field(S, h, vv, tv, t_wall, t_floor, band=5.0):
    """the rind's outer surface as the exact offset of the air surface: the distance of every node near the air mesh to its nearest
    vertex, minus the rind thickness (thicker where the rock is below the air: floors). (An sdf-gradient offset folded into a double skin.)"""
    from mathutils.kdtree import KDTree
    n = np.zeros_like(vv)
    f0, f1, f2 = vv[tv[:, 0]], vv[tv[:, 1]], vv[tv[:, 2]]
    fn = np.cross(f1 - f0, f2 - f0)
    for k in range(3):
        np.add.at(n, tv[:, k], fn)
    n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    kd = KDTree(len(vv))
    for i, v in enumerate(vv):
        kd.insert(Vector(v), i)
    kd.balance()
    out = (S - t_wall).astype(np.float32)
    idx = np.argwhere((S > -0.2) & (S < band))
    org = np.array(P['_sdf_org'])
    for (i, j, k) in idx:
        p = org + np.array((i, j, k)) * h
        co, vi, d = kd.find(Vector(p))
        if S[i, j, k] < 0:
            out[i, j, k] = -1.0
            continue
        tt = t_wall + (t_floor - t_wall) * min(1.0, max(0.0, -n[vi][2]))
        out[i, j, k] = d - tt
    return out


def build_room(P):
    t0 = time.time()
    sh = P['_shape']
    piece = Piece(P['name'])
    piece.frames = False
    lo, hi = sh.bounds()
    h = P['nr_grid']
    S, org = NS.eval_grid(sh.sdf, lo, hi, h)
    P['_sdf_org'] = tuple(org)
    vv, tv = NS.mt_surface(S, org, h, 0.0)
    Ssh = shell_field(S, h, vv, tv, sh.p['wall_t'], sh.p['floor_t'])
    vo, to_ = NS.mt_surface(Ssh, org, h, 0.0)
    P['_sdf'] = (S, org, h)
    print('sdf grid %s: void mesh %d tris, outer mesh %d tris (%.1f s)' % (S.shape, len(tv), len(to_), time.time() - t0))
    bm_v = NS.to_bmesh(vv, tv)
    bm_o = NS.to_bmesh(vo, to_)
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
    far_all = {}
    for op in sh.openings:
        side, along, dz = op['side'], op['along'], op['dz']
        out, lat = SIDE[side]
        far = max(v.co.dot(out) for v in ob_s.data.vertices)
        wmin, wmax = probe_opening_nr(tree, side, along, dz)
        base = lat * along + out * wmin
        base.z = dz
        start = lat * along + out * (wmax + 0.55)
        end = lat * along + out * max(far + 0.35, wmax + 1.4)
        start.z = dz
        end.z = dz
        hole = bmesh.new()
        hole_end = lat * along + out * (wmax + 2.2)
        hole_end.z = dz
        prism(hole, [(base - out * 0.3, out), (hole_end, out)], offset(INNER, 0.001))
        cutters.append(to_object(hole, P['name'] + '_tmp_hole'))
        prism(collar, [(base - out * 0.3, out), (start + out * 0.3, out)], offset(OUTER, -0.05))
        stubs.append((start, end, out))
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
    for a, b, out in stubs:
        sweep(piece.bm, [(a, out), (b, out)], INNER, OUTER, closed=True, mat=0)
        piece.socket(b, out)
    P['_open'] = opens
    P['_paths'] = [Vector((o['base'].x, o['base'].y, 0)) for o in opens]
    plan_pools(P, V2)
    print('shell built in %.1f s' % (time.time() - t0))
    return piece, V2


# the floor field of v4 raises/lowers the floor near the openings to nothing; with a real floor function the opening areas are already flat

# collision: the inner surface only (the outer skin is the terrain's business), decimated with the bore / routes protected
def nr_collider(final_bm, utm, ob_lod):
    cb = final_bm.copy()
    cl = cb.faces.layers.int.get('collide')
    drop = [f for f in cb.faces if (cl is not None and f[cl] == 0) or f.material_index == MAT_GROUND]
    bmesh.ops.delete(cb, geom=drop, context='FACES')
    utm.data.clear_geometry()
    cb.to_mesh(utm.data)
    cb.free()
    n_full = len(utm.data.polygons)
    if n_full > COLL_TARGET:
        co = np.empty(len(utm.data.vertices) * 3, dtype=np.float32)
        utm.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        w = np.full(len(co), 0.5, dtype=np.float32)
        if ROOM == 'swim':
            B = shape.bore
            for i in range(0, len(co), 20000):
                c = co[i:i + 20000]
                d = np.sqrt(((c[:, None, :] - B[None, ::3, :3]) ** 2).sum(axis=2)).min(axis=1)
                w[i:i + 20000] = np.where(d < shape.p['bore_r'] + 1.0, 0.0, 0.5)
        vg = utm.vertex_groups.new(name='imp')
        for lv in np.unique(w):
            vg.add(np.nonzero(w == lv)[0].tolist(), float(lv), 'REPLACE')
        md = utm.modifiers.new('dec', 'DECIMATE')
        md.ratio = COLL_TARGET / n_full
        md.use_collapse_triangulate = True
        if ROOM == 'swim':
            md.vertex_group = 'imp'
            md.vertex_group_factor = 1.0
        dg = bpy.context.evaluated_depsgraph_get()
        me_c = bpy.data.meshes.new_from_object(utm.evaluated_get(dg))
        utm.modifiers.clear()
        old = utm.data
        utm.data = me_c
        bpy.data.meshes.remove(old)
    return n_full, len(utm.data.polygons)


def nr_markers(piece_name):
    """Blender-side markers (not exported to the FBX: the tunnel catalog turns every FBX bone into a socket)"""
    out = {}
    if ROOM == 'swim':
        e = bpy.data.objects.new('WaterLevel', None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 1.5
        e.location = (0.0, 0.0, shape.WL)
        bpy.context.scene.collection.objects.link(e)
        out['WaterLevel'] = shape.WL
    return out

RENDER = False
