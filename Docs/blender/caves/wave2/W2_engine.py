"""W2_engine: the shape engine for the wave-2 cave assets (numpy only, Blender-free).

A `Cave2D` is a 2.5D cave: a footprint (smooth union of centre-line paths with a half width, and ellipses, minus rock islands), a floor
function and a headroom function of position (and of the main path's arc length), plus SDF extras: free-standing rocks, columns from floor
to ceiling, 3D pockets, and 'dug' tubes (the TT dug kit's exact 1.4 x 2.1 m inner profile) for the dug-to-cave transitions.
sdf(X, Y, Z) < 0 is air.  Everything random is seeded; the same numbers give the same cave.
"""
import math
import numpy as np
from W2_helpers import (perlin, fbm, sm01, smax, smin, gauss_smooth, Polyline, Ramp, mt_surface, eval_grid, to_bmesh)

def mk_ring(hw, H, r, nf=4, na=6):
    """the new TT dug kit's ring profile (a copy of mk_profile in tunnelkit_build_clear.py: flat floor, quarter-circle fillet r, straight wall,
    elliptical shoulder, flat crown; 24 points, counter-clockwise, x across, z up from the floor)"""
    cr = min(0.3, hw * 0.45)
    zws = r + 0.55 * (H - r)
    right = []
    for k in range(nf + 1):
        a = math.radians(-90 + 90 * k / nf)
        right.append((hw - r + r * math.cos(a), r + r * math.sin(a)))
    right.append((hw, zws))
    for i in range(1, na + 1):
        a = math.radians(90 * i / na)
        right.append((cr + (hw - cr) * math.cos(a), zws + (H - zws) * math.sin(a)))
    left = [(-x, z) for x, z in reversed(right)]
    return right + left


RING_S = mk_ring(0.80, 2.20, 0.30)      # the dug kit's standing ring, 1.6 m x 2.2 m clear, fillet 0.30 (user decision 2026-11-24, no timber)
KIT_INNER = RING_S                      # what a 'dug tube' is made of


def sd_ellipse(x, y, cx, cy, rx, ry, rot=0.0):
    """approximate signed distance (negative inside) to a rotated ellipse"""
    c, s = math.cos(rot), math.sin(rot)
    u = (x - cx) * c + (y - cy) * s
    v = -(x - cx) * s + (y - cy) * c
    k0 = np.sqrt((u / rx) ** 2 + (v / ry) ** 2)
    k1 = np.sqrt((u / (rx * rx)) ** 2 + (v / (ry * ry)) ** 2)
    return np.where(k1 < 1e-6, -min(rx, ry), k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)).astype(np.float32)


