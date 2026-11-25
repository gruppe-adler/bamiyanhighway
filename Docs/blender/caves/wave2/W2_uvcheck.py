import bpy, sys, json
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
fbx, out = argv[0], argv[1]
RES = int(argv[2]) if len(argv) > 2 else 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
report = {'objects': []}
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    me = ob.data
    me.calc_loop_triangles()
    info = {'name': ob.name, 'verts': len(me.vertices), 'tris': len(me.loop_triangles),
            'uv_layers': [l.name for l in me.uv_layers],
            'materials': [m.name if m else None for m in me.materials],
            'matrix_identity': ob.matrix_world == ob.matrix_world.Identity(4)}
    mat_idx = np.array([t.material_index for t in me.loop_triangles])
    info['mat_index_counts'] = {int(k): int(v) for k, v in zip(*np.unique(mat_idx, return_counts=True))}
    tris = me.loop_triangles
    n = len(tris)
    loops = np.array([t.loops for t in tris])            # n x 3
    for li, layer in enumerate(me.uv_layers):
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        a = uv[loops[:, 0]]; b = uv[loops[:, 1]]; c = uv[loops[:, 2]]
        area2 = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
        u = {}
        u['nan'] = int(np.isnan(uv).any(axis=1).sum())
        mn = uv.min(axis=0); mx = uv.max(axis=0)
        u['range'] = [float(mn[0]), float(mn[1]), float(mx[0]), float(mx[1])]
        outside = ((uv < -0.0001) | (uv > 1.0001)).any(axis=1)
        u['loops_outside_0_1'] = int(outside.sum())
        tri_out = outside[loops].any(axis=1)
        u['tris_outside_0_1'] = int(tri_out.sum())
        tiny = np.abs(area2) < 1e-10
        u['tris_zero_uv_area'] = int(tiny.sum())
        pos = area2 > 0; neg = area2 < 0
        u['tris_uv_winding_pos'] = int(pos.sum()); u['tris_uv_winding_neg'] = int(neg.sum())
        # 3D area of those triangles (to see whether zero-UV ones are visible)
        # raster overlap: texel centres inside a triangle
        cnt = np.zeros((RES, RES), dtype=np.uint16)
        first = np.full((RES, RES), -1, dtype=np.int32)
        over_tri = set()
        px = uv * RES
        for ti in range(n):
            if tiny[ti]:
                continue
            p0 = px[loops[ti, 0]]; p1 = px[loops[ti, 1]]; p2 = px[loops[ti, 2]]
            x0 = int(max(0, np.floor(min(p0[0], p1[0], p2[0])))); x1 = int(min(RES - 1, np.ceil(max(p0[0], p1[0], p2[0]))))
            y0 = int(max(0, np.floor(min(p0[1], p1[1], p2[1])))); y1 = int(min(RES - 1, np.ceil(max(p0[1], p1[1], p2[1]))))
            if x1 < x0 or y1 < y0:
                continue
            xs = np.arange(x0, x1 + 1) + 0.5; ys = np.arange(y0, y1 + 1) + 0.5
            X, Y = np.meshgrid(xs, ys)
            d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((p1[1] - p2[1]) * (X - p2[0]) + (p2[0] - p1[0]) * (Y - p2[1])) / d
            l2 = ((p2[1] - p0[1]) * (X - p2[0]) + (p0[0] - p2[0]) * (Y - p2[1])) / d
            l3 = 1 - l1 - l2
            inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            if not inside.any():
                continue
            iy, ix = np.nonzero(inside)
            gy = iy + y0; gx = ix + x0
            prev = first[gy, gx]
            clash = prev >= 0
            if clash.any():
                over_tri.add(ti)
                for q in np.unique(prev[clash]):
                    over_tri.add(int(q))
            cnt[gy, gx] += 1
            first[gy, gx] = np.where(prev < 0, ti, prev)
        u['texels_covered'] = int((cnt > 0).sum())
        u['texels_overlapping'] = int((cnt > 1).sum())
        u['coverage_percent'] = round(100.0 * float((cnt > 0).sum()) / (RES * RES), 2)
        u['tris_in_overlap'] = len(over_tri)
        # 3D positions of overlapping triangles (cluster summary)
        pts = []
        for ti in list(over_tri)[:4000]:
            t = tris[ti]
            c = sum((me.vertices[v].co for v in t.vertices), Vector()) / 3
            pts.append((round(c.x, 1), round(c.y, 1), round(c.z, 1)))
        u['overlap_tri_samples'] = pts[:40]
        if pts:
            arr = np.array(pts)
            u['overlap_bbox_min'] = arr.min(axis=0).tolist(); u['overlap_bbox_max'] = arr.max(axis=0).tolist()
        # per material
        u['overlap_by_material'] = {}
        for ti in over_tri:
            m = int(mat_idx[ti]); u['overlap_by_material'][m] = u['overlap_by_material'].get(m, 0) + 1
        # tris not covered at all at their own centroid texel (unbaked)
        info['uv_%d_%s' % (li, layer.name)] = u
    report['objects'].append(info)
    print('UVCHECK', ob.name, json.dumps({k: v for k, v in info.items() if k.startswith('uv_')}, indent=1)[:3000])
json.dump(report, open(out, 'w'), indent=1)
print('UVCHECK DONE')
