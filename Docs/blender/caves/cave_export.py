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
import bmesh
# The rock is bumpy at every scale, and smart_project cuts an island wherever the face normal turns 60 degrees from the island's:
# on the raw mesh that gave tens of thousands of dot-sized islands (8 px each on a 4096 map), so the walls, floor and ceiling had
# no mask at all (black between the dots) and mips / block compression turned the dots into dark streaks in the engine.
# The mask is low-frequency, so unwrap a heavily smoothed copy of the same topology (big, coherent islands) and keep its UVs.
SMOOTH_IT = int(os.environ.get('CAVE_UV_SMOOTH', '60'))
FINE_AREA = float(os.environ.get('CAVE_UV_FINE_AREA', '0.002'))        # m2: below this a face is formation detail
FINE_SHARE = float(os.environ.get('CAVE_UV_FINE_SHARE', '0.30'))       # share of the atlas height given to the fine faces
UV_ANGLE = math.radians(float(os.environ.get('CAVE_UV_ANGLE', '66')))
UV_MARGIN = float(os.environ.get('CAVE_UV_MARGIN', '0.0006'))
# One uniform texel density leaves the many tiny faces of the formations (1-2 cm) far below one texel, so they got no mask at all.
# So two groups, each unwrapped over the whole square and then squeezed into its own band of the atlas: the fine faces get a band
# of their own (a much higher density), the rock shell the rest.
bm_u = bmesh.new()
bm_u.from_mesh(me)
orig_co = [v.co.copy() for v in bm_u.verts]
is_fine = [f.calc_area() < FINE_AREA for f in bm_u.faces]
bm_u.free()
print('UV groups: %d fine faces (< %.4f m2), %d shell faces' % (sum(is_fine), FINE_AREA, len(is_fine) - sum(is_fine)))


