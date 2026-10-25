"""Paint the 8 dome ribs into the R (BandPaint layer) channel of Mosque_01_MASK.tif.
Input: dome_tris.npy dumped from Blender (rows: u0 v0 u1 v1 u2 v2 x0 y0 z0 x1 y1 z1 x2 y2 z2). usage: python mosque_mask_ribs.py ribs dome_tris.npy | python mosque_mask_ribs.py walls wall_tris.npy dome_tris.npy"""
import sys, numpy as np
from PIL import Image
MASK = "Prefabs/Structures/Mosque_01/Mosque_01_MASK.tif"
HALF_DEG, SOFT_DEG, PHASE, N = 3.0, 0.6, 90.0, 8
MODE = sys.argv[1]
BODY_STRIPES = [(3.45, 3.90)]                       # extra brown stripes on the octagon walls (photo: striped plaster)
DRUM_STRIPES = []   # drum stripes disabled: new drum faces borrow UVs from dome islands and polluted them
img = np.array(Image.open(MASK)); R = img[..., 0].astype(np.float32); S = img.shape[0]
from PIL import ImageDraw
excl = None
if MODE == 'walls':   # never touch texels that belong to dome islands (some drum/wall UVs overlap them after the UV projection)
    ex = Image.new('L', (S, S), 0); dr = ImageDraw.Draw(ex)
    for r in np.load(sys.argv[3]): dr.polygon([(r[0] * S, r[1] * S), (r[2] * S, r[3] * S), (r[4] * S, r[5] * S)], fill=255)
    excl = np.array(ex) > 0
for row in np.load(sys.argv[2]):
    uv = row[:6].reshape(3, 2) * S; P = row[6:].reshape(3, 3)
    x0, x1 = int(np.floor(uv[:, 0].min())), int(np.ceil(uv[:, 0].max())); y0, y1 = int(np.floor(uv[:, 1].min())), int(np.ceil(uv[:, 1].max()))
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    a, b, c = uv; d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-9: continue
    w0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
    w1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
    w2 = 1 - w0 - w1; m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
    if not m.any(): continue
    X = w0 * P[0, 0] + w1 * P[1, 0] + w2 * P[2, 0]; Y = w0 * P[0, 1] + w1 * P[1, 1] + w2 * P[2, 1]
    rad = np.hypot(X, Y); ang = np.degrees(np.arctan2(Y, X))
    if MODE == 'ribs':
        off = np.abs(((ang - PHASE + 180.0 / N) % (360.0 / N)) - 180.0 / N)        # distance to nearest rib axis
        val = np.clip((HALF_DEG + SOFT_DEG - off) / (2 * SOFT_DEG), 0, 1) * (rad > 1.0) * 255
    else:
        Z = w0 * P[0, 2] + w1 * P[1, 2] + w2 * P[2, 2]; val = np.zeros_like(Z)
        for lo, hi in (DRUM_STRIPES if rad.mean() < 7.0 else BODY_STRIPES):
            val = np.maximum(val, np.clip(np.minimum(Z - lo, hi - Z) / 0.03, 0, 1) * 255)
    ys, xs = np.nonzero(m)
    yy, xx = ys + y0, xs + x0; ok = (yy >= 0) & (yy < S) & (xx >= 0) & (xx < S)
    if excl is not None: ok &= ~excl[np.clip(yy, 0, S - 1), np.clip(xx, 0, S - 1)]
    if MODE == 'ribs' and P[:, 2].min() > 9.2:      # upper dome: overwrite (removes stray old paint), base ring keeps its band
        R[yy[ok], xx[ok]] = val[ys[ok], xs[ok]]
    else:
        R[yy[ok], xx[ok]] = np.maximum(R[yy[ok], xx[ok]], val[ys[ok], xs[ok]])
img[..., 0] = R.astype(np.uint8); Image.fromarray(img).save(MASK)
print("saved", MASK, "R>0:", int((img[..., 0] > 0).sum()))
