"""NR_shapes: signed-distance shapes for the two new cave rooms (numpy only; Blender-free except `to_bmesh`).

  TT_Cave_Hall_TwoLevel     HallShape   two walkable levels (gallery +5.4 m), a cascade ramp down the west wall, a rubble slope
  TT_Cave_Room_SwimThrough  SwimShape   two chambers with a pool each and a submerged, curved bore between them (water level -1.0)

A shape gives sdf(X, Y, Z) (negative = air), floor2d(x, y), plus the routes / sockets / water level the generator needs.
`mt_surface` is a vectorised marching-tetrahedra iso-surface (no tables, watertight, shared edges welded).
Run this file directly to print a quick numeric summary of both shapes.
"""
import math
import numpy as np

# ---------------------------------------------------------------------------------------------------------------------
# noise (improved Perlin, vectorised)

_rs = np.random.RandomState(20241124)
_PERM = _rs.permutation(256).astype(np.int32)
_PERM = np.concatenate([_PERM, _PERM])
_GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1], [1, 1, 0], [-1, 1, 0], [0, -1, 1], [0, -1, -1]], dtype=np.float32)


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(x, y, z):
    x, y, z = np.broadcast_arrays(np.asarray(x, np.float32), np.asarray(y, np.float32), np.asarray(z, np.float32))
    xi = np.floor(x).astype(np.int32)
    yi = np.floor(y).astype(np.int32)
    zi = np.floor(z).astype(np.int32)
    xf, yf, zf = x - xi, y - yi, z - zi
    X, Y, Z = xi & 255, yi & 255, zi & 255
    u, v, w = _fade(xf), _fade(yf), _fade(zf)

    def g(ix, iy, iz, dx, dy, dz):
        h = _PERM[_PERM[_PERM[ix] + iy] + iz] & 15
        gr = _GRAD[h]
        return gr[..., 0] * dx + gr[..., 1] * dy + gr[..., 2] * dz

    n000 = g(X, Y, Z, xf, yf, zf)
    n100 = g(X + 1, Y, Z, xf - 1, yf, zf)
    n010 = g(X, Y + 1, Z, xf, yf - 1, zf)
    n110 = g(X + 1, Y + 1, Z, xf - 1, yf - 1, zf)
    n001 = g(X, Y, Z + 1, xf, yf, zf - 1)
    n101 = g(X + 1, Y, Z + 1, xf - 1, yf, zf - 1)
    n011 = g(X, Y + 1, Z + 1, xf, yf - 1, zf - 1)
    n111 = g(X + 1, Y + 1, Z + 1, xf - 1, yf - 1, zf - 1)
    a = n000 + u * (n100 - n000)
    b = n010 + u * (n110 - n010)
    c = n001 + u * (n101 - n001)
    d = n011 + u * (n111 - n011)
    return (a + v * (b - a)) + w * ((c + v * (d - c)) - (a + v * (b - a)))


def fbm(x, y, z, octaves=3, lac=2.03, gain=0.5, off=(0.0, 0.0, 0.0)):
    amp, tot, out = 1.0, 0.0, 0.0
    fx = 1.0
    for o in range(octaves):
        out = out + amp * perlin(x * fx + off[0] + 17.3 * o, y * fx + off[1] + 5.1 * o, z * fx + off[2] + 9.7 * o)
        tot += amp
        amp *= gain
        fx *= lac
    return out / tot


# ---------------------------------------------------------------------------------------------------------------------
# helpers

def sm01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def smax(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


def smin(a, b, k):
    return -smax(-a, -b, k)


def sd_rbox(x, y, cx, cy, bx, by, r):
    qx = np.abs(x - cx) - (bx - r)
    qy = np.abs(y - cy) - (by - r)
    return np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0)) + np.minimum(np.maximum(qx, qy), 0.0) - r


