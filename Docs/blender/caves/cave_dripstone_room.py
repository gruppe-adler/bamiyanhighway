"""PROTOTYPE (not for the addon): one dripstone-cave room for the TT tunnel kit, with seeded stalactites, stalagmites,
columns, soda straws, rimstone pools, and a baked "thickness -> emissive" atlas that fakes calcite glowing from behind.

Run headless (always --factory-startup):
  blender.exe --factory-startup -b --python cave_dripstone_room.py
Environment switches:
  CAVE_VARIANT = A | B | C | D        which room (parameter set + seed), default A
  CAVE_MODE    = room | library       'library' = the prefab-able single formations in a row
  CAVE_OUT     = output folder        default: folder of this script
  CAVE_RENDER  = 1 | 0                EEVEE preview PNGs
  CAVE_FBX     = 1 | 0                also export <Name>.fbx (LOD0 + UTM_ + empties 1,2,3) into CAVE_OUT
  TT_KIT       = path of tunnelkit_build.py (read only; its helpers are exec'd, nothing there is changed)

Re-uses the kit's own helpers (INNER profile, sweep/prism/joint, finish() = split_inside + UVs + 'Col' + smoothing,
keep_exact fade), so the openings are the same standard profile and the mesh comes out in the kit's three materials plus
one new slot (TT_CalciteGlow).
Blender space like the kit: X right, Y forward, Z up, floor at Z 0, openings axis-aligned (S/N = -Y/+Y, W/E = -X/+X).
"""
import bpy, bmesh, math, os, sys, json, random, time
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()
KIT = os.environ.get('TT_KIT', r"c:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Docs\blender\tunnelkit_build.py")
OUTDIR = os.environ.get('CAVE_OUT', HERE)
VARIANT = os.environ.get('CAVE_VARIANT', 'A')
MODE = os.environ.get('CAVE_MODE', 'room')
RENDER = os.environ.get('CAVE_RENDER', '1') == '1'
FBX = os.environ.get('CAVE_FBX', '0') == '1'
RES = int(os.environ.get('CAVE_RES', '960'))
os.makedirs(OUTDIR, exist_ok=True)
for _o in list(bpy.data.objects):          # factory startup scene: default cube, light, camera
    bpy.data.objects.remove(_o)

# ---- the kit's helpers, exec'd into this namespace (everything above its BUILDERS list) -----------------------------
TT_EXPORT = False
_src = open(KIT, encoding='utf-8').read().split("BUILDERS = [")[0]
exec(compile(_src, KIT, 'exec'), globals())

REFINE = 0.5            # the voxel remesh already gives ~0.3 m quads; refine() only splits what is longer than this
MAT_GLOW = 3            # final mesh slot of TT_CalciteGlow (slot 3 is only the build-time MAT_HIDDEN, gone after finish())
EMBED = 0.25            # how far a formation's root sits inside the rock
GLOW_L = 0.16           # metres of calcite the light gets through (guess; tune against the held exposure)
ATLAS_W, ATLAS_H = 512, 1024
TILE_W, TILE_H = 64, 128                       # one formation = one tile (u around the axis, v along it, tip at v = 1)
COLS, ROWS = ATLAS_W // TILE_W, ATLAS_H // TILE_H

# ---------------------------------------------------------------------------------------------------------------------
# Room parameter sets: ONE generator, four rooms. Everything random comes from `seed`.
VARIANTS = {
    # tall cathedral: big dome, a few fat columns, long stalactites, two big rimstone pools
    'A': dict(label='Cathedral', seed=11, rx=4.6, ry=3.9, h=5.4, depth=1.5, p=2.7, wobble=0.10,
              openings=[('S', -1.0), ('E', 0.6), ('N', 1.2)],
              pools=2, pool_r=(1.1, 1.7), pool_depth=(0.28, 0.45), lip=(0.08, 0.14), talus=0.30, relief=0.08,
              ribs=0.07, wall_amp=0.17, stalactites=12, stalagmites=6, columns=3, pairs=3, straws=3, len_st=(0.6, 2.6)),
    # low, wide crawl-hall: ceiling just above head height, very many short stalactites and straws, no deep water
    'B': dict(label='LowHall', seed=23, rx=5.4, ry=4.3, h=3.9, depth=1.5, p=4.0, wobble=0.06,
              openings=[('W', 0.8), ('E', -0.9), ('N', 0.4)],
              pools=1, pool_r=(0.9, 1.3), pool_depth=(0.2, 0.3), lip=(0.06, 0.1), talus=0.22, relief=0.06,
              ribs=0.05, wall_amp=0.13, stalactites=26, stalagmites=9, columns=2, pairs=4, straws=7, len_st=(0.3, 1.2)),
    # terraced rimstone hall: gour pools stepping across the floor, few formations
    'C': dict(label='Terraces', seed=37, rx=5.0, ry=4.2, h=4.4, depth=1.5, p=3.2, wobble=0.08,
              openings=[('S', 0.9), ('N', -0.8), ('W', 0.5)],
              pools=5, pool_r=(0.9, 1.5), pool_depth=(0.25, 0.5), lip=(0.1, 0.18), talus=0.35, relief=0.10,
              ribs=0.05, wall_amp=0.15, stalactites=10, stalagmites=4, columns=1, pairs=2, straws=3, len_st=(0.5, 1.8)),
    # curtain hall: narrow tall chimney, deep flowstone ribbing on the walls, thick stalagmites and columns
    'D': dict(label='Curtains', seed=51, rx=3.5, ry=3.2, h=7.6, depth=1.5, p=2.6, wobble=0.12,
              openings=[('S', 0.0), ('E', -0.5)],
              pools=1, pool_r=(0.9, 1.2), pool_depth=(0.2, 0.3), lip=(0.07, 0.12), talus=0.28, relief=0.07,
              ribs=0.18, wall_amp=0.17, col_clear=1.9, stalactites=9, stalagmites=7, columns=4, pairs=2, straws=4, len_st=(0.7, 3.4)),
    # a low chamber you can only cross prone: wider than one person, ceiling tilted (0.8 m at one side, 1.7 at the other), floor rising
    # 4 degrees; both openings are standing-size, each with a neck (the ceiling comes down from 2.3 m in 0.3 m per metre)
    'F': dict(label='CrawlSlab', asset='TT_Cave_Room_CrawlSlab', seed=89, rx=5.2, ry=4.6, h=1.5, depth=1.0, p=2.3, sink=0.5, wobble=0.04, slope=0.07, voxel=0.12,
              openings=[('S', -1.6), ('E', 2.0)], neck=4.6, ceil_tilt=(0.0, -0.16), ceil_var=0.2, asym=0.8, alcoves=4, pockets=2, drops=0,
              up_cap=0.2, side_cap=0.3, lopside=0.14, ico=5, vault=0.12, bank=0.2, swell=0.1,
              pools=0, pool_r=(1.0, 1.4), pool_depth=(0.2, 0.3), lip=(0.06, 0.1), talus=0.15, relief=0.05,
              ribs=0.04, wall_amp=0.08, stalactites=4, stalagmites=1, columns=0, pairs=0, straws=0, len_st=(0.06, 0.2)),
    # the everyday connector: a narrow winding passage, standing height, 18 m long, with waists and a few formations
    'G': dict(label='Meander', asset='TT_Cave_Pass_Meander', seed=97, rx=2.3, ry=9.5, h=3.3, depth=1.2, p=2.8, wobble=0.07, voxel=0.12,
              openings=[('S', 0.0), ('N', 0.0)], meander=2.4, pinches=3, asym=0.8, alcoves=6, pockets=3, drops=2, ico=5,
              ceil_var=0.3, up_cap=0.4, side_cap=0.35, lopside=0.2,
              pools=0, pool_r=(0.8, 1.1), pool_depth=(0.2, 0.3), lip=(0.06, 0.1), talus=0.25, relief=0.08,
              ribs=0.08, wall_amp=0.16, stalactites=14, stalagmites=5, columns=1, pairs=3, straws=0, len_st=(0.15, 1.1)),
    # a jewel grotto: a small round dead-end chamber, one opening, crowded with formations
    'H': dict(label='Grotto', asset='TT_Cave_Room_Grotto', seed=101, rx=3.3, ry=3.0, h=3.8, depth=1.3, p=2.6, wobble=0.1, voxel=0.12,
              openings=[('S', 0.0)], asym=0.8, alcoves=4, pockets=3, drops=2, ico=5, ceil_var=0.3,
              pools=2, pool_r=(0.6, 0.9), pool_depth=(0.15, 0.25), lip=(0.05, 0.09), talus=0.3, relief=0.08,
              ribs=0.1, wall_amp=0.15, stalactites=22, stalagmites=12, columns=3, pairs=5, straws=0, len_st=(0.15, 1.4)),
    # a junction round a rock island: four ways in, a ring passage round a column of rock (a loop to walk)
    'I': dict(label='Island', asset='TT_Cave_Jct_Island', seed=113, rx=7.6, ry=7.6, h=4.8, depth=1.4, p=2.5, wobble=0.08, voxel=0.14,
              openings=[('S', 0.0), ('N', 0.0), ('E', 0.0), ('W', 0.0)], island=(0.2, -0.1, 3.0, 3.5), probe_from=4.6,
              asym=0.8, alcoves=6, pockets=3, drops=2, ico=5, ceil_var=0.25, up_cap=0.4, side_cap=0.3, lopside=0.14,
              pools=1, pool_r=(0.9, 1.3), pool_depth=(0.2, 0.3), lip=(0.06, 0.1), talus=0.3, relief=0.08,
              ribs=0.1, wall_amp=0.17, stalactites=26, stalagmites=8, columns=2, pairs=4, straws=0, len_st=(0.2, 1.8)),
    # a cathedral 100 m long and 20 m wide, floor rising 5 m over its length, openings at both ends and on the sides
    'E': dict(label='Cathedral100', seed=73, rx=8.0, ry=41.0, h=9.0, depth=1.5, p=3.2, wobble=0.07, slope=0.05, voxel=0.3,
              openings=[('S', 0.0), ('N', 0.0), ('E', -22.0), ('E', 24.0), ('W', 8.0)],
              pools=4, pool_r=(2.0, 3.5), pool_depth=(0.3, 0.6), lip=(0.1, 0.18), talus=0.5, relief=0.12,
              ribs=0.15, wall_amp=0.25, stalactites=140, stalagmites=45, columns=14, pairs=22, straws=0, len_st=(0.6, 3.5),
              asym=0.85, alcoves=18, pockets=10, drops=7, ceil_var=0.35, vault=1.4, bank=0.9, swell=0.4, ico=6, side_cap=0.3, up_cap=0.4, lopside=0.14, pinches=7, meander=3.2),
}
P = dict(VARIANTS[VARIANT])
P['name'] = P.get('asset') or ('TT_Room_Drip_' + VARIANT)
P['_off'] = Vector((random.Random(P['seed']).uniform(-90, 90), random.Random(P['seed'] + 1).uniform(-90, 90),
                    random.Random(P['seed'] + 2).uniform(-90, 90)))