def poly_sd(px, pz, poly):
    """signed distance (negative inside) from points (px, pz) to a closed polygon [(x, z), ...]"""
    shape = np.broadcast(px, pz).shape
    d2 = np.full(shape, 1e9, dtype=np.float32)
    inside = np.zeros(shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        ex, ez = bx - ax, bz - az
        wx, wz = px - ax, pz - az
        t = np.clip((wx * ex + wz * ez) / (ex * ex + ez * ez), 0.0, 1.0)
        dx, dz = wx - ex * t, wz - ez * t
        d2 = np.minimum(d2, dx * dx + dz * dz)
        if abs(ez) > 1e-12:
            cond = (az <= pz) != (bz <= pz)
            xint = ax + (pz - az) * ex / ez
            inside = inside ^ (cond & (px < xint))
    d = np.sqrt(d2)
    return np.where(inside, -d, d)


def smooth_xy(pts, sigma=0.8, step=0.1):
    """a polyline through control points (x, y), resampled every `step` m and gaussian-smoothed with the ends pinned"""
    P = np.array(pts, dtype=np.float64)
    seg = np.hypot(*(P[1:] - P[:-1]).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(cum[-1] / step) + 1)
    ss = np.linspace(0.0, cum[-1], n)
    x = np.interp(ss, cum, P[:, 0])
    y = np.interp(ss, cum, P[:, 1])
    if sigma > 0:
        k = max(1, int(sigma / step))
        pad = 4 * k
        out = []
        for a in (x, y):
            lo = 2 * a[0] - a[1:pad + 1][::-1]          # odd reflection keeps the end points where they are
            hi = 2 * a[-1] - a[-pad - 1:-1][::-1]
            ap = np.concatenate([lo, a, hi])
            out.append(gauss_smooth(ap, k)[pad:-pad])
        x, y = out
    return np.stack([x, y], axis=1)


class PathObj:
    """a centre line with a half width that varies along it (control points (x, y, half width))"""

    def __init__(self, pts_xyh, smooth=0.8):
        P = np.array(pts_xyh, dtype=np.float64)
        ctrl_len = np.concatenate([[0.0], np.cumsum(np.hypot(*(P[1:, :2] - P[:-1, :2]).T))])
        xy = smooth_xy(P[:, :2], smooth)
        self.line = Polyline(xy)
        self.L = self.line.L
        u = self.line.cum / self.L
        self.hw_u = np.array(u)
        hw = np.interp(u, ctrl_len / ctrl_len[-1], P[:, 2])
        self.hw = gauss_smooth(np.concatenate([np.full(20, hw[0]), hw, np.full(20, hw[-1])]), 6)[20:-20]

    def query(self, x, y):
        return self.line.query(x, y)

    def hw_at(self, s):
        return np.interp(s / self.L, self.hw_u, self.hw)

    def xy_at(self, s):
        return self.line.at(s)


class Profile:
    """a smooth function of arc length from control points [(s, v), ...] (flat outside them), gaussian-smoothed by `smooth_m`"""

    def __init__(self, ctrl, L, smooth_m=0.8):
        ss = np.linspace(0.0, L, int(L / 0.05) + 1)
        v = np.interp(ss, [c[0] for c in ctrl], [c[1] for c in ctrl])
        pad = 80
        vp = np.concatenate([np.full(pad, v[0]), v, np.full(pad, v[-1])])
        self.ss = ss
        self.v = gauss_smooth(vp, max(smooth_m / 0.05 / 2.0, 0.5))[pad:-pad] if smooth_m > 0 else v

    def __call__(self, s):
        return np.interp(s, self.ss, self.v)


def bump(x, y, cx, cy, rx, ry, rot, blend):
    """1 inside an ellipse, falling to 0 over `blend` metres outside it (smoothstep)"""
    q = sd_ellipse(x, y, cx, cy, rx, ry, math.radians(rot))
    return 1.0 - sm01(q / max(blend, 1e-3))


def arch(s, pa=2.6):
    s = np.clip(s, 0.0, 1.0)
    return (1.0 - (1.0 - s) ** pa) ** (1.0 / pa)


class Cave2D:
    def __init__(self, name, seed, **kw):
        self.name = name
        self.seed = seed
        self.off = (seed * 13.7, seed * 7.3, seed * 3.9)
        self.p = dict(wall_t=0.9, floor_t=1.5, k_corner=0.9, k_floor=0.6, wa=0.9, pa=2.6, use_arch=True, H0=3.0,
                      wall_noise=(0.55, 0.20), wall_open_r=(1.5, 3.5), floor_noise=(0.04, 0.012), head_noise=(0.25, 0.10),
                      lean=(0.0, 0.0), lean_ref=0.0, k_foot=0.8, open_h=2.7)
        self.p.update(kw)
        self.paths, self.ells, self.islands = [], [], []
        self.floor_terms = []            # callables (x, y, ctx) -> array, summed into the flat floor
        self.zones = []                  # headroom limits
        self.prof_head = None            # (Profile of headroom along the main path, reach in m)
        self.rocks, self.cols, self.dug, self.pockets, self.pockets_3d = [], [], [], [], []
        self.openings = []
        self.routes = {}                 # name -> dict(pts=[(x, y), ...], mode='W'|'C'|'P', w=required width, a=(x, y), b=(x, y))
        self.route_hw = {}
        self.gours = []
        self.main = None
        self.dug_frames = []             # (x, y, z, out_dir) timber frames inside dug tubes (kit profile, drawn by the build script)

    # ---- building blocks -------------------------------------------------------------------------------------------
    def add_path(self, pts, smooth=0.8):
        p = PathObj(pts, smooth)
        self.paths.append(p)
        if self.main is None:
            self.main = p
        return p

    def add_ellipse(self, cx, cy, rx, ry, rot=0.0):
        self.ells.append((cx, cy, rx, ry, math.radians(rot)))

    def add_island(self, cx, cy, rx, ry, rot=0.0):
        self.islands.append((cx, cy, rx, ry, math.radians(rot)))

    def add_opening(self, side, along, dz, pf, xy):
        self.openings.append(dict(side=side, along=along, dz=dz, pf=pf, xy=xy))

    def add_zone(self, cx, cy, rx, ry, rot, hz, fall=1.5, grad=0.0):
        """headroom limit hz (+ grad per metre along the zone's long axis) inside the ellipse, easing back over `fall` m"""
        self.zones.append((cx, cy, rx, ry, math.radians(rot), hz, fall, grad))

    def add_rock(self, cx, cy, cz, rx, ry, rz, seed=0):
        self.rocks.append((cx, cy, cz, rx, ry, rz, seed))

    def add_column(self, x, y, r, seed=0):
        self.cols.append((x, y, r, seed))

    def add_dug(self, x0, ya, yb, z0=0.0, slope=0.0):
        self.dug.append((x0, ya, yb, z0, slope))

    def add_floor(self, fn):
        self.floor_terms.append(fn)

    # ---- 2D fields -------------------------------------------------------------------------------------------------
    def depth(self, x, y):
        """metres to the nearest wall (positive inside the footprint)"""
        w = None
        for p in self.paths:
            d, s = p.query(x, y)
            dep = p.hw_at(s) - d
            w = dep if w is None else smax(w, dep, self.p['k_foot'])
        for (cx, cy, rx, ry, rot) in self.ells:
            dep = -sd_ellipse(x, y, cx, cy, rx, ry, rot)
            w = dep if w is None else smax(w, dep, self.p['k_foot'])
        for (cx, cy, rx, ry, rot) in self.islands:
            w = smin(w, sd_ellipse(x, y, cx, cy, rx, ry, rot), 0.7)
        return w

    def open_mask(self, x, y):
        m = 1.0
        r0, r1 = self.p['wall_open_r']
        for op in self.openings:
            d = np.hypot(x - op['xy'][0], y - op['xy'][1])
            m = m * sm01((d - r0) / (r1 - r0))
        return m

    def ctx(self, x, y):
        c = {'W2': self.depth(x, y)}
        if self.main is not None:
            c['d'], c['s'] = self.main.query(x, y)
        c['mk'] = self.open_mask(x, y)
        return c

    def floor_flat(self, x, y, c):
        f = 0.0
        for t in self.floor_terms:
            f = f + t(x, y, c)
        for op in self.openings:                   # dead flat (= the socket's floor) where a piece joins on
            d = np.hypot(x - op['xy'][0], y - op['xy'][1])
            f = f + (op['dz'] - f) * (1.0 - sm01((d - 2.0) / 2.5))
        return f

    def floor(self, x, y, c=None, ff=None):
        c = c or self.ctx(x, y)
        ff = self.floor_flat(x, y, c) if ff is None else ff
        o = self.off
        a1, a2 = self.p['floor_noise']
        n = a1 * perlin(x / 2.6 + o[0], y / 2.6 + o[1], 8.5) + a2 * perlin(x / 0.9 + o[2], y / 0.9 + o[0], 3.3)
        return ff + n * c['mk']

    def headroom(self, x, y, c=None, ff=None):
        """ceiling height above the flat floor"""
        c = c or self.ctx(x, y)
        p = self.p
        o = self.off
        W2 = c['W2']
        H0 = p['H0']
        if callable(H0):
            H0 = H0(x, y, c)
        ar = arch(W2 / p['wa'], p['pa']) if p['use_arch'] else 1.0
        H = H0 * ar
        a1, a2 = p['head_noise']
        H = H + (a1 * perlin(x / 4.5 + o[0], y / 4.5 + o[1], 5.5) + a2 * perlin(x / 1.8 + o[2], y / 1.8 + o[0], 6.5)) * c['mk'] * ar
        for (px, py, amp, r) in self.pockets:
            H = H + amp * np.exp(-((x - px) ** 2 + (y - py) ** 2) / (r * r))
        if self.prof_head is not None:
            prof, dmax = self.prof_head
            w = 1.0 - sm01((c['d'] - dmax) / 1.2)
            Hp = prof(c['s'])
            H = H + (np.minimum(H, Hp) - H) * w
        for (cx, cy, rx, ry, rot, hz, fall, grad) in self.zones:
            q = sd_ellipse(x, y, cx, cy, rx, ry, rot)
            m = 1.0 - sm01(q / max(fall, 1e-3))
            u = (x - cx) * math.cos(rot) + (y - cy) * math.sin(rot)
            H = H + (np.minimum(H, hz + grad * u) - H) * m
        for op in self.openings:                   # standing height at every mouth
            d = np.hypot(x - op['xy'][0], y - op['xy'][1])
            lift = p['open_h'] * (1.0 - sm01((d - 2.2) / 1.6))
            H = np.maximum(H, lift)
        return H

    def floor2d(self, x, y):
        return self.floor(x, y)

    def W2(self, x, y):
        return self.depth(x, y)

    def head2d(self, x, y):
        return self.headroom(x, y)

    # ---- the signed distance field ---------------------------------------------------------------------------------
    def sdf(self, X, Y, Z, with_dug=True):
        p = self.p
        o = self.off
        c = self.ctx(X, Y)
        ff = self.floor_flat(X, Y, c)
        F = self.floor(X, Y, c, ff)
        C = ff + self.headroom(X, Y, c, ff)
        W2 = c['W2']
        mk = c['mk']
        lx, ly = p['lean']
        if lx or ly:
            zc = (np.clip(Z - ff, 0.0, 12.0) - p['lean_ref']) * mk       # no lean at the mouths
            W2z = self.depth(X + lx * zc, Y + ly * zc)
        else:
            W2z = W2
        a1, a2 = p['wall_noise']
        Wz = W2z + (a1 * perlin(X / 6.5 + o[0], Y / 6.5 + o[1], Z / 4.8 + o[2]) + a2 * perlin(X / 2.4 + o[2], Y / 2.4 + o[0], Z / 2.0 + o[1])) * mk
        up = smax(Z - C, -Wz, p['k_corner'])
        s = smax(up, F - Z, p['k_floor'])
        for (cx, cy, cz, rx, ry, rz, sd) in self.rocks:           # solid blocks standing in the air
            q = np.sqrt(((X + 0.25 * perlin(X * 1.1 + sd, Y * 1.1, Z * 1.1 + 3.0) - cx) / rx) ** 2
                        + ((Y + 0.25 * perlin(X * 1.1, Y * 1.1 + sd, Z * 1.1) - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2) - 1.0
            s = smax(s, -(q * min(rx, ry, rz) * 0.9), 0.22)
        for (cx, cy, r, sd) in self.cols:                          # columns floor to ceiling, flaring at both ends
            rr = r * (1.0 + 0.35 * np.exp(-np.maximum(C - Z, 0.0) / 0.55) + 0.30 * np.exp(-np.maximum(Z - F, 0.0) / 0.55)
                      + 0.10 * perlin(X * 1.7 + sd, Y * 1.7, Z * 0.9))
            s = smax(s, -(np.hypot(X - cx, Y - cy) - rr), 0.3)
        for (cx, cy, cz, rx, ry, rz) in self.pockets_3d:
            q = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2) - 1.0
            s = smin(s, q * min(rx, ry, rz), 0.9)
        if with_dug:
            dd = self.dug_sd(X, Y, Z)
            if dd is not None:
                s = np.minimum(s, dd)
        return s

    def dug_sd(self, X, Y, Z):
        out = None
        for (x0, ya, yb, z0, sl) in self.dug:
            sp = poly_sd(X - x0, Z - (z0 + sl * Y), KIT_INNER)
            v = np.maximum(sp, np.maximum(ya - Y, Y - yb))
            out = v if out is None else np.minimum(out, v)
        return out

    def bounds(self):
        xs, ys = [], []
        for p in self.paths:
            m = p.hw.max() + 0.5
            xs += [p.line.p[:, 0].min() - m, p.line.p[:, 0].max() + m]
            ys += [p.line.p[:, 1].min() - m, p.line.p[:, 1].max() + m]
        for (cx, cy, rx, ry, rot) in self.ells:
            r = max(rx, ry)
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        for (x0, ya, yb, z0, sl) in self.dug:
            xs += [x0 - 1.5, x0 + 1.5]
            ys += [ya, yb]
        for op in self.openings:
            xs.append(op['xy'][0])
            ys.append(op['xy'][1])
        m = 2.7
        x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
        gx = np.arange(x0, x1, 0.4)
        gy = np.arange(y0, y1, 0.4)
        GX, GY = np.meshgrid(gx, gy, indexing='ij')
        c = self.ctx(GX, GY)
        ff = self.floor_flat(GX, GY, c)
        F = self.floor(GX, GY, c, ff)
        C = ff + self.headroom(GX, GY, c, ff)
        ok = c['W2'] > 0.0
        zmin = float(F[ok].min()) if ok.any() else -1.0
        zmax = float(C[ok].max()) if ok.any() else 3.0
        for (x0_, ya, yb, z0, sl) in self.dug:
            zmin = min(zmin, z0 + min(sl * ya, sl * yb))
            zmax = max(zmax, z0 + 2.1 + max(sl * ya, sl * yb))
        return (x0, y0, zmin - 2.4), (x1, y1, zmax + 1.6)

    def shell_sdf(self, S, h):
        """outer surface: the air sdf pushed out by the rind (walls thinner than the floor)"""
        gx, gy, gz = np.gradient(S, h)
        n = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-9
        down = np.clip(-gz / n, 0.0, 1.0)
        t = self.p['wall_t'] + (self.p['floor_t'] - self.p['wall_t']) * down
        return S - t * np.clip(n, 0.7, 2.0)


# ---------------------------------------------------------------------------------------------------------------------
# summary / plan view (plain Python, for quick looks without Blender)

def plan_summary(cv, step=0.25):
    lo, hi = cv.bounds()
    xs = np.arange(lo[0], hi[0], step)
    ys = np.arange(lo[1], hi[1], step)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    c = cv.ctx(X, Y)
    ff = cv.floor_flat(X, Y, c)
    F = cv.floor(X, Y, c, ff)
    H = cv.headroom(X, Y, c, ff)
    return dict(xs=xs, ys=ys, W2=c['W2'], F=F, H=H, C=ff + H, lo=lo, hi=hi)
