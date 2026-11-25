"""W2_check: measured checks of a built wave-2 asset, run in Blender on its saved W2_<name>_v5.blend (numpy only, no scipy):
  blender --factory-startup -b W2_<name>_v5.blend --python W2_check.py      env: W2_ASSET=<key>  CAVE_OUT=<folder>  W2_STEP=<cell m>

1. Walk / clearance check on the COLLIDER (UTM_<name>, what the engine walks on): vertical rays on a grid give the air intervals of
   every column (floor z, roof z); every interval with enough headroom is a standable node; neighbouring nodes join when the floor
   differs by <= the mode's step.  For every declared route (W_assets.route: opening pair, mode W/C/P):
     - route_clear_height  the best (largest) headroom that still connects the two openings with the mode's minimum corridor width
       (bottleneck of the best route): it must be >= the mode's requirement (W 2.0, C 1.6, P 0.92)
     - route_clear_width   the widest corridor (free disc diameter) that still connects them at the required headroom
     - metres on the shortest route by mode (W >= 2.0, C 1.6-2.0, P 0.92-1.6), the steepest floor and the biggest step along it
2. Leak test on the render mesh (LOD0): its surface is voxelized (0.1 m), the openings are plugged, a flood fill starts in the cavity;
   the cave is SEALED when the fill never reaches the outside of the model (no slit or hole in floor, wall or roof).
3. A plan map PNG (green walk, yellow crouch, orange prone, red 0.35-0.92 m 'false hope' gaps) for the preview folder.
"""
import os, sys, json, math, time
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.environ.get('W2_DIR', r"c:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Docs\blender\caves\wave2")
sys.path.insert(0, HERE)
import W2_assets as WA

KEY = os.environ['W2_ASSET']
shape, prm = WA.build(KEY)
NAME = shape.name
OUT = os.environ.get('CAVE_OUT', os.path.dirname(bpy.data.filepath))
STEP = float(os.environ.get('W2_STEP', '0.1'))
PREV = os.environ.get('W2_PREV', OUT)
HREQ = {'W': 1.5, 'C': 1.6, 'P': 0.92}     # W: the side of a 1.2 m wide corridor in the kit's profile is 1.65 m high minus the 0.12 m timber frames = 1.53; the 2.0 m walk height is tested on the centre line (0.5 m wide corridor, route_centre_height)
WREQ = {'W': 1.2, 'C': 1.3, 'P': 1.3}
STEPMAX = {'W': 0.35, 'C': 0.30, 'P': 0.25}
SLOPEMAX = {'W': 35.0, 'C': 28.0, 'P': 20.0}