SIDE = {'S': (Vector((0, -1, 0)), Vector((1, 0, 0))), 'N': (Vector((0, 1, 0)), Vector((1, 0, 0))),
        'E': (Vector((1, 0, 0)), Vector((0, 1, 0))), 'W': (Vector((-1, 0, 0)), Vector((0, 1, 0)))}


def clamp01(x):
    return min(max(x, 0.0), 1.0)


# ---------------------------------------------------------------------------------------------------------------------
# 1. The air volume: a superellipsoid blob (steep walls, domed roof, flat floor), voxel-remeshed to a uniform quad mesh

def build_void_low(P):
    bm = bmesh.new()
    ico = P.get('ico', 3)               # a long hall needs a finer base: the shapes must be wider than its point spacing
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=ico, radius=1.0)
    except TypeError:
        bmesh.ops.create_icosphere(bm, subdivisions=ico, diameter=1.0)
    o1, o2 = P['_off'], P['_off'] * 0.37 + Vector((7.1, 3.3, 1.9))
    o3, o4 = P['_off'] * 0.61 + Vector((3.7, 9.1, 2.3)), P['_off'] * 0.83 + Vector((11.3, 1.7, 6.1))
    asym = P.get('asym', 0.7)
    rg = random.Random(P['seed'] * 3 + 5)

    def blob(az, el, w, amp):
        ex = math.sqrt(max(0.0, 1 - el * el))
        return (Vector((ex * math.cos(az), ex * math.sin(az), el)), w, amp)

    # side alcoves and lobes (low on the walls) and pockets up into the ceiling, all at random places and sizes
    alcoves = [blob(rg.uniform(0, 2 * math.pi), rg.uniform(0.02, 0.4), rg.uniform(0.22, 0.6), rg.uniform(0.15, 0.42) * (0.4 + asym))
               for _ in range(P.get('alcoves', 6))]
    pockets = [blob(rg.uniform(0, 2 * math.pi), rg.uniform(0.55, 0.95), rg.uniform(0.2, 0.5), rg.uniform(0.18, 0.5) * (0.4 + asym))
               for _ in range(P.get('pockets', 4))]
    drops = [blob(rg.uniform(0, 2 * math.pi), rg.uniform(0.5, 0.9), rg.uniform(0.2, 0.4), -rg.uniform(0.12, 0.3) * (0.4 + asym))
             for _ in range(P.get('drops', 3))]
    for v in bm.verts:
        d = v.co.normalized()
        cz = P['h'] if d.z > 0 else P['depth']
        if d.z > 0:
            cz *= 1 + P.get('ceil_var', 0.3) * asym * noise.noise(d * 1.2 + o3)
            up = 0.0
            down = 0.0
            for (pv, w, amp) in pockets:
                up += max(0.0, amp) * math.exp(-(math.acos(max(-1.0, min(1.0, d.dot(pv)))) / w) ** 2)
            for (pv, w, amp) in drops:
                down += max(0.0, -amp) * math.exp(-(math.acos(max(-1.0, min(1.0, d.dot(pv)))) / w) ** 2)
            cz *= (1 + min(up, P.get('up_cap', 0.55))) * (1 - min(down, 0.3))       # bumps add up, and are capped (they used to multiply)
        k = (abs(d.x / P['rx']) ** P['p'] + abs(d.y / P['ry']) ** P['p'] + abs(d.z / cz) ** P['p']) ** (-1.0 / P['p'])
        side = 0.0
        for (pv, w, amp) in alcoves:
            side += amp * math.exp(-(math.acos(max(-1.0, min(1.0, d.dot(pv)))) / w) ** 2)
        k *= 1 + min(side, P.get('side_cap', 0.5))
        k *= 1 + P.get('lopside', 0.22) * asym * noise.noise(d * 0.9 + o4)
        big = noise.noise(d * 1.3 + o1)
        mid = noise.noise(d * 3.1 + o2)
        v.co = d * (k * (1 + P['wobble'] * (0.7 * big + 0.3 * mid)))
    # one-sided pinches (the wall comes in on ONE side over a stretch: a waist, never on both sides at once) and a gentle
    # meander of the whole axis; both fade out at the ends, and pinches keep away from side openings on their own side
    pinches = []
    for i in range(P.get('pinches', 0)):
        for _try in range(80):
            side = 1 if rg.random() < 0.5 else -1
            yc = rg.uniform(-0.62, 0.62) * P['ry']
            ln = rg.uniform(0.12, 0.28) * P['ry']
            if any(so in ('E', 'W') and (1 if so == 'E' else -1) == side and abs(al - yc) < ln * 2.2 for so, al in P['openings']):
                continue
            if any(s2 == side and abs(y2 - yc) < 1.25 * (l2 + ln) for (s2, y2, l2, f2) in pinches):
                continue                                            # no two on one side close together (that is a canyon)
            pinches.append((side, yc, ln, rg.uniform(0.4, 0.6)))
            break
    amp = P.get('meander', 0.0)
    ph = rg.uniform(0, 2 * math.pi)
    if pinches or amp:
        for v in bm.verts:
            x, y = v.co.x, v.co.y
            red = 0.0
            for (side, yc, ln, frac) in pinches:
                if x * side > 0:
                    red += frac * math.exp(-((y - yc) / ln) ** 2)
            x *= 1 - min(red, 0.6)                                  # at most 60 percent narrower, however many overlap
            if amp:
                env = max(0.0, math.sin(math.pi * (y + P['ry']) / (2 * P['ry']))) if abs(y) < P['ry'] else 0.0
                x += amp * env * math.sin(2 * math.pi * 1.3 * (y / (2 * P['ry'])) + ph)
            v.co.x = x
    P['_pinches'] = pinches
    tilt = P.get('ceil_tilt')
    if tilt:                             # the ceiling tilted across the room (a fraction of its height per room half-width)
        for v in bm.verts:
            if v.co.z > 0:
                f = 1 + tilt[0] * v.co.x / P['rx'] + tilt[1] * v.co.y / P['ry']
                v.co.z *= max(0.45, f)
    if P.get('sink'):                    # the whole blob sunk: the floor cuts it below its equator, so the walls slope in like a lens
        for v in bm.verts:
            v.co.z -= P['sink']
    for v in bm.verts:
        v.co.z = max(v.co.z, 0.0)        # the flat floor, exactly at the kit's Z 0
    s_ = P.get('slope', 0.0)
    if s_:
        for v in bm.verts:               # a floor rising along Y (the openings follow it; the sections stay upright)
            v.co.z += s_ * v.co.y
    if P.get('neck'):
        add_necks(bm, P)
    return bm


