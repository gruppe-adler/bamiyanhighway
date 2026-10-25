"""Builds + exports the carpet floors (porch rect + hall octagon) as separate mesh Mosque_01_CarpetFloor.fbx.
UV = metres / 3.5 (one texture tile = 4x4 prayer niches = 3.5 m), grid aligned so that x=0 is a niche centre -> symmetric. Niche tips point to -y (away from the entrance)."""
import bpy, bmesh, math, os
from mathutils import Vector
ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Prefabs\Structures\Mosque_01"
Z = 0.915; TILE = 3.5
def uvf(x, y): return (x / TILE + 0.125 + 8.0, -y / TILE + 0.125 + 8.0)
me = bpy.data.meshes.new('Mosque_01_CarpetFloor_LOD0'); bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap')
def poly(pts):
    f = bm.faces.new([bm.verts.new((x, y, Z)) for x, y in pts])
    if f.normal.z < 0: f.flip()
    for l in f.loops: l[uv].uv = uvf(l.vert.co.x, l.vert.co.y)
    return f
A = 7.95                                              # hall carpet octagon apothem (wall inner 8.43)
k = A / math.cos(math.radians(22.5))
hall = poly([(k * math.cos(math.radians(67.5 + 45 * i)), k * math.sin(math.radians(67.5 + 45 * i))) for i in range(8)])
bmesh.ops.triangulate(bm, faces=[hall])
CELL = TILE / 4
poly([(-2.5 * CELL, 9.1875), (2.5 * CELL, 9.1875), (2.5 * CELL, 9.1875 + 4 * CELL), (-2.5 * CELL, 9.1875 + 4 * CELL)])   # porch: 5 x 4 niches
bmesh.ops.triangulate(bm, faces=bm.faces[:])
for f in bm.faces: f.smooth = False
bm.to_mesh(me); bm.free()
mat = bpy.data.materials.get('Mosque_01_CarpetFloor') or bpy.data.materials.new('Mosque_01_CarpetFloor'); me.materials.append(mat)
ob = bpy.data.objects.new('Mosque_01_CarpetFloor_LOD0', me); bpy.context.collection.objects.link(ob)
bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=os.path.join(ADDON, 'Mosque_01_CarpetFloor.fbx'), use_selection=True, object_types={'MESH'}, mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False)
bpy.data.objects.remove(ob); print('carpet exported', len(me.polygons))
