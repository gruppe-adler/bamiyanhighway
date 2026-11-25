"""Preview renders of the redesigned TT pieces (Workbench engine, headless; builds the pieces itself from tunnelkit_build_clear.py):
blender --factory-startup -b --python Docs/blender/CL_preview.py   ->  Docs/blender/previews/CL_*.png"""
import bpy, bmesh, math, os
from mathutils import Vector

CL_NORUN = True
here = os.path.dirname(os.path.abspath(__file__))
exec(compile(open(os.path.join(here, "tunnelkit_build_clear.py"), encoding="utf-8").read(), "tunnelkit_build_clear.py", "exec"))
OUTDIR = os.path.join(here, "previews")
os.makedirs(OUTDIR, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1000, 600
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_backface_culling = False
sh.show_cavity = True
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('CL_w')
world.use_nodes = False
world.color = (0.55, 0.6, 0.65)
scene.world = world
EARTH = (0.62, 0.48, 0.34, 1)
GROUND = (0.35, 0.5, 0.25, 1)


def place(piece, at, cut=None):
    """cut: (plane point, normal): the part on the normal's side is removed so the inside can be seen"""
    objs = finish(piece, Vector(at))
    for o in objs:
        if o.name.startswith('UTM_') or o.type == 'EMPTY':
            o.hide_render = True
            o.hide_set(True)
    lod = objs[0]
    lod.data.materials[0].diffuse_color = EARTH
    lod.data.materials[1].diffuse_color = GROUND
    if cut:
        co, no = cut
        bm = bmesh.new()
        bm.from_mesh(lod.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=Vector(co) - Vector(at), plane_no=no, clear_outer=True)
        bm.to_mesh(lod.data)
        bm.free()
    return lod


def camera(loc, look_at, ortho=None, lens=24):
    cam = bpy.data.cameras.new('CL_cam')
    cam.clip_start = 0.02
    cam.clip_end = 200
    if ortho:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho
    else:
        cam.lens = lens
    ob = bpy.data.objects.new('CL_cam', cam)
    scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = ob
    return ob


def shot(name, size=None):
    if size:
        scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    print('rendered', name, flush=True)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


# 1. plan view, cut at 1.0 m: the chain A, standard, C, A (the ring at every joint, the neck and the bulge between)
clear()
chain = [build_straight(4, 'S', 'A'), build_straight(4, 'S', ''), build_straight(4, 'S', 'C'), build_straight(4, 'S', 'A')]
for i, pc in enumerate(chain):
    place(pc, (0, 4.0 * i, 0), cut=((0, 0, 1.0), (0, 0, 1)))
camera((0, 8, 30), (0, 8, 0), ortho=19)
shot('CL_plan_chain_A_std_C_A.png', (700, 1000))

# 2. cross sections: rings and the middle of each variant, cut across the middle, seen from the open end
clear()
for i, var in enumerate(('A', '', 'C')):
    pc = build_straight(4, 'S', var)
    place(pc, (i * 4.5, 0, 0), cut=((0, 2.0, 0), (0, 1, 0)))
for i, cls in enumerate(('C', 'P')):
    pc = build_straight(4, cls)
    place(pc, (13.5 + i * 3.2, 0, 0), cut=((0, 2.0, 0), (0, 1, 0)))
camera((7.5, 14, 1.5), (7.5, 2.0, 1.5), ortho=20)
shot('CL_sections_A_std_C_crouch_prone.png', (1200, 520))

# 3. inside, at a joint of two copies (standing), eye height 1.6 m, looking along the tunnel
clear()
a = build_straight(4, 'S', '')
b = build_straight(4, 'S', 'C')
place(a, (0, 0, 0))
place(b, (0, 4, 0))
camera((0, 1.2, 1.6), (0, 10, 1.3), lens=20)
shot('CL_inside_joint_std_to_C.png')
camera((0, 5.2, 1.6), (0, -4, 1.3), lens=20)       # the other way: from the wide one into the standard
shot('CL_inside_joint_C_to_std.png')

# 4. the neck: from the ring looking into A (one player wide)
clear()
a = build_straight(4, 'S', 'A')
place(a, (0, 0, 0))
place(build_straight(4, 'S', ''), (0, 4, 0))
camera((0, -1.2, 1.6), (0, 6, 1.2), lens=20)
shot('CL_inside_neck_A.png')

# 5. the floor-wall fillet, low and close
camera((0.5, 1.0, 0.45), (-0.8, 2.6, 0.15), lens=28)
shot('CL_fillet_closeup.png')

# 6. turn (plan, cut at 1.0 m) and the junction
clear()
t = build_turn()
place(t, (0, 0, 0), cut=((0, 0, 1.0), (0, 0, 1)))
place(build_straight(4, 'S', ''), (0, -4, 0), cut=((0, 0, 1.0), (0, 0, 1)))
camera((1.8, 0.5, 14), (1.8, 0.5, 0), ortho=12)
shot('CL_plan_turn90.png', (900, 700))
clear()
j = build_junction()
place(j, (0, 0, 0), cut=((0, 0, 1.0), (0, 0, 1)))
camera((0, 0, 14), (0, 0, 0), ortho=10)
shot('CL_plan_junction.png', (800, 800))
clear()
j = build_junction()
place(j, (0, 0, 0))
camera((0, -2.2, 1.6), (0.2, 1.0, 1.2), lens=18)       # standing in the south door, looking in
shot('CL_inside_junction_from_door.png')

# 7. crouch and prone straights, inside
for cls, eye in (('C', 1.0), ('P', 0.5)):
    clear()
    place(build_straight(4, cls), (0, 0, 0))
    camera((0, 0.3, eye), (0, 6, eye * 0.85), lens=20)
    shot('CL_inside_%s_straight.png' % ('crouch' if cls == 'C' else 'prone'))

# 8. phase 2 pieces: the staggered junctions (plan, cut at 0.8 m), the room, the entries, transitions, wide turn / dogleg
def plan(name, pieces, centre, ortho, size=(900, 900), z=0.8):
    clear()
    for pc, at in pieces:
        place(pc, at, cut=((0, 0, z), (0, 0, 1)))
    camera((centre[0], centre[1], 30), (centre[0], centre[1], 0), ortho=ortho)
    shot(name, size)


plan('CL_plan_junction_staggered.png', [(build_junction(), (0, 0, 0))], (0, 0), 11)
plan('CL_plan_junction_crouch_prone.png', [(build_junction('C'), (0, 0, 0)), (build_junction('P'), (9, 0, 0))], (4.5, 0), 15, (1200, 700), 0.6)
plan('CL_plan_room.png', [(build_room(), (0, 0, 0))], (0, 0), 14)
plan('CL_plan_turn90_C.png', [(build_turn('S', 'C'), (0, 0, 0)), (build_turn('S', ''), (9, 0, 0)), (build_turn('S', 'A'), (16, 0, 0))], (8, 1), 20, (1300, 600))
plan('CL_plan_dogleg_C.png', [(build_dogleg('L', 'S', 'C'), (0, 0, 0)), (build_dogleg('R', 'S', 'A'), (9, 0, 0))], (1.5, 3.5), 14, (900, 800))
plan('CL_plan_turn90_Wide.png', [(build_turn_wide(), (0, 0, 0))], (1.5, 1.5), 9, (800, 800))

clear()
inc = build_entry_incline()
place(inc, (0, 0, 0), cut=((0, 0, 0), (1, 0, 0)))
camera((14, -1.0, -1.5), (0, -1.0, -1.5), ortho=11)
shot('CL_section_entry_incline.png', (1100, 800))
clear()
place(build_entry_horizontal(), (0, 0, 0))
camera((0, -1.5, 1.6), (0, 6, 1.3), lens=18)
shot('CL_inside_entry_horizontal_mouth.png')
clear()
for i, (a_, b_) in enumerate((('S', 'C'), ('C', 'P'), ('S', 'P'))):
    place(build_trans(a_, b_), (0, i * 4.0, 0), cut=((0, 0, 0), (1, 0, 0)))
camera((14, 5.5, 1.2), (0, 5.5, 1.2), ortho=14)
shot('CL_section_transitions.png', (1300, 500))
clear()
place(build_straight(4, 'S', 'C'), (0, 0, 0))
place(build_straight(4, 'S', 'A'), (0, 4, 0))
camera((0, -1.2, 1.6), (0, 7, 1.3), lens=18)
shot('CL_inside_wide_C_into_neck_A.png')
print('done')
