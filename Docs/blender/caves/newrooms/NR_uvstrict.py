"""NR_uvstrict: UV2 overlap with STRICT interior tests (a texel centre exactly on a shared edge is not an overlap), per LOD, several resolutions.
  blender --factory-startup -b --python NR_uvstrict.py -- <fbx> <out.json> [res res ...]"""
import bpy, sys, json, math
import numpy as np
argv = sys.argv[sys.argv.index('--') + 1:]
fbx, out = argv[0], argv[1]
RESS = [int(a) for a in argv[2:]] or [1024, 4096]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)


def overlap(P, res):
    first = np.full((res, res), -1, dtype=np.int32)
    over = np.zeros((res, res), dtype=np.uint8)
    bad = set()
    for tt in range(len(P)):
        a, b, c = P[tt]
        x0, x1 = int(math.floor(min(a[0], b[0], c[0]))), int(math.ceil(max(a[0], b[0], c[0])))
        y0, y1 = int(math.floor(min(a[1], b[1], c[1]))), int(math.ceil(max(a[1], b[1], c[1])))
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
        if x1 < x0 or y1 < y0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5, indexing='ij')
        w0 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        w1 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        w2 = 1.0 - w0 - w1
        inside = (w0 > 1e-6) & (w1 > 1e-6) & (w2 > 1e-6)
        if not inside.any():
            continue
        ii, jj = np.nonzero(inside)
        gx, gy = ii + x0, jj + y0
        prev = first[gx, gy]
        hit = prev >= 0
        if hit.any():
            over[gx[hit], gy[hit]] += 1
            bad.add(tt)
            bad.update(int(p) for p in np.unique(prev[hit]))
        first[gx[~hit], gy[~hit]] = tt
    return int((over > 0).sum()), bad


res_all = {}
for ob in bpy.data.objects:
    if ob.type != 'MESH' or ob.name.startswith('UTM'):
        continue
    me = ob.data
    me.calc_loop_triangles()
    loops = np.array([t.loops for t in me.loop_triangles])
    lay = me.uv_layers[1] if len(me.uv_layers) > 1 else me.uv_layers[0]
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    lay.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2).astype(np.float64)
    tri = uv[loops]
    sa = 0.5 * ((tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1]) - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    r = dict(layer=lay.name, tris=len(tri), zero_area=int((np.abs(sa) < 1e-10).sum()), negative=int((sa < -1e-10).sum()), outside_0_1=int((((tri < -1e-4) | (tri > 1 + 1e-4)).any(axis=(1, 2))).sum()))
    for res in RESS:
        n, bad = overlap(tri * res, res)
        r['overlap_texels_%d' % res] = n
        r['overlap_tris_%d' % res] = len(bad)
    res_all[ob.name] = r
    print('UVSTRICT', ob.name, r)
json.dump(res_all, open(out, 'w'), indent=1)
