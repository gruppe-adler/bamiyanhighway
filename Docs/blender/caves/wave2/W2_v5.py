"""W2 COPY of cave_dripstone_v5.py (wave-2 assets): the generator with hooks for the W2 shape engine (see W2_overrides.py).
Original docstring:
Dripstone rooms, v5: a real geometry merge. The room shell, the formations and the boulders are voxel-remeshed into
ONE surface (every root, cluster and overlap fused the same way), smoothed round the roots with volume preserved (the
"expand, smooth, fatten" step), decimated to a budget, and get their attributes back from the mesh before the remesh.
Kept out of the remesh, untouched: the joint stubs, sleeves and frames (so the openings keep the kit's exact profile),
soda straws and very small formations (they would vanish in the voxels; they still hug the rock).

Builds on cave_dripstone_v4.py (exec'd, run with CAVE_WELD=0). Run:
  blender.exe --factory-startup -b --python cave_dripstone_v5.py
Environment as v4, plus:
  CAVE_VOXEL      remesh voxel size in metres (default 0.025)
  CAVE_BUDGET     triangles of the merged surface after decimation (default 320000)
  CAVE_KEEP_SMALL horizontal extent (m) below which a formation stays out of the remesh (default 0.22)
CAVE_OUT defaults to a temp folder, never this folder.
"""
import os, sys, math, time, json, tempfile
os.environ.setdefault('CAVE_OUT', os.path.join(tempfile.gettempdir(), 'cave_out'))
os.environ['CAVE_WELD'] = '0'
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

_HERE5 = os.path.dirname(os.path.abspath(__file__))
_V4 = os.path.join(_HERE5, 'W2_v4.py')
_src4 = open(_V4, encoding='utf-8').read().split("\npiece, objs, water, img, stats, V2 = assemble2(P)")[0]
# small fill formations (spec key 'small'): 6-8 sides, a gentle compact root flare (4 fillet rings), 5 body rings, a rounded top
# for the blunt stalagmites. (They used to be 4-5 sided pyramids with a fillet 3x their own radius: square plinths.)
def _sub(a, b):
    global _src4
    assert _src4.count(a) == 1, a
    _src4 = _src4.replace(a, b)


_sub("def speleothem3(kind, Lvis, r, seed, tile, atlas, sides=8, n_body=9, bend=0.0, bake=True):",
     "def speleothem3(kind, Lvis, r, seed, tile, atlas, sides=8, n_body=9, bend=0.0, bake=True, small_flag=False):")
_sub("    f = fillet_of(kind, r, Lvis)\n    phase = rnd.uniform(0, 6.28)\n",
     "    f = fillet_of(kind, r, Lvis)\n    if small_flag:\n        f = min(0.8 * r + 0.012, 0.05, 0.4 * Lvis)\n    phase = rnd.uniform(0, 6.28)\n")
_sub("    fil = [f * (1 - math.cos(k / 6 * math.pi / 2)) for k in range(1, 7)] if f > 0 else []",
     "    _nf = 4 if small_flag else 6\n    fil = [f * (1 - math.cos(k / _nf * math.pi / 2)) for k in range(1, _nf + 1)] if f > 0 else []")
_sub("    small = sides <= 5                      # a cheap formation", "    small = small_flag                      # a cheap formation")
_sub("        if kind == 'stalagmite' and not small and mite_blunt:", "        if kind == 'stalagmite' and mite_blunt:")
_sub("        nb = max(4, s['rings'] - 4)", "        nb = 5 if s.get('small') else max(4, s['rings'] - 4)")
_sub("sides=s['sides'], n_body=nb, bend=s['bend'], bake=bake)", "sides=s['sides'], n_body=nb, bend=s['bend'], bake=bake, small_flag=bool(s.get('small')))")
exec(compile(_src4, _V4, 'exec'), globals())

# ---------------------------------------------------------------------------------------------------------------------
# Fill: many small, cheap formations (5 sides, ~60 triangles) between the big ones, planned with the rest (so their drip
# mounds go into the floor before it is shaped). They stay out of the voxel merge (too small for its voxels).

