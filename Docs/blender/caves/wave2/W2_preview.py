"""W2_preview: preview renders of a built wave-2 asset (EEVEE, torch light, the warm cave materials saved in the build blend).
  blender --factory-startup -b W2_<name>_v5.blend --python W2_preview.py     env: W2_ASSET  W2_PREV_OUT=<folder>  W2_RES=<width>
Views: a roof-cut plan, a roof-cut oblique overview, and walking views along the first route (from the first opening, at 1/3 and 2/3 of
the route, and back from the end) at the eye height of the route's mode.  Writes W2_<name>_<view>.png.
"""
import os, sys, math
import bpy, bmesh
from mathutils import Vector

HERE = os.environ.get('W2_DIR', r"c:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Docs\blender\caves\wave2")
sys.path.insert(0, HERE)
import W2_assets as WA

shape, prm = WA.build(os.environ['W2_ASSET'])
NAME = shape.name
OUT = os.environ.get('W2_PREV_OUT', os.path.dirname(bpy.data.filepath))
RES = int(os.environ.get('W2_RES', '1000'))
sc = bpy.context.scene
lod = bpy.data.objects[NAME + '_LOD0']
for o in list(bpy.data.objects):
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
sc.render.resolution_x, sc.render.resolution_y = RES, int(RES * 0.64)


def cam(name, loc, tgt, lens=20, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.04
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


def clear_lights():
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            bpy.data.objects.remove(o)


def shoot(c, name, res=None):
    sc.render.resolution_x, sc.render.resolution_y = res or (RES, int(RES * 0.64))
    sc.camera = c
    sc.render.filepath = os.path.join(OUT, 'W2_%s_%s.png' % (NAME, name))
    bpy.ops.render.render(write_still=True)
    print('rendered', name)


def torch_at(c, e=260):
    clear_lights()
    light('torch', 'POINT', c.location + Vector((0.15, 0.1, 0.1)), e, (1.0, 0.78, 0.52), 0.08)
    light('fill', 'POINT', c.location + Vector((0, 0, 1.8)), 50, (0.5, 0.62, 1.0), 0.4)


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


pts = [Vector((x, y, 0)) for x, y in list(shape.routes.values())[0]['pts']] if shape.routes else []
mode = list(shape.routes.values())[0]['mode'] if shape.routes else 'W'
eye = {'W': 1.65, 'C': 1.2, 'P': 0.45}[mode]
import numpy as np
co = np.array([tuple(v.co) for v in lod.data.vertices])
ctr = Vector(tuple((co.min(axis=0) + co.max(axis=0)) / 2))
ext = Vector(tuple(co.max(axis=0) - co.min(axis=0)))
zc = float(os.environ.get('W2_CUTZ', str(2.0 + max(shape.p.get('open_h', 2.5) - 2.0, 0.0))))
# floor height under a route point: cast a ray on the render mesh
from mathutils.bvhtree import BVHTree
bm0 = bmesh.new()
bm0.from_mesh(lod.data)
tree = BVHTree.FromBMesh(bm0)


def floor_z(x, y, z0=3.0):
    h = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)))
    return h[0].z if h[0] is not None else 0.0


def floor_z_low(x, y):
    return float(shape.floor2d(np.array([x]), np.array([y]))[0])


def floor_z_old(x, y):
    """the first floor found by a ray from just above the lowest air: start at 6 m and take the lowest hit that faces up"""
    best = None
    o = Vector((x, y, co[:, 2].max() + 1))
    for _ in range(10):
        h = tree.ray_cast(o, Vector((0, 0, -1)))
        if h[0] is None:
            break
        if h[1].z > 0.5:
            best = h[0].z
            break
        o = h[0] + Vector((0, 0, -0.01))
    return best if best is not None else 0.0


# 1 plan with the roof cut away
if os.environ.get('W2_NOPLAN') != '1':
    sec = cut(lod, Vector((0, 0, zc)), Vector((0, 0, 1)), 'plan_cut')
    lod.hide_render = True
    clear_lights()
    light('area', 'AREA', (ctr.x, ctr.y, 40), 90000, (1.0, 0.92, 0.8), 40)
    big = max(ext.x, ext.y)
    c = cam('plan', (ctr.x, ctr.y, 60), (ctr.x, ctr.y, 0), ortho=big * 1.08)
    c.rotation_euler = (0, 0, 0)
    shoot(c, 'plan', (RES, RES) if ext.x > 0.6 * ext.y else (int(RES * 0.5), RES))
    # oblique overview
    clear_lights()
    a = light('area', 'AREA', (ctr.x, ctr.y - big * 0.4, 25), 70000, (1.0, 0.9, 0.78), 25)
    a.rotation_euler = (math.radians(30), 0, 0)
    c = cam('ov', (ctr.x + big * 0.5, ctr.y - big * 0.85, big * 0.75), (ctr.x, ctr.y, 0.5), 30)
    shoot(c, 'overview')
    bpy.data.objects.remove(sec)
    lod.hide_render = False

# 2 walking views along the first route
if pts:
    L = len(pts)
    for name, fi, back in (('view_start', 0.0, False), ('view_third', 0.34, False), ('view_twothirds', 0.67, False), ('view_back', 1.0, True)):
        k = min(L - 1, int(fi * (L - 1)))
        p = pts[k]
        # walk the route forward (or back): look ahead ~3.5 m along it
        step = -1 if back else 1
        k2 = k
        acc = 0.0
        while 0 <= k2 + step < L and acc < 3.5:
            acc += (pts[k2 + step] - pts[k2]).length
            k2 += step
        if k2 == k:
            k2 = max(0, min(L - 1, k - step))
        q = pts[k2]
        d = (q - p)
        if d.length < 0.1:
            continue
        d.normalize()
        p0 = p - d * 0.8 if k > 0 and not back else p
        if back:
            p0 = p - d * 0.8
        fz = floor_z_low(p0.x, p0.y)
        loc = Vector((p0.x, p0.y, fz + eye))
        fz2 = floor_z_low(q.x, q.y)
        c = cam('walk', loc, Vector((q.x, q.y, fz2 + eye * 0.9)), 19)
        torch_at(c, 260 if mode == 'W' else 150)
        shoot(c, name)
print('previews done')
