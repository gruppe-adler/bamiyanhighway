"""Lighting package for the mosque (Enfusion Blender Tools conventions, see BI wiki "Portal Tools"):
sockets (win/door) -> PRT_ portals (via ebt.generate_portals, needs Workbench net API) -> PRTVOL_ rooms, BOXVOL_ probe volumes, BSP_ hull.
Run in the interactive Blender (EBT add-on loaded, Workbench running) on mosque_v4_baked.blend. Idempotent."""
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler

PFX = ('socket_', 'PRT_', 'PRTVOL_', 'BOXVOL_', 'BSP_', 'UTM_tmp')
for ob in list(bpy.data.objects):
    if ob.name.startswith(PFX): bpy.data.objects.remove(ob, do_unlink=True)
for cname in ('Light Portals',):
    c = bpy.data.collections.get(cname)
    if c and not c.objects: bpy.data.collections.remove(c)

main = bpy.data.objects['Mosque_LOD0']
A_I, Z_FLOOR, Z_TOP = 8.35, 0.95, 5.58           # hall volumes: inset 8 cm from walls/floor/ceiling (they poked through the roof)
DR_A, Z_DOME = 4.4, 13.0                         # dome-space octagon apothem and top

dummy = bpy.data.materials.get('dummyvolume_D3975B51F51E6BD5') or bpy.data.materials.new('dummyvolume_D3975B51F51E6BD5')
coll = bpy.context.scene.collection

def link(ob): coll.objects.link(ob); return ob

# ---------- sockets at window centres (orientation of the pane objects: local X = width, Z = up, Y = outward normal) ----------
n_b = n_d = 0
for ob in sorted([o for o in bpy.data.objects if o.name.startswith(('Pane_Body_', 'Pane_Drum_'))], key=lambda o: o.name):
    body = ob.name.startswith('Pane_Body')
    h = max(v.co.z for v in ob.data.vertices)
    if body: n_b += 1; name = f'socket_win1_{n_b:02d}'
    else: n_d += 1; name = f'socket_win2_{n_d:02d}'
    e = bpy.data.objects.new(name, None); e.empty_display_type = 'ARROWS'; e.empty_display_size = 0.25
    e.matrix_world = Matrix.Translation(ob.matrix_world @ Vector((0, 0, h / 2))) @ ob.matrix_world.to_3x3().to_4x4()
    link(e)
door = bpy.data.objects.new('socket_door_ext_01', None); door.empty_display_type = 'ARROWS'; door.empty_display_size = 0.4
door.location = (0, 8.93, Z_FLOOR); door.rotation_euler = (0, 0, 0); link(door)
print('sockets', n_b, n_d, 1)

# ---------- portals: own generator (ebt.generate_portals could not raycast in a scripted session) ----------
from mathutils import bvhtree
from enfusion import workbench
from EnfusionBlenderTools.ebt import ebt_utils
info = ebt_utils.get_workbench_connection_info()
W = [45, 55, 70, 90, 100, 130, 141, 150, 170, 195, 340, 400]; H = [72, 142, 182, 245, 340, 350]
dg = bpy.context.evaluated_depsgraph_get(); tree = bvhtree.BVHTree.FromObject(main, dg)
def ray(p, d):
    loc, nrm, idx, dist = tree.ray_cast(p, d); return dist if idx is not None else None
def portal_mat(w_cm, h_cm, sock):
    """nearest standard portal material that exists in the game (tries the closest size combinations first)"""
    combos = sorted(((abs(w - w_cm) / 100 + abs(h - h_cm) / 100, w, h) for w in W for h in H))[:12]
    for _, w, h in combos:
        r = workbench.call_function(info, 'GetPortalMat', {'matHeights': [h], 'matWidths': [w], 'socketNames': [sock]})
        nm = (r.get('matNames') or [''])[0]
        if nm and f'{w}x{h}' in nm: return nm, w, h
    return '', 0, 0
