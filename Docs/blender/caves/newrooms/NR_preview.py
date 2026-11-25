"""NR_preview: preview renders of a built room (EEVEE, torch light, cave-like warm materials from the build blend).
  blender --factory-startup -b NR_<name>_v5.blend --python NR_preview.py      env: NR_ROOM=hall|swim  NR_PREV_OUT=<folder>  NR_RES=<width>
Writes NR_<room>_*.png.  A translucent water plane (swim room, preview only, never exported) is added with NR_WATER=1.
"""
import os, sys, math
import bpy, bmesh
from mathutils import Vector

ROOM = os.environ.get('NR_ROOM', 'hall')
OUT = os.environ.get('NR_PREV_OUT', os.path.dirname(bpy.data.filepath))
RES = int(os.environ.get('NR_RES', '1100'))
ONLY = os.environ.get('NR_ONLY', '')
sc = bpy.context.scene
lod = next(o for o in bpy.data.objects if o.name.endswith('_LOD0') and o.type == 'MESH')
for o in bpy.data.objects:
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o)
    elif o is not lod:
        o.hide_render = True
        o.hide_viewport = True
lod.hide_render = False
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
sc.render.resolution_x = RES
sc.render.resolution_y = int(RES * 0.64)
try:
    sc.eevee.taa_render_samples = 32
except Exception:
    pass
for vt in ('AgX', 'Filmic', 'Standard'):
    try:
        sc.view_settings.view_transform = vt
        break
    except TypeError:
        continue
w = bpy.data.worlds.new('dark')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.004, 0.005, 0.008, 1)
sc.world = w


