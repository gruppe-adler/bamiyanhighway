"""Export the irrigation ditch kit (graben_modul_kit.blend) to the addon, headless:
  blender --factory-startup -b <graben_modul_kit.blend> --python graben_export.py
Does not save the blend. Writes per variant Graben_<V>.fbx (LOD0-2 + UTM_ collider, triangles only, white 'Col' layer,
materials Graben_Ground / Graben_Lehm) and the packed textures Graben_Lehm_BCR.tif (RGB diffuse, A roughness) and
Graben_Lehm_NMO.tif (RG DirectX normal, B metal 0, A AO).
"""
import bpy, bmesh, os, math
from mathutils import Matrix, Vector
import numpy as np

SRC = r"G:\Meine Ablage\Gruppe Adler\mapbau\bamiyan highway\irrigation"
OUT = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Assets\Structures\Irrigation\Graben"
TEX = os.path.join(SRC, "GRABEN_Lehm")
VARIANTS = ['STRAIGHT', 'SWERVE_a', 'SWERVE_b', 'CORNER_a', 'CORNER_b', 'TJ_a', 'TJ_b']
MATS = {'GRABEN_Ground': 'Graben_Ground', 'GRABEN_Lehm': 'Graben_Lehm'}


def load(name):
    img = bpy.data.images.load(os.path.join(TEX, name))
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels), w, h


def save(arr, w, h, path):
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(arr.reshape(-1))
    img.file_format = 'TIFF'
    img.filepath_raw = path
    s = bpy.context.scene.render.image_settings
    s.file_format = 'TIFF'; s.color_depth = '8'; s.color_mode = 'RGBA'
    img.save(quality=100)


def textures():
    diff, w, h = load('GRABEN_Lehm_diff_2k.jpg')
    rough, _, _ = load('GRABEN_Lehm_rough_2k.jpg')
    nor, _, _ = load('GRABEN_Lehm_nor_dx_2k.jpg')
    ao, _, _ = load('GRABEN_Lehm_ao_2k.jpg')
    bcr = np.ones((h, w, 4), np.float32); bcr[..., :3] = diff[..., :3]; bcr[..., 3] = rough[..., 0]
    nmo = np.zeros((h, w, 4), np.float32); nmo[..., :2] = nor[..., :2]; nmo[..., 2] = 0.0; nmo[..., 3] = ao[..., 0]
    save(bcr, w, h, os.path.join(OUT, 'Data', 'Graben_Lehm_BCR.tif'))
    save(nmo, w, h, os.path.join(OUT, 'Data', 'Graben_Lehm_NMO.tif'))
    print('textures', w, h)


BANK_LEN = 0.5          # length of the river-side bank pieces (m)
SHORT_LEN = 0.25         # length of Graben_SHORT (m)
FLARE_X0 = 0.3           # lateral offset where the 45 deg butterfly flare starts (channel edge is 0.25)
_R = (3 * 2.0 - 2 * 0.4) / math.radians(90.0)   # CORNER arc radius from generate_graben_kit.py (3 tiles, lead 0.4)


def joints(variant):
    """Joint planes in the module frame (before rotation): (centre xy, outward tangent xy)."""
    if variant == 'STRAIGHT' or variant.startswith('SWERVE'):
        return [((0, 0), (0, -1)), ((0, 2), (0, 1))]
    if variant.startswith('CORNER'):
        sg = 1.0 if variant.endswith('_a') else -1.0
        return [((0, 0), (0, -1)), ((sg * (_R + 0.4), 0.4 + _R), (sg, 0))]
    sg = 1.0 if variant.endswith('_a') else -1.0
    return [((0, 0), (0, -1)), ((0, 6), (0, 1)), ((sg * 3.0, 3.0), (sg, 0))]