def unwrap_group(flags):
    """smart_project the faces with flags[i] True only (the mesh is in object mode before and after)."""
    bm_e = bmesh.new()
    bm_e.from_mesh(me)
    bm_e.faces.ensure_lookup_table()
    for f in bm_e.faces:
        f.select = False
    for e in bm_e.edges:
        e.select = False
    for v in bm_e.verts:
        v.select = False
    for k, f in enumerate(bm_e.faces):
        if flags[k]:
            f.select_set(True)
    bm_e.to_mesh(me)
    bm_e.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project(angle_limit=UV_ANGLE, island_margin=UV_MARGIN, area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def place_group(flags, v0, v1):
    """squeeze the UVs of the faces in the group into the band v0..v1 of the atlas"""
    uvd = me.uv_layers['UVMask'].data
    for k, poly in enumerate(me.polygons):
        if flags[k]:
            for li in poly.loop_indices:
                u, v = uvd[li].uv
                uvd[li].uv = (u, v0 + (v1 - v0) * v)


# the fine group on the real geometry
unwrap_group(is_fine)
place_group(is_fine, 1.0 - FINE_SHARE, 1.0)
# the shell: the rock is bumpy at every scale and smart_project cuts an island wherever the normal turns 66 degrees from the
# island's, which on the raw mesh gave dot-sized islands (walls, floor and ceiling with no mask, dark streaks through the mips).
# The mask is low-frequency, so unwrap a heavily smoothed copy of the same topology (big, coherent islands).
bm_u = bmesh.new()
bm_u.from_mesh(me)
for _ in range(SMOOTH_IT):
    bmesh.ops.smooth_vert(bm_u, verts=bm_u.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm_u.to_mesh(me)
bm_u.free()
me.update()
is_shell = [not x for x in is_fine]
unwrap_group(is_shell)
place_group(is_shell, 0.0, 1.0 - FINE_SHARE)
for v, c in zip(me.vertices, orig_co):
    v.co = c
me.update()
print('UV set 2 done (shell unwrapped on a mesh smoothed %d times; fine faces in the top %.0f%% of the atlas)' % (SMOOTH_IT, 100 * FINE_SHARE))

# --- bake the mask (on a copy with one bake material, so the export keeps its own material slots)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 1
sc.cycles.device = 'CPU'
img = bpy.data.images.new(name + '_MASK', RES, RES, alpha=False, float_buffer=False)
bake_ob = lod.copy()
bake_ob.data = me.copy()


def break_up_repetition(mesh, seed):
    """Large-scale variation baked into the mask, so no surface shows ONE texture tiled over 100 m: patches of other layers at
    different scales over walls, ceilings and floors. Mask R = flowstone (floor sheets, smooth wall zones, roots/crusts as built),
    G = dripstone (the formations as built + blocky wall zones), B = sediment (floor ground, outside the flowstone sheets)."""
    import numpy as np
    from mathutils import noise, Vector
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    nm = np.empty(n * 3, dtype=np.float32)
    mesh.vertex_normals.foreach_get('vector', nm)
    nz = nm.reshape(n, 3)[:, 2]
    att = {}
    for key in ('Calcite', 'Tip', 'Tip2'):
        a_ = mesh.color_attributes.get(key)
        buf = np.zeros(n * 4, dtype=np.float32)
        if a_ is not None and a_.domain == 'POINT':
            a_.data.foreach_get('color', buf)
        att[key] = (a_, buf.reshape(n, 4))
    R, G = att['Calcite'][1][:, 0].copy(), att['Tip'][1][:, 0].copy()
    off = Vector((seed * 1.37 % 97, seed * 2.11 % 89, seed * 0.73 % 83))

    def sm(x):
        x = np.clip(x, 0.0, 1.0)
        return x * x * (3 - 2 * x)

    nA = np.empty(n, dtype=np.float32)
    nB = np.empty(n, dtype=np.float32)
    nC = np.empty(n, dtype=np.float32)
    for i in range(n):
        c = Vector(co[i])
        nA[i] = noise.noise(c / 8.0 + off) + 0.35 * noise.noise(c / 3.1 + off * 1.7)
        nB[i] = noise.noise(c / 2.6 + off * 0.6)
        nC[i] = noise.noise(c / 13.0 + off * 2.3) + 0.3 * noise.noise(c / 4.7 + off * 0.4)
    floor = sm((nz - 0.35) / 0.25)
    ceil = sm((-nz - 0.15) / 0.3)
    wall = np.clip(1.0 - floor - ceil, 0.0, 1.0)
    form = np.clip(G * 1.6, 0.0, 1.0)                       # where a formation is (as built): leave it to its own layer
    # walls and ceilings: tone in tone (patches at about a third of the strength, soft edges); the floor keeps its flowstone sheets
    WALL_K = float(os.environ.get('CAVE_WALL_PATCH', '0.38'))
    flow = floor * sm((nA + 0.5 * nB + 0.05) / 0.3) + wall * sm((nA - 0.05) / 0.45) * WALL_K + ceil * sm((nA - 0.1) / 0.45) * WALL_K * 0.8
    block = wall * sm((nC - 0.05) / 0.45) * WALL_K * 0.7 + ceil * sm((nC - 0.15) / 0.45) * WALL_K * 0.5
    sed = floor * (1.0 - np.clip(flow, 0, 1) * 0.85) * (0.55 + 0.45 * sm((nB + 0.35) / 0.5))
    R2 = np.maximum(R, flow * (1.0 - form))
    G2 = np.maximum(G, block * (1.0 - form) * (1.0 - R2 * 0.7))
    B2 = sed * (1.0 - form) * (1.0 - R2)
    print('mask coverage: flowstone %.0f%%, dripstone %.0f%%, sediment %.0f%% of vertices (mean values)' % (100 * R2.mean(), 100 * G2.mean(), 100 * B2.mean()))
    for key, vals in (('Calcite', R2), ('Tip', G2), ('Tip2', B2)):
        a_, buf = att[key]
        if a_ is None or a_.domain != 'POINT':
            a_ = mesh.color_attributes.new(key, 'FLOAT_COLOR', 'POINT')
        out = np.stack([vals, vals, vals, np.ones(n, dtype=np.float32)], axis=1).astype(np.float32).reshape(-1)
        a_.data.foreach_set('color', out)


if os.environ.get('CAVE_MASK_VARIATION', '1') == '1':
    break_up_repetition(bake_ob.data, sum(ord(ch) for ch in name))
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
bpy.ops.object.bake(type='EMIT', margin=12, use_clear=True)

# --- self check: the baked mask sampled at every corner's UV must equal the vertex attributes it was baked from. Overlapping or
# folded islands, or vertices on an island seam that landed in the wrong island, show up as large errors.
import numpy as np
_m = bake_ob.data
_nl = len(_m.loops)
_uv = np.empty(_nl * 2, dtype=np.float32)
_m.uv_layers['UVMask'].data.foreach_get('uv', _uv)
_uv = _uv.reshape(_nl, 2)
_vi = np.empty(_nl, dtype=np.int32)
_m.loops.foreach_get('vertex_index', _vi)
_px = np.empty(RES * RES * 4, dtype=np.float32)
img.pixels.foreach_get(_px)
_px = _px.reshape(RES, RES, 4)
_ix = np.clip((_uv[:, 0] * RES).astype(np.int32), 0, RES - 1)
_iy = np.clip((_uv[:, 1] * RES).astype(np.int32), 0, RES - 1)
_samp = _px[_iy, _ix, :3]
_exp = np.zeros((len(_m.vertices), 3), dtype=np.float32)
for _k, _key in enumerate(('Calcite', 'Tip', 'Tip2')):
    _b = np.zeros(len(_m.vertices) * 4, dtype=np.float32)
    _a = _m.color_attributes.get(_key)
    if _a is not None:
        _a.data.foreach_get('color', _b)
        _exp[:, _k] = _b.reshape(-1, 4)[:, 0]
_err = np.abs(_samp - _exp[_vi]).max(axis=1)
if os.environ.get('CAVE_DEBUG_NPZ'):
    _co = np.empty(len(_m.vertices) * 3, dtype=np.float32)
    _m.vertices.foreach_get('co', _co)
    np.savez(os.environ['CAVE_DEBUG_NPZ'], uv=_uv, vi=_vi, exp=_exp, samp=_samp, co=_co.reshape(-1, 3))
print('MASKCHECK per channel: expected mean %s, sampled mean %s, mean abs error %s' % (
    np.round(_exp[_vi].mean(axis=0), 3), np.round(_samp.mean(axis=0), 3), np.round(np.abs(_samp - _exp[_vi]).mean(axis=0), 3)))
print('MASKCHECK corners %d: mean error %.3f, > 0.25 on %.1f%%, > 0.5 on %.1f%%; atlas empty %.0f%%' % (
    _nl, _err.mean(), 100 * (_err > 0.25).mean(), 100 * (_err > 0.5).mean(), 100 * (_px[:, :, :3].max(axis=2) < 0.004).mean()))
img.filepath_raw = os.path.join(OUT, name + '_MASK.tif')
img.file_format = 'TIFF'
sc.render.image_settings.color_depth = '8'
img.save()
print('mask baked ->', img.filepath_raw)
bpy.data.objects.remove(bake_ob)

# --- vertex colours: the mask data (Calcite/Tip/Tip2) is baked into the MaskMap and must NOT travel into the FBX: the first colour set
# of the FBX is read as the vertex colour, and a flowstone mask there darkens every surface where the mask is 0 (soft dark blobs, no
# texture detail change, the "cow pattern"). Only one plain white 'Col' layer goes out (a missing one renders black).
for key in ('Calcite', 'Tip', 'Tip2', 'Col'):
    a_ = me.color_attributes.get(key)
    if a_ is not None:
        me.color_attributes.remove(a_)
white = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
import numpy as _np
white.data.foreach_set('color', _np.ones(len(me.loops) * 4, dtype=_np.float32))
me.color_attributes.active_color = white
me.color_attributes.render_color_index = list(me.color_attributes).index(white)
print('vertex colour layers exported:', [a.name for a in me.color_attributes])

# --- unused material slots out (the timber frames are gone: a leftover TT_Wood slot would travel into the FBX, and Workbench then
# lists a material nothing uses and warns about it as "deleted" on every reimport)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = lod
lod.select_set(True)
used_slots = {p.material_index for p in me.polygons}
print('material slots before:', [s.material.name if s.material else None for s in lod.material_slots], 'used', sorted(used_slots))
bpy.ops.object.material_slot_remove_unused()
print('material slots after:', [s.material.name if s.material else None for s in lod.material_slots])
if utm is not None and utm.type == 'MESH':
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = utm
    utm.select_set(True)
    bpy.ops.object.material_slot_remove_unused()
    print('collision slots after:', [s.material.name if s.material else None for s in utm.material_slots], [p.material_index for p in utm.data.polygons[:3]])
    utm.select_set(False)
    bpy.context.view_layer.objects.active = lod
    lod.select_set(True)

# --- FBX
me.uv_layers.active = world_uv
for o in bpy.context.view_layer.objects:
    o.select_set(False)
# --- LODs: the same room with fewer triangles for distance (a long hall is mostly seen far away)
lods = []
n0 = len(me.polygons)
LOD_RATIOS = [(1, float(os.environ.get('CAVE_LOD1', '0.40'))), (2, float(os.environ.get('CAVE_LOD2', '0.14')))]
if n0 > int(os.environ.get('CAVE_LOD_MIN', '120000')):
    for level, ratio in LOD_RATIOS:
        ob = bpy.data.objects.new('%s_LOD%d' % (name, level), me.copy())
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = lod.matrix_world
        d = ob.modifiers.new('dec', 'DECIMATE')
        d.ratio = ratio
        d.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        me_l = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        old = ob.data
        ob.data = me_l
        bpy.data.meshes.remove(old)
        ob.data.name = ob.name
        for p_ in ob.data.polygons:
            p_.use_smooth = True
        lods.append(ob)
        print('LOD%d: %d triangles (%.0f percent)' % (level, len(ob.data.polygons), 100.0 * len(ob.data.polygons) / n0))
for o in [lod, utm] + lods + empties:
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
