"""Destructible window parts, modelled on the vanilla church window (Win_ChurchSmall_E_A_*: frame xob + glass prefab with SCR_DestructionMultiPhaseComponent + '_dst' shard model).
Per window kind (Body 1.24x2.09 m, Drum 0.75x1.12 m) exports into Prefabs/Structures/Mosque_01/Windows/:
  Win_Mosque_<K>.fbx            frame mesh (+ UTM collider)
  Glass_Mosque_<K>.fbx          intact glass (+ UTM collider)
  Glass_Mosque_<K>_dst.fbx      shattered glass: jagged shards, some missing, slightly sagging
Run in Blender on mosque_v4_baked.blend (uses the Pane_Body_2_1 / Pane_Drum_0 meshes)."""
import bpy, bmesh, math, os, random
from mathutils import Vector

OUT = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Prefabs\Structures\Mosque_01\Windows"
os.makedirs(OUT, exist_ok=True)
KINDS = {'Body': 'Pane_Body_2_1', 'Drum': 'Pane_Drum_0'}


def sub_mesh(src_me, mat_index, name):
    bm = bmesh.new(); bm.from_mesh(src_me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mat_index], context='FACES')
    for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
    uv = bm.loops.layers.uv.verify()
    xs = [v.co.x for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    w = max(xs) - min(xs); h = max(zs) - min(zs)
    for f in bm.faces:
        for l in f.loops: l[uv].uv = ((l.vert.co.x - min(xs)) / w, (l.vert.co.z - min(zs)) / h)       # planar UV (the panes had none -> Workbench warning)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in src_me.materials: me.materials.append(m)
    # drop the unused slot so the FBX only lists the used material
    return me


def outline(me):
    """arch outline (x,z) of the glass: the front face has the most vertices"""
    bm = bmesh.new(); bm.from_mesh(me)
    f = max(bm.faces, key=lambda f: len(f.verts) if f.normal.y < 0 else 0)
    pts = [(v.co.x, v.co.z) for v in f.verts]; bm.free(); return pts


def clip(poly, a, b, c):
    """keep the half plane a*x+b*z <= c (Sutherland-Hodgman)"""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0: out.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            t = fp / (fp - fq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def shards(poly, seed, n=14, keep=0.62):
    rnd = random.Random(seed)
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    # impact point near the middle: seeds denser there (looks like a bullet hole / crack star)
    cx, cz = rnd.uniform(-0.1, 0.1) * (max(xs) - min(xs)), (min(zs) + max(zs)) / 2 + rnd.uniform(-0.1, 0.1)
    seeds = [(cx, cz)] + [(cx + rnd.gauss(0, 0.28 * (max(xs) - min(xs))), cz + rnd.gauss(0, 0.28 * (max(zs) - min(zs)))) for _ in range(n - 1)]
    cells = []
    for i, s in enumerate(seeds):
        cell = list(poly)
        for j, t in enumerate(seeds):
            if i == j: continue
            a, b = t[0] - s[0], t[1] - s[1]; c = (t[0] ** 2 + t[1] ** 2 - s[0] ** 2 - s[1] ** 2) / 2
            cell = clip(cell, a, b, c)
            if len(cell) < 3: break
        if len(cell) >= 3: cells.append(cell)
    rnd.shuffle(cells)
    return cells[: max(4, int(len(cells) * keep))]


def dst_mesh(poly, name, seed, src_mats):
    bm = bmesh.new(); uv = bm.loops.layers.uv.verify(); rnd = random.Random(seed)
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]; w = max(xs) - min(xs); h = max(zs) - min(zs)
    for cell in shards(poly, seed):
        cxm = sum(p[0] for p in cell) / len(cell); czm = sum(p[1] for p in cell) / len(cell)
        sag = max(0.0, (max(zs) - czm) / h) * rnd.uniform(0.0, 0.02)           # upper shards hang a bit lower
        tilt = rnd.uniform(-0.015, 0.015)
        pts = []
        for (x, z) in cell:                                                      # shrink 4 % -> crack gaps
            x2 = cxm + (x - cxm) * 0.96; z2 = czm + (z - czm) * 0.96
            pts.append((x2, z2))
        for y in (-0.004, 0.004):
            pass
        front = [bm.verts.new((x, -0.004 + tilt * (z - czm), z - sag)) for x, z in pts]
        back = [bm.verts.new((x, 0.004 + tilt * (z - czm), z - sag)) for x, z in pts]
        try:
            ff = bm.faces.new(front); fb = bm.faces.new(back[::-1])
            for i in range(len(pts)): bm.faces.new((front[i], front[(i + 1) % len(pts)], back[(i + 1) % len(pts)], back[i]))
        except ValueError: pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        for l in f.loops: l[uv].uv = ((l.vert.co.x - min(xs)) / w, (l.vert.co.z - min(zs)) / h)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(src_mats[0]); return me


def export(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH'}, use_mesh_modifiers=True, mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False)


mats = {}
for kind, pane in KINDS.items():
    src = bpy.data.objects[pane].data
    gm = {m.name: m for m in src.materials}
    glass_mat = gm['Glas']; frame_mat = gm['Rahmen_weiss']
    old = (glass_mat.name, frame_mat.name); glass_mat.name = 'Mosque_01_Glass'; frame_mat.name = 'Mosque_01_PaneFrame'
    try:
        parts = {
            f'Win_Mosque_{kind}': sub_mesh(src, 1, f'Win_Mosque_{kind}'),
            f'Glass_Mosque_{kind}': sub_mesh(src, 0, f'Glass_Mosque_{kind}'),
            f'Glass_Mosque_{kind}_dst': dst_mesh(outline(sub_mesh(src, 0, 'tmp')), f'Glass_Mosque_{kind}_dst', 17 if kind == 'Body' else 29, [glass_mat]),
        }
        for base, me in parts.items():
            lod = bpy.data.objects.new(base + '_LOD0', me); col = bpy.data.objects.new('UTM_' + base, me.copy())
            for o in (lod, col): bpy.context.collection.objects.link(o)
            export([lod, col], os.path.join(OUT, base + '.fbx'))
            for o in (lod, col): bpy.data.objects.remove(o)
            print('exported', base, len(me.polygons), 'tris')
    finally:
        glass_mat.name, frame_mat.name = old