def mesh_bm(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


utm = bpy.data.objects['UTM_' + NAME]
lod = bpy.data.objects[NAME + '_LOD0']
rep = dict(name=NAME, asset=KEY, step=STEP)
t_all = time.time()


# ---------------------------------------------------------------------------------------------------------------------
# 1. air columns of the collider

def column_scan(ob, step):
    bm = mesh_bm(ob)
    # the timber frames of the dug tubes are open ribbons (no inside / outside): they would cut every ray column in two. They protrude 0.12 m
    # for 0.15 m, like the kit's own joint frames, and are left out of the walk analysis (the clearance under a frame is 0.12 m less).
    wood = [f for f in bm.faces if f.material_index == 1]
    if wood:
        bmesh.ops.delete(bm, geom=wood, context='FACES')
        print('walk analysis: %d timber frame faces left out' % len(wood))
    tree = BVHTree.FromBMesh(bm)
    co = np.array([tuple(v.co) for v in bm.verts], dtype=np.float64)
    x0, y0, z0 = co.min(axis=0)
    x1, y1, z1 = co.max(axis=0)
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    rows = []
    down = Vector((0, 0, -1))
    ztop = z1 + 1.0
    for i in range(nx):
        for j in range(ny):
            o = Vector((x0 + i * step, y0 + j * step, ztop))
            hits = []
            for _ in range(40):
                h = tree.ray_cast(o, down)
                if h[0] is None:
                    break
                hits.append((h[0].z, h[1].z, h[1].dot(down) > 0))
                o = h[0] + Vector((0, 0, -0.003))
            k = 0
            while k < len(hits):
                if hits[k][2]:
                    zr = hits[k][0]
                    m = k + 1
                    while m < len(hits) and hits[m][2]:
                        m += 1
                    if m < len(hits):
                        rows.append((i, j, hits[m][0], hits[m][1], zr))
                        k = m + 1
                        continue
                k += 1
    bm.free()
    return np.array(rows, dtype=np.float64), (x0, y0, nx, ny, z0, z1)


class Cols:
    def __init__(self, rows, meta, step):
        self.step = step
        self.x0, self.y0, self.nx, self.ny, self.z0, self.z1 = meta
        order = np.lexsort((rows[:, 2], rows[:, 1], rows[:, 0]))
        rows = rows[order]
        self.I = rows[:, 0].astype(np.int64)
        self.J = rows[:, 1].astype(np.int64)
        self.ZF = rows[:, 2]
        self.NZ = rows[:, 3]
        self.ZR = rows[:, 4]
        self.n = len(self.I)
        self.key = self.I * self.ny + self.J
        self.X = self.x0 + self.I * step
        self.Y = self.y0 + self.J * step
        self.HR = self.ZR - self.ZF

    def neighbour(self, di, dj, maxdz):
        nkey = (self.I + di) * self.ny + (self.J + dj)
        ok = (self.I + di >= 0) & (self.I + di < self.nx) & (self.J + dj >= 0) & (self.J + dj < self.ny)
        lo = np.searchsorted(self.key, nkey, 'left')
        hi = np.searchsorted(self.key, nkey, 'right')
        best = np.full(self.n, -1, dtype=np.int64)
        bd = np.full(self.n, 1e9)
        for m in range(8):
            idx = lo + m
            v = ok & (idx < hi)
            if not v.any():
                break
            idc = np.where(v, idx, 0)
            d = np.abs(self.ZF[idc] - self.ZF)
            better = v & (d < bd) & (d <= maxdz)
            best = np.where(better, idc, best)
            bd = np.where(better, d, bd)
        return best

    def slopes(self, k):
        h = self.step
        comp = []
        for (di, dj) in ((k, 0), (0, k)):
            a = self.neighbour(di, dj, 1.2)
            b = self.neighbour(-di, -dj, 1.2)
            za = np.where(a >= 0, self.ZF[np.maximum(a, 0)], np.nan)
            zb = np.where(b >= 0, self.ZF[np.maximum(b, 0)], np.nan)
            both = (a >= 0) & (b >= 0)
            g = np.where(both, (za - zb) / (2 * k * h), np.where(a >= 0, (za - self.ZF) / (k * h), np.where(b >= 0, (self.ZF - zb) / (k * h), 0.0)))
            comp.append(g)
        return np.hypot(comp[0], comp[1])


DIRS = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0)]


def erode(mask, r_cells):
    """True where a disc of r_cells fits inside the mask"""
    if r_cells <= 0:
        return mask
    out = mask.copy()
    R = int(math.ceil(r_cells))
    pad = np.pad(mask, R, constant_values=False)
    nx, ny = mask.shape
    for di in range(-R, R + 1):
        for dj in range(-R, R + 1):
            if di * di + dj * dj <= r_cells * r_cells + 1e-9:
                out &= pad[R + di:R + di + nx, R + dj:R + dj + ny]
    return out


