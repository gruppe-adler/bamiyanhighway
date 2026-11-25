"""W2_sdfcheck: the route / clearance check of W2_check.py run in plain Python on the shape's own signed distance field (no Blender, no build).
It finds design problems (a route that does not connect, a clearance below the mode's requirement) in seconds, before an asset is built.
  python -I W2_sdfcheck.py <key> [<key> ...]      or  all
The numbers differ a little from the collider measurement (the build adds roughness and decimation): the design needs about 0.1 m of margin.
"""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import W2_assets as A
import W2_helpers as H

HREQ = {'W': 1.5, 'C': 1.6, 'P': 0.92}     # W: 1.65 m at the sides of the 1.2 m wide corridor (the kit's profile is 2.1 m only on its centre line; the centre line is reported separately)
STEPMAX = {'W': 0.35, 'C': 0.30, 'P': 0.25}
SLOPEMAX = {'W': 35.0, 'C': 28.0, 'P': 20.0}
DUG = []
DIRS = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0)]


def columns(cv, step):
    lo, hi = cv.bounds()
    xs = np.arange(lo[0], hi[0], step)
    ys = np.arange(lo[1], hi[1], step)
    dz = 0.05
    zs = np.arange(lo[2], hi[2], dz)
    rows = []
    for i, x in enumerate(xs):
        X = np.full((len(ys), len(zs)), x, dtype=np.float32)
        Y = np.repeat(ys[:, None], len(zs), axis=1).astype(np.float32)
        Z = np.repeat(zs[None, :], len(ys), axis=0).astype(np.float32)
        S = cv.sdf(X, Y, Z)
        air = S < 0
        for j in range(len(ys)):
            a = air[j]
            if not a.any():
                continue
            d = np.diff(np.concatenate([[0], a.astype(np.int8), [0]]))
            st = np.nonzero(d == 1)[0]
            en = np.nonzero(d == -1)[0]
            Sj = S[j]
            for s0, e0 in zip(st, en):
                zf = zs[s0] if s0 == 0 else zs[s0 - 1] + dz * Sj[s0 - 1] / (Sj[s0 - 1] - Sj[s0])         # the sub-cell crossings (no 5 cm stair steps)
                zr = zs[e0 - 1] if e0 >= len(zs) else zs[e0 - 1] + dz * Sj[e0 - 1] / (Sj[e0 - 1] - Sj[e0])
                if zr - zf < 0.3:
                    continue
                rows.append((i, j, zf, 1.0, zr))
    return np.array(rows), (lo[0], lo[1], len(xs), len(ys), lo[2], hi[2])


class Cols:
    def __init__(self, rows, meta, step):
        self.step = step
        self.x0, self.y0, self.nx, self.ny, self.z0, self.z1 = meta
        order = np.lexsort((rows[:, 2], rows[:, 1], rows[:, 0]))
        rows = rows[order]
        self.I = rows[:, 0].astype(np.int64)
        self.J = rows[:, 1].astype(np.int64)
        self.ZF = rows[:, 2]
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


