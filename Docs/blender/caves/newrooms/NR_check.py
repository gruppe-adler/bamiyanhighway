"""NR_check: numeric verification of the two new rooms (plain Python 3 + numpy + scipy, not Blender).
Input: npz files written by NR_voxelize.py (air intervals per 0.2 m column) of the COLLIDER (UTM_) and of the render mesh (LOD0).
  python -I NR_check.py hall  <collider.npz> <lod0.npz> [report.json]
  python -I NR_check.py swim  <collider.npz> <lod0.npz> [report.json]
(PYTHONPATH must contain scipy; NR_shapes.py is imported from this folder for the design floor / sockets.)

Walk graph: every air interval of a column with >= 1.8 m headroom is a standable node at its floor height; nodes of neighbouring
columns join when the floor differs by <= 0.5 m; a node is walkable when the floor slope over a 1.2 m baseline is <= 35 deg
(the design target is 30 deg; the measured slope along the found routes is reported separately).
"""
import sys, os, json, math
import numpy as np
import scipy.ndimage as ndi
import scipy.sparse as sp
import scipy.sparse.csgraph as cg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import NR_shapes as NS

H1 = 1.8
SLOPE_MAX = math.tan(math.radians(35.0))
STEP_MAX = 0.5


class Cols:
    def __init__(self, path):
        d = np.load(path)
        self.step = float(d['step'])
        self.x0, self.y0 = float(d['x0']), float(d['y0'])
        self.nx, self.ny = int(d['nx']), int(d['ny'])
        iv = d['iv']
        self.I = iv[:, 0].astype(np.int64)
        self.J = iv[:, 1].astype(np.int64)
        self.ZF = iv[:, 2].astype(np.float64)
        self.NZ = iv[:, 3].astype(np.float64)
        self.ZR = iv[:, 4].astype(np.float64)
        self.n = len(self.I)
        self.key = self.I * self.ny + self.J
        order = np.argsort(self.key, kind='stable')
        for a in ('I', 'J', 'ZF', 'NZ', 'ZR', 'key'):
            setattr(self, a, getattr(self, a)[order])
        self.X = self.x0 + self.I * self.step
        self.Y = self.y0 + self.J * self.step
        self.HR = self.ZR - self.ZF

    def neighbour(self, di, dj, maxdz=1.2):
        """for every node the node of column (i+di, j+dj) whose floor is closest in height (or -1)"""
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

    def slopes(self, k=3):
        h = self.step
        out = np.zeros(self.n)
        comp = []
        for (di, dj) in ((k, 0), (0, k)):
            a = self.neighbour(di, dj)
            b = self.neighbour(-di, -dj)
            za = np.where(a >= 0, self.ZF[np.maximum(a, 0)], np.nan)
            zb = np.where(b >= 0, self.ZF[np.maximum(b, 0)], np.nan)
            both = (a >= 0) & (b >= 0)
            g = np.where(both, (za - zb) / (2 * k * h), np.where(a >= 0, (za - self.ZF) / (k * h), np.where(b >= 0, (self.ZF - zb) / (k * h), 0.0)))
            comp.append(g)
        return np.hypot(comp[0], comp[1])

    def graph(self, walk):
        rows, cols_, w = [], [], []
        h = self.step
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                nb = self.neighbour(di, dj, STEP_MAX)
                ok = (nb >= 0) & walk
                ok &= walk[np.maximum(nb, 0)]
                a = np.nonzero(ok)[0]
                b = nb[a]
                dz = self.ZF[b] - self.ZF[a]
                rows.append(a)
                cols_.append(b)
                w.append(np.sqrt((di * h) ** 2 + (dj * h) ** 2 + dz * dz))
        r = np.concatenate(rows)
        c = np.concatenate(cols_)
        ww = np.concatenate(w)
        return sp.csr_matrix((ww, (r, c)), shape=(self.n, self.n))

    def node_at(self, x, y, z, rad=0.8, dz=0.9):
        """the node nearest in plan to (x, y) whose floor is within dz of z"""
        d = np.hypot(self.X - x, self.Y - y)
        ok = (d < rad) & (np.abs(self.ZF - z) < dz)
        if not ok.any():
            return -1
        idx = np.nonzero(ok)[0]
        return int(idx[np.argmin(d[idx] + 0.3 * np.abs(self.ZF[idx] - z))])