def gauss_smooth(arr, sigma_samples):
    n = int(sigma_samples * 4) | 1
    xs = np.arange(n) - n // 2
    k = np.exp(-0.5 * (xs / sigma_samples) ** 2)
    k /= k.sum()
    pad = np.pad(arr, (n // 2, n // 2), mode='edge')
    return np.convolve(pad, k, mode='valid')


class Polyline:
    """a 2D polyline with arc length; closest-point queries on arrays"""

    def __init__(self, pts):
        self.p = np.array(pts, dtype=np.float64)
        d = np.hypot(*(self.p[1:] - self.p[:-1]).T)
        self.cum = np.concatenate([[0.0], np.cumsum(d)])
        self.L = float(self.cum[-1])

    def query(self, x, y):
        """(distance, arc length s of the closest point) for arrays x, y"""
        best = np.full(np.broadcast(x, y).shape, 1e9, dtype=np.float32)
        bs = np.zeros_like(best)
        for i in range(len(self.p) - 1):
            ax, ay = self.p[i]
            bx, by = self.p[i + 1]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = np.clip(((x - ax) * dx + (y - ay) * dy) / l2, 0.0, 1.0)
            px, py = ax + t * dx, ay + t * dy
            d = np.hypot(x - px, y - py)
            m = d < best
            best = np.where(m, d, best)
            bs = np.where(m, self.cum[i] + t * math.sqrt(l2), bs)
        return best, bs

    def at(self, s):
        s = np.clip(s, 0.0, self.L)
        x = np.interp(s, self.cum, self.p[:, 0])
        y = np.interp(s, self.cum, self.p[:, 1])
        return x, y


class Ramp:
    """a ridge along a polyline whose top follows z_c(s) (piecewise linear control points, smoothed), with steep flanks"""

    def __init__(self, pts, zs, hw, flank, smooth_m=1.8):
        self.line = Polyline(pts)
        self.hw, self.flank = hw, flank
        ss = np.linspace(0.0, self.line.L, int(self.line.L / 0.05) + 1)
        zc = np.interp(ss, [c[0] for c in zs], [c[1] for c in zs])
        pad = 60
        zc_p = np.concatenate([np.full(pad, zc[0]), zc, np.full(pad, zc[-1])])
        self.ss = ss
        self.zc = gauss_smooth(zc_p, smooth_m / 0.05 / 2.0)[pad:-pad]

    def F(self, x, y):
        d, s = self.line.query(x, y)
        zc = np.interp(s, self.ss, self.zc)
        return np.maximum(0.0, zc - self.flank * np.maximum(0.0, d - self.hw))

    def max_slope_deg(self):
        g = np.gradient(self.zc, self.ss)
        return float(np.degrees(np.arctan(np.abs(g).max())))


# ---------------------------------------------------------------------------------------------------------------------
# marching tetrahedra

_CORNER = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]], dtype=np.int64)
_TETS = []
for _perm in ((1, 2, 4), (1, 4, 2), (2, 1, 4), (2, 4, 1), (4, 1, 2), (4, 2, 1)):
    _TETS.append((0, _perm[0], _perm[0] | _perm[1], 7))
_EDGES = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]