def erode(mask, r_cells):
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
    def __init__(self, C, mode, stub_pts):
        self.C, self.mode, self.only, self.force = C, mode, None, []
        self.slope = C.slopes(max(2, int(round(0.5 / C.step))))
        self.nb = [C.neighbour(di, dj, STEPMAX[mode]) for di, dj in DIRS]
        self.stub = np.zeros(C.n, dtype=bool)
        for (x, y) in stub_pts:
            self.stub |= (np.hypot(C.X - x, C.Y - y) < 4.6)
        for (dx0, dya, dyb, dz0, dsl) in DUG:
            self.stub |= (np.abs(C.X - dx0) < 1.0) & (C.Y >= dya) & (C.Y <= dyb)

    def nodes_ok(self, Hh, rw):
        C = self.C
        ok = (C.HR >= Hh) & (self.slope <= math.tan(math.radians(SLOPEMAX[self.mode])))
        if self.only is not None:
            ok &= self.only
        if rw > 0:
            M = np.zeros((C.nx, C.ny), dtype=bool)
            M[C.I[ok], C.J[ok]] = True
            E = erode(M, rw / C.step)
            ok &= (E[C.I, C.J] | self.stub)
        for k in self.force:
            ok[k] = True                  # the end nodes sit on the void's rim, where the one-sided slope estimate is wrong
        return ok

    def bfs(self, ok, a, b):
        n = self.C.n
        seen = np.zeros(n, dtype=bool)
        if a < 0 or b < 0 or not ok[a]:
            return False
        seen[a] = True
        front = np.array([a], dtype=np.int64)
        while len(front):
            nxt = []
            for nbk in self.nb:
                t = nbk[front]
                t = t[t >= 0]
                t = t[ok[t] & ~seen[t]]
                if len(t):
                    t = np.unique(t)
                    seen[t] = True
                    nxt.append(t)
            front = np.concatenate(nxt) if nxt else np.zeros(0, dtype=np.int64)
            if seen[b]:
                return True
        return bool(seen[b])


def node_at(C, x, y, z, rad=1.0, dz=1.0, need=0.0):
    d = np.hypot(C.X - x, C.Y - y)
    ok = (d < rad) & (np.abs(C.ZF - z) < dz) & (C.HR >= need)
    if not ok.any():
        return -1
    idx = np.nonzero(ok)[0]
    return int(idx[np.argmin(d[idx] + 0.3 * np.abs(C.ZF[idx] - z))])


def run(key, step=0.12):
    global DUG
    cv, prm = A.build(key)
    DUG = cv.dug
    t = time.time()
    rows, meta = columns(cv, step)
    C = Cols(rows, meta, step)
    ops = cv.openings
    print('== %s: %d air intervals (%.0f s)' % (cv.name, C.n, time.time() - t))
    allpass = True
    for rname, r in cv.routes.items():
        mode = r['mode']
        i, j = r['sock']
        Aop, Bop = ops[i], ops[j]
        W = Walker(C, mode, [o['xy'] for o in ops])
        if r.get('only') is not None:
            W.only = np.array([bool(r['only'](x, y)) for x, y in zip(C.X, C.Y)])
        a = node_at(C, Aop['xy'][0], Aop['xy'][1], Aop['dz'], 1.2, 0.9, 1.9)
        if r.get('to'):
            tx, ty = r['to']
            b = node_at(C, tx, ty, float(cv.floor2d(np.array([tx]), np.array([ty]))[0]), 1.0, 0.6, 0.0)
        else:
            b = node_at(C, Bop['xy'][0], Bop['xy'][1], Bop['dz'], 1.2, 0.9, 1.9)
        need = HREQ[mode]
        W.force = [k for k in (a, b) if k >= 0]
        lo_h, hi_h = 0.3, 3.2
        for _ in range(10):
            mid = 0.5 * (lo_h + hi_h)
            if W.bfs(W.nodes_ok(mid, r['w'] / 2), a, b):
                lo_h = mid
            else:
                hi_h = mid
        lo_w, hi_w = 0.0, 4.0
        for _ in range(8):
            mid = 0.5 * (lo_w + hi_w)
            if W.bfs(W.nodes_ok(need, mid / 2), a, b):
                lo_w = mid
            else:
                hi_w = mid
        ok = a >= 0 and b >= 0 and lo_h >= need + 0.05
        allpass &= ok
        print('  route %-14s %s: start %s end %s clear height %.2f (need %.2f), width %.2f (need %.1f) %s' % (rname, mode, a, b, lo_h, need, lo_w, r['w'], 'ok' if ok else '<<<<< PROBLEM'))
    return allpass


if __name__ == '__main__':
    keys = sys.argv[1:]
    if keys == ['all']:
        A.build('crack')
        keys = list(A.ASSETS)
    for k in keys:
        run(k)