FILL_CEIL = int(os.environ.get('CAVE_FILL', '260'))       # small stalactites per room (before spacing rejects)
_plan_specs_v4 = plan_specs


def plan_specs(P, void_bm):
    specs, curtains, rocks, used = _plan_specs_v4(P, void_bm)
    tree = BVHTree.FromBMesh(void_bm)
    rng = random.Random(P['seed'] * 31 + 7)
    taken_c = [(s['x'], s['y'], s['r']) for s in specs if s['down'] or s['kind'] == 'column']
    taken_f = [(s['x'], s['y'], s['r']) for s in specs if not s['down']]

    def free(lst, x, y, r, gap):
        return all(math.hypot(x - a, y - b) > r + c + gap for a, b, c in lst)

    def in_water(x, y):
        return any(gour_eval(g, x, y)[1] > 0.25 for g in P['_gours']) or \
            any(math.hypot(x - b['x'], y - b['y']) < b['r'] * 1.1 for b in P['_basins']) or WATERMASK(x, y)

    def lim_down(x, y, span):
        return span - 2.25 if path_dist(x, y) < 1.15 else span - 0.5

    # where to put them: round the big ones (clusters), along the cracks, and a light scatter
    seeds = [(s['x'], s['y']) for s in specs if s['down'] and s['r'] > 0.04]
    for pts in P['_cracks']:
        seeds += [(q.x, q.y) for q in pts[::3]]
    n_ok = n_mites = n_mounds = 0
    for k in range(FILL_CEIL):
        if seeds and rng.random() < 0.75:
            sx, sy = seeds[rng.randrange(len(seeds))]
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0.12, 0.8)
            x, y = sx + d * math.cos(a), sy + d * math.sin(a)
        else:
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.random()) * 0.85
            x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
        pr = probe_raw(tree, x, y)
        if not pr:
            continue
        span = pr[1] - pr[0]
        L = min(math.exp(rng.gauss(math.log(0.12), 0.55)), 0.4, lim_down(x, y, span))
        if L < 0.04:
            continue
        r = max(0.012, L / rng.uniform(5.0, 8.0))
        if not free(taken_c, x, y, r, 0.03):
            continue
        specs.append(dict(kind='stalactite', x=x, y=y, L=L, r=r, down=True, collide=False, sides=6 if r < 0.02 else (7 if r < 0.03 else 8), rings=4,
                          small=True, bend=rng.uniform(-0.012, 0.012), seed=rng.randint(0, 10 ** 6)))
        taken_c.append((x, y, r))
        n_ok += 1
        # below it: a small stalagmite about half the time, otherwise a drip mound shaped into the floor
        if in_water(x, y) or rng.random() < 0.1:
            continue
        fx, fy = x + rng.gauss(0, 0.03), y + rng.gauss(0, 0.03)
        H = min(L * math.exp(rng.gauss(math.log(0.7), 0.5)), 0.3, span - L - 0.4)
        on_path = path_dist(fx, fy) < 0.55
        if not on_path and H > 0.04 and rng.random() < 0.5 and free(taken_f, fx, fy, r * 1.4, 0.03):
            specs.append(dict(kind='stalagmite', x=fx, y=fy, L=H, r=max(0.012, H / rng.uniform(3.0, 5.5)), down=False,
                              collide=False, sides=7 if r < 0.03 else 8, rings=4, small=True, bend=rng.uniform(-0.01, 0.01), seed=rng.randint(0, 10 ** 6)))
            taken_f.append((fx, fy, r * 1.4))
            n_mites += 1
        else:
            add_skirt(SKIRT_F, fx, fy, 0.05 + 0.25 * L, min(0.01 + 0.05 * L, 0.03) * (0.35 if on_path else 1.0))
            n_mounds += 1
    P['_fill_stats'] = dict(small_stalactites=n_ok, small_stalagmites=n_mites, drip_mounds=n_mounds)
    print('fill:', P['_fill_stats'])
    return specs, curtains, rocks, used


VOX = float(os.environ.get('CAVE_VOXEL', '0.025'))
BUDGET = int(os.environ.get('CAVE_BUDGET', '320000'))
KEEP_SMALL = float(os.environ.get('CAVE_KEEP_SMALL', '0.22'))
HOLE_GROW = VOX * 0.5            # the remesh shrinks the opening holes by about half a voxel: cut them that much larger

