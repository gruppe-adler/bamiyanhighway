"""Export mosque + panes to the addon (run in Blender after mosque_rebuild.py; works on the open scene, does not save it).
Conventions copied from the existing Mosque_01.fbx: objects Mosque_01_LOD0..3 + UTM_Mosque_01 (collider), materials Mosque_01_<Name>,
white 'Col' colour layer, default Blender FBX axes (-Z fwd, Y up), scale 1.
"""
import bpy, bmesh, os

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Prefabs\Structures\Mosque_01"
MAT = {'MOS_PLASTER': 'Mosque_01_Plaster', 'MOS_STONE': 'Mosque_01_Stone', 'MOS_PAINT': 'Mosque_01_Paint',
       'MOS_WOOD': 'Mosque_01_Wood', 'MOS_GOLD': 'Mosque_01_Gold', 'MOS_CARPET': 'Mosque_01_Carpet', 'MOS_RIB': 'Mosque_01_Rib'}
LOD_TRIS = [None, 0.50, 0.25, 0.10]      # target fraction of LOD0 tris (planar dissolve first, then collapse; plain collapse tore holes in stairs/walls)


def export(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'}, use_mesh_modifiers=True,
                             mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')


def tri(ob):
    """Enfusion triangulates n-gons itself and breaks concave ones (holes in walls, open stairs) -> export triangles only, like the old pipeline"""
    t = ob.modifiers.new('tri', 'TRIANGULATE'); t.min_vertices = 4; t.quad_method = 'BEAUTY'; t.ngon_method = 'BEAUTY'


def n_tris(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh(); n = sum(len(p.vertices) - 2 for p in me.polygons); ev.to_mesh_clear(); return n


def copy_obj(src, name, target=None):
    me = src.data.copy(); me.name = name
    if 'Zone' in me.attributes: me.attributes.remove(me.attributes['Zone'])
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.matrix_world = src.matrix_world
    if target:
        d = ob.modifiers.new('dis', 'DECIMATE'); d.decimate_type = 'DISSOLVE'; d.angle_limit = 0.0523599; d.delimit = {'MATERIAL', 'UV'}
        base = n_tris(ob); goal = n_tris(src) * target
        if base > goal:
            c = ob.modifiers.new('dec', 'DECIMATE'); c.decimate_type = 'COLLAPSE'; c.ratio = goal / base; c.use_collapse_triangulate = True
    tri(ob)
    return ob


src = bpy.data.objects['Mosque_LOD0']
renamed = []
for m in src.data.materials:
    if m and m.name in MAT: renamed.append((m, m.name)); m.name = MAT[m.name]
tmp = []
for i, r in enumerate(LOD_TRIS): tmp.append(copy_obj(src, f'Mosque_01_LOD{i}', r))
tmp.append(copy_obj(src, 'UTM_Mosque_01', 1.0))
LIGHTING = globals().get('LIGHTING', ('PRT_', 'PRTVOL_', 'BOXVOL_', 'BSP_', 'socket_'))   # set LIGHTING = () before exec to export without
extra = [o for o in bpy.data.objects if LIGHTING and o.name.startswith(tuple(LIGHTING))]   # lighting package (mosque_lighting.py)
print('lighting objects exported:', len(extra))
export(tmp + extra, os.path.join(ADDON, 'Mosque_01.fbx'))
dg = bpy.context.evaluated_depsgraph_get()
print('tris', [sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).to_mesh().polygons) for o in tmp])
for o in tmp: bpy.data.objects.remove(o)
for m, n in renamed: m.name = n

# panes: one representative mesh per kind, at origin (materials must be called like in the xob.meta: Mosque_01_Glass / Mosque_01_PaneFrame)
PMAT = {'Glas': 'Mosque_01_Glass', 'Rahmen_weiss': 'Mosque_01_PaneFrame'}
for kind, srcname in (('Pane_Body', 'Pane_Body_2_1'), ('Pane_Drum', 'Pane_Drum_0')):
    p = bpy.data.objects[srcname]
    pren = []
    for m in p.data.materials:
        if m and m.name in PMAT: pren.append((m, m.name)); m.name = PMAT[m.name]
    lod = bpy.data.objects.new(f'{kind}_LOD0', p.data.copy()); col = bpy.data.objects.new(f'UTM_{kind}', p.data.copy())
    tri(lod); tri(col)
    for o in (lod, col): bpy.context.collection.objects.link(o)
    export([lod, col], os.path.join(ADDON, 'Panes', f'{kind}.fbx'))
    for o in (lod, col): bpy.data.objects.remove(o)
    for m, n in pren: m.name = n
print('exported')