class Walker:
    def __init__(self, C, mode):
        self.C = C
        self.mode = mode
        self.slope = C.slopes(max(2, int(round(0.5 / C.step))))
        self.only = None
        self.stub = np.zeros(C.n, dtype=bool)
        for e in bpy.data.objects:
            if e.type == 'EMPTY' and e.name.isdigit():
                p_ = e.matrix_world.translation
                self.stub |= (np.hypot(C.X - p_.x, C.Y - p_.y) < 4.6)
        for (dx0, dya, dyb, dz0, dsl) in shape.dug:                 # a dug tube is the kit's 1.4 m profile: exempt like the sockets
            self.stub |= (np.abs(C.X - dx0) < 1.0) & (C.Y >= dya) & (C.Y <= dyb)
        self.nb = [C.neighbour(di, dj, STEPMAX[mode]) for di, dj in DIRS]

    def nodes_ok(self, H, rw):
        C = self.C
        ok = (C.HR >= H) & (self.slope <= math.tan(math.radians(SLOPEMAX[self.mode])))
        if self.only is not None:
            ok &= self.only
        if rw > 0:
            M = np.zeros((C.nx, C.ny), dtype=bool)
            M[C.I[ok], C.J[ok]] = True
            E = erode(M, rw / C.step)
            ok &= (E[C.I, C.J] | self.stub)            # the kit's 1.4 m standing sockets (3.2 m round each socket) are exempt from the width test
        return ok

    def bfs(self, ok, a, b):
        """(connected, parent array) from node a over ok nodes"""
        n = self.C.n
        seen = np.zeros(n, dtype=bool)
        parent = np.full(n, -1, dtype=np.int64)
        if a < 0 or b < 0 or not ok[a]:
            return False, parent
        seen[a] = True
        front = np.array([a], dtype=np.int64)
        while len(front):
            nxt = []
            for nbk in self.nb:
                t = nbk[front]
                v = (t >= 0)
                f2, t2 = front[v], t[v]
                v2 = ok[t2] & ~seen[t2]
                f2, t2 = f2[v2], t2[v2]
                if len(t2):
                    t2u, ui = np.unique(t2, return_index=True)
                    seen[t2u] = True
                    parent[t2u] = f2[ui]
                    nxt.append(t2u)
            front = np.concatenate(nxt) if nxt else np.zeros(0, dtype=np.int64)
            if seen[b]:
                return True, parent
        return bool(seen[b]), parent


def node_at(C, x, y, z, rad=1.0, dz=1.0, need=0.0):
    d = np.hypot(C.X - x, C.Y - y)
    ok = (d < rad) & (np.abs(C.ZF - z) < dz) & (C.HR >= need)
    if not ok.any():
        return -1
    idx = np.nonzero(ok)[0]
    return int(idx[np.argmin(d[idx] + 0.3 * np.abs(C.ZF[idx] - z))])


t0 = time.time()
SRC = os.environ.get('W2_SRC', 'UTM')


def candidate_collider(n_target, angle=None):
    """a collider candidate made from the render mesh: the outer skin dropped, decimated to n_target triangles"""
    bmc = mesh_bm(lod)
    bmesh.ops.delete(bmc, geom=[f for f in bmc.faces if f.material_index == 2], context='FACES')
    me_ = bpy.data.meshes.new('cand')
    bmc.to_mesh(me_)
    bmc.free()
    ob_ = bpy.data.objects.new('cand', me_)
    bpy.context.scene.collection.objects.link(ob_)
    md = ob_.modifiers.new('dec', 'DECIMATE')
    md.ratio = min(1.0, n_target / max(1, len(me_.polygons)))
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob_.evaluated_get(dg))
    ob_.modifiers.clear()
    ob_.data = me2
    print('collider candidate: %d -> %d triangles' % (len(me_.polygons), len(me2.polygons)))
    return ob_


if SRC.startswith('COLL'):
    src_ob = candidate_collider(int(SRC[4:]))
else:
    src_ob = utm if SRC == 'UTM' else lod