_prism_base = prism


def prism(bm, samples, profile, mat=0):
    """the room's opening-hole cutters come out HOLE_GROW larger (identified by their profile)"""
    ref = offset(INNER, 0.001)
    if len(profile) == len(ref) and all(abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9 for a, b in zip(profile, ref)):
        profile = offset(INNER, 0.001 + HOLE_GROW)
    return _prism_base(bm, samples, profile, mat)


def components(bm):
    """connected face sets"""
    seen = set()
    out = []
    for f in bm.faces:
        if f in seen:
            continue
        stack = [f]
        comp = []
        seen.add(f)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        out.append(comp)
    return out


def split_for_remesh(me, sockets):
    """(remesh_bm, keep_bm): what goes into the voxel remesh and what stays exactly as built"""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    fid = bm.faces.layers.int.get('fid')
    comps = components(bm)
    biggest = max(comps, key=len)
    keep_faces = set()
    why = {'joint': 0, 'small': 0, 'remesh': 0}
    for comp in comps:
        if comp is biggest:
            why['remesh'] += 1
            continue
        vs = set(v for f in comp for v in f.verts)
        lo = Vector((min(v.co.x for v in vs), min(v.co.y for v in vs), min(v.co.z for v in vs)))
        hi = Vector((max(v.co.x for v in vs), max(v.co.y for v in vs), max(v.co.z for v in vs)))
        ctr = (lo + hi) * 0.5
        is_form = fid is not None and any(f[fid] > 0 for f in comp)
        # the stub's mouth is at the socket: measure to the box of the part, not to its centre (a long stub has its centre far away)
        def gap(pos):
            d = Vector((max(lo.x - pos.x, 0.0, pos.x - hi.x), max(lo.y - pos.y, 0.0, pos.y - hi.y), max(lo.z - pos.z, 0.0, pos.z - hi.z)))
            return d.length
        near_joint = any(gap(pos) < 0.3 for pos, out in sockets)
        is_frame = all(f.material_index == MAT_WOOD for f in comp)       # a timber frame inside a dug tube: kept exact
        if not is_form and (near_joint or is_frame):
            keep_faces.update(comp)
            why['joint'] += 1
        elif is_form and max(hi.x - lo.x, hi.y - lo.y) < KEEP_SMALL:
            keep_faces.update(comp)
            why['small'] += 1
        else:
            why['remesh'] += 1
    rem = bm.copy()
    keep = bm.copy()
    rem.faces.ensure_lookup_table()
    keep.faces.ensure_lookup_table()
    kidx = set(f.index for f in keep_faces)
    bmesh.ops.delete(rem, geom=[f for f in rem.faces if f.index in kidx], context='FACES')
    bmesh.ops.delete(keep, geom=[f for f in keep.faces if f.index not in kidx], context='FACES')
    bm.free()
    return rem, keep, why


def world_uv_kept(keep):
    """The formations kept out of the remesh were built with UVs into a formation atlas tile; the material's layers run on world-space
    UVs, so those few cm of tile are the whole texture there: stretched streaks, no continuity with the rock. Give each formation ONE
    planar world projection (a random vertical plane per formation: no seams, no per-face axis switch) at the same density as the rock,
    so it takes the colour of the rock at its root and the texture runs along it."""
    uvl = keep.loops.layers.uv.verify()
    fid = keep.faces.layers.int.get('fid')
    n = 0
    for comp in components(keep):
        if fid is None or not any(f[fid] > 0 for f in comp):
            continue
        c = comp[0].calc_center_median()
        a = (math.floor(c.x * 977 + c.y * 131 + c.z * 53) % 360) * math.pi / 180.0
        ca, sa = math.cos(a), math.sin(a)
        for f in comp:
            for l in f.loops:
                co = l.vert.co
                l[uvl].uv = ((co.x * ca + co.y * sa) * UV_EARTH, co.z * UV_EARTH)
        n += 1
    return n


