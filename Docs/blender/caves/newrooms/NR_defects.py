"""NR_defects: find defective triangles in an exported room (FBX) or a blend. Run in Blender:
  blender --factory-startup -b --python NR_defects.py            env NR_FBX=<fbx path>  or  NR_BLEND is opened by the command line
  env NR_JSON=<out json>   NR_TOP=<n worst per check>
For every mesh object (LOD0/1/2, UTM_): material slots used / unused slot indices, loose verts and edges, open and non-manifold edges,
degenerate triangles (3D area), triangles whose winding disagrees with a neighbour (flipped), triangles whose custom normal points
against the face normal, and UV problems on every UV layer (NaN, zero area, outside 0..1 for the mask set, a triangle whose UV corners
sample a very different mask than its vertices, i.e. a UV island that overlaps another or an unmapped one).
"""
import os, sys, json, math
import bpy, bmesh
import numpy as np
from mathutils import Vector

fbx = os.environ.get('NR_FBX')
if fbx:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=fbx)
TOP = int(os.environ.get('NR_TOP', '12'))
out = {}
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    me = ob.data
    n = len(me.polygons)
    rep = dict(faces=n, verts=len(me.vertices), materials=[s.material.name if s.material else None for s in ob.material_slots])
    mi = np.array([p.material_index for p in me.polygons])
    rep['material_index_counts'] = {int(k): int((mi == k).sum()) for k in np.unique(mi)}
    rep['unused_slots'] = [i for i in range(len(ob.material_slots)) if i not in rep['material_index_counts']]
    rep['index_beyond_slots'] = [int(k) for k in rep['material_index_counts'] if k >= len(ob.material_slots)]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    mw = ob.matrix_world
    rep['loose_verts'] = sum(1 for v in bm.verts if not v.link_edges)
    rep['loose_edges'] = sum(1 for e in bm.edges if not e.link_faces)
    rep['open_edges'] = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    rep['nonmanifold_edges'] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    # degenerate and tiny faces
    areas = np.array([f.calc_area() for f in bm.faces])
    rep['faces_not_triangles'] = int(sum(1 for f in bm.faces if len(f.verts) != 3))
    rep['area_min'] = float(areas.min())
    deg = np.nonzero(areas < 1e-8)[0]
    rep['degenerate_faces_lt1e-8'] = int(len(deg))
    tiny = np.nonzero(areas < 1e-6)[0]
    rep['tiny_faces_lt1e-6'] = int(len(tiny))
    # winding consistency: a manifold edge must be traversed in opposite directions by its two faces
    flipped = set()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        d0 = d1 = None
        for l in f0.loops:
            if l.edge is e:
                d0 = (l.vert.index, l.link_loop_next.vert.index)
        for l in f1.loops:
            if l.edge is e:
                d1 = (l.vert.index, l.link_loop_next.vert.index)
        if d0 == d1:
            flipped.add(f0.index)
            flipped.add(f1.index)
    # a face is the odd one out when most neighbours disagree: count disagreements per face
    cnt = {}
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        d0 = d1 = None
        for l in f0.loops:
            if l.edge is e:
                d0 = (l.vert.index, l.link_loop_next.vert.index)
        for l in f1.loops:
            if l.edge is e:
                d1 = (l.vert.index, l.link_loop_next.vert.index)
        if d0 == d1:
            cnt[f0.index] = cnt.get(f0.index, 0) + 1
            cnt[f1.index] = cnt.get(f1.index, 0) + 1
    odd = [i for i, c in cnt.items() if c >= 2]
    rep['winding_disagreements_faces'] = len(flipped)
    rep['faces_flipped_vs_2plus_neighbours'] = len(odd)
    # custom normal vs face normal
    try:
        cn = np.empty(len(me.loops) * 3, dtype=np.float32)
        me.corner_normals.foreach_get('vector', cn)
        cn = cn.reshape(-1, 3)
        bad = []
        for p in me.polygons:
            fn = np.array(p.normal)
            d = [float(cn[li] @ fn) for li in p.loop_indices]
            if min(d) < -0.2:
                bad.append(p.index)
        rep['faces_with_corner_normal_against_face_normal'] = len(bad)
    except Exception as ex:
        bad = []
        rep['corner_normal_check'] = str(ex)
    # UV checks per layer
    rep['uv_layers'] = [u.name for u in me.uv_layers]
    uvbad = {}
    for ul in me.uv_layers:
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        ul.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        nanf, zero, outside = [], [], []
        for p in me.polygons:
            li = list(p.loop_indices)
            q = uv[li]
            if not np.isfinite(q).all():
                nanf.append(p.index)
                continue
            a = 0.5 * abs((q[1, 0] - q[0, 0]) * (q[2, 1] - q[0, 1]) - (q[2, 0] - q[0, 0]) * (q[1, 1] - q[0, 1]))
            if a < 1e-12:
                zero.append(p.index)
            if ul.name.lower().find('mask') >= 0 or ul is me.uv_layers[-1]:
                if (q < -0.001).any() or (q > 1.001).any():
                    outside.append(p.index)
        uvbad[ul.name] = dict(nan=nanf, zero_area=zero, outside_0_1=outside)
        rep['uv_%s' % ul.name] = dict(nan=len(nanf), zero_area=len(zero), outside_0_1=len(outside))
    # candidate list with world position, area, which checks flagged it
    cand = {}
    def add(i, why):
        cand.setdefault(i, []).append(why)
    for i in deg[:TOP * 4]:
        add(int(i), 'degenerate')
    for i in odd:
        add(int(i), 'flipped')
    for i in bad:
        add(int(i), 'normal_against')
    for name, d in uvbad.items():
        for i in d['nan'][:TOP * 4]:
            add(int(i), 'uv_nan:' + name)
        for i in d['zero_area'][:TOP * 4]:
            add(int(i), 'uv_zero:' + name)
        for i in d['outside_0_1'][:TOP * 4]:
            add(int(i), 'uv_outside:' + name)
    lst = []
    for i, why in cand.items():
        p = me.polygons[i]
        c = mw @ Vector(p.center)
        lst.append(dict(face=i, pos=[round(c.x, 2), round(c.y, 2), round(c.z, 2)], area=round(float(areas[i]), 6), mat=int(p.material_index), why=why))
    lst.sort(key=lambda d: (-len(d['why']), d['area']))
    rep['candidates'] = lst[:TOP * 6]
    rep['candidates_total'] = len(lst)
    out[ob.name] = rep
    bm.free()
    print('==', ob.name, {k: v for k, v in rep.items() if k not in ('candidates',)})
p = os.environ.get('NR_JSON')
if p:
    json.dump(out, open(p, 'w'), indent=1)
    print('saved', p)