n = 0
for s_ in sorted([o for o in bpy.data.objects if o.name.startswith('socket_')], key=lambda o: o.name):
    M = s_.matrix_world; ex, ey, ez = M.to_3x3().col[0].normalized(), M.to_3x3().col[1].normalized(), M.to_3x3().col[2].normalized()
    c = M.translation.copy()
    if 'door' in s_.name:          # measure the opening with rays (centre of the arch, a bit above the floor)
        c = c + Vector((0, 0.15, 2.0)); wl, wr, up = ray(c, -ex), ray(c, ex), ray(c, Vector((0, 0, 1)))
        w = (wl or 1.5) + (wr or 1.5); h_top = (up or 1.5) + 2.0; h = h_top; c = M.translation + Vector((0, 0, h / 2)) + Vector((ex * ((wr or 1.5) - (wl or 1.5)) / 2))
    elif 'win1' in s_.name: w, h = 1.20, 2.05
    else: w, h = 0.75, 1.10
    n += 1; name = f'PRT_{n:02d}'
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    q = [bm.verts.new((sx * (w + 0.15) / 2, 0, sz * (h + 0.15) / 2)) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = bm.faces.new(q)
    if f.normal.y > 0: f.flip()            # normal points to the building centre ( EBT convention )
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = Matrix.Translation(c - M.translation) @ M if 'door' not in s_.name else Matrix.Translation(c) @ M.to_3x3().to_4x4()
    if 'door' not in s_.name: ob.matrix_world = M
    link(ob)
    nm, wm, hm = portal_mat(w * 100, h * 100, s_.name)
    if nm: ob.data.materials.append(bpy.data.materials.get(nm) or bpy.data.materials.new(nm))
    if n <= 3 or 'door' in s_.name: print(name, s_.name, f'{w*100:.0f}x{h*100:.0f}', '->', nm)
    ob['socket'] = s_.name
# is the portal normal really facing the centre?  (sanity)
prts = [o for o in bpy.data.objects if o.name.startswith('PRT_') and not o.name.startswith('PRTVOL')]
bad = sum(1 for p in prts if (p.matrix_world.to_3x3() @ p.data.polygons[0].normal).dot(Vector((0, 0, 0)) - p.matrix_world.translation) <= 0 and (abs(p.matrix_world.translation.x) + abs(p.matrix_world.translation.y)) > 1)
print('portals', len(prts), 'facing outwards (should be 0):', bad)

# ---------- volumes ----------
def box(name, size, loc, rot_z_deg):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bm.to_mesh(me); bm.free(); me.materials.append(dummy)
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.rotation_euler = (0, 0, math.radians(rot_z_deg)); link(ob); return ob
def octagon_prism(name, apothem, z0, z1):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); k = apothem / math.cos(math.radians(22.5))
    lo = [bm.verts.new((k * math.cos(math.radians(67.5 + 45 * i)), k * math.sin(math.radians(67.5 + 45 * i)), z0)) for i in range(8)]
    hi = [bm.verts.new((v.co.x, v.co.y, z1)) for v in lo]
    bm.faces.new(lo[::-1]); bm.faces.new(hi)
    for i in range(8): bm.faces.new((lo[i], lo[(i + 1) % 8], hi[(i + 1) % 8], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free(); me.materials.append(dummy)
    ob = bpy.data.objects.new(name, me); link(ob); return ob
# stepped volumes that follow the real inner space (hole in the ceiling r 4.96, drum inner r 5.36, dome inner radius shrinking above z 10); lighting report 2026-10-25:
# the old single dome octagon (apothem 4.4) left the drum windows and the lower dome shell outside every volume, and hall/dome volumes did not touch.
TIERS = [(4.5, 5.0, 6.2), (4.95, 6.15, 8.7), (3.9, 8.65, 12.0)]          # (apothem, z0, z1) above the hall: ceiling hole, drum, dome; PRTVOL/BOXVOL may overlap
BSP_TIERS = [(4.5, Z_TOP + 0.05, 6.13), (4.95, 6.18, 8.65), (3.9, 8.7, 12.0)]   # BSP must not overlap
Z_FLOOR_V = 0.85                                                          # volume floor below the floor (carpets at 0.945 were outside the 0.95 volumes)
octagon_prism('PRTVOL_01', A_I, Z_FLOOR_V, Z_TOP)          # hall
for n, (a_, z0, z1) in enumerate(TIERS, 2): octagon_prism(f'PRTVOL_{n:02d}', a_, z0, z1)
bn = 1
for i, rot in enumerate((0, 45, 90, 135), 1):                                  # an octagon = union of 4 boxes, also used as probe volumes
    side = 2 * A_I * math.tan(math.radians(22.5)); h = Z_TOP - Z_FLOOR_V
    box(f'BOXVOL_{bn:02d}', (2 * A_I, side, h), (0, 0, Z_FLOOR_V + h / 2), rot); bn += 1
for a_, z0, z1 in TIERS:
    for rot in (0, 45, 90, 135):
        side = 2 * a_ * math.tan(math.radians(22.5)); h = z1 - z0
        box(f'BOXVOL_{bn:02d}', (2 * a_, side, h), (0, 0, z0 + h / 2), rot); bn += 1
# BSP: overlapping boxes make the FBX build fail in Workbench ("Build failed") -> non-overlapping convex prisms
octagon_prism('BSP_01', A_I, Z_FLOOR_V, Z_TOP)
for n, (a_, z0, z1) in enumerate(BSP_TIERS, 2): octagon_prism(f'BSP_{n:02d}', a_, z0, z1)
print('volumes done:', [o.name for o in bpy.data.objects if o.name.startswith(('PRTVOL_', 'BOXVOL_', 'BSP_'))])
