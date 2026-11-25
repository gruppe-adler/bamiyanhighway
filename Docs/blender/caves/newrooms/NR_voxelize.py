"""NR_voxelize: run in Blender on a built room (blend with UTM_<name>, the collider = the cavity's inner skin).
Casts a vertical ray per grid column and stores the air intervals of every column (floor z, floor normal z, roof z) in an npz
for NR_check.py (plain Python + scipy).  Env: NR_BLEND (blend path), NR_NPZ (output), NR_STEP (m, default 0.2),
NR_OBJ ('UTM_' or LOD0 object name prefix: default the collider).
   blender --factory-startup -b <blend> --python NR_voxelize.py
"""
import os, sys, math, time
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

step = float(os.environ.get('NR_STEP', '0.2'))
out = os.environ.get('NR_NPZ', 'nr_vox.npz')
prefix = os.environ.get('NR_OBJ', 'UTM_')
ob = next(o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == 'MESH')
print('voxelizing', ob.name, len(ob.data.polygons), 'faces')
bm = bmesh.new()
bm.from_mesh(ob.data)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
tree = BVHTree.FromBMesh(bm)
xs = [v.co.x for v in bm.verts]
ys = [v.co.y for v in bm.verts]
zs = [v.co.z for v in bm.verts]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
z0, z1 = min(zs), max(zs)
nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
print('bbox', (x0, y0, z0), (x1, y1, z1), 'columns', nx * ny)
rows = []
t0 = time.time()
down = Vector((0, 0, -1))
ztop = z1 + 1.0
for i in range(nx):
    for j in range(ny):
        o = Vector((x0 + i * step, y0 + j * step, ztop))
        hits = []
        for _ in range(40):
            h = tree.ray_cast(o, down)
            if h[0] is None:
                break
            hits.append((h[0].z, h[1].z, h[1].dot(down) > 0))     # z, normal z, back face (the ray comes from the rock: entering air)
            o = h[0] + Vector((0, 0, -0.003))
        # air intervals: from a back-face hit (enter air) down to the next front-face hit (leave air)
        k = 0
        while k < len(hits):
            if hits[k][2]:
                zr = hits[k][0]
                m = k + 1
                while m < len(hits) and hits[m][2]:
                    m += 1                                   # a doubled surface: stay in the air until a front-face hit
                if m < len(hits):
                    rows.append((i, j, hits[m][0], hits[m][1], zr))
                    k = m + 1
                    continue
            k += 1
print('intervals', len(rows), 'in %.1f s' % (time.time() - t0))
arr = np.array(rows, dtype=np.float32)
np.savez_compressed(out, iv=arr, x0=x0, y0=y0, step=step, nx=nx, ny=ny, z0=z0, z1=z1)
print('saved', out)
