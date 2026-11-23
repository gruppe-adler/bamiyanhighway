"""Export a v5 room for Workbench: a second UV set (unique unwrap) for MatPBRMulti's MaskMap, the mask baked from the
vertex attributes (R = Calcite/flowstone, G = Tip/formation look, B = Tip2/white tips), and the FBX (<Name>_LOD0,
UTM_<Name>, memory points 1, 2, ...). Run on a saved v5 scene:
  blender.exe --factory-startup -b <TT_Room_Drip_A_v5.blend> --python cave_export.py
Environment: CAVE_ASSETS = target folder (default the addon's Assets/Tunnels/Cave), CAVE_MASK_RES (default 4096).
"""
import os, math
import bpy

ADDON = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OUT = os.environ.get('CAVE_ASSETS', os.path.join(ADDON, 'Assets', 'Tunnels', 'Cave'))
RES = int(os.environ.get('CAVE_MASK_RES', '4096'))
os.makedirs(OUT, exist_ok=True)

lod = next(o for o in bpy.data.objects if o.name.endswith('_LOD0') and o.type == 'MESH')
name = lod.name[:-len('_LOD0')]
utm = bpy.data.objects.get('UTM_' + name)
empties = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.isdigit()]
me = lod.data
print('exporting', name, len(me.polygons), 'triangles,', len(empties), 'memory points')

# --- UV set 2: a unique unwrap for the mask
world_uv = me.uv_layers[0]
world_uv.name = 'UVMap'
mask_uv = me.uv_layers.get('UVMask') or me.uv_layers.new(name='UVMask')
me.uv_layers.active = mask_uv
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = lod
lod.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0015, area_weight=0.0, scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT')
print('UV set 2 done')

# --- bake the mask (on a copy with one bake material, so the export keeps its own material slots)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 1
sc.cycles.device = 'CPU'
img = bpy.data.images.new(name + '_MASK', RES, RES, alpha=False, float_buffer=False)
bake_ob = lod.copy()
bake_ob.data = me.copy()
sc.collection.objects.link(bake_ob)
bake_ob.data.uv_layers.active = bake_ob.data.uv_layers['UVMask']
bmat = bpy.data.materials.new('mask_bake')
bmat.use_nodes = True
nt = bmat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
outn = nt.nodes.new('ShaderNodeOutputMaterial')
em = nt.nodes.new('ShaderNodeEmission')
comb = nt.nodes.new('ShaderNodeCombineColor')
for ch, att in (('Red', 'Calcite'), ('Green', 'Tip'), ('Blue', 'Tip2')):
    a = nt.nodes.new('ShaderNodeAttribute')
    a.attribute_name = att
    nt.links.new(a.outputs['Fac'], comb.inputs[ch])
nt.links.new(comb.outputs['Color'], em.inputs['Color'])
nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])
texn = nt.nodes.new('ShaderNodeTexImage')
texn.image = img
nt.nodes.active = texn
bake_ob.data.materials.clear()
bake_ob.data.materials.append(bmat)
for p in bake_ob.data.polygons:
    p.material_index = 0
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bake_ob.select_set(True)
bpy.context.view_layer.objects.active = bake_ob
img.colorspace_settings.name = 'Non-Color'
bpy.ops.object.bake(type='EMIT', margin=6, use_clear=True)
img.filepath_raw = os.path.join(OUT, name + '_MASK.tif')
img.file_format = 'TIFF'
sc.render.image_settings.color_depth = '8'
img.save()
print('mask baked ->', img.filepath_raw)
bpy.data.objects.remove(bake_ob)

# --- FBX
me.uv_layers.active = world_uv
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in [lod, utm] + empties:
    if o:
        o.hide_set(False)
        o.select_set(True)
bpy.context.view_layer.objects.active = lod
path = os.path.join(OUT, name + '.fbx')
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'}, use_mesh_modifiers=True,
                         mesh_smooth_type='EDGE', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
print('fbx ->', path)

# --- the water: its own model (a child of the room prefab), and the room's inner size for its dark probe
import json
water = next((o for o in bpy.data.objects if o.name.startswith('Water_') and o.type == 'MESH'), None)
if False and water and len(water.data.polygons):      # water export off: the user adds their own
    water.name = name + '_Water_LOD0'
    water.data.name = name + '_Water_LOD0'
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    water.hide_set(False)
    water.select_set(True)
    bpy.context.view_layer.objects.active = water
    wpath = os.path.join(OUT, name + '_Water.fbx')
    bpy.ops.export_scene.fbx(filepath=wpath, use_selection=True, object_types={'MESH'}, mesh_smooth_type='FACE',
                             add_leaf_bones=False, bake_anim=False)
    print('water fbx ->', wpath)
socks = [e.location.copy() for e in empties]
pts = [v.co for v in me.vertices]
inner = []
earth_vs = set(i for p in me.polygons if p.material_index == 0 for i in p.vertices)
for i in earth_vs:
    co = me.vertices[i].co
    if all((co - s).length > 1.6 for s in socks):
        inner.append(co)
lo = [min(c[k] for c in inner) for k in range(3)]
hi = [max(c[k] for c in inner) for k in range(3)]
info = dict(name=name, inner_min=lo, inner_max=hi, water=bool(water and len(water.data.polygons)))
json.dump(info, open(os.path.join(OUT, name + '_info.json'), 'w'), indent=1)
print('info', info)