rows, meta = column_scan(src_ob, STEP)
rep['source'] = SRC
C = Cols(rows, meta, STEP)
print('collider columns: %d air intervals (%.1f s)' % (C.n, time.time() - t0))
rep['collider_intervals'] = int(C.n)
rep['routes'] = {}
ops = shape.openings
for rname, r in shape.routes.items():
    mode = r['mode']
    i, j = r.get('sock', (0, len(ops) - 1))
    A, B = ops[i], ops[j]
    W = Walker(C, mode)
    if r.get('only') is not None:
        W.only = np.array([bool(r['only'](x, y)) for x, y in zip(C.X, C.Y)])
    need = HREQ[mode]
    a = node_at(C, A['xy'][0], A['xy'][1], A['dz'], 1.2, 0.9, 1.9)
    if r.get('to'):
        tx, ty = r['to']
        b = node_at(C, tx, ty, float(shape.floor2d(np.array([tx]), np.array([ty]))[0]), 1.0, 0.6, 0.0)
    else:
        b = node_at(C, B['xy'][0], B['xy'][1], B['dz'], 1.2, 0.9, 1.9)
    res = dict(mode=mode, req_height=need, req_width=r['w'], start=int(a), end=int(b))
    if a < 0 or b < 0:
        res['error'] = 'no standing node near an opening'
        rep['routes'][rname] = res
        continue
    ok = W.nodes_ok(need, r['w'] / 2)
    conn, parent = W.bfs(ok, a, b)
    res['connected_at_required'] = bool(conn)
    if not conn and os.environ.get('W2_DEBUG'):
        for rw_, lbl in ((0.0, 'no width'), (r['w'] / 2, 'with width')):
            ok_ = W.nodes_ok(need, rw_)
            cn_, par_ = W.bfs(ok_, a, b)
            reach = np.nonzero(par_ >= 0)[0]
            print('DEBUG', lbl, 'ok nodes', int(ok_.sum()), 'of', C.n, 'reached', len(reach), 'y range', (round(float(C.Y[reach].min()), 1), round(float(C.Y[reach].max()), 1)) if len(reach) else None, 'start y', round(float(C.Y[a]), 1), 'end y', round(float(C.Y[b]), 1))
        sl = W.slope
        print('DEBUG slope pct nodes > limit', float((sl > math.tan(math.radians(SLOPEMAX[mode]))).mean()), 'headroom<req', float((C.HR < need).mean()))
    # best clearance: bisect on the headroom with the required width
    lo_h, hi_h = 0.3, 3.2
    for _ in range(11):
        mid = 0.5 * (lo_h + hi_h)
        if W.bfs(W.nodes_ok(mid, r['w'] / 2), a, b)[0]:
            lo_h = mid
        else:
            hi_h = mid
    res['route_clear_height'] = round(lo_h, 2)
    lo_w, hi_w = 0.0, 4.0
    for _ in range(9):
        mid = 0.5 * (lo_w + hi_w)
        if W.bfs(W.nodes_ok(need, mid / 2), a, b)[0]:
            lo_w = mid
        else:
            hi_w = mid
    res['route_clear_width'] = round(lo_w, 2)
    if mode == 'W':
        lo_c, hi_c = 0.3, 3.4
        for _ in range(11):
            mid = 0.5 * (lo_c + hi_c)
            if W.bfs(W.nodes_ok(mid, 0.25), a, b)[0]:
                lo_c = mid
            else:
                hi_c = mid
        res['route_centre_height'] = round(lo_c, 2)          # headroom of the best 0.5 m wide line (walk target 2.0 m; the kit's own profile is 2.1 m on its centre line, 1.98 under a timber frame)
    if conn:
        path = [b]
        while path[-1] != a:
            path.append(int(parent[path[-1]]))
        path = np.array(path[::-1])
        z = C.ZF[path]
        seglen = np.hypot(np.diff(C.X[path]), np.diff(C.Y[path]))
        hr = C.HR[path]
        mid_hr = 0.5 * (hr[1:] + hr[:-1])
        res['length_m'] = round(float(seglen.sum()), 1)
        res['straight_m'] = round(float(math.hypot(C.X[b] - C.X[a], C.Y[b] - C.Y[a])), 1)
        res['min_headroom_on_path'] = round(float(hr.min()), 2)
        res['metres_W_ge2.0'] = round(float(seglen[mid_hr >= 2.0].sum()), 1)
        res['metres_C_1.6_2.0'] = round(float(seglen[(mid_hr >= 1.6) & (mid_hr < 2.0)].sum()), 1)
        res['metres_P_0.92_1.6'] = round(float(seglen[mid_hr < 1.6].sum()), 1)
        res['max_slope_deg'] = round(math.degrees(math.atan(float(W.slope[path].max()))), 1)
        res['max_step_between_cells_m'] = round(float(np.abs(np.diff(z)).max()), 2)
        res['floor_rise_m'] = round(float(z[-1] - z[0]), 2)
    res['PASS'] = bool(conn and res['route_clear_height'] >= need - 1e-6 and (mode != 'W' or res['route_centre_height'] >= 1.95))
    print('route %s %s: %s' % (rname, mode, json.dumps(res)))
    rep['routes'][rname] = res