def add_necks(bm, P):
    """At every opening a standing-height passage (wider than the kit's door) whose roof comes down towards the room in
    NECK_SLOPE metres per metre until it meets the chamber's own ceiling: a closed wedge added to the void before the
    remesh (the voxel remesh unions it with the room). The ceiling over the wedge is never lower than the room's ceiling."""
    L = P['neck']
    s_ = P.get('slope', 0.0)
    for side, along in P['openings']:
        out, lat = SIDE[side]
        r_out = (P['ry'] if side in ('S', 'N') else P['rx']) + 0.8          # starts outside the room, inside the shell
        w = 0.9
        top0 = 2.35
        ring = []
        for t_ in (0.0, 1.5, L):
            pos_c = lat * along + out * (r_out - t_)
            # the wedge's roof: from top0 at the mouth, sinking 0.3 m per metre but never under 0.55 m
            zt = max(1.05, top0 - 0.3 * t_)
            row = []
            for u, z in ((-w, 0.0), (w, 0.0), (w, zt), (-w, zt)):
                pp = pos_c + lat * u
                pp.z = z + s_ * pp.y
                row.append(bm.verts.new(pp))
            ring.append(row)
        for i in range(len(ring) - 1):
            r0, r1 = ring[i], ring[i + 1]
            for k in range(4):
                bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
        bm.faces.new(ring[0][::-1])
        bm.faces.new(ring[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def cut_island(V2, P):
    """A column of rock from floor to ceiling (an irregular, slightly waisted ellipse) cut out of the void: the room becomes a ring"""
    ix, iy, rx_, ry_ = P['island']
    g = bmesh.new()
    bmesh.ops.create_cone(g, cap_ends=True, cap_tris=False, segments=40, radius1=1.0, radius2=1.0, depth=P['h'] * 3.0)
    rg = random.Random(P['seed'] + 17)
    ph = rg.uniform(0, 6.28)
    for v in g.verts:
        a = math.atan2(v.co.y, v.co.x)
        k = 1 + 0.18 * math.sin(2 * a + ph) + 0.12 * math.sin(3 * a + 2 * ph) + 0.06 * math.sin(5 * a)
        waist = 1 - 0.10 * math.cos(v.co.z / (P['h'] * 1.5) * math.pi * 1.4) ** 2
        v.co.x = ix + v.co.x * rx_ * k * waist
        v.co.y = iy + v.co.y * ry_ * k * waist
        v.co.z = v.co.z + P['h'] * 0.5
    bmesh.ops.triangulate(g, faces=g.faces[:])
    ob_v = to_object(V2, P['name'] + '_tmp_v')
    ob_i = to_object(g, P['name'] + '_tmp_island')
    m = ob_v.modifiers.new('isl', 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.solver = 'EXACT'
    m.object = ob_i
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob_v.evaluated_get(dg))
    bpy.data.objects.remove(ob_i)
    bpy.data.objects.remove(ob_v)
    out = bmesh.new()
    out.from_mesh(me)
    bpy.data.meshes.remove(me)
    return out


def remesh(bm_low, voxel=0.3):
    """Uniform quads from the coarse blob (floor included), via the Remesh modifier (voxel mode)"""
    me = bpy.data.meshes.new('void_low')
    bm_low.to_mesh(me)
    ob = bpy.data.objects.new('void_low', me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new('remesh', 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = voxel
    m.adaptivity = 0.0
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bm = bmesh.new()
    bm.from_mesh(me2)
    bpy.data.meshes.remove(me2)
    return bm


def outer_from(bm_low, P, shell_wall=0.9, shell_floor=1.5):
    """The solid's outside: the coarse blob pushed out along its normals (floor thicker, for the pools)"""
    S = bm_low.copy()
    S.normal_update()
    moves = []
    for v in S.verts:
        n = v.normal.copy()
        t = shell_wall + (shell_floor - shell_wall) * max(0.0, -n.z)
        moves.append((v, n * t))
    for v, d in moves:
        v.co += d
    return S


# ---------------------------------------------------------------------------------------------------------------------
# 2. Openings: standard INNER profile, axis-aligned, stub reaches the piece's bounding box so the catalog's OutwardOf
#    (nearest bbox face among the four axis directions) resolves to this opening's direction

def probe_opening(tree, side, along):
    out, lat = SIDE[side]
    s_ = P.get('slope', 0.0)
    d_ = (out + Vector((0, 0, s_ * out.y))).normalized()       # rays follow the sloped floor
    dists = []
    for dx in (-0.7, 0.0, 0.7):
        for z in (0.2, 1.0, 1.9):
            o = lat * (along + dx) + out * P.get('probe_from', 0.0)
            o = o + Vector((0, 0, z + s_ * o.y))
            hit = tree.ray_cast(o, d_)
            if hit[0] is not None:
                dists.append(hit[3] + P.get('probe_from', 0.0))
    return min(dists), max(dists)


def build_room(P):
    t0 = time.time()
    piece = Piece(P['name'])
    piece.frames = False                 # a cave has no timber (the dug tunnel's own frame at the joint stays)
    low = build_void_low(P)
    V2 = remesh(low, P.get('voxel', 0.36))
    if P.get('island'):
        V2 = cut_island(V2, P)
    if P.get('neck'):
        # the low blob is not one clean solid any more (the necks overlap the room): push the remeshed union out instead
        S = outer_from(V2, P, 1.1, 1.5)
        for _ in range(3):
            bmesh.ops.smooth_vert(S, verts=S.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    else:
        S = outer_from(low, P)
    tree = BVHTree.FromBMesh(V2)
    ob_s = to_object(S, P['name'] + '_tmp_outer')
    union = V2.copy() if P.get('neck') else None         # necked rooms: void and holes are ONE cutter (the holes sit inside the void; sequential cuts broke the shell)
    ob_v = to_object(V2.copy(), P['name'] + '_tmp_void')
    cutters = [ob_v] if union is None else []
    stubs, opens = [], []
    bbox = {}
    collar = bmesh.new() if not P.get('neck') else None        # rock round each opening (see below)
    for side, along in P['openings']:
        out, lat = SIDE[side]
        far = max(v.co.dot(out) for v in ob_s.data.vertices)
        if P.get('neck'):
            # a low room: the probe rays would start inside the rock. The neck's mouth is a flat wall at a known distance
            wmin = wmax = (P['ry'] if side in ('S', 'N') else P['rx']) + 0.8
        else:
            wmin, wmax = probe_opening(tree, side, along)
        base = lat * along + out * wmin
        z0 = P.get('slope', 0.0) * base.y                       # the floor height where this opening meets the wall
        base.z = z0
        start = lat * along + out * (wmax + 0.55)
        end = lat * along + out * max(far + 0.35, wmax + 1.4)
        start.z = z0
        end.z = z0
        hole = bmesh.new() if union is None else union
        hole_end = lat * along + out * (wmax + 2.2)
        hole_end.z = z0
        prism(hole, [(base - out * 0.3, out), (hole_end, out)], offset(INNER, 0.001))
        if union is None:
            cutters.append(to_object(hole, P['name'] + '_tmp_hole'))
        if collar is not None:
            # A solid tube of (almost) the sleeve's outer profile from behind the room's wall out past the sleeve's start cap, unioned into
            # the rock BEFORE the cuts (the void cut trims what lies inside the room). Without it the rock skin can end before the sleeve
            # starts and there is a see-through slot between them (0.3-0.6 m, measured with ray scans in the Island and Drip rooms).
            prism(collar, [(base - out * 0.3, out), (start + out * 0.3, out)], offset(OUTER, -0.05))
        stubs.append((start, end, out))
        opens.append(dict(side=side, base=base, out=out, lat=lat, wmin=wmin, wmax=wmax, end=end))
        # headroom where the tunnel meets the wall
        up = tree.ray_cast(base - out * 0.3 + Vector((0, 0, 0.3)), Vector((0, 0, 1)))
        if up[0] is not None and up[3] < 2.3 and not P.get('neck'):
            print('WARNING: low ceiling (%.2f m) at opening %s' % (up[3], side))
    if union is not None:
        cutters.append(to_object(union, P['name'] + '_tmp_cut'))
    ob_collar = None
    if collar is not None and len(collar.faces):
        ob_collar = to_object(collar, P['name'] + '_tmp_collar')
        m = ob_s.modifiers.new('collar', 'BOOLEAN')
        m.operation = 'UNION'
        m.solver = 'EXACT'
        m.object = ob_collar
    for c in cutters:
        m = ob_s.modifiers.new('cut', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = c
        if union is not None:
            m.use_self = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob_s.evaluated_get(dg))
    for c in cutters + ([ob_collar] if ob_collar else []):
        bpy.data.objects.remove(c)
    bpy.data.objects.remove(ob_s)
    piece.bm.from_mesh(me)
    print('shell after boolean: %d faces, volume %.1f (void %.1f)' % (len(piece.bm.faces), piece.bm.calc_volume(), V2.calc_volume()))
    bpy.data.meshes.remove(me)
    for a, b, out in stubs:
        sweep(piece.bm, [(a, out), (b, out)], INNER, OUTER, closed=True, mat=0)
        piece.socket(b, out)
    P['_open'] = opens
    P['_paths'] = [Vector((o['base'].x, o['base'].y, 0)) for o in opens]
    plan_pools(P, V2)
    print('shell built in %.1f s' % (time.time() - t0))
    return piece, V2


# ---------------------------------------------------------------------------------------------------------------------
# 3. Fine shaping inside the kit's finish(): floor field (pools with rimstone lips, talus, relief) and flowstone ribs.
#    Replaces the kit's roughen(); the openings stay exact through the kit's keep_exact() fade.

def seg_dist(p, a, b):
    ab = b - a
    t = clamp01((p - a).dot(ab) / max(ab.dot(ab), 1e-9))
    return (p - (a + ab * t)).length


def path_dist(x, y):
    p = Vector((x, y, 0))
    return min(seg_dist(p, Vector((0, 0, 0)), q) for q in P['_paths'])


def plan_pools(P, V2):
    rng = random.Random(P['seed'] * 5 + 1)
    basins = []
    tries = 0
    while len(basins) < P['pools'] and tries < 400:
        tries += 1
        a = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.72
        x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
        r = rng.uniform(*P['pool_r'])
        ar = rng.uniform(0.7, 1.0)
        if path_dist(x, y) < r + 0.7:
            continue
        if any(math.hypot(x - b['x'], y - b['y']) < r + b['r'] + 0.5 for b in basins):
            continue
        basins.append(dict(x=x, y=y, r=r, ar=ar, rot=rng.uniform(0, math.pi), depth=rng.uniform(*P['pool_depth']),
                           lip=rng.uniform(*P['lip'])))
    P['_basins'] = basins


def basin_z(b, x, y):
    dx, dy = x - b['x'], y - b['y']
    c, s = math.cos(b['rot']), math.sin(b['rot'])
    u, v = dx * c + dy * s, -dx * s + dy * c
    rho = math.sqrt((u / b['r']) ** 2 + (v / (b['r'] * b['ar'])) ** 2)
    z = 0.0
    if rho < 1.0:
        z -= b['depth'] * (1 - rho * rho)
    z += b['lip'] * math.exp(-((rho - 1.0) / 0.2) ** 2)
    return z


def floor_field(x, y):
    off = P['_off']
    rho = math.sqrt((x / P['rx']) ** 2 + (y / P['ry']) ** 2)
    z = P['talus'] * smooth(clamp01((rho - 0.72) / 0.28))
    z += P['relief'] * noise.noise(Vector((x * 0.3, y * 0.3, 0.0)) + off)
    for b in P['_basins']:
        z += basin_z(b, x, y)
    for o in P['_open']:
        d = math.hypot(x - o['base'].x, y - o['base'].y)
        z *= smooth(clamp01((d - 0.9) / 2.4))
    return z


def roughen_cave(bm, keep):
    bm.normal_update()
    off = P['_off']
    moves = []
    for v in bm.verts:
        inside = [f for f in v.link_faces if f.material_index == MAT_EARTH]
        if not inside or any(f.material_index == MAT_WOOD for f in v.link_faces):
            continue
        w = keep_exact(v.co, keep)
        if w <= 0:
            continue
        n = Vector()
        for f in inside:
            n += f.normal * f.calc_area()
        if n.length < 1e-9:
            continue
        n.normalize()
        c = v.co
        h = 0.6 * noise.noise(c * 0.5 + off) + 0.3 * noise.noise(c * 1.4 + off * 0.7) + 0.1 * noise.noise(c * 4.0 + off * 1.3)
        if n.z > 0.6:                                   # floor: pools, lips, talus, relief (z only)
            moves.append((v, Vector((0, 0, floor_field(c.x, c.y) * w + 0.015 * h))))
            continue
        wall = smooth(clamp01((0.75 - abs(n.z)) / 0.5))   # 1 on vertical faces
        rib = 1.0 - 2.0 * abs(noise.noise(Vector((c.x * 2.3, c.y * 2.3, c.z * 0.30)) + off * 0.5))   # ridged, stretched along Z
        hh = h
        if n.z < -0.3 and hh > 0:
            hh *= 0.5                                   # ceiling: keep headroom
        moves.append((v, n * ((hh * P['wall_amp'] + rib * P['ribs'] * wall) * w)))
    for v, d in moves:
        v.co += d
    bm.normal_update()


roughen = roughen_cave      # finish() looks the name up in this namespace


# ---------------------------------------------------------------------------------------------------------------------
# 4. Speleothems: lathe solids (closed), cylinder UVs into an atlas tile, per-vertex thickness by ray casting, baked glow

class Atlas:
    def __init__(self):
        self.em = [0.0] * (ATLAS_W * ATLAS_H * 3)
        self.th = [0.0] * (ATLAS_W * ATLAS_H)
        self.n = 0

    def next_tile(self):
        i = self.n
        self.n += 1
        if i >= COLS * ROWS:
            i = i % (COLS * ROWS)
        return (i % COLS, i // COLS)

    def put(self, x, y, rgb, th):
        if 0 <= x < ATLAS_W and 0 <= y < ATLAS_H:
            k = y * ATLAS_W + x
            self.em[k * 3:k * 3 + 3] = rgb
            self.th[k] = th


def glow_value(th, u, v, seed):
    """Thin = bright, thick = dark, with calcite banding. th in metres"""
    g = math.exp(-th / GLOW_L)
    band = 0.78 + 0.22 * noise.noise(Vector((u * 3.0, v * 9.0, seed * 0.13)))
    return clamp01(g * band * 1.25)


def thickness_per_vertex(bm):
    """Local wall thickness = the shortest chord through the solid from each vertex: a bundle of rays in a 25 degree cone
    around the inward normal (works for any closed mesh, also baked flowstone sheets; for a lathe it is ~2 x radius)"""
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    out = {}
    for v in bm.verts:
        n = v.normal.normalized()
        if n.length < 0.5:
            out[v] = 0.05
            continue
        a = n.cross(Vector((0, 0, 1)))
        if a.length < 0.1:
            a = n.cross(Vector((1, 0, 0)))
        a.normalize()
        b = n.cross(a)
        best = None
        o = v.co - n * 0.002
        for k in range(7):
            if k == 0:
                d = -n
            else:
                ang = (k - 1) * math.pi / 3
                d = (-n * math.cos(math.radians(25)) + (a * math.cos(ang) + b * math.sin(ang)) * math.sin(math.radians(25))).normalized()
            hit = tree.ray_cast(o, d)
            if hit[0] is not None:
                best = hit[3] if best is None else min(best, hit[3])
        out[v] = best if best is not None else 0.05
    return out


def speleothem(kind, length, r, seed, tile, atlas, sides=8, rings=9, bend=0.0, bake=True):
    """Closed solid along +Z (root at 0, buried EMBED m; tip at `length`). kind: stalactite | stalagmite | column | straw.
    Material = MAT_GLOW. UVs: cylinder unwrap into atlas tile `tile` (u around, v along, tip v = 1)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    e = EMBED / length
    info = {}
    ringv = []
    phase = rnd.uniform(0, 6.28)
    for i in range(rings):
        t = i / rings
        if kind == 'column':
            s = clamp01((t - e) / max(1 - 2 * e, 0.05))
            rad = r * (1 + 0.9 * (2 * abs(s - 0.5)) ** 2.2)
        else:
            s = clamp01((t - e) / max(1 - e, 0.05))
            if kind == 'stalagmite':
                rad = r * (0.16 + 0.84 * (1 - s) ** 1.15)
            else:   # stalactite, straw
                rad = r * ((1 - s) ** 1.15 * (1 + 0.10 * math.sin(s * 14 + phase)) + 0.05)
        if kind != 'column' and kind != 'straw':
            rad *= 1 + 0.45 * math.exp(-s / 0.14)            # flare where it meets the rock
        cx = bend * math.sin(clamp01((t - e)) * math.pi * 0.9)
        cy = bend * 0.4 * math.sin(clamp01((t - e)) * math.pi * 1.3)
        row = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + 0.25 * t
            rr = rad * (1 + 0.16 * noise.noise(Vector((math.cos(a), math.sin(a), t * 2.5)) * 1.3 + off)) if kind != 'straw' else rad
            vt = bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), t * length))
            info[vt] = (k, i)
            row.append(vt)
        ringv.append(row)
    apex = None
    if kind != 'column':
        apex = bm.verts.new((bend * math.sin(clamp01(1 - e) * math.pi * 0.9), bend * 0.4 * math.sin(clamp01(1 - e) * math.pi * 1.3), length))
        info[apex] = (None, rings)
    faces = []
    for i in range(rings - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append(bm.faces.new((ringv[i][k], ringv[i][k2], ringv[i + 1][k2], ringv[i + 1][k])))
    top = ringv[-1]
    if apex is not None:
        for k in range(sides):
            faces.append(bm.faces.new((top[k], top[(k + 1) % sides], apex)))
    else:
        faces.append(bm.faces.new(list(reversed(top))))
        top_cap = faces[-1]
    faces.append(bm.faces.new(list(reversed(ringv[0]))))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # UVs: per loop, u from the ring index (the seam face gets u = 1 on its k = 0 vertices), v from the ring
    c0, r0 = tile
    for f in bm.faces:
        ks = [info[l.vert][0] for l in f.loops if info[l.vert][0] is not None]
        wraps = ks and min(ks) == 0 and max(ks) == sides - 1 and len(ks) > 2
        us = []
        for l in f.loops:
            k, i = info[l.vert]
            if k is None:
                us.append(None)
                continue
            u = k / sides
            if wraps and k == 0:
                u = 1.0
            us.append(u)
        known = [u for u in us if u is not None]
        mean = sum(known) / len(known) if known else 0.5
        for l, u in zip(f.loops, us):
            k, i = info[l.vert]
            uu = mean if u is None else u
            vv = 1.0 if k is None else i / rings
            l[uvl].uv = ((c0 + 0.04 + 0.92 * uu) / COLS, (r0 + 0.02 + 0.96 * vv) / ROWS)
    for f in bm.faces:
        f.material_index = MAT_GLOW
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    if bake and atlas is not None:
        bake_tile(bm, uvl, atlas, seed)
    return bm


def bake_tile(bm, uvl, atlas, seed):
    th = thickness_per_vertex(bm)
    for f in bm.faces:
        pts = [(l[uvl].uv[0] * ATLAS_W, l[uvl].uv[1] * ATLAS_H, th[l.vert]) for l in f.loops]
        (x0, y0, t0), (x1, y1, t1), (x2, y2, t2) = pts
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        xmin, xmax = int(math.floor(min(x0, x1, x2))) - 1, int(math.ceil(max(x0, x1, x2))) + 1
        ymin, ymax = int(math.floor(min(y0, y1, y2))) - 1, int(math.ceil(max(y0, y1, y2))) + 1
        for py in range(ymin, ymax + 1):
            for px in range(xmin, xmax + 1):
                cx, cy = px + 0.5, py + 0.5
                a = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / den
                b = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / den
                c = 1 - a - b
                if a < -0.25 or b < -0.25 or c < -0.25:
                    continue
                tt = max(0.0, a * t0 + b * t1 + c * t2)
                u = (cx % TILE_W) / TILE_W
                v = (cy % TILE_H) / TILE_H
                g = glow_value(tt, u, v, seed)
                atlas.put(px, py, (g, g * 0.80, g * 0.52), tt)


def save_atlas(atlas, name):
    img = bpy.data.images.new(name, ATLAS_W, ATLAS_H, alpha=False)
    buf = []
    for k in range(ATLAS_W * ATLAS_H):
        buf.extend((atlas.em[k * 3], atlas.em[k * 3 + 1], atlas.em[k * 3 + 2], 1.0))
    img.pixels.foreach_set(buf)
    img.filepath_raw = os.path.join(OUTDIR, name + '.png')
    img.file_format = 'PNG'
    img.save()
    dbg = bpy.data.images.new(name + '_thickness', ATLAS_W, ATLAS_H, alpha=False)
    b2 = []
    for k in range(ATLAS_W * ATLAS_H):
        g = 1 - clamp01(atlas.th[k] / 0.5)
        b2.extend((g, g, g, 1.0))
    dbg.pixels.foreach_set(b2)
    dbg.filepath_raw = os.path.join(OUTDIR, name + '_thickness.png')
    dbg.file_format = 'PNG'
    dbg.save()
    return img


# ---------------------------------------------------------------------------------------------------------------------
# 5. Placing the formations on the finished shell (ray casts floor/ceiling), keeping the walking routes clear

def probe(tree, x, y, z0=1.0):
    z0 = z0 + P.get('slope', 0.0) * y
    up = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, 1)))
    dn = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)))
    if up[0] is None or dn[0] is None or up[1].z > -0.3 or dn[1].z < 0.3:
        return None
    return dn[0].z, up[0].z


def plan_formations(P, shell_bm, atlas):
    tree = BVHTree.FromBMesh(shell_bm)
    rng = random.Random(P['seed'] * 7 + 3)
    placed = []     # (x, y, r)
    out = []        # (bm, matrix, collide, kind)

    def site(maxrho=0.82, need=1.6):
        for _ in range(80):
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.random()) * maxrho
            x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
            pr = probe(tree, x, y)
            if pr and pr[1] - pr[0] > need:
                return x, y, pr[0], pr[1]
        return None

    def free(x, y, r, gap=0.25):
        return all(math.hypot(x - px, y - py) > r + pr + gap for px, py, pr in placed)

    def add(kind, x, y, z_root, length_visible, r, down, collide, **kw):
        L = length_visible + EMBED * (2 if kind == 'column' else 1)
        bm = speleothem(kind, L, r, rng.randint(0, 10 ** 6), atlas.next_tile(), atlas, **kw)
        if kind == 'column':
            m = Matrix.Translation((x, y, z_root - EMBED))
        elif down:
            m = Matrix.Translation((x, y, z_root + EMBED)) @ Matrix.Rotation(math.pi, 4, 'X')
        else:
            m = Matrix.Translation((x, y, z_root - EMBED))
        out.append((bm, m, collide, kind))
        placed.append((x, y, r))

    for _ in range(P['columns']):
        for _try in range(40):
            s = site(0.68, 2.2)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            if span > 7.8 or path_dist(x, y) < P.get('col_clear', 1.4) or fz < -0.1:
                continue
            r = rng.uniform(0.15, 0.36) * (0.8 + 0.1 * span)
            if free(x, y, r * 1.9, 0.5):
                add('column', x, y, fz, span, r, False, True, sides=10, rings=15, bend=rng.uniform(-0.05, 0.05))
                break
    for _ in range(P['pairs']):
        for _try in range(40):
            s = site(0.75, 2.8)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            if path_dist(x, y) < 1.0 or fz < -0.1:
                continue
            L1 = min(rng.uniform(0.3, 0.55) * span, span - 2.3 if path_dist(x, y) < 1.4 else span)
            H = rng.uniform(0.12, 0.28) * span
            if span - L1 - H < 0.4:
                H = max(0.2, span - L1 - 0.4)
            r1, r2 = max(0.04, L1 / rng.uniform(4.5, 7)), max(0.06, H / rng.uniform(2.6, 4))
            if L1 > 0.3 and free(x, y, max(r1, r2) * 1.5):
                add('stalactite', x, y, cz, L1, r1, True, L1 > span - 2.3, sides=8, rings=10, bend=rng.uniform(-0.04, 0.04))
                add('stalagmite', x, y, fz, H, r2, False, True, sides=8, rings=8)
                break
    for _ in range(P['stalagmites']):
        for _try in range(40):
            s = site(0.8, 2.0)
            if not s:
                continue
            x, y, fz, cz = s
            if path_dist(x, y) < 0.9 or fz < -0.1:
                continue
            H = min(rng.uniform(0.3, 1.3), cz - fz - 1.2)
            if H < 0.25:
                continue
            r = H / rng.uniform(2.5, 4.5) + 0.05
            if free(x, y, r * 1.3):
                add('stalagmite', x, y, fz, H, r, False, True, sides=8, rings=8)
                break
    for _ in range(P['stalactites']):
        for _try in range(40):
            s = site(0.85, 1.8)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            L = rng.uniform(*P['len_st'])
            lim = span - 2.3 if path_dist(x, y) < 1.1 else span - 0.6
            L = min(L, lim)
            if L < 0.25:
                continue
            r = max(0.04, L / rng.uniform(5, 9))
            if free(x, y, r * 1.3, 0.15):
                add('stalactite', x, y, cz, L, r, True, (span - L) < 2.3, sides=7, rings=8, bend=rng.uniform(-0.04, 0.04))
                break
    for _ in range(P['straws']):
        s = site(0.85, 1.8)
        if not s:
            continue
        x, y, fz, cz = s
        span = cz - fz
        for k in range(rng.randint(3, 5)):
            xx, yy = x + rng.uniform(-0.22, 0.22), y + rng.uniform(-0.22, 0.22)
            pr = probe(tree, xx, yy)
            if not pr:
                continue
            L = min(rng.uniform(0.25, 0.9), pr[1] - pr[0] - (2.3 if path_dist(xx, yy) < 1.1 else 0.6))
            if L < 0.2:
                continue
            add('straw', xx, yy, pr[1], L, rng.uniform(0.012, 0.02), True, False, sides=5, rings=4)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# 6. Pool water (separate, collision-free mesh) from the same basin definitions

def pool_water(P):
    bm = bmesh.new()
    for b in P['_basins']:
        level = b['lip'] * 0.45
        # widest rho still below the water level
        rho_w = 0.0
        for k in range(1, 100):
            rho = k / 100 * 1.1
            z = (-b['depth'] * (1 - rho * rho) if rho < 1 else 0.0) + b['lip'] * math.exp(-((rho - 1.0) / 0.2) ** 2)
            if z < level - 0.01:
                rho_w = rho
        rho_w = max(rho_w, 0.3)
        c, s = math.cos(b['rot']), math.sin(b['rot'])
        ctr = bm.verts.new((b['x'], b['y'], level))
        ring = []
        for k in range(28):
            a = 2 * math.pi * k / 28
            ru = rho_w * b['r'] * (1 + 0.05 * math.sin(3 * a + b['x']))
            rv = rho_w * b['r'] * b['ar'] * (1 + 0.05 * math.sin(3 * a + b['x']))
            u, v = ru * math.cos(a), rv * math.sin(a)
            ring.append(bm.verts.new((b['x'] + u * c - v * s, b['y'] + u * s + v * c, level)))
        for k in range(28):
            bm.faces.new((ctr, ring[k], ring[(k + 1) % 28]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('Water_' + P['name'])
    bm.to_mesh(me)
    n = len(me.polygons)
    bm.free()
    ob = bpy.data.objects.new('Water_' + P['name'], me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, n


# ---------------------------------------------------------------------------------------------------------------------
# 7. Assemble: kit finish() on the shell, then add the formations (+ collider without the high stalactites)

def assemble(P):
    piece, V2 = build_room(P)
    objs = finish(piece)                      # kit: triangulate, split_inside (3 materials), refine, roughen_cave, UVs, 'Col'
    lod, utm = objs[0], objs[1]
    me = lod.data
    shell_tris = len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    col = bm.loops.layers.color['Col']
    uvl = bm.loops.layers.uv.verify()
    clay = bm.faces.layers.int.new('collide')
    for f in bm.faces:
        f[clay] = 1
    atlas = Atlas()
    t0 = time.time()
    forms = plan_formations(P, bm, atlas)
    print('formations: %d baked in %.1f s' % (len(forms), time.time() - t0))
    counts = {}
    spl_tris = 0
    for fbm, m, collide, kind in forms:
        bmesh.ops.transform(fbm, matrix=m, verts=fbm.verts[:])
        tmp = bpy.data.meshes.new('tmp')
        fbm.to_mesh(tmp)
        n_before = len(bm.faces)
        bm.from_mesh(tmp)       # appends
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        # from_mesh keeps the uv layer name 'UVMap' of the tmp mesh, which matches the kit's layer
        for f in bm.faces[n_before:]:
            f.material_index = MAT_GLOW
            f[clay] = 1 if collide else 0
            for l in f.loops:
                l[col] = (1.0, 1.0, 1.0, 1.0)
        spl_tris += len(bm.faces) - n_before
        counts[kind] = counts.get(kind, 0) + 1
        bpy.data.meshes.remove(tmp)
        fbm.free()
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(60) and e.link_faces[0].material_index != MAT_GLOW)
    glow_mat = bpy.data.materials.get('TT_CalciteGlow') or bpy.data.materials.new('TT_CalciteGlow')
    glow_mat.diffuse_color = (0.9, 0.85, 0.7, 1)
    me.clear_geometry()
    bm.to_mesh(me)
    me.materials.append(glow_mat)
    for p in me.polygons:
        p.use_smooth = p.material_index in (MAT_EARTH, MAT_GLOW)
    # collider: everything but the formations nobody can touch (high stalactites, straws)
    cb = bm.copy()
    cl = cb.faces.layers.int['collide']
    cb.faces.ensure_lookup_table()
    bmesh.ops.delete(cb, geom=[f for f in cb.faces if f[cl] == 0], context='FACES')
    utm.data.clear_geometry()
    cb.to_mesh(utm.data)
    utm.data.materials.clear()
    for mt in me.materials:
        utm.data.materials.append(mt)
    coll_tris = len(utm.data.polygons)
    cb.free()
    bm.free()
    img = save_atlas(atlas, 'Cave_Glow_EM_' + VARIANT)
    water, water_tris = pool_water(P)
    by_mat = {}
    for p_ in me.polygons:
        by_mat[me.materials[p_.material_index].name] = by_mat.get(me.materials[p_.material_index].name, 0) + 1
    stats = dict(tris_by_material=by_mat, name=P['name'], variant=VARIANT, label=P['label'], seed=P['seed'],
                 tris_shell=shell_tris, tris_formations=spl_tris, tris_lod0=len(me.polygons), tris_collider=coll_tris,
                 tris_water=water_tris, formations=counts, openings=[o['side'] for o in P['_open']], pools=len(P['_basins']),
                 bbox=[round(x, 2) for x in lod.dimensions])
    return piece, objs, water, img, stats, V2


def verify(piece, lod):
    """Every opening's end ring still has all INNER profile points, and the mesh has no open edges"""
    me = lod.data
    ok = []
    for pos, out in piece.sockets:
        lat = out.cross(Z).normalized()
        found = 0
        for (px, pz) in INNER:
            target = pos + lat * px + Z * pz
            if any((v.co - target).length < 2e-3 for v in me.vertices):
                found += 1
        ok.append('%d/%d' % (found, len(INNER)))
    bm = bmesh.new()
    bm.from_mesh(me)
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    lo, hi = Vector((min(xs), min(ys), 0)), Vector((max(xs), max(ys), 0))
    facing = []
    for pos, out in piece.sockets:
        gaps = {(1, 0): hi.x - pos.x, (-1, 0): pos.x - lo.x, (0, 1): hi.y - pos.y, (0, -1): pos.y - lo.y}
        best = min(gaps, key=gaps.get)
        facing.append(best == (round(out.x), round(out.y)))
    return ok, open_edges, facing


# ---------------------------------------------------------------------------------------------------------------------
# 8. Preview materials + EEVEE renders (preview only; not the Enfusion materials)

def preview_materials(img):
    def principled(name, base, rough, emit_img=None):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        bsdf.inputs['Roughness'].default_value = rough
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = 3.0
        tex.inputs['Detail'].default_value = 6.0
        mapn = nt.nodes.new('ShaderNodeTexCoord')
        nt.links.new(mapn.outputs['Object'], tex.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (base[0] * 0.65, base[1] * 0.65, base[2] * 0.65, 1)
        ramp.color_ramp.elements[1].color = (base[0] * 1.15, base[1] * 1.15, base[2] * 1.15, 1)
        nt.links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bump = nt.nodes.new('ShaderNodeBump')
        tex2 = nt.nodes.new('ShaderNodeTexNoise')
        tex2.inputs['Scale'].default_value = 28.0
        tex2.inputs['Detail'].default_value = 8.0
        nt.links.new(mapn.outputs['Object'], tex2.inputs['Vector'])
        nt.links.new(tex2.outputs['Fac'], bump.inputs['Height'])
        bump.inputs['Strength'].default_value = 0.25
        nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
        m.diffuse_color = (*base, 1)
        return m, bsdf

    principled('TT_Earth', (0.50, 0.44, 0.36), 0.85)
    principled('TT_Wood', (0.35, 0.25, 0.15), 0.8)
    principled('TT_Ground', (0.30, 0.45, 0.20), 0.9)
    m, bsdf = principled('TT_CalciteGlow', (0.88, 0.82, 0.68), 0.35)
    nt = m.node_tree
    texn = nt.nodes.new('ShaderNodeTexImage')
    texn.image = img
    texn.interpolation = 'Linear'
    nt.links.new(texn.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.0
    w = bpy.data.materials.get('TT_Water') or bpy.data.materials.new('TT_Water')
    w.use_nodes = True
    wn = next(n for n in w.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    wn.inputs['Base Color'].default_value = (0.03, 0.07, 0.08, 1)
    wn.inputs['Roughness'].default_value = 0.04
    wn.inputs['Alpha'].default_value = 0.8
    try:
        w.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m, bsdf


def set_glow(bsdf, strength):
    bsdf.inputs['Emission Strength'].default_value = strength


def setup_render(res):
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.5625)
    sc.render.film_transparent = False
    try:
        sc.eevee.taa_render_samples = 48
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    w = bpy.data.worlds.new('Dark')
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.004, 0.005, 0.008, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = w
    return sc


def add_light(name, kind, loc, energy, color, size=0.1):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'POINT':
        ld.shadow_soft_size = size
    if kind == 'AREA':
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    return ob


def make_cam(name, loc, target, lens=20, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 80
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def shoot(cam, name):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = os.path.join(OUTDIR, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('rendered', name)


def side_by_side(a, b, out):
    import numpy as np
    ia = bpy.data.images.load(os.path.join(OUTDIR, a + '.png'))
    ib = bpy.data.images.load(os.path.join(OUTDIR, b + '.png'))
    w, h = ia.size
    A = np.array(ia.pixels[:], dtype=np.float32).reshape(h, w, 4)
    B = np.array(ib.pixels[:], dtype=np.float32).reshape(h, w, 4)
    C = np.concatenate([A, np.ones((h, 6, 4), np.float32), B], axis=1)
    im = bpy.data.images.new(out, C.shape[1], h, alpha=False)
    im.pixels.foreach_set(C.reshape(-1))
    im.filepath_raw = os.path.join(OUTDIR, out + '.png')
    im.file_format = 'PNG'
    im.save()


def cut_copy(obj, co, no):
    me = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, clear_outer=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(obj.name + '_cut', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def render_room(P, lod, water, bsdf):
    sc = setup_render(RES)
    o0, o1 = P['_open'][0], P['_open'][min(1, len(P['_open']) - 1)]
    rx, ry, h = P['rx'], P['ry'], P['h']
    for o in bpy.data.objects:
        if o.type == 'EMPTY' or o.name.startswith('UTM_'):
            o.hide_render = True
            o.hide_viewport = True
    torch = add_light('torch', 'POINT', (0, 0, 1.7), 220, (1.0, 0.72, 0.45), 0.08)
    fill = add_light('fill', 'POINT', (0, 0, 2.5), 60, (0.45, 0.6, 1.0), 0.3)
    # 1: standing in the first opening, torch in hand
    cam = make_cam('cam1', o0['base'] - o0['out'] * 0.9 + Vector((0, 0, 1.65)), (0, 0, 2.3), 19)
    torch.location = cam.location + Vector((0.15, 0, -0.1))
    fill.location = Vector((0, 0, h * 0.55))
    shoot(cam, f'{P["name"]}_view1_entrance')
    # 2: from the second opening, other side
    cam = make_cam('cam2', o1['base'] - o1['out'] * 0.9 + Vector((0, 0, 1.6)), (0, 0, 2.0), 19)
    torch.location = cam.location + Vector((0.15, 0, -0.1))
    shoot(cam, f'{P["name"]}_view2_second')
    # 3: low, looking up into the roof (stalactites)
    cam = make_cam('cam3', (-0.2 * rx, -0.35 * ry, 0.5), (0.1 * rx, 0.15 * ry, h * 0.8), 17)
    torch.location = cam.location + Vector((0.1, 0.2, 0.3))
    shoot(cam, f'{P["name"]}_view3_up')
    # 4: glow only, no torch: the faked calcite shine-through, side by side with glow off
    torch.hide_render = True
    fill.hide_render = True
    cam = make_cam('cam4', (-0.05 * rx, -0.55 * ry, 1.3), (0.1 * rx, 0.2 * ry, h * 0.55), 17)
    set_glow(bsdf, 0.0)
    shoot(cam, f'{P["name"]}_view4_dark_glow_off')
    set_glow(bsdf, 12.0)
    shoot(cam, f'{P["name"]}_view4_dark_glow_on')
    side_by_side(f'{P["name"]}_view4_dark_glow_off', f'{P["name"]}_view4_dark_glow_on', f'{P["name"]}_view4_glow_compare')
    # cutaways
    torch.hide_render = False
    fill.hide_render = False
    set_glow(bsdf, 1.0)
    lod.hide_render = True
    water.hide_render = False
    sec = cut_copy(lod, Vector((0, 0, 0)), Vector((0, 1, 0)))
    sec.data.materials.clear()
    for mt in lod.data.materials:
        sec.data.materials.append(mt)
    area = add_light('area', 'AREA', (0, 6, h * 0.9), 3500, (1.0, 0.9, 0.75), 8)
    area.rotation_euler = (math.radians(120), 0, 0)
    torch.location = (0, 3.0, h * 0.35)
    torch.data.energy = 600
    fill.location = (0, 2, h * 0.5)
    cam = make_cam('cam5', (0, ry * 3.8 + 4, h * 0.38), (0, 0, h * 0.38), 28)
    shoot(cam, f'{P["name"]}_view5_section')
    bpy.data.objects.remove(sec)
    # plan view, roof cut away at 2.3 m
    sec = cut_copy(lod, Vector((0, 0, 2.3)), Vector((0, 0, 1)))
    sec.data.materials.clear()
    for mt in lod.data.materials:
        sec.data.materials.append(mt)
    area.location = (0, 0, 12)
    area.rotation_euler = (0, 0, 0)
    area.data.energy = 1400
    cam = make_cam('cam6', (0, 0, 18), (0, 0, 0), 28, ortho=max(rx, ry) * 2.9)
    cam.rotation_euler = (0, 0, 0)
    shoot(cam, f'{P["name"]}_view6_plan')


# ---------------------------------------------------------------------------------------------------------------------
# 9. Library mode: the prefab-able single formations in a row (each its own mesh, own tile of ONE atlas)

def library():
    atlas = Atlas()
    specs = [('stalactite', 0.5, 0.07, 7, 7), ('stalactite', 1.2, 0.14, 8, 9), ('stalactite', 2.4, 0.25, 8, 10), ('stalactite', 1.4, 0.12, 7, 9),
             ('straw', 0.7, 0.015, 5, 4), ('stalagmite', 0.5, 0.15, 8, 7), ('stalagmite', 1.0, 0.25, 8, 8), ('stalagmite', 1.6, 0.34, 9, 9),
             ('column', 2.6, 0.2, 10, 15), ('column', 3.4, 0.32, 10, 15), ('stalactite', 0.35, 0.05, 6, 6), ('column', 2.2, 0.14, 8, 12)]
    objs, rows = [], []
    x = 0.0
    for i, (kind, L, r, sides, rings) in enumerate(specs):
        bm = speleothem(kind, L + EMBED * (2 if kind == 'column' else 1), r, 100 + i, atlas.next_tile(), atlas, sides=sides, rings=rings,
                        bend=0.05 if i % 3 == 1 else 0.0)
        me = bpy.data.meshes.new(f'SPL_{kind}_{i}')
        bm.to_mesh(me)
        rows.append((f'SPL_{kind}_{i}', len(me.polygons)))
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        if kind == 'stalactite' or kind == 'straw':
            ob.rotation_euler = (math.pi, 0, 0)
            ob.location = (x, 0, L + EMBED + 0.3)
        else:
            ob.location = (x, 0, 0.3 - EMBED)
        x += max(0.9, r * 4 + 0.5)
        objs.append(ob)
    img = save_atlas(atlas, 'Cave_Glow_EM_library')
    return objs, rows, img, x


if MODE == 'library':
    objs, rows, img, width = library()
    mat, bsdf = preview_materials(img)
    for o in objs:
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.use_smooth = True
    json.dump(dict(library=rows), open(os.path.join(OUTDIR, 'stats_library.json'), 'w'), indent=1)
    print(rows)
    if RENDER:
        sc = setup_render(RES)
        add_light('torch', 'POINT', (width * 0.5, -3.0, 1.5), 90, (1.0, 0.75, 0.5), 0.1)
        cx = (width - 0.6) * 0.5
        cam = make_cam('cam', (cx, -9.5, 1.9), (cx, 0, 1.7), 24)
        set_glow(bsdf, 0.0)
        shoot(cam, 'library_front_glow_off')
        set_glow(bsdf, 12.0)
        shoot(cam, 'library_front_glow_on')
        bpy.context.scene.objects['torch'].hide_render = True
        shoot(cam, 'library_front_glow_only')
else:
    piece, objs, water, img, stats, V2 = assemble(P)
    lod = objs[0]
    ok, open_edges, facing = verify(piece, lod)
    stats['catalog_facing_ok'] = facing
    stats['opening_profile_points_found'] = ok
    stats['open_edges_lod0'] = open_edges
    print(json.dumps(stats))
    json.dump(stats, open(os.path.join(OUTDIR, 'stats_%s.json' % P['name']), 'w'), indent=1)
    mat, bsdf = preview_materials(img)
    water.data.materials.append(bpy.data.materials['TT_Water'])
    if FBX:
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = lod
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUTDIR, P['name'] + '.fbx'), use_selection=True, object_types={'MESH', 'EMPTY'},
                                 use_mesh_modifiers=True, mesh_smooth_type='EDGE', add_leaf_bones=False, bake_anim=False, path_mode='AUTO')
        print('fbx written')
    if RENDER:
        render_room(P, lod, water, bsdf)
print('DONE')
