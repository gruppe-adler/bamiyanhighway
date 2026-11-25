"""plain-Python sanity test of the shapes: headroom along every route straight from the sdf (no Blender). python -I W2_quicktest.py [keys]"""
import sys, time
sys.path.insert(0, '.')
import numpy as np
import W2_assets as A, W2_engine as E
keys = sys.argv[1:] or ['squeezep']
if keys == ['all']:
    A.build('crack')
    keys = list(A.ASSETS)
for k in keys:
    t = time.time()
    cv, prm = A.build(k)
    lo, hi = cv.bounds()
    print('==', k, cv.name, 'bounds', tuple(round(float(v), 1) for v in lo), tuple(round(float(v), 1) for v in hi))
    for rn, r in cv.routes.items():
        pts = np.array(r['pts'])
        # densify
        out = []
        for i in range(len(pts) - 1):
            n = max(1, int(np.hypot(*(pts[i + 1] - pts[i])) / 0.25))
            for q in range(n):
                out.append(pts[i] + (pts[i + 1] - pts[i]) * q / n)
        out.append(pts[-1])
        out = np.array(out)
        zs = np.arange(lo[2], hi[2], 0.02)
        hs = []
        for (x, y) in out:
            s = cv.sdf(np.full_like(zs, x), np.full_like(zs, y), zs)
            fl = float(cv.floor2d(np.array([x]), np.array([y]))[0]) + 0.15
            k0 = int(np.argmin(np.abs(zs - fl)))
            if s[k0] >= 0:
                hs.append(0.0)
                continue
            a = k0
            while a > 0 and s[a - 1] < 0: a -= 1
            b = k0
            while b < len(zs) - 1 and s[b + 1] < 0: b += 1
            hs.append(zs[b] - zs[a])
        hs = np.array(hs)
        print('  route %s mode %s: min headroom on the centre line %.2f (req %.2f), length %.1f, W2 min %.2f' % (rn, r['mode'], hs.min(), {'W': 2.0, 'C': 1.6, 'P': 0.92}[r['mode']], len(out) * 0.25, cv.W2(out[:, 0], out[:, 1]).min()))
    print('  %.1f s' % (time.time() - t))
