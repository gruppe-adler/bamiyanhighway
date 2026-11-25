"""W2_helpers: noise, marching tetrahedra and grid helpers. A snapshot of the helper block of NR_shapes.py
(Docs/blender/caves/newrooms/, another agent's work) so that this folder stays self-contained and stable."""
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