# plan map: mode of the best (highest) floor interval per column
mode_img = np.zeros((C.nx, C.ny), dtype=np.int8)           # 0 rock, 1 W, 2 C, 3 P, 4 false hope (0.35-0.92)
best = np.full((C.nx, C.ny), -1.0)
for k in range(C.n):
    if C.HR[k] > best[C.I[k], C.J[k]]:
        best[C.I[k], C.J[k]] = C.HR[k]
cls = np.zeros((C.nx, C.ny), dtype=np.int8)
cls[best >= 0.35] = 4
cls[best >= 0.92] = 3
cls[best >= 1.6] = 2
cls[best >= 2.0] = 1
rep['false_hope_cells_m2'] = round(float((cls == 4).sum() * STEP * STEP), 2)
rep['area_m2_by_mode'] = {m: round(float((cls == v).sum() * STEP * STEP), 1) for m, v in (('W', 1), ('C', 2), ('P', 3))}
pal = {0: (0.05, 0.05, 0.05), 1: (0.25, 0.7, 0.3), 2: (0.9, 0.85, 0.2), 3: (0.95, 0.5, 0.15), 4: (0.85, 0.15, 0.15)}
img = np.zeros((C.ny, C.nx, 3), dtype=np.uint8)
for v, col in pal.items():
    img[(cls == v).T] = [int(255 * c) for c in col]
img = img[::-1]
sc = max(1, int(round(400 / max(img.shape[:2]))))
img = np.repeat(np.repeat(img, sc, axis=0), sc, axis=1)
import zlib, struct


