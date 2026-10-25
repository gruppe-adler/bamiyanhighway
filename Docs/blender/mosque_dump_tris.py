"""Run in Blender after mosque_rebuild.py: dumps dome + wall triangles (uv + world pos) for mosque_mask_ribs.py. OUT dir = scratch dir."""
import bpy, bmesh, numpy as np, math
from mathutils import Vector
OUT = r"C:\Users\nomisum\AppData\Local\Temp\claude\c--Users-nomisum-Documents-my-games-ArmaReforgerWorkbench-addons-Shashpul\12e399ca-c852-4ce1-a42f-43a252cb2278\scratchpad"
o = bpy.data.objects['Mosque_LOD0']; bm = bmesh.new(); bm.from_mesh(o.data); bm.normal_update(); uv = bm.loops.layers.uv.active
dome, wall = [], []
for f in bm.faces:
    ls = f.loops; c = f.calc_center_median()
    for i in range(1, len(ls) - 1):
        t = (ls[0], ls[i], ls[i + 1])
        row = [*(x for l in t for x in (l[uv].uv.x, l[uv].uv.y)), *(x for l in t for x in l.vert.co)]
        if min(l.vert.co.z for l in ls) >= 8.40 and f.normal.dot(c - Vector((0, 0, 8.4))) > 0: dome.append(row)
        if 0.9 <= c.z <= 8.45 and abs(f.normal.z) <= 0.5 and f.normal.dot(Vector((c.x, c.y, 0))) > 0 and math.hypot(c.x, c.y) >= 4.9: wall.append(row)
np.save(OUT + r"\dome_tris.npy", np.array(dome, np.float32)); np.save(OUT + r"\wall_tris.npy", np.array(wall, np.float32))
print('dumped', len(dome), len(wall))