def mt_surface(S, origin, h, level=0.0):
    """iso-surface S == level of a node array S[nx, ny, nz] (inside = S < level). Returns (verts (n,3) float64, tris (m,3)).
    Triangles are oriented with the normal pointing towards S > level (out of the inside)."""
    nx, ny, nz = S.shape
    S = S.astype(np.float32)
    ins = S < level
    c = np.zeros((nx - 1, ny - 1, nz - 1), dtype=np.int8)
    for dx, dy, dz in _CORNER:
        c += ins[dx:nx - 1 + dx, dy:ny - 1 + dy, dz:nz - 1 + dz].astype(np.int8)
    cross = np.argwhere((c > 0) & (c < 8))
    ci, cj, ck = cross[:, 0], cross[:, 1], cross[:, 2]
    node = lambda i, j, k: (i * ny + j) * nz + k
    Sf = S.reshape(-1)
    corner_idx = []
    for dx, dy, dz in _CORNER:
        corner_idx.append(node(ci + dx, cj + dy, ck + dz))
    corner_idx = np.stack(corner_idx, axis=1).astype(np.int64)          # (ncell, 8)
    tri_a, tri_b, tri_c = [], [], []                                    # edge keys (a, b) per triangle vertex (node ids, a<b)
    for tet in _TETS:
        ids = corner_idx[:, list(tet)]                                  # (n, 4)
        val = Sf[ids]
        inside = val < level
        ncount = inside.sum(axis=1)
        for want in (1, 2, 3):
            sel = np.nonzero(ncount == want)[0]
            if len(sel) == 0:
                continue
            idv = ids[sel]
            ins_m = inside[sel]
            order = np.argsort(~ins_m, axis=1, kind='stable')           # inside corners first
            idv = np.take_along_axis(idv, order, axis=1)
            if want == 1:
                o = idv[:, 0]
                tris = [(o, idv[:, 1], o, idv[:, 2], o, idv[:, 3])]
                tris = [((o, idv[:, 1]), (o, idv[:, 2]), (o, idv[:, 3]))]
            elif want == 3:
                o = idv[:, 3]
                tris = [((idv[:, 0], o), (idv[:, 1], o), (idv[:, 2], o))]
            else:
                a, b, c_, d = idv[:, 0], idv[:, 1], idv[:, 2], idv[:, 3]
                # inside a, b; outside c, d: quad on edges ac, ad, bd, bc
                tris = [((a, c_), (a, d), (b, d)), ((a, c_), (b, d), (b, c_))]
            for t in tris:
                tri_a.append(t[0])
                tri_b.append(t[1])
                tri_c.append(t[2])
    ea = [np.stack(p, axis=1) for p in tri_a]
    eb = [np.stack(p, axis=1) for p in tri_b]
    ec = [np.stack(p, axis=1) for p in tri_c]
    E = np.concatenate([np.concatenate(ea), np.concatenate(eb), np.concatenate(ec)], axis=0) if ea else np.zeros((0, 2), np.int64)
    ntri = sum(len(x) for x in ea)
    lo = np.minimum(E[:, 0], E[:, 1])
    hi = np.maximum(E[:, 0], E[:, 1])
    key = lo * (nx * ny * nz) + hi
    uk, inv = np.unique(key, return_inverse=True)
    ulo = uk // (nx * ny * nz)
    uhi = uk % (nx * ny * nz)
    va, vb = Sf[ulo], Sf[uhi]
    t = np.clip((level - va) / np.where(np.abs(vb - va) < 1e-12, 1e-12, (vb - va)), 0.0, 1.0)

    def pos(n):
        i = n // (ny * nz)
        j = (n // nz) % ny
        k = n % nz
        return np.stack([i, j, k], axis=1).astype(np.float64)

    pa, pb = pos(ulo), pos(uhi)
    P = pa + (pb - pa) * t[:, None]
    verts = np.asarray(origin, np.float64) + P * h
    T = inv.reshape(3, ntri).T.astype(np.int64)
    # orientation: normal towards the outside (S > level): use the gradient sign via the edge's endpoint values
    v0, v1, v2 = verts[T[:, 0]], verts[T[:, 1]], verts[T[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    # reference direction: from an inside node to an outside node of the first edge of the triangle
    a_n, b_n = E[:ntri, 0], E[:ntri, 1]
    a_in = Sf[a_n] < level
    p_in = np.where(a_in[:, None], pos(a_n), pos(b_n))
    p_out = np.where(a_in[:, None], pos(b_n), pos(a_n))
    ref = p_out - p_in
    flip = np.einsum('ij,ij->i', n, ref) < 0
    T[flip] = T[flip][:, ::-1]
    return verts, T


def eval_grid(sdf, lo, hi, h, chunk=24):
    """sdf(X, Y, Z) on a regular node grid from lo to hi (inclusive) with spacing h; returns S array and the origin"""
    xs = np.arange(lo[0], hi[0] + 1e-6, h, dtype=np.float32)
    ys = np.arange(lo[1], hi[1] + 1e-6, h, dtype=np.float32)
    zs = np.arange(lo[2], hi[2] + 1e-6, h, dtype=np.float32)
    S = np.empty((len(xs), len(ys), len(zs)), dtype=np.float32)
    for i0 in range(0, len(xs), chunk):
        X = xs[i0:i0 + chunk][:, None, None]
        S[i0:i0 + chunk] = sdf(X, ys[None, :, None], zs[None, None, :])
    return S, np.array(lo, np.float64)


def to_bmesh(verts, tris):
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(v)) for v in verts]
    bm.verts.ensure_lookup_table()
    for t in tris:
        try:
            bm.faces.new((vs[t[0]], vs[t[1]], vs[t[2]]))
        except ValueError:
            pass
    return bm


# ---------------------------------------------------------------------------------------------------------------------
# Hall: two levels

class HallShape:
    name = 'TT_Cave_Hall_TwoLevel'

    def __init__(self, **kw):
        p = dict(HX=7.0, HY=28.6, RC=5.5, U=5.4, HC=10.8, WW=5.2, PA=3.2, seed=3,
                 wall_t=0.9, floor_t=1.5, k_corner=1.3)
        p.update(kw)
        self.p = p
        self.U = p['U']
        s = p['seed']
        self.off = (s * 13.7, s * 7.3, s * 3.9)
        rng = np.random.RandomState(s * 31 + 7)
        # openings (x, y, floor z, outward side)
        self.openings = [dict(side='N', along=-4.4, dz=self.U, xy=(-4.4, p['HY'])),
                         dict(side='S', along=1.2, dz=0.0, xy=(1.2, -p['HY']))]
        # the cascade down the west wall (gallery south end -> lower floor)
        self.ramp = Ramp([(-4.6, 9.0), (-4.7, 2.6), (-4.8, -4.0), (-3.9, -10.5), (-2.6, -16.0), (-1.6, -18.8)],
                         [(0, self.U), (6.4, self.U), (11.0, 3.55), (13.5, 3.55), (18.1, 1.7), (20.4, 1.7), (24.8, 0.0), (40, 0.0)],
                         hw=2.0, flank=1.25, smooth_m=3.2)
        # the shorter, steeper rubble slope from the gallery's east edge
        self.talus = Ramp([(-2.4, 21.8), (-0.6, 18.8), (1.8, 14.6), (4.4, 10.4), (5.4, 8.2)],
                          [(0, self.U), (1.0, self.U), (15.2, 0.0), (30, 0.0)],
                          hw=1.9, flank=1.7, smooth_m=1.8)
        self.gal_y0 = 3.2
        # ceiling pockets (x, y, amp, radius) and drops
        self.pockets = []
        for k in range(9):
            r = rng.uniform(2.2, 4.0)
            for _t in range(30):
                x, y = rng.uniform(-5.5, 5.5), rng.uniform(-24, 24)
                if all(math.hypot(x - a, y - b) > 0.7 * (r + rr) for a, b, _, rr in self.pockets):
                    break
            self.pockets.append((x, y, rng.uniform(1.4, 3.0), r))
        self.drops = []
        for k in range(6):
            self.drops.append((rng.uniform(-5.5, 5.5), rng.uniform(-24, 24), rng.uniform(1.0, 2.2), rng.uniform(1.6, 2.6)))
        # side chambers off the east wall (cx, cy, cz, rx, ry, rz)
        self.alcoves = [(7.3, -12.5, 3.0, 2.8, 3.6, 2.4), (7.6, 14.5, 3.4, 2.6, 3.3, 2.7), (-7.2, -23.0, 2.6, 2.3, 2.8, 2.1)]
        self.routes = dict(
            main=[(-4.6, 9.0), (-4.7, 2.6), (-4.8, -4.0), (-3.9, -10.5), (-2.6, -16.0), (-1.6, -18.8)],
            upper=[(-4.4, 28.6), (-4.4, 22.0), (-4.5, 9.0)],
            talus=[(-2.4, 21.8), (-0.6, 18.8), (1.8, 14.6), (4.4, 10.4), (5.4, 8.2)],
            lower=[(1.2, -28.6), (1.0, -22.0), (-1.6, -18.8)])
        self.route_hw = dict(main=2.0, upper=1.6, talus=1.9, lower=1.6)

    # ---- 2D fields
    def mask_open(self, x, y):
        m = 1.0
        for o in self.openings:
            d = np.hypot(x - o['xy'][0], y - o['xy'][1])
            m = m * sm01((d - 1.5) / 4.0)
        return m

    def W2(self, x, y):
        p = self.p
        hxy = p['HX'] + 0.6 * np.tanh(y / 18.0)
        d = sd_rbox(x, y, 0.0, 0.0, hxy, p['HY'], p['RC'])
        w = -d
        mk = self.mask_open(x, y)
        o = self.off
        warp = 1.5 * perlin(x / 13.0 + o[0], y / 13.0 + o[1], 0.5 + o[2]) + 0.7 * perlin(x / 5.2 + o[1], y / 5.2 + o[2], 1.7 + o[0]) \
            + 0.22 * perlin(x / 1.9 + o[2], y / 1.9 + o[0], 3.1)
        return w + warp * mk

    def Wz(self, x, y, z, W2):
        o = self.off
        mk = self.mask_open(x, y)
        a = 0.95 * perlin(x / 6.5 + o[0], y / 6.5 + o[1], z / 4.8 + o[2]) + 0.38 * perlin(x / 2.4 + o[2], y / 2.4 + o[0], z / 2.0 + o[1])
        return W2 + a * mk

    def xg(self, y):
        o = self.off
        return -1.3 + 1.5 * perlin(y / 9.0 + o[0], 0.5, 0.5) + 0.45 * perlin(y / 3.3 + o[1], 4.5, 0.5)

    def gallery_F(self, x, y):
        o = self.off
        gd = np.minimum(self.xg(y) - x, y - self.gal_y0 + 0.9 * perlin(x / 3.0 + o[0], y / 3.0, 7.5))
        gd = gd + 0.35 * perlin(x / 1.4 + o[1], y / 1.4 + o[2], 2.2)
        return self.U * sm01(gd / 2.2)

    def floor2d(self, x, y):
        f = self.gallery_F(x, y)
        for r in (self.ramp, self.talus):
            g = r.F(x, y)
            mx = np.maximum(f, g)
            f = mx + (smax(f, g, 0.6) - mx) * sm01(np.minimum(f, g) / 0.8)
        f = np.maximum(f, 0.0)
        for op in self.openings:                       # the floor is dead flat (= the socket's floor) where a piece joins on
            d = np.hypot(x - op['xy'][0], y - op['xy'][1])
            f = f + (op['dz'] - f) * (1.0 - sm01((d - 2.5) / 3.0))
        return f

    def ceil2d(self, x, y, W2):
        p = self.p
        s = np.clip(W2 / p['WW'], 0.0, 1.0)
        arch = (1.0 - (1.0 - s) ** p['PA']) ** (1.0 / p['PA'])
        o = self.off
        c = p['HC'] * arch
        c = c + (1.1 * perlin(x / 9.0 + o[0], y / 9.0 + o[1], 5.5) + 0.45 * perlin(x / 3.6 + o[2], y / 3.6 + o[0], 6.5)) * arch
        for (px, py, amp, r) in self.pockets:
            c = c + amp * np.exp(-((x - px) ** 2 + (y - py) ** 2) / (r * r)) * arch
        for (px, py, amp, r) in self.drops:
            c = c - amp * np.exp(-((x - px) ** 2 + (y - py) ** 2) / (r * r)) * arch
        return c

    def sdf(self, X, Y, Z):
        W2 = self.W2(X, Y)
        Wz = self.Wz(X, Y, Z, W2)
        F = self.floor2d(X, Y)
        C = self.ceil2d(X, Y, W2)
        s1 = F - Z
        s2 = Z - C
        s3 = -Wz
        up = smax(s2, s3, self.p['k_corner'])
        for (cx, cy, cz, rx, ry, rz) in self.alcoves:
            wx = 0.7 * perlin(X / 2.3 + cy, Y / 2.3, Z / 2.3 + cx)
            wy = 0.7 * perlin(X / 2.3 + 5.0, Y / 2.3 + cx, Z / 2.3)
            q = np.sqrt(((X + wx - cx) / rx) ** 2 + ((Y + wy - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2) - 1.0
            up = smin(up, q * min(rx, ry, rz), 2.2)
        return smax(up, s1, 0.8)

    def bounds(self):
        p = self.p
        return (-12.5, -p['HY'] - 4.5, -1.8), (12.5, p['HY'] + 4.5, p['HC'] + 4.6)

    def shell_sdf(self, S, h):
        """outer surface: the air sdf pushed out by the rind (walls thinner than the floor)"""
        gx, gy, gz = np.gradient(S, h)
        n = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-9
        down = np.clip(-gz / n, 0.0, 1.0)           # the rock is below the air here: a floor
        t = self.p['wall_t'] + (self.p['floor_t'] - self.p['wall_t']) * down
        return S - t * np.clip(n, 0.7, 2.0)


# ---------------------------------------------------------------------------------------------------------------------
# Swim-through

class SwimShape:
    name = 'TT_Cave_Room_SwimThrough'

    def __init__(self, **kw):
        p = dict(WL=-1.0, seed=7, YA0=-12.2, YA1=-4.3, YB0=4.3, YB1=12.2, bore_r=1.18, wall_t=0.95, floor_t=1.5, k_corner=1.1)
        p.update(kw)
        self.p = p
        s = p['seed']
        self.off = (s * 13.7, s * 7.3, s * 3.9)
        self.WL = p['WL']
        self.openings = [dict(side='S', along=0.0, dz=0.0, xy=(0.0, p['YA0'])),
                         dict(side='N', along=-0.6, dz=0.0, xy=(-0.6, p['YB1']))]
        # the bore: a smooth curve through the rock between the two basins (x, y, z, radius)
        t = np.linspace(0.0, 1.0, 241)
        y = p['YA1'] - 1.2 + (p['YB0'] + 1.2 - (p['YA1'] - 1.2)) * t
        x = 1.5 + (-1.3 - 1.5) * (3 * t * t - 2 * t ** 3) + 1.05 * np.sin(2 * math.pi * t)
        z = -3.5 + (-3.7 + 3.5) * t - 0.42 * np.sin(math.pi * t) + 0.16 * np.sin(3 * math.pi * t)
        r = p['bore_r'] * (1.0 + 0.07 * np.sin(2 * math.pi * 2.3 * t + 0.8)) * (1.0 + 0.30 * (np.exp(-((t - 0.11) / 0.06) ** 2) + np.exp(-((t - 0.89) / 0.06) ** 2)))
        self.bore = np.stack([x, y, z, r], axis=1)
        self.routes = dict(entry=[(0.0, p['YA0']), (0.0, -8.4)], exit=[(-0.6, 8.6), (-0.6, p['YB1'])])
        self.route_hw = dict(entry=1.6, exit=1.6)
        # arc length of the part that lies between the basin walls
        seg = np.hypot(np.hypot(np.diff(x), np.diff(y)), np.diff(z))
        self.bore_len = float(seg.sum())

    # lobes: (cx, cy, hx, hy, r, ceiling, floor profile (y, z) pairs)
    def lobe(self, which):
        p = self.p
        if which == 'A':
            return dict(cx=0.4, cy=0.5 * (p['YA0'] + p['YA1']), hx=6.6, hy=0.5 * (p['YA1'] - p['YA0']), r=3.2, ceil=6.6,
                        prof=[(-14, 0.0), (-9.6, 0.0), (-8.4, -0.5), (-7.4, -1.4), (-6.5, -2.6), (-5.7, -3.8), (-5.1, -4.35), (0, -4.35)])
        return dict(cx=-0.9, cy=0.5 * (p['YB0'] + p['YB1']), hx=6.0, hy=0.5 * (p['YB1'] - p['YB0']), r=3.0, ceil=5.4,
                    prof=[(0, -4.35), (5.1, -4.35), (5.7, -3.8), (6.5, -2.6), (7.4, -1.4), (8.4, -0.5), (9.6, 0.0), (14, 0.0)])

    def W2(self, x, y, L):
        o = self.off
        d = sd_rbox(x, y, L['cx'], L['cy'], L['hx'], L['hy'], L['r'])
        w = -d
        warp = 1.0 * perlin(x / 7.0 + o[0], y / 7.0 + o[1], 0.5) + 0.5 * perlin(x / 3.6 + o[1], y / 3.6 + o[2], 1.7) + 0.2 * perlin(x / 1.7 + o[2], y / 1.7 + o[0], 3.1)
        mk = 1.0
        for op in self.openings:
            mk = mk * sm01((np.hypot(x - op['xy'][0], y - op['xy'][1]) - 1.5) / 3.5)
        return w + warp * mk

    def floor_lobe(self, x, y, L):
        o = self.off
        ys = [c[0] for c in L['prof']]
        zs = [c[1] for c in L['prof']]
        f = np.interp(y, ys, zs)
        # across: a central trough in the pool part, the sides a little shallower
        pool = sm01((-f - 0.3) / 1.5)
        f = f + pool * 0.7 * sm01((np.abs(x - L['cx']) - 2.5) / 3.5)
        f = f + 0.35 * perlin(x / 3.2 + o[0], y / 3.2 + o[1], 8.5) * (1 - pool * 0.3) + 0.12 * perlin(x / 1.1 + o[2], y / 1.1, 3.3)
        for op in self.openings:
            d = np.hypot(x - op['xy'][0], y - op['xy'][1])
            f = f + (op['dz'] - f) * (1.0 - sm01((d - 2.5) / 3.0))
        return f

    def ceil_lobe(self, x, y, W2, L, ph):
        s = np.clip(W2 / 4.4, 0.0, 1.0)
        arch = (1.0 - (1.0 - s) ** 3.0) ** (1.0 / 3.0)
        o = self.off
        c = L['ceil'] * arch + (0.7 * perlin(x / 5.5 + o[0] + ph, y / 5.5 + o[1], 5.5) + 0.3 * perlin(x / 2.5 + o[2], y / 2.5 + o[0], 6.5)) * arch
        # a dome over the pool, drops elsewhere
        c = c + 1.6 * np.exp(-((x - L['cx']) ** 2 / 9.0 + (y - (L['cy'] + (2.2 if ph == 0 else -2.2))) ** 2 / 6.0)) * arch
        return c

    def lobe_sdf(self, X, Y, Z, which):
        L = self.lobe(which)
        W2 = self.W2(X, Y, L)
        o = self.off
        mk = 1.0
        for op in self.openings:
            mk = mk * sm01((np.hypot(X - op['xy'][0], Y - op['xy'][1]) - 1.5) / 3.5)
        Wz = W2 + (1.3 * perlin(X / 5.5 + o[0], Y / 5.5 + o[1], Z / 4.0 + o[2]) + 0.5 * perlin(X / 2.2 + o[2], Y / 2.2 + o[0], Z / 1.8)) * mk
        F = self.floor_lobe(X, Y, L)
        C = self.ceil_lobe(X, Y, W2, L, 0 if which == 'A' else 3.7)
        up = smax(Z - C, -Wz, self.p['k_corner'])
        return smax(up, F - Z, 0.7)

    def bore_sdf(self, X, Y, Z):
        """distance to the bore's centre line minus its radius, only evaluated near it (elsewhere a large positive value)"""
        shape = np.broadcast(X, Y, Z).shape
        Xb, Yb, Zb = [np.broadcast_to(a, shape) for a in (X, Y, Z)]
        out = np.full(shape, 50.0, dtype=np.float32)
        B = self.bore
        near = (Xb > B[:, 0].min() - 3) & (Xb < B[:, 0].max() + 3) & (Yb > B[:, 1].min() - 3) & (Yb < B[:, 1].max() + 3) & (Zb > B[:, 2].min() - 3) & (Zb < B[:, 2].max() + 3)
        idx = np.nonzero(near)
        if len(idx[0]) == 0:
            return out
        px, py, pz = Xb[idx], Yb[idx], Zb[idx]
        best = np.full(px.shape, 1e9, dtype=np.float32)
        rad = np.zeros(px.shape, dtype=np.float32)
        for i in range(len(B) - 1):
            a, b = B[i, :3], B[i + 1, :3]
            ab = b - a
            l2 = float(ab @ ab)
            t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1] + (pz - a[2]) * ab[2]) / l2, 0.0, 1.0)
            qx, qy, qz = a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2]
            d = np.sqrt((px - qx) ** 2 + (py - qy) ** 2 + (pz - qz) ** 2)
            m = d < best
            best = np.where(m, d, best)
            rad = np.where(m, B[i, 3] * (1 - t) + B[i + 1, 3] * t, rad)
        out[idx] = best - rad
        return out

    def sdf(self, X, Y, Z):
        a = self.lobe_sdf(X, Y, Z, 'A')
        b = self.lobe_sdf(X, Y, Z, 'B')
        br = self.bore_sdf(X, Y, Z)
        return smin(smin(a, b, 0.7), br, 0.9)

    def bounds(self):
        return (-11.0, -16.0, -7.4), (11.0, 16.0, 9.6)

    def shell_sdf(self, S, h):
        gx, gy, gz = np.gradient(S, h)
        n = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-9
        down = np.clip(-gz / n, 0.0, 1.0)
        t = self.p['wall_t'] + (self.p['floor_t'] - self.p['wall_t']) * down
        return S - t * np.clip(n, 0.7, 2.0)


def height_png(path, arr, lo, hi):
    """write a greyscale/rgb PNG without PIL (for quick looks)"""
    import zlib, struct
    a = np.clip((arr - lo) / (hi - lo), 0, 1)
    img = (a * 255).astype(np.uint8)
    h, w = img.shape[:2]
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=2)
    raw = b''.join(b'\x00' + img[i].tobytes() for i in range(h))
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


if __name__ == '__main__':
    import time
    t0 = time.time()
    H = HallShape()
    print('ramp max slope %.1f deg, talus %.1f deg' % (H.ramp.max_slope_deg(), H.talus.max_slope_deg()), 'len', H.ramp.line.L, H.talus.line.L)
    xs = np.arange(-12, 12, 0.25)
    ys = np.arange(-34, 34, 0.25)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    F = H.floor2d(X, Y)
    W2 = H.W2(X, Y)
    print('floor z range', F.min(), F.max(), 'time', time.time() - t0)
    img = np.where(W2 > 0, F / 5.4, -0.3)
    height_png('NR_hall_floor.png', img.T[::-1], -0.3, 1.0)