def plug_floor_slits(me_):
    """Leak repair. Here and there the shell's outer skin rises up into or through the floor (the offset surface folds where the floor
    is very uneven): the floor slab is then HOLLOW (an air layer under the floor surface, 0.3-0.8 m) or has a hole, and the hollows and
    holes join up into thin channels from the room to the outside (found by ray scans in the Meander and the cathedral).
    Scan the footprint with downward rays and read each column as solid intervals (up-facing hit enters, down-facing leaves). The floor
    slab of a column is its lowest interval plus every interval above it that is less than 0.8 m away (a hollow floor). Then
      - air gaps inside a floor slab are filled (a solid box over the gap, overlapping both slabs);
      - a column whose lowest solid is far above the neighbouring floors (a ceiling or the underside of a formation, nothing under it)
        is a hole: fill it from below the neighbouring bottom skin up to the neighbouring floor level.
    The boxes are separate closed bodies and merge with the shell in the voxel remesh."""
    bm_ = bmesh.new()
    bm_.from_mesh(me_)
    bm_.faces.ensure_lookup_table()
    xs = [v.co.x for v in bm_.verts]
    ys = [v.co.y for v in bm_.verts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    step = max(0.05, math.sqrt((x1 - x0) * (y1 - y0) / 150000.0))
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    tr_ = BVHTree.FromBMesh(bm_)
    zt = max(v.co.z for v in bm_.verts) + 1.0
    down = Vector((0, 0, -1))
    GAP = 0.8
    low = {}                       # column -> (top, bottom) of its LOWEST solid interval
    stk = {}                       # column -> (floor top, floor bottom, [(gap low, gap high), ...]) for columns whose lowest solid is a slab
    for i in range(nx):
        for j in range(ny):
            o_ = Vector((x0 + i * step, y0 + j * step, zt))
            hz, hu, hm = [], [], []
            for _ in range(10):
                h_ = tr_.ray_cast(o_, down)
                if h_[0] is None:
                    break
                hz.append(h_[0].z)
                hu.append(h_[1].z > 0)
                hm.append(bm_.faces[h_[2]].material_index)
                o_ = h_[0] + Vector((0, 0, -0.004))
            ivs = [(hz[k], hz[k + 1], hm[k + 1]) for k in range(len(hz) - 1) if hu[k] and not hu[k + 1]]      # (top, bottom, bottom's material), highest first
            if not ivs:
                continue
            top, bot, bmat = ivs[-1]
            low[(i, j)] = (top, bot)
            if top - bot < 0.3 or bmat != 2 or len(ivs) < 2:
                continue                                      # a sliver, a formation tip, or a roof slab / wall rock (a floor always has the roof above it: two solid intervals): not a floor slab
            gaps = []
            for top2, bot2, _m in reversed(ivs[:-1]):
                if bot2 - top < GAP:
                    if bot2 - top > 0.02:
                        gaps.append((top, bot2))
                    top = top2
                else:
                    break
            stk[(i, j)] = (top, bot, gaps)
    # floor-like columns: a slab 0.3-3 m thick
    cand = {c: (s[0], s[1]) for c, s in stk.items() if 0.3 < s[0] - s[1] < 3.0}
    holes = []
    for c, (ltop, lbot) in low.items():
        if c in cand:
            continue
        near = []
        for r in range(1, 25):
            for di in range(-r, r + 1):
                for dj in ((-r, r) if abs(di) < r else range(-r, r + 1)):
                    g = cand.get((c[0] + di, c[1] + dj))
                    if g is not None:
                        near.append((di * di + dj * dj, g))
            if len(near) >= 3 and r >= 2:
                break
        if len(near) < 3:
            continue
        enclosed = False
        for ax_i, ax_j in ((1, 0), (0, 1)):
            neg = any((c[0] - k * ax_i, c[1] - k * ax_j) in cand for k in range(1, 25))
            pos = any((c[0] + k * ax_i, c[1] + k * ax_j) in cand for k in range(1, 25))
            if neg and pos:
                enclosed = True
                break
        if not enclosed:
            continue                                          # floor on one side only: rock outside the room, not a hole in the floor
        near.sort(key=lambda t_: t_[0])
        sel = [g for _, g in near[:12]]
        ft = min(g[0] for g in sel)                           # the lowest nearby floor (formation bodies sit higher)
        if lbot > ft + 0.3:                                   # this column's lowest solid is well above that floor: nothing under it
            holes.append((c, ft, min(g[1] for g in sel[:4]) - 0.4))
    boxes = []
    for c, ft, bot in holes:
        boxes.append((x0 + c[0] * step, y0 + c[1] * step, bot, ft + 0.02))
    # hollow floors: only near the holes (a hollow floor and a hole are the same fault; air gaps under stalactites are not)
    R = int(math.ceil(1.6 / step))
    zone = set()
    for c, _, _ in holes:
        for di in range(-R, R + 1):
            for dj in range(-R, R + 1):
                zone.add((c[0] + di, c[1] + dj))
    n_gap = 0
    for c in zone:
        s = stk.get(c)
        if s is None:
            continue
        for lo, hi in s[2]:
            boxes.append((x0 + c[0] * step, y0 + c[1] * step, lo - 0.05, hi + 0.05))
            n_gap += 1
    n_hole = len(holes)
    if os.environ.get('CAVE_DEBUG_COL'):
        _tx, _ty = [float(v) for v in os.environ['CAVE_DEBUG_COL'].split(',')]
        _tc = (int(round((_tx - x0) / step)), int(round((_ty - y0) / step)))
        for _di in (-2, 0, 2):
            _c = (_tc[0] + _di, _tc[1])
            print('DEBUGPLUG col', _c, 'low', low.get(_c), 'stk', stk.get(_c), 'cand', _c in cand, 'hole', any(h[0] == _c for h in holes))
    cl = bm_.faces.layers.int.get('collide')
    MAXB = 40000
    for x, y, lo, hi in boxes[:MAXB]:
        fs = box(bm_, (x - 0.55 * step, y - 0.55 * step, lo), (x + 0.55 * step, y + 0.55 * step, hi), 0)
        if cl is not None and fs:
            for f in fs:
                f[cl] = 1
    print('floor repair: %d hollow-floor gaps and %d hole columns filled (%d boxes, scan step %.2f m, %d columns)' % (n_gap, n_hole, min(len(boxes), MAXB), step, len(stk)))
    if boxes:
        bm_.to_mesh(me_)
    bm_.free()
    return len(boxes)


IMPORTANCE = os.environ.get('CAVE_IMPORTANCE', '1') == '1'
STAGE1 = int(os.environ.get('CAVE_STAGE1', '1600000'))        # triangles after the uniform first pass
IMP_FACTOR = float(os.environ.get('CAVE_IMP_FACTOR', '1'))   # how strongly the weights steer the second pass


def importance_groups(ob, picks, sockets, void_tree=None):
    """Vertex group 'imp': 1 where detail is looked at (the floor walked on, the lower walls, formation roots, openings),
    low on the high ceiling and the upper walls, where the normal map can carry the fine detail"""
    import numpy as np
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    nm = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get('normal', nm)
    nm = nm.reshape(n, 3)
    hz = co[:, 2] - FLOORV(co[:, 0], co[:, 1])            # height above the floor (W2: a floor function)
    nz = nm[:, 2]
    w = np.full(n, 0.5, dtype=np.float32)
    floor = nz > 0.45
    ceil = nz < -0.2
    wall = ~(floor | ceil)
    w[floor] = 0.85
    w[ceil & (hz < 4.5)] = 0.5
    w[ceil & (hz >= 4.5)] = 0.2
    w[wall & (hz < 2.6)] = 0.65
    w[wall & (hz >= 2.6) & (hz < 5.0)] = 0.32
    w[wall & (hz >= 5.0)] = 0.18
    # the walking ways on the floor: full detail
    outside = np.zeros(n, dtype=bool)
    if void_tree is not None:
        # the hidden outer shell: further than 0.5 m from the cavity surface. Nobody sees it: least detail of all
        for k in range(n):
            hit = void_tree.find_nearest(Vector(co[k]), 0.5)
            if hit[0] is None:
                outside[k] = True
        w[outside] = 0.0
    kd = KDTree(len(picks) + len(sockets) + 1)
    rad = []
    for pk in picks:
        kd.insert(pk['pt'], len(rad))
        rad.append(pk['r'] + 0.35)
    for pos, out in sockets:
        kd.insert(pos, len(rad))
        rad.append(3.0)
    kd.balance()
    maxr = max(rad) if rad else 0.0
    boosted = 0
    for k in range(n):
        hit = kd.find_range(Vector(co[k]), maxr)
        for (c_, idx, dist) in hit:
            if dist <= rad[idx] and not outside[k]:
                w[k] = 1.0
                boosted += 1
                break
    # round to a few levels: one call per level
    levels = np.array([0.0, 0.18, 0.2, 0.32, 0.5, 0.65, 0.85, 1.0], dtype=np.float32)
    snapped = levels[np.abs(w[:, None] - levels[None, :]).argmin(axis=1)]
    vg = ob.vertex_groups.new(name='imp')
    for lv in levels:
        idx = np.nonzero(snapped == lv)[0].tolist()
        if idx:
            vg.add(idx, float(0.6 - 0.5 * lv), 'REPLACE')     # importance 1 -> 0.1 (protected), 0.18 -> 0.51, outside 0 -> 0.6 (decimated hardest)
    return boosted


def decimate_to(ob, target_tris, group=None):
    d = ob.modifiers.new('dec', 'DECIMATE')
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    d.ratio = min(1.0, target_tris / max(tris, 1))
    d.use_collapse_triangulate = True
    if group:
        d.vertex_group = group
        d.vertex_group_factor = IMP_FACTOR      # Blender: LOW weight protects, HIGH weight is decimated away (tested)
    dg = bpy.context.evaluated_depsgraph_get()
    me3 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me3
    bpy.data.meshes.remove(old)


def remesh_object(src_bm, name, picks=None, sockets=None, void_tree=None):
    me = bpy.data.meshes.new(name)
    src_bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new('remesh', 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = VOX
    m.adaptivity = 0.0
    m.use_smooth_shade = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    n_rem = len(me2.polygons)
    ob.modifiers.clear()
    ob.data = me2
    bpy.data.meshes.remove(me)
    if IMPORTANCE and picks is not None:
        # pass 1: uniform, down to a size the weights can be worked out on; pass 2: weighted, down to the budget
        decimate_to(ob, min(STAGE1, BUDGET * 3))
        t0 = time.time()
        boosted = importance_groups(ob, picks, sockets or [], void_tree)
        print('importance weights on %d vertices (%d near roots and openings) in %.1f s' % (len(ob.data.vertices), boosted, time.time() - t0))
        decimate_to(ob, BUDGET, 'imp')
    elif n_rem * 2 > BUDGET:
        decimate_to(ob, BUDGET)
    out = bmesh.new()
    out.from_mesh(ob.data)
    bmesh.ops.triangulate(out, faces=out.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bpy.data.meshes.remove(ob.data)
    return out, n_rem


def fuse_roots(bm, picks):
    """the tutorial's last step: expand round each junction and smooth with the volume kept (no shrinking)"""
    bm.verts.ensure_lookup_table()
    kd = KDTree(len(bm.verts))
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()
    band = set()
    for pk in picks:
        rad = 1.6 * pk['r'] + 0.08
        for (co, i, d) in kd.find_range(pk['pt'], rad):
            band.add(bm.verts[i])
    band = list(band)
    for _ in range(5):
        bmesh.ops.smooth_laplacian_vert(bm, verts=band, lambda_factor=0.5, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    return len(band)


def transfer(dst, src):
    """materials, collide, Calcite/Tip/Tip2 from the mesh before the remesh (nearest face, barycentric)"""
    src.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(src)
    names = ('Calcite', 'Tip', 'Tip2')
    s_layers = [src.verts.layers.float_color.get(n) for n in names]
    s_coll = src.faces.layers.int.get('collide')
    d_layers = [dst.verts.layers.float_color.get(n) or dst.verts.layers.float_color.new(n) for n in names]
    d_coll = dst.faces.layers.int.get('collide') or dst.faces.layers.int.new('collide')
    for v in dst.verts:
        co, nrm, fi, dist = tree.find_nearest(v.co)
        if fi is None:
            continue
        f = src.faces[fi]
        ws = []
        for u in f.verts:
            ws.append(1.0 / max((u.co - co).length, 1e-5))
        tot = sum(ws)
        for sl, dl in zip(s_layers, d_layers):
            if sl is None:
                continue
            val = sum(u[sl][0] * w for u, w in zip(f.verts, ws)) / tot
            v[dl] = (val, val, val, 1.0)
    for f in dst.faces:
        co, nrm, fi, dist = tree.find_nearest(f.calc_center_median())
        if fi is None:
            continue
        sf = src.faces[fi]
        f.material_index = sf.material_index
        f[d_coll] = sf[s_coll] if s_coll is not None else 1
        if f.material_index == MAT_GLOW:
            f.material_index = MAT_EARTH


def finish_surface(dst):
    uvl = dst.loops.layers.uv.verify()
    col = dst.loops.layers.color.get('Col') or dst.loops.layers.color.new('Col')
    dst.normal_update()
    for f in dst.faces:
        box_uv(f, uvl)
        c = {MAT_EARTH: EARTH_COL, MAT_WOOD: WOOD_COL}.get(f.material_index, GROUND_COL)
        for l in f.loops:
            l[col] = c


# ---------------------------------------------------------------------------------------------------------------------

# W2: the asset's parameters, shape and overrides (W2_overrides.py), selected with W2_ASSET=<key>
exec(compile(open(os.path.join(_HERE5, 'W2_overrides.py'), encoding='utf-8').read(), 'W2_overrides.py', 'exec'), globals())
t_all = time.time()
piece, objs, water, img, stats, V2 = assemble2(P)
lod, utm = objs[0], objs[1]
me = lod.data
sockets = piece.sockets + piece.fades
t0 = time.time()
if os.environ.get('W2_NOPLUG', '0') != '1':
    plug_floor_slits(me)
else:
    print('floor repair (plug_floor_slits) skipped: W2_NOPLUG=1')
rem_src, keep, why = split_for_remesh(me, sockets)
print('split:', why)


def debug_column(bm_, label):
    """CAVE_DEBUG_COL="x,y": print the vertical hit column of a mesh at that spot (leak hunting)"""
    spec_ = os.environ.get('CAVE_DEBUG_COL')
    if not spec_:
        return
    cx_, cy_ = [float(v) for v in spec_.split(',')]
    tr_ = BVHTree.FromBMesh(bm_)
    for dx_, dy_ in ((0.0, 0.0), (-0.5, 0.0), (0.5, 0.0), (0.0, -0.5), (0.0, 0.5)):
        hits_, o_ = [], Vector((cx_ + dx_, cy_ + dy_, 40.0))
        for _ in range(14):
            h_ = tr_.ray_cast(o_, Vector((0, 0, -1)))
            if h_[0] is None:
                break
            hits_.append((round(h_[0].z, 2), 'U' if h_[1].z > 0 else 'D'))
            o_ = h_[0] + Vector((0, 0, -0.005))
        print('DEBUGCOL %s (%+.1f,%+.1f): %s' % (label, dx_, dy_, hits_))


_bm_full = bmesh.new()
_bm_full.from_mesh(me)
debug_column(_bm_full, 'full mesh (shell+formations+stubs) before the split')
if os.environ.get('CAVE_DEBUG_COL'):
    _cx, _cy = [float(v) for v in os.environ['CAVE_DEBUG_COL'].split(',')]
    _bnd = [e for e in _bm_full.edges if len(e.link_faces) == 1]
    _near = [e for e in _bnd if abs(e.verts[0].co.x - _cx) < 3 and abs(e.verts[0].co.y - _cy) < 3 and e.verts[0].co.z < 3]
    print('DEBUGCOL full mesh: %d boundary edges in total, %d near the spot (z<3)' % (len(_bnd), len(_near)), [tuple(round(c, 2) for c in e.verts[0].co) for e in _near[:6]])
    _nm = [e for e in _bm_full.edges if len(e.link_faces) > 2]
    print('DEBUGCOL full mesh: %d non-manifold edges' % len(_nm))
    _fl = [f for f in _bm_full.faces if abs(f.calc_center_median().x - _cx) < 0.6 and abs(f.calc_center_median().y - _cy) < 0.6 and f.calc_center_median().z < 3]
    print('DEBUGCOL faces within 0.6 m of the spot (z<3):', len(_fl), 'material idx', sorted(set(f.material_index for f in _fl)), 'z range', (round(min(f.calc_center_median().z for f in _fl), 2), round(max(f.calc_center_median().z for f in _fl), 2)) if _fl else None)
_bm_full.free()
debug_column(rem_src, 'before remesh')
print('world UVs on %d kept formations' % world_uv_kept(keep))
merged, n_vox = remesh_object(rem_src, P['name'] + '_rem', P['_picks'], sockets, BVHTree.FromBMesh(V2))
print('remesh: %d voxel quads, %d triangles after decimation, %.1f s' % (n_vox, len(merged.faces), time.time() - t0))
debug_column(merged, 'after remesh+decimation')
band = fuse_roots(merged, P['_picks'])
transfer(merged, rem_src)
finish_surface(merged)
rem_src.free()
# join the remeshed surface with the parts kept exact
tmp_m = bpy.data.meshes.new('tmp_merged')
merged.to_mesh(tmp_m)
merged.free()
tmp_k = bpy.data.meshes.new('tmp_keep')
keep.to_mesh(tmp_k)
keep.free()
final = bmesh.new()
final.from_mesh(tmp_m)
final.from_mesh(tmp_k)
w2_retag(final)
bpy.data.meshes.remove(tmp_m)
bpy.data.meshes.remove(tmp_k)
me.clear_geometry()                 # keeps the material slots; to_mesh keeps each face's material index
final.to_mesh(me)
for p_ in me.polygons:
    p_.use_smooth = p_.material_index in (MAT_EARTH, MAT_GLOW)
# collider: the touchable inner surface, decimated (W2: the outer skin is dropped)
n_coll_full, _n_coll = w2_collider(final, utm, lod)
final.free()
ok, open_edges, facing = verify(piece, lod)
stats.update(dict(fill=P.get('_fill_stats'), merge='voxel remesh', voxel=VOX, split=why, voxel_quads=n_vox, fused_band_verts=band,
                  tris_lod0=len(me.polygons), tris_collider=len(utm.data.polygons), catalog_facing_ok=facing,
                  opening_profile_points_found=ok, open_edges_lod0=open_edges, build_s=round(time.time() - t_all, 1)))
print(json.dumps(stats))
json.dump(stats, open(os.path.join(OUTDIR, 'W2_stats_%s.json' % P['name']), 'w'), indent=1)

mat, bsdf = preview_materials(img)
warm_up_materials()
if shape.dug:
    _md = bpy.data.materials.get('TT_EarthDug') or bpy.data.materials.new('TT_EarthDug')
    _md.diffuse_color = (0.30, 0.22, 0.15, 1)
    for _o in (lod, utm):
        while len(_o.data.materials) < 5:
            _o.data.materials.append(_md)
_w = bpy.data.materials['TT_Water']
_wn = next(n for n in _w.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
_wn.inputs['Alpha'].default_value = 1.0
_wn.inputs['Base Color'].default_value = (0.012, 0.02, 0.022, 1)
_wn.inputs['Roughness'].default_value = 0.02
water.data.materials.append(_w)
if os.environ.get('CAVE_BLEND', '1') == '1':
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, 'W2_' + P['name'] + '_v5.blend'))
if RENDER:
    set_glow(bsdf, 0.0)
    WELD = True                                   # close-up file tag: these are the merged ones
    if os.environ.get('CAVE_VIEWS', 'all') == 'close':
        setup_render(RES)
        for o_ in bpy.data.objects:
            if o_.type == 'EMPTY' or o_.name.startswith('UTM_'):
                o_.hide_render = True
        print('CLOSEUPS', closeups(P, lod, water))
    else:
        _sg = set_glow
        set_glow = lambda b, s: _sg(b, 0.0 if s == 1.0 else s)
        render_room(P, lod, water, bsdf)
        _sg(bsdf, 0.0)
        extra_views(P, lod, water)
        print('CLOSEUPS', closeups(P, lod, water))
print('DONE')
