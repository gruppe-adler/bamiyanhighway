import bpy, sys, json
import numpy as np
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
fbx, out = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
res = {}
for ob in bpy.data.objects:
    if ob.type != 'MESH' or not ob.name.endswith('LOD0') or ob.name.startswith('UTM'):
        continue
    me = ob.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    n = len(tris)
    loops = np.array([t.loops for t in tris])
    layer = me.uv_layers['UVMask']
    uv = np.empty(len(me.loops) * 2, dtype=np.float32); layer.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    a = uv[loops[:, 0]]; b = uv[loops[:, 1]]; c = uv[loops[:, 2]]
    area2 = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    co = np.empty(len(me.vertices) * 3, dtype=np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    vi = np.array([t.vertices for t in tris])
    p0 = co[vi[:, 0]]; p1 = co[vi[:, 1]]; p2 = co[vi[:, 2]]
    area3 = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    cen = (p0 + p1 + p2) / 3
    mat = np.array([t.material_index for t in tris])
    zero = np.abs(area2) < 1e-10
    # also "tiny" UV area relative to 3D area (texel density collapse)
    dens = np.abs(area2) / np.maximum(area3, 1e-9)
    res['tris'] = n
    res['zero_uv'] = int(zero.sum())
    zr = {}
    zr['area3_percentiles'] = [float(x) for x in np.percentile(area3[zero], [0, 25, 50, 75, 95, 100])] if zero.any() else []
    zr['visible_gt_0.01m2'] = int((area3[zero] > 0.01).sum())
    zr['visible_gt_0.05m2'] = int((area3[zero] > 0.05).sum())
    zr['by_material'] = {int(k): int(v) for k, v in zip(*np.unique(mat[zero], return_counts=True))}
    # are all three UV points identical (a point) or collinear (a line)?
    same = (np.abs(a - b).max(axis=1) < 1e-9) & (np.abs(a - c).max(axis=1) < 1e-9)
    zr['uv_all_three_identical'] = int((same & zero).sum())
    zr['uv_collinear_not_identical'] = int((zero & ~same).sum())
    # clusters of 3 m cells
    cell = np.floor(cen[zero] / 3.0).astype(int)
    keys, counts = np.unique(cell, axis=0, return_counts=True)
    order = np.argsort(-counts)[:15]
    zr['top_clusters_cell3m'] = [{'cell_center': (keys[i] * 3.0 + 1.5).tolist(), 'count': int(counts[i])} for i in order]
    # low UV density but non-zero: texel stretching
    nz = ~zero
    texel = np.sqrt(np.abs(area2[nz]) / np.maximum(area3[nz], 1e-9))   # uv units per metre
    zr['uv_per_metre_percentiles_nonzero'] = [float(x) for x in np.percentile(texel, [1, 5, 50, 95])]
    zr['very_stretched_lt_5pct_of_median'] = int((texel < 0.05 * np.median(texel)).sum())
    res['zero'] = zr
    res['name'] = ob.name
    # sample positions of visible zero tris
    vis = np.nonzero(zero & (area3 > 0.01))[0][:30]
    res['visible_samples'] = [[round(float(x), 2) for x in cen[i]] + [round(float(area3[i]), 3), int(mat[i])] for i in vis]
json.dump(res, open(out, 'w'), indent=1)
print('UVZERO DONE')
