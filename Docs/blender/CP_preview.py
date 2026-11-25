"""Preview renders of the crouch / prone families and transitions (Workbench engine, headless):
blender --factory-startup -b --python Docs/blender/CP_preview.py   ->  Docs/blender/previews/CP_*.png"""
import bpy, bmesh, math, os
from mathutils import Vector

TT_NORUN = True
TT_EXPORT = False
here = os.path.dirname(os.path.abspath(__file__))
exec(compile(open(os.path.join(here, "tunnelkit_build_cp.py"), encoding="utf-8").read(), "tunnelkit_build_cp.py", "exec"))
OUTDIR = os.path.join(here, "previews")
os.makedirs(OUTDIR, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1000, 560
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_backface_culling = False
sh.show_cavity = True
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('CP_w')
world.use_nodes = False
world.color = (0.55, 0.6, 0.65)
scene.world = world


def place(piece, at, cut=None):
    """cut: (plane point, normal, keep side) halves the mesh so the inside can be seen"""
    objs = finish(piece, Vector(at))
    for o in objs:
        if o.name.startswith('UTM_') or o.type == 'EMPTY':
            o.hide_render = True
            o.hide_set(True)
    lod = objs[0]
    if cut:
        co, no = cut
        bm = bmesh.new()
        bm.from_mesh(lod.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co - Vector(at) if False else (Vector(co) - Vector(at)), plane_no=no, clear_outer=True)
        bm.to_mesh(lod.data)
        bm.free()
    return lod


def camera(loc, look_at, ortho=None, lens=24):
    cam = bpy.data.cameras.new('CP_cam')
    cam.clip_start = 0.02
    cam.clip_end = 200
    if ortho:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho
    else:
        cam.lens = lens
    ob = bpy.data.objects.new('CP_cam', cam)
    scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = ob
    return ob


def shot(name):
    scene.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    print('rendered', name)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


# 1. the three profiles side by side, looking down the tunnel from the mouth (the S piece is the standing kit's profile)
clear()
place(build_s_partner(), (-4, 0, 0))
place(build_straight('C', 4), (0, 0, 0))
place(build_straight('P', 4), (4, 0, 0))
camera((0, -13, 1.0), (0, 0, 1.0), ortho=None, lens=32)
shot('CP_profiles_front.png')

# 2. longitudinal sections of the three transitions, side by side (looking from +X, cut at X = 0)
clear()
for i, (a, b) in enumerate((('S', 'C'), ('C', 'P'), ('S', 'P'))):
    place(build_trans(a, b), (0, 4.8 * i, 0), cut=((0, 0, 0), (1, 0, 0)))
camera((12, 6.4, 1.0), (0, 6.4, 1.0), ortho=17)
scene.render.resolution_x, scene.render.resolution_y = 1400, 560
shot('CP_trans_sections.png')
scene.render.resolution_x, scene.render.resolution_y = 1000, 560

# 3. the crouch family in plan (roof cut off), the prone family below
clear()
row = [lambda f: build_straight(f, 4), build_turn, lambda f: build_dogleg(f, 'L'), build_junction, build_end]
for fam, y0 in (('C', 0.0), ('P', -9.0)):
    cursor = 0.0
    for b in row:
        lod = place(b(fam), (0, y0, 0), cut=((0, 0, 1.0 if fam == 'C' else 0.5), (0, 0, 1)))
        xs = [v[0] for v in lod.bound_box]
        dx = cursor - min(xs)
        for o in bpy.data.objects:
            if o.location.y == y0 and getattr(o, '_cp_moved', None) is None and o.location.x == 0 and o.name.startswith(('TT_', 'UTM_', '1', '2', '3')):
                o.location.x += dx
        cursor += max(xs) - min(xs) + 0.8
camera((17, -3, 30), (17, -3, 0), ortho=40)
scene.render.resolution_x, scene.render.resolution_y = 1400, 560
shot('CP_family_plan.png')
scene.render.resolution_x, scene.render.resolution_y = 1000, 560

if os.environ.get('CP_PARTS') == '123':
    raise SystemExit

# 4. inside views: walking along each family's straight, and through the S->P transition from the standing end
for tag, build, at, look in (('C_inside', lambda: build_straight('C', 4), (0, 0.4, 0.9), (0, 4, 0.8)),
                             ('P_inside', lambda: build_straight('P', 4), (0, 0.4, 0.4), (0, 4, 0.45)),
                             ('Trans_S_P_inside', lambda: build_trans('S', 'P'), (0, -2.0, 1.4), (0, 3.0, 0.5))):
    clear()
    place(build(), (0, 0, 0), cut=None)
    camera(at, look, lens=20)
    shot('CP_%s.png' % tag)

# 5. the entries in section (crouch above, prone below)
clear()
place(build_entry('C'), (0, 0, 0), cut=((0, 0, 0), (1, 0, 0)))
place(build_entry('P'), (0, 0, -3.6), cut=((0, 0, 0), (1, 0, 0)))
camera((9, 2.6, -1.0), (0, 2.6, -1.0), ortho=11)
shot('CP_entries_sections.png')