def pdist(x, y, pts):
    best = np.full(np.shape(x), 1e9)
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = np.clip(((x - ax) * dx + (y - ay) * dy) / l2, 0, 1)
        best = np.minimum(best, np.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def route_stats(C, path, slope):
    z = C.ZF[path]
    s = slope[path]
    st = np.abs(np.diff(z))
    horiz = np.hypot(np.diff(C.X[path]), np.diff(C.Y[path])).sum()
    return dict(nodes=int(len(path)), horizontal_m=round(float(horiz), 1), drop_m=round(float(z.max() - z.min()), 2),
                max_slope_deg=round(math.degrees(math.atan(s.max())), 1), p95_slope_deg=round(math.degrees(math.atan(np.percentile(s, 95))), 1),
                mean_slope_deg_on_slopes=round(math.degrees(math.atan(float(s[s > 0.12].mean()))) if (s > 0.12).any() else 0.0, 1),
                min_headroom_m=round(float(C.HR[path].min()), 2), max_step_between_nodes_m=round(float(st.max()), 2))


def widest(C, walk, comp_nodes, a, b):
    """largest r such that nodes with distance-to-non-walkable >= r (plan view, any level) still connect a and b"""
    mask = np.zeros((C.nx, C.ny), dtype=bool)
    mask[C.I[comp_nodes], C.J[comp_nodes]] = True
    edt = ndi.distance_transform_edt(mask) * C.step
    score = edt[C.I, C.J]
    G = C.graph(walk)
    lo_r, hi_r = 0.0, 6.0
    for _ in range(14):
        r = 0.5 * (lo_r + hi_r)
        keep = walk & (score >= r)
        Gk = G[keep][:, keep]
        idx = np.nonzero(keep)[0]
        pos = {int(v): k for k, v in enumerate(idx)}
        if a not in pos or b not in pos:
            hi_r = r
            continue
        nc, lab = cg.connected_components(Gk, directed=False)
        if lab[pos[a]] == lab[pos[b]]:
            lo_r = r
        else:
            hi_r = r
    return lo_r


def cross_widths(C, walk, ramp, hz_lo=0.35, hz_hi=None, step=0.1):
    """Walkable width across a descent: at every 0.5 m along the ramp's centre line, the contiguous run of walkable floor
    (floor height within 0.6 m of the centre's) along the perpendicular, measured in 0.1 m steps (up to 5 m each side)."""
    lookup = {}
    for n in np.nonzero(walk)[0]:
        lookup.setdefault((int(C.I[n]), int(C.J[n])), []).append(n)
    def find(x, y, z):
        i, j = int(round((x - C.x0) / C.step)), int(round((y - C.y0) / C.step))
        best = None
        for di in (0, -1, 1):
            for dj in (0, -1, 1):
                for n in lookup.get((i + di, j + dj), []):
                    if abs(C.ZF[n] - z) <= 0.6 and (best is None or abs(C.ZF[n] - z) < abs(C.ZF[best] - z)):
                        best = n
        return best
    out = []
    L = ramp.line.L
    for s in np.arange(1.0, L - 1.0, 0.5):
        zc = float(np.interp(s, ramp.ss, ramp.zc))
        if zc < hz_lo or (hz_hi is not None and zc > hz_hi):
            continue
        x, y = ramp.line.at(s)
        x2, y2 = ramp.line.at(s + 0.3)
        x1, y1 = ramp.line.at(s - 0.3)
        tx, ty = x2 - x1, y2 - y1
        nn = math.hypot(tx, ty)
        px, py = -ty / nn, tx / nn
        # start from the walkable node nearest the centre (the centre itself may be a stalagmite: allow a 1 m search)
        c0 = None
        for off in (0.0, 0.3, -0.3, 0.6, -0.6, 1.0, -1.0):
            n = find(x + px * off, y + py * off, zc)
            if n is not None:
                c0 = (off, n)
                break
        if c0 is None:
            out.append((float(s), 0.0))
            continue
        z_here = C.ZF[c0[1]]
        run = [0.0, 0.0]
        for sign, k in ((1, 0), (-1, 1)):
            d = c0[0]
            misses = 0
            while d < 5.0 and d > -5.0:
                d += sign * step
                n = find(x + px * d, y + py * d, z_here)
                if n is None:
                    break
            run[k] = d
        out.append((float(s), round(run[0] - run[1], 2)))
    return out


def hall(coll_path, lod_path, rep):
    sh = NS.HallShape()
    C = Cols(coll_path)
    slope = C.slopes()
    walk = (C.HR >= H1) & (slope <= SLOPE_MAX)
    G = C.graph(walk)
    up_op, lo_op = sh.openings[0], sh.openings[1]
    a = C.node_at(up_op['xy'][0], up_op['xy'][1] - 1.2, up_op['dz'])
    b = C.node_at(lo_op['xy'][0], lo_op['xy'][1] + 1.2, lo_op['dz'])
    rep['upper_socket_node'] = int(a)
    rep['lower_socket_node'] = int(b)
    print('socket nodes', a, b)
    if a < 0 or b < 0:
        rep['error'] = 'socket node missing'
        return
    nc, lab = cg.connected_components(G, directed=False)
    rep['walkable_nodes'] = int(walk.sum())
    rep['upper_connects_to_lower'] = bool(lab[a] == lab[b])
    comp = np.nonzero(lab == lab[a])[0]
    rep['reachable_area_m2'] = round(len(comp) * C.step ** 2, 0)
    # the two descent routes: block one ramp's slope (z > 0.5 within its corridor) and route over the other
    routes = {}
    for name, block, other in (('main_cascade', 'talus', 'ramp'), ('rubble_slope', 'ramp', 'talus')):
        poly = sh.routes['talus' if block == 'talus' else 'main']
        hwb = sh.route_hw['talus' if block == 'talus' else 'main']
        near = pdist(C.X, C.Y, poly) < hwb + 1.5
        w2 = walk & ~(near & (C.ZF > 0.5) & (C.ZF < sh.U - 0.35))       # the other slope only (not the gallery plateau above it)
        G2 = C.graph(w2)
        dist, pred = cg.dijkstra(G2, directed=False, indices=a, return_predecessors=True)
        if not np.isfinite(dist[b]):
            routes[name] = dict(connected=False)
            continue
        path = [b]
        while path[-1] != a:
            path.append(int(pred[path[-1]]))
        path = np.array(path[::-1])
        st = route_stats(C, path, slope)
        # restrict the slope numbers to the descent itself (floor above 0.3 and below the gallery)
        z = C.ZF[path]
        sel = (z > 0.4) & (z < sh.U - 0.2)
        if sel.any():
            st['descent_max_slope_deg'] = round(math.degrees(math.atan(slope[path][sel].max())), 1)
            st['descent_p95_slope_deg'] = round(math.degrees(math.atan(np.percentile(slope[path][sel], 95))), 1)
            st['descent_length_m'] = round(float(dist[path][sel][-1] - dist[path][sel][0]), 1)
        comp2 = np.nonzero(cg.connected_components(G2, directed=False)[1] == cg.connected_components(G2, directed=False)[1][a])[0]
        a_room = C.node_at(up_op['xy'][0], up_op['xy'][1] - 4.0, up_op['dz'])
        b_room = C.node_at(lo_op['xy'][0], lo_op['xy'][1] + 4.0, lo_op['dz'])
        rm = widest(C, w2, comp2, a_room, b_room)
        st['bottleneck_width_m'] = round(2 * rm, 2)
        st['connected'] = True
        # width of the walkable band across the ramp itself: median plan width at the descent nodes
        routes[name] = st
    rep['routes'] = routes
    for name, ramp in (('main_cascade', sh.ramp), ('rubble_slope', sh.talus)):
        cw = cross_widths(C, walk, ramp, 0.35, sh.U - 0.35)
        w = np.array([c[1] for c in cw])
        if len(w):
            routes[name]['cross_section_width_min_m'] = round(float(w.min()), 2)
            routes[name]['cross_section_width_p10_m'] = round(float(np.percentile(w, 10)), 2)
            routes[name]['cross_section_width_median_m'] = round(float(np.median(w)), 2)
            routes[name]['cross_sections'] = len(w)
            routes[name]['narrowest_at'] = [(round(float(ramp.line.at(c[0])[0]), 1), round(float(ramp.line.at(c[0])[1]), 1), c[1]) for c in sorted(cw, key=lambda c: c[1])[:3]]
    # floor integrity: columns inside the footprint without any air interval, and floors far below the design floor (slits)
    L = Cols(lod_path)
    W2 = sh.W2(L.x0 + np.arange(L.nx)[:, None] * L.step, L.y0 + np.arange(L.ny)[None, :] * L.step)
    F = sh.floor2d(L.x0 + np.arange(L.nx)[:, None] * L.step, L.y0 + np.arange(L.ny)[None, :] * L.step)
    has = np.zeros((L.nx, L.ny), dtype=bool)
    lowest = np.full((L.nx, L.ny), 1e9)
    has[L.I, L.J] = True
    np.minimum.at(lowest, (L.I, L.J), L.ZF)
    inside = W2 > 1.6
    missing = inside & ~has
    low = inside & has & (lowest < F - 0.6)
    rep['render_mesh_columns_inside'] = int(inside.sum())
    rep['render_columns_without_air'] = int(missing.sum())
    rep['render_columns_floor_0.6m_below_design'] = int(low.sum())
    if missing.any():
        ii, jj = np.nonzero(missing)
        rep['missing_examples'] = [(round(L.x0 + i * L.step, 1), round(L.y0 + j * L.step, 1)) for i, j in list(zip(ii, jj))[:12]]
    if low.any():
        ii, jj = np.nonzero(low)
        rep['low_floor_examples'] = [(round(L.x0 + i * L.step, 1), round(L.y0 + j * L.step, 1), round(float(lowest[i, j]), 2), round(float(F[i, j]), 2)) for i, j in list(zip(ii, jj))[:12]]
    # headroom on the two levels
    for nm, (lo_z, hi_z) in dict(upper=(sh.U - 0.4, sh.U + 0.4), lower=(-0.4, 0.4)).items():
        m = (C.ZF > lo_z) & (C.ZF < hi_z) & walk
        rep['%s_level_walkable_area_m2' % nm] = round(float(m.sum()) * C.step ** 2, 0)
        rep['%s_level_median_headroom_m' % nm] = round(float(np.median(C.HR[m])), 2) if m.any() else 0


def swim(coll_path, lod_path, rep):
    sh = NS.SwimShape()
    WL = sh.WL
    C = Cols(coll_path)
    h = C.step
    slope = C.slopes()
    ent, ext = sh.openings[0], sh.openings[1]
    # ---- (a) wading + dry walk from the entrance: floors at most 1.2 m under water, 1.0 m headroom, slopes <= 45 deg, steps <= 0.5
    walk_a = (C.ZF >= WL - 1.2) & (C.HR >= 1.0) & (slope <= math.tan(math.radians(45.0)))
    a = C.node_at(ent['xy'][0], ent['xy'][1] + 1.2, 0.0)
    b = C.node_at(ext['xy'][0], ext['xy'][1] - 1.2, 0.0)
    rep['entrance_node'], rep['exit_node'] = int(a), int(b)
    G = C.graph(walk_a)
    nc, lab = cg.connected_components(G, directed=False)
    reach = lab == lab[a]
    rep['a_wade_walk_reaches_exit'] = bool(lab[b] == lab[a])
    rep['a_wade_walk_reached_nodes'] = int(reach.sum())
    rep['a_wade_walk_reached_area_m2'] = round(float(reach.sum()) * h * h, 0)
    rep['a_wade_walk_lowest_floor_z'] = round(float(C.ZF[reach].min()), 2)
    rep['a_wade_walk_max_y_reached'] = round(float(C.Y[reach].max()), 2)
    rep['a_wade_walk_reaches_basin_surface'] = bool((np.abs(C.ZF[reach] - WL) < 0.35).any())
    # entrance lobe nodes that are NOT reached but are on the entrance side (should only be deep floor) / exit lobe nodes reached (must be none)
    rep['a_exit_lobe_nodes_reached'] = int((reach & (C.Y > 4.4)).sum())
    # ---- 3D void grid
    z0, z1 = float(C.ZF.min()) - 0.4, float(C.ZR.max()) + 0.4
    nz = int((z1 - z0) / h) + 1
    V = np.zeros((C.nx, C.ny, nz), dtype=bool)
    k0 = np.round((C.ZF - z0) / h).astype(int)
    k1 = np.round((C.ZR - z0) / h).astype(int)
    for i, j, a_, b_ in zip(C.I, C.J, k0, k1):
        V[i, j, a_:b_ + 1] = True
    zc = z0 + np.arange(nz) * h

    def cell(x, y, z):
        return (int(round((x - C.x0) / h)), int(round((y - C.y0) / h)), int(round((z - z0) / h)))

    dry = V & (zc[None, None, :] > WL)
    wet = V & (zc[None, None, :] <= WL)
    lab_d, nd = ndi.label(dry, structure=np.ones((3, 3, 3)))
    ce, cx_ = cell(ent['xy'][0], ent['xy'][1] + 1.5, 1.0), cell(ext['xy'][0], ext['xy'][1] - 1.5, 1.0)
    rep['air_above_water_connected_entrance_to_exit'] = bool(lab_d[ce] == lab_d[cx_] and lab_d[ce] > 0)
    rep['air_components_above_water'] = int(nd)
    # (b) swim connectivity with clearance
    edt = ndi.distance_transform_edt(V) * h
    # start / end: the roomiest water cell within 1.2 m of the bore centre line where it enters each pool (t = 0.06 / 0.94)
    def roomiest_near(p):
        i0, j0, k0c = cell(p[0], p[1], p[2])
        r_ = int(1.2 / h)
        sub = edt[i0 - r_:i0 + r_ + 1, j0 - r_:j0 + r_ + 1, k0c - r_:k0c + r_ + 1]
        o = np.unravel_index(np.argmax(sub), sub.shape)
        return (i0 - r_ + o[0], j0 - r_ + o[1], k0c - r_ + o[2])
    sA = roomiest_near(sh.bore[14])
    sB = roomiest_near(sh.bore[226])
    rep['swim_start_clearance_m'] = round(float(edt[sA]), 2)
    best = 0.0
    lo_r, hi_r = 0.3, 2.0
    for _ in range(12):
        r = 0.5 * (lo_r + hi_r)
        lab, _n = ndi.label(edt >= r, structure=np.ones((3, 3, 3)))
        if lab[sA] > 0 and lab[sA] == lab[sB]:
            lo_r = r
        else:
            hi_r = r
    rep['b_swim_connected_with_radius_0.9'] = bool(lab[sA] > 0 and (ndi.label(edt >= 0.9, structure=np.ones((3, 3, 3)))[0][sA] == ndi.label(edt >= 0.9, structure=np.ones((3, 3, 3)))[0][sB]))
    rep['b_min_bore_clearance_diameter_m'] = round(2 * lo_r, 2)
    # bore top vs water level: the highest air in the rock between the basins
    iy = np.arange(C.ny)
    yy = C.y0 + iy * h
    # the bore proper: air cells within 1.12 x radius of its centre line, between the basin walls
    Bc = sh.bore
    xs_all = C.x0 + np.arange(C.nx) * h
    ys_all = C.y0 + np.arange(C.ny) * h
    near = np.zeros(V.shape, dtype=bool)
    for p in Bc[::2]:
        i0, i1 = int((p[0] - 2 * p[3] - C.x0) / h), int((p[0] + 2 * p[3] - C.x0) / h) + 1
        j0, j1 = int((p[1] - 2 * p[3] - C.y0) / h), int((p[1] + 2 * p[3] - C.y0) / h) + 1
        k0_, k1_ = int((p[2] - 2 * p[3] - z0) / h), int((p[2] + 2 * p[3] - z0) / h) + 1
        gx, gy, gz = np.meshgrid(xs_all[i0:i1], ys_all[j0:j1], zc[k0_:k1_], indexing='ij')
        near[i0:i1, j0:j1, k0_:k1_] |= (np.sqrt((gx - p[0]) ** 2 + (gy - p[1]) ** 2 + (gz - p[2]) ** 2) <= 1.12 * p[3])
    inbore = V & near
    jj_in = np.nonzero(inbore.any(axis=(0, 2)))[0]
    top_b = max(zc[np.nonzero(inbore[:, jj, :].any(axis=0))[0].max()] for jj in jj_in)
    rep['bore_roof_highest_z_between_basins'] = round(float(top_b), 2)
    rep['bore_roof_margin_below_water_m'] = round(float(WL - top_b), 2)
    # mouths: roof of the void within 2.2 m of the bore centre line at y = -4.4 and +4.4
    B = sh.bore
    for nm, yv in (('A', -4.4), ('B', 4.4)):
        jj = int(round((yv - C.y0) / h))
        cc = B[np.argmin(np.abs(B[:, 1] - yv))]
        xs_ = np.arange(C.nx) * h + C.x0
        gx, gz = np.meshgrid(xs_, zc, indexing='ij')
        near_c = np.hypot(gx - cc[0], gz - cc[2]) <= cc[3] * 1.15
        cols = V[:, jj, :] & near_c
        zt = zc[np.nonzero(cols.any(axis=0))[0].max()] if cols.any() else float('nan')
        rep['mouth_%s_roof_z' % nm] = round(float(zt), 2)
        rep['mouth_%s_roof_below_water_m' % nm] = round(float(WL - zt), 2)
    # bore length: centre line length between the two basin end walls
    seg = np.hypot(np.hypot(np.diff(B[:, 0]), np.diff(B[:, 1])), np.diff(B[:, 2]))
    ymask = (np.abs(0.5 * (B[1:, 1] + B[:-1, 1])) <= 4.3)
    rep['bore_centreline_length_between_basin_walls_m'] = round(float(seg[ymask].sum()), 1)
    rep['bore_centreline_total_m'] = round(float(seg.sum()), 1)
    # (c) dry walk from the exit chamber shore to the exit socket
    walk_c = (C.ZF >= WL) & (C.HR >= H1) & (slope <= SLOPE_MAX)
    Gc = C.graph(walk_c)
    _, labc = cg.connected_components(Gc, directed=False)
    # shore nodes of the exit chamber: floor within 0.4 m above the water level, y > 4.4
    shore = np.nonzero((np.abs(C.ZF - WL) < 0.45) & (C.Y > 4.4) & walk_c)[0]
    rep['c_exit_socket_in_component_with_shore'] = bool(len(shore) and (labc[shore] == labc[b]).any())
    rep['c_exit_shore_nodes'] = int(len(shore))
    rep['c_exit_shore_nodes_connected'] = int((labc[shore] == labc[b]).sum()) if len(shore) else 0
    # entrance floor above water near the entrance
    near = (np.hypot(C.X - ent['xy'][0], C.Y - ent['xy'][1]) < 3.0)
    rep['entrance_floor_min_z_within_3m'] = round(float(C.ZF[near].min()), 2) if near.any() else None
    near = (np.hypot(C.X - ext['xy'][0], C.Y - ext['xy'][1]) < 3.0)
    rep['exit_floor_min_z_within_3m'] = round(float(C.ZF[near].min()), 2) if near.any() else None
    # (roof over the basin stays above the water: min headroom above the water surface where the floor is submerged)
    sub = (C.ZF < WL - 0.3) & (np.abs(C.Y) > 4.6)
    rep['min_air_gap_above_water_over_pool_m'] = round(float((C.ZR[sub] - WL).min()), 2)
    # render-mesh integrity: columns that lack air inside the chambers or have a floor far under the design floor
    L = Cols(lod_path)
    lobeA, lobeB = sh.lobe('A'), sh.lobe('B')
    X = L.x0 + np.arange(L.nx)[:, None] * L.step
    Y = L.y0 + np.arange(L.ny)[None, :] * L.step
    WA, WB = sh.W2(X, Y, lobeA), sh.W2(X, Y, lobeB)
    Wd = np.where(Y < 0, WA, WB)
    F = np.where(Y < 0, sh.floor_lobe(X + 0 * Y, Y + 0 * X, lobeA), sh.floor_lobe(X + 0 * Y, Y + 0 * X, lobeB))
    has = np.zeros((L.nx, L.ny), dtype=bool)
    lowest = np.full((L.nx, L.ny), 1e9)
    has[L.I, L.J] = True
    np.minimum.at(lowest, (L.I, L.J), L.ZF)
    inside = (Wd > 1.6) & (np.abs(Y) > 4.9)
    rep['render_columns_inside'] = int(inside.sum())
    rep['render_columns_without_air'] = int((inside & ~has).sum())
    rep['render_columns_floor_0.6m_below_design'] = int((inside & has & (lowest < F - 0.6)).sum())


if __name__ == '__main__':
    which, coll, lod = sys.argv[1], sys.argv[2], sys.argv[3]
    rep = {}
    (hall if which == 'hall' else swim)(coll, lod, rep)
    print(json.dumps(rep, indent=1))
    if len(sys.argv) > 4:
        json.dump(rep, open(sys.argv[4], 'w'), indent=1)