def flare(me, frames):
    """Butterfly: shoulder/skirt vertices of each joint loop slide outward along 45 deg so neighbouring pieces overlap on the outside of a bend (the channel loop |x|<0.25 stays put and still matches exactly)."""
    for v in me.vertices:
        for (cx, cy), (tx, ty) in frames:
            dx, dy = v.co.x - cx, v.co.y - cy
            if abs(dx * tx + dy * ty) > 1e-4: continue
            lat = abs(dx * ty - dy * tx)
            if lat > FLARE_X0:
                k = lat - FLARE_X0
                v.co.x += tx * k; v.co.y += ty * k
            break


def shape(me, kind, variant=None, with_flare=True):
    """kind: None | 'SHORT' (STRAIGHT halved to 1 m) | 'END' / 'START' (1 m ramp that opens flush into the terrain at the free end, plan view rounded)"""
    length = {'SHORT': SHORT_LEN, 'BANK_R': BANK_LEN, 'BANK_L': BANK_LEN}.get(kind, 1.0)
    bank = kind in ('BANK_R', 'BANK_L')
    if kind:
        me.transform(Matrix.Scale(length / 2.0, 4, Vector((0, 1, 0))))
        uv = me.uv_layers.active.data
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv[li].uv = (co.x / 2.0, co.y / 2.0)
    # bury the outer shoulder edge (-0.12 -> -0.30 m) so seams on bends disappear into the terrain
    for v in me.vertices:
        if -0.1301 < v.co.z < -1e-4: v.co.z *= 2.5
    if bank:
        # keep only x >= channel edge (0.25 m): shoulder + a closed vertical mud wall facing the river
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0.25, 0, 0), plane_no=(1, 0, 0), dist=1e-5, clear_inner=True)
        edges = [e for e in bm.edges if e.is_boundary]
        new = bmesh.ops.holes_fill(bm, edges=edges, sides=0)['faces']
        for f in new: f.material_index = 1
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        print('BANK boundary edges after fill:', sum(e.is_boundary for e in bm.edges), 'nonmanifold:', sum(not e.is_manifold for e in bm.edges))
        bm.to_mesh(me); bm.free()
        uv = me.uv_layers.active.data
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv[li].uv = (co.y / 2.0, co.z / 2.0) if poly.material_index == 1 and abs(co.x - 0.25) < 1e-4 and abs(poly.normal.x) > 0.9 else (co.x / 2.0, co.y / 2.0)
    if with_flare:
        if kind in ('SHORT', 'BANK_R', 'BANK_L'):
            frames = [((0, 0), (0, -1)), ((0, length), (0, 1))]
        elif kind in ('END', 'START'):
            frames = [((0, 0), (0, -1))]          # only the joint end; the open end stays clean
        else:
            frames = joints(variant)
        flare(me, frames)
    if kind in ('END', 'START'):
        for v in me.vertices:
            t = v.co.y                       # 0 at the joint, 1 at the open end (length is 1 m)
            d = 1.0 - t * t * (3.0 - 2.0 * t)
            if v.co.z > -0.9: v.co.z *= d
            v.co.x *= 1.0 - 0.4 * t * t
        if kind == 'START':
            for v in me.vertices: v.co.y = 1.0 - v.co.y
            me.flip_normals()
    if kind == 'BANK_L':
        me.transform(Matrix.Scale(-1, 4, Vector((1, 0, 0))))
        me.flip_normals()
    me.update()


def prep(src, name, kind=None, variant=None, collider=False):
    me = src.data.copy(); me.name = name
    shape(me, kind, variant, with_flare=not collider)
    # kit runs along Blender +Y; WallGenerator lays pieces along local X -> rotate -90 deg about Z so the length ends up on +X
    me.transform(Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 0, 0)
    me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
    # Graben_Ground is a MatTerrainObject: vertex colour R = 0 shows the terrain beneath, Lehm stays white
    col = me.color_attributes['Col'].data
    for poly in me.polygons:
        c = (0, 1, 1, 1) if poly.material_index == 0 else (1, 1, 1, 1)
        for li in poly.loop_indices: col[li].color = c
    t = ob.modifiers.new('tri', 'TRIANGULATE'); t.min_vertices = 4; t.quad_method = 'BEAUTY'; t.ngon_method = 'BEAUTY'
    return ob