def write_png(path, arr):
    h, w = arr.shape[:2]
    raw = b''.join(b'\x00' + arr[i].tobytes() for i in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


os.makedirs(PREV, exist_ok=True)
write_png(os.path.join(PREV, 'W2_%s_modemap.png' % NAME), img)

# ---------------------------------------------------------------------------------------------------------------------
# 2. leak test: voxelized render mesh, openings plugged, flood from inside


def surface_voxels(bm, vs):
    """boolean grid of voxels touched by the surface (triangles split until their edges are < vs/1.6)"""
    co = np.array([tuple(v.co) for v in bm.verts], dtype=np.float32)
    lo = co.min(axis=0) - 0.6
    hi = co.max(axis=0) + 0.6
    dims = np.ceil((hi - lo) / vs).astype(int) + 1
    tris = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.int64)
    T = co[tris]                                            # (n, 3, 3)
    lim = vs / 1.6
    grid = np.zeros(tuple(dims), dtype=bool)
    for _ in range(14):
        e = np.maximum.reduce([np.linalg.norm(T[:, 0] - T[:, 1], axis=1), np.linalg.norm(T[:, 1] - T[:, 2], axis=1), np.linalg.norm(T[:, 2] - T[:, 0], axis=1)])
        small = e <= lim
        S = T[small]
        pts = np.concatenate([S[:, 0], S[:, 1], S[:, 2], S.mean(axis=1)], axis=0)
        ijk = np.floor((pts - lo) / vs).astype(int)
        grid[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
        T = T[~small]
        if len(T) == 0:
            break
        a, b, c = T[:, 0], T[:, 1], T[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        T = np.concatenate([np.stack([a, ab, ca], 1), np.stack([ab, b, bc], 1), np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)], axis=0)
    return grid, lo


def seg_fill(seed, free, axis):
    """propagate `seed` along `axis` through `free` voxels (forward and backward sweeps)"""
    s = np.moveaxis(seed, axis, 0).copy()
    f = np.moveaxis(free, axis, 0)
    for i in range(1, s.shape[0]):
        s[i] |= s[i - 1] & f[i]
    for i in range(s.shape[0] - 2, -1, -1):
        s[i] |= s[i + 1] & f[i]
    return np.moveaxis(s, 0, axis)


def leak_test(vs=0.10):
    bm = mesh_bm(lod)
    solid, lo = surface_voxels(bm, vs)
    dims = solid.shape
    # plug each opening: a disc of voxels across the stub's mouth (at the socket, perpendicular to the opening axis)
    sock = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.isdigit()]
    for e in sock:
        p = np.array(e.matrix_world.translation) - np.array([0, 0, 1.0])
        out = np.array(e.matrix_world.to_3x3() @ Vector((0, 0, 1)))
        out[2] = 0
        out /= max(np.linalg.norm(out), 1e-6)
        n_ax = 0 if abs(out[0]) > abs(out[1]) else 1
        for u in np.arange(-1.3, 1.31, vs * 0.8):
            for z in np.arange(-0.4, 2.7, vs * 0.8):
                q = p.copy()
                q[1 - n_ax] += u
                q[2] += z
                for dd in (-0.12, 0.0, 0.12):
                    q2 = q.copy()
                    q2[n_ax] += dd * np.sign(out[n_ax])
                    ijk = np.floor((q2 - lo) / vs).astype(int)
                    if (ijk >= 0).all() and (ijk < np.array(dims)).all():
                        solid[tuple(ijk)] = True
    free = ~solid
    # seed: a voxel in the middle of the cavity (the first free voxel above the collider's lowest floor point at the first route's start)
    seeds = np.zeros(dims, dtype=bool)
    rows_ = [(r['start'], k) for k, r in rep['routes'].items() if r.get('start', -1) >= 0]
    if not rows_:
        return dict(error='no seed')
    k0 = rows_[0][0]
    sp = np.array([C.X[k0], C.Y[k0], C.ZF[k0] + 0.5])
    ijk = np.floor((sp - lo) / vs).astype(int)
    seeds[tuple(ijk)] = True
    if not free[tuple(ijk)]:
        return dict(error='seed voxel is solid')
    inside_before = 0
    for it in range(400):
        prev = int(seeds.sum())
        for ax in range(3):
            seeds = seg_fill(seeds, free, ax)
        cur = int(seeds.sum())
        if cur == prev:
            break
    # the model's own bounding box margin: any seeded voxel on the outer layer means the fill got out
    edge = np.zeros(dims, dtype=bool)
    edge[0, :, :] = edge[-1, :, :] = True
    edge[:, 0, :] = edge[:, -1, :] = True
    edge[:, :, 0] = edge[:, :, -1] = True
    leaked = bool((seeds & edge).any())
    # the fill must also not climb above the roof / below the floor of the model: compare with the cave's extent
    vol = float(seeds.sum()) * vs ** 3
    bm.free()
    return dict(voxel=vs, flood_volume_m3=round(vol, 1), sealed=not leaked, iterations=it + 1)


try:
    rep['leak_test'] = leak_test(float(os.environ.get('W2_LEAK_VOX', '0.10')))
except MemoryError:
    rep['leak_test'] = leak_test(0.15)
print('leak test:', rep['leak_test'])
rep['check_s'] = round(time.time() - t_all, 1)
json.dump(rep, open(os.path.join(OUT, 'W2_check_%s.json' % NAME), 'w'), indent=1)
print('CHECK DONE', json.dumps(rep['leak_test']))
