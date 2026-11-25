"""W2_shapeplan: a plan-view PNG of a shape's design (footprint, headroom class, floor height, openings, routes), plain Python, no Blender.
  python -I W2_shapeplan.py <key> [<key> ...] | all        writes <outdir>/W2_plan_<key>.png   (outdir: env W2_PLAN_OUT or ./_scratch)
Colours: grey = rock, green headroom >= 2.0, yellow 1.6-2.0, orange 0.92-1.6, red 0.35-0.92; brightness follows the floor height; white dots = openings, cyan = routes.
"""
import sys, os, zlib, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import W2_assets as A

OUT = os.environ.get('W2_PLAN_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '_scratch'))


def png(path, arr):
    h, w = arr.shape[:2]
    raw = b''.join(b'\x00' + arr[i].tobytes() for i in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def plan(key, step=0.1):
    cv, prm = A.build(key)
    lo, hi = cv.bounds()
    xs = np.arange(lo[0], hi[0], step)
    ys = np.arange(lo[1], hi[1], step)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    c = cv.ctx(X, Y)
    ff = cv.floor_flat(X, Y, c)
    F = cv.floor(X, Y, c, ff)
    Hh = cv.headroom(X, Y, c, ff)
    inside = c['W2'] > 0.0
    for (x0, ya, yb, z0, sl) in cv.dug:
        dd = cv.dug_sd(X, Y, np.full_like(X, z0 + 1.0))
        inside |= dd < 0
        Hh = np.where(dd < 0, 2.1, Hh)
    img = np.zeros(X.shape + (3,), dtype=np.float32)
    img[:] = (0.12, 0.12, 0.12)
    base = np.array([(0.2, 0.75, 0.3) if h >= 2.0 else (0.9, 0.85, 0.2) if h >= 1.6 else (0.95, 0.5, 0.15) if h >= 0.92 else (0.85, 0.15, 0.15) for h in Hh.ravel()]).reshape(X.shape + (3,))
    zmin, zmax = float(F[inside].min()), float(F[inside].max())
    shade = 0.55 + 0.45 * (F - zmin) / max(zmax - zmin, 0.5)
    img = np.where(inside[..., None], base * shade[..., None], img)
    for op in cv.openings:
        i = int((op['xy'][0] - lo[0]) / step)
        j = int((op['xy'][1] - lo[1]) / step)
        img[max(i - 4, 0):i + 5, max(j - 4, 0):j + 5] = (1, 1, 1)
    for rn, r in cv.routes.items():
        for (x, y) in r['pts']:
            i = int((x - lo[0]) / step)
            j = int((y - lo[1]) / step)
            img[max(i - 1, 0):i + 2, max(j - 1, 0):j + 2] = (0.1, 0.9, 0.95)
    im = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    im = np.transpose(im, (1, 0, 2))[::-1]
    sc = max(1, 700 // max(im.shape[:2]))
    im = np.repeat(np.repeat(im, sc, axis=0), sc, axis=1)
    os.makedirs(OUT, exist_ok=True)
    png(os.path.join(OUT, 'W2_plan_%s.png' % key), im)
    print(key, 'floor %.2f..%.2f' % (zmin, zmax), im.shape)


if __name__ == '__main__':
    keys = sys.argv[1:]
    if keys == ['all']:
        A.build('crack')
        keys = list(A.ASSETS)
    for k in keys:
        plan(k)