def cam(name, loc, tgt, lens=20, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 300
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    o = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def light(name, kind, loc, e, color=(1, 0.8, 0.55), size=0.2):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = e
    ld.color = color
    if kind == 'POINT':
        ld.shadow_soft_size = size
    if kind == 'AREA':
        ld.size = size
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.location = loc
    return o


def shoot(c, name, res=None):
    if ONLY and not any(o in name for o in ONLY.split(',')):
        return
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    else:
        sc.render.resolution_x, sc.render.resolution_y = RES, int(RES * 0.64)
    sc.camera = c
    sc.render.filepath = os.path.join(OUT, 'NR_%s_%s.png' % (ROOM, name))
    bpy.ops.render.render(write_still=True)
    print('rendered', name)


def cut(obj, co, no, name):
    me = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, clear_outer=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def clear_lights():
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            bpy.data.objects.remove(o)


def torch_at(c, e=250):
    clear_lights()
    light('torch', 'POINT', c.location + Vector((0.2, 0.1, 0.1)), e, (1.0, 0.78, 0.52), 0.08)
    light('fill', 'POINT', c.location + Vector((0, 0, 2.5)), 60, (0.5, 0.62, 1.0), 0.4)


def overview(name, cut_z, cam_loc, tgt, lens, e_area=60000, size=40, sun_dir=(55, 0, 25)):
    sec = cut(lod, Vector((0, 0, cut_z)), Vector((0, 0, 1)), name + '_cut')
    lod.hide_render = True
    clear_lights()
    a = light('area', 'AREA', (0, 0, cut_z + 20), e_area, (1.0, 0.92, 0.8), size)
    a.rotation_euler = (math.radians(sun_dir[0]), math.radians(sun_dir[1]), math.radians(sun_dir[2]))
    c = cam('ov', cam_loc, tgt, lens)
    shoot(c, name)
    bpy.data.objects.remove(sec)
    lod.hide_render = False


if ROOM == 'hall':
    sc.render.resolution_y = int(RES * 0.64)
    overview('overview_roofcut_south', 8.2, (13, -50, 30), (-1, -6, 2), 32, 90000, 50, (50, 0, 20))
    overview('overview_roofcut_north', 8.2, (14, 46, 30), (-1, 10, 2), 32, 90000, 50, (50, 0, 160))
    # plan
    sec = cut(lod, Vector((0, 0, 8.2)), Vector((0, 0, 1)), 'plan_cut')
    lod.hide_render = True
    clear_lights()
    a = light('area', 'AREA', (0, 0, 40), 140000, (1.0, 0.92, 0.8), 60)
    c = cam('plan', (0, 0, 90), (0, 0, 0), ortho=74)
    c.rotation_euler = (0, 0, 0)
    shoot(c, 'plan', (560, 1100))
    bpy.data.objects.remove(sec)
    lod.hide_render = False
    # standing at the lower entrance, looking up the hall
    c = cam('in_s', (1.2, -27.4, 1.7), (-2.5, 4.0, 4.5), 17)
    torch_at(c, 700)
    shoot(c, 'inside_lower_entrance')
    # the descent: on the gallery at the top of the cascade, looking down the ramp
    c = cam('ramp_down', (-4.6, 6.4, 7.0), (-4.0, -12.0, 2.4), 20)
    torch_at(c, 900)
    shoot(c, 'descent_from_top')
    # and from the bottom looking up the ramp
    c = cam('ramp_up', (-1.2, -19.5, 1.7), (-4.8, -3.0, 4.8), 20)
    torch_at(c, 900)
    shoot(c, 'descent_from_bottom')
    # the rubble slope from the lower floor
    c = cam('talus_up', (5.0, 7.0, 1.7), (-1.0, 17.0, 5.0), 18)
    torch_at(c, 900)
    shoot(c, 'rubble_slope_from_bottom')
    # on the gallery at the upper entrance, looking south over the hall
    c = cam('gallery', (-4.4, 26.0, 7.1), (0.0, 0.0, 4.0), 17)
    torch_at(c, 900)
    shoot(c, 'inside_upper_entrance')
    # the gallery edge from the lower floor
    c = cam('scarp', (3.0, 10.0, 1.7), (-3.5, 15.0, 6.5), 22)
    torch_at(c, 900)
    shoot(c, 'gallery_scarp_from_floor')
else:
    WL = -1.0
    # swim room
    sec = cut(lod, Vector((0, 0, -3.1)), Vector((0, 0, 1)), 'cut_bore')
    lod.hide_render = True
    clear_lights()
    a = light('area', 'AREA', (0, 0, 30), 60000, (1.0, 0.92, 0.8), 30)
    c = cam('plan', (0, 0, 60), (0, 0, 0), ortho=32)
    c.rotation_euler = (0, 0, 0)
    shoot(c, 'cutaway_bore_plan', (760, 1000))
    c = cam('persp', (9, -16, 8), (0, 0, -3.2), 28)
    a.location = (6, -6, 14)
    a.rotation_euler = (math.radians(35), 0, math.radians(20))
    shoot(c, 'cutaway_bore_persp')
    bpy.data.objects.remove(sec)
    sec = cut(lod, Vector((0, 0, 1.0)), Vector((0, 0, 1)), 'cut_roof')
    clear_lights()
    a = light('area', 'AREA', (0, 0, 30), 70000, (1.0, 0.92, 0.8), 30)
    c = cam('ov', (14, -24, 20), (0, 0, -2), 32)
    shoot(c, 'overview_roofcut')
    bpy.data.objects.remove(sec)
    lod.hide_render = False
    # longitudinal section: cut along x through the bore, camera from the side
    sec = cut(lod, Vector((0.3, 0, 0)), Vector((-1, 0, 0)), 'cut_x')
    lod.hide_render = True
    clear_lights()
    light('area', 'AREA', (-20, 0, 10), 90000, (1.0, 0.92, 0.8), 30).rotation_euler = (0, math.radians(-60), 0)
    c = cam('side', (-34, 0, -1.0), (0.3, 0, -1.0), ortho=34, lens=30)
    shoot(c, 'section_long', (1000, 640))
    bpy.data.objects.remove(sec)
    lod.hide_render = False
    # standing at the entrance
    c = cam('in_s', (0.0, -11.4, 1.7), (0.4, -3.0, -1.5), 17)
    torch_at(c, 600)
    shoot(c, 'entrance_chamber')
    # on the shore, looking down into the pool at the tunnel mouth
    c = cam('mouth', (0.4, -8.6, 0.6), (2.0, -4.6, -3.4), 28)
    torch_at(c, 2500)
    shoot(c, 'tunnel_mouth_from_shore')
    # inside the bore (diver's view): camera in the tunnel looking along it
    B = [(1.5, -4.7, -3.05), (1.2, -3.0, -3.1), (0.5, -1.0, -3.3)]
    c = cam('bore', (2.2, -3.7, -3.35), (1.0, -0.9, -3.8), 40)
    torch_at(c, 1500)
    shoot(c, 'inside_bore_a')
    c = cam('bore2', (-2.0, 3.7, -3.55), (0.1, 0.0, -3.9), 40)
    torch_at(c, 1500)
    shoot(c, 'inside_bore_b')
    # exit chamber from the exit socket
    c = cam('in_n', (-0.6, 11.4, 1.7), (0.0, 4.0, -1.5), 17)
    torch_at(c, 600)
    shoot(c, 'exit_chamber')
    # with a preview water plane at the water level
    if os.environ.get('NR_WATER', '1') == '1':
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=14.0)
        me = bpy.data.meshes.new('wl')
        bm.to_mesh(me)
        wp = bpy.data.objects.new('wl', me)
        sc.collection.objects.link(wp)
        wp.location = (0, 0, WL)
        m = bpy.data.materials.new('wmat')
        m.use_nodes = True
        bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bs.inputs['Base Color'].default_value = (0.02, 0.06, 0.07, 1)
        bs.inputs['Roughness'].default_value = 0.05
        bs.inputs['Alpha'].default_value = 0.6
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
        me.materials.append(m)
        c = cam('wat', (0.0, -11.4, 1.5), (0.4, -3.0, -1.5), 17)
        torch_at(c, 600)
        shoot(c, 'entrance_chamber_with_preview_water')
print('previews done')