BERM = dict(inner=0.3, outer=float(os.environ.get('GRABEN_BERM_OUTER', 0.6)), height=0.3, length=0.5, centre=0.45, base=-0.1, off=-0.02)
BERM_DETAIL = {0: (32, 17), 1: (20, 9), 2: (10, 5)}   # (segments around, rings along) per LOD; collider = LOD2


def build_berm(name, side, lod):
    """Short ellipsoid berm along +Y (pivot at its start). Inner side (towards the river) round and steep, outer side a cosine bell that
    eases to zero thickness at ground level (tangent to the terrain). Surface = Graben_Ground (terrain blend, vertex colour R = 0)."""
    L, c, h = BERM['length'], BERM['centre'], BERM['height']
    seg, rings = BERM_DETAIL[lod]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co                       # unit sphere, pole axis Z reused as the long axis
        rho = math.hypot(x, y)
        t = x / rho if rho > 1e-9 else 0.0
        if t > 0:
            hp = (1 + math.cos(math.pi * t)) / 2 if y >= 0 else -math.sqrt(max(0.0, 1 - t * t))
            lat = rho * t * BERM['outer']
        else:
            hp = math.sqrt(max(0.0, 1 - t * t)) * (1 if y >= 0 else -1)
            lat = rho * t * BERM['inner']
        v.co = Vector((side * (c + lat), L / 2.0 + z * L / 2.0, max(rho * h * hp + BERM['off'], BERM['base'])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.calc_volume(signed=True) < 0:      # axis swap / side mirror may leave the faces pointing inward
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    print('BERM volume', name, round(bm.calc_volume(signed=True), 4))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(bpy.data.materials['Graben_Ground'])
    uv = me.uv_layers.new(name='UVMap').data
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = (co.x / 2.0, co.y / 2.0)
    me.transform(Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
    for d in me.color_attributes['Col'].data: d.color = (0, 1, 1, 1)      # R = 0 -> terrain shows through
    t = ob.modifiers.new('tri', 'TRIANGULATE'); t.min_vertices = 4; t.quad_method = 'BEAUTY'; t.ngon_method = 'BEAUTY'
    return ob


def export_berms():
    for side, tag in ((1, 'R'), (-1, 'L')):
        v = f'BERM_{tag}'
        objs = [build_berm(f'Graben_{v}_LOD{i}', side, i) for i in range(3)] + [build_berm(f'UTM_Graben_{v}', side, 2)]
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs: o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f'Graben_{v}.fbx'), use_selection=True, object_types={'MESH'},
                                 use_mesh_modifiers=True, mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
        dg = bpy.context.evaluated_depsgraph_get()
        print(v, [sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).to_mesh().polygons) for o in objs])


def main():
    os.makedirs(os.path.join(OUT, 'Data'), exist_ok=True)
    if not os.environ.get('GRABEN_SKIP_TEX'): textures()
    for old, new in MATS.items(): bpy.data.materials[old].name = new
    for v, base, kind in [(v, v, None) for v in VARIANTS] + [('SHORT', 'STRAIGHT', 'SHORT'), ('END', 'STRAIGHT', 'END'), ('START', 'STRAIGHT', 'START'), ('BANK_R', 'STRAIGHT', 'BANK_R'), ('BANK_L', 'STRAIGHT', 'BANK_L')]:
        objs = [prep(bpy.data.objects[f'GrabenModul_{base}_LOD{2 if kind == "SHORT" else i}'], f'Graben_{v}_LOD{i}', kind, v) for i in range(3)]
        objs.append(prep(bpy.data.objects[f'UCX_{base}'], f'UTM_Graben_{v}', kind, v, True))
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs: o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f'Graben_{v}.fbx'), use_selection=True, object_types={'MESH'},
                                 use_mesh_modifiers=True, mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
        dg = bpy.context.evaluated_depsgraph_get()
        print(v, [sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).to_mesh().polygons) for o in objs])
    export_berms()
    print('done')


main()
