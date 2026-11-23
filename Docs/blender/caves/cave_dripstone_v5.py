"""Dripstone rooms, v5: a real geometry merge. The room shell, the formations and the boulders are voxel-remeshed into
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
_V4 = os.path.join(_HERE5, 'cave_dripstone_v4.py')
_src4 = open(_V4, encoding='utf-8').read().split("\npiece, objs, water, img, stats, V2 = assemble2(P)")[0]
# low-poly formations (5 sides or fewer): 3 fillet rings instead of 6, 2 body rings instead of 4+
_a = "    fil = [f * (1 - math.cos(k / 6 * math.pi / 2)) for k in range(1, 7)] if f > 0 else []"
assert _src4.count(_a) == 1
_src4 = _src4.replace(_a, "    _nf = 3 if sides <= 5 else 6\n    fil = [f * (1 - math.cos(k / _nf * math.pi / 2)) for k in range(1, _nf + 1)] if f > 0 else []")
_a = "        nb = max(4, s['rings'] - 4)"
assert _src4.count(_a) == 1
_src4 = _src4.replace(_a, "        nb = 2 if s['sides'] <= 5 else max(4, s['rings'] - 4)")
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
            any(math.hypot(x - b['x'], y - b['y']) < b['r'] * 1.1 for b in P['_basins'])

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
        specs.append(dict(kind='stalactite', x=x, y=y, L=L, r=r, down=True, collide=False, sides=5, rings=4,
                          bend=rng.uniform(-0.01, 0.01), seed=rng.randint(0, 10 ** 6)))
        taken_c.append((x, y, r))
        n_ok += 1
        # below it: a small stalagmite about half the time, otherwise a drip mound shaped into the floor
        if in_water(x, y) or rng.random() < 0.1:
            continue
        fx, fy = x + rng.gauss(0, 0.03), y + rng.gauss(0, 0.03)
        H = min(L * math.exp(rng.gauss(math.log(0.7), 0.5)), 0.3, span - L - 0.4)
        on_path = path_dist(fx, fy) < 0.55
        if not on_path and H > 0.04 and rng.random() < 0.5 and free(taken_f, fx, fy, r * 1.4, 0.03):
            specs.append(dict(kind='stalagmite', x=fx, y=fy, L=H, r=max(0.015, H / rng.uniform(1.8, 2.8)), down=False,
                              collide=False, sides=5, rings=4, bend=0.0, seed=rng.randint(0, 10 ** 6)))
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
        near_joint = any((ctr - pos).length < 2.2 for pos, out in sockets)
        if not is_form and near_joint:
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


def remesh_object(src_bm, name):
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
    if n_rem * 2 > BUDGET:              # quads -> triangles after decimation
        d = ob.modifiers.new('dec', 'DECIMATE')
        d.ratio = BUDGET / (n_rem * 2.0)
        d.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        me3 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        old = ob.data
        ob.data = me3
        bpy.data.meshes.remove(old)
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

t_all = time.time()
piece, objs, water, img, stats, V2 = assemble2(P)
lod, utm = objs[0], objs[1]
me = lod.data
sockets = piece.sockets + piece.fades
t0 = time.time()
rem_src, keep, why = split_for_remesh(me, sockets)
print('split:', why)
merged, n_vox = remesh_object(rem_src, P['name'] + '_rem')
print('remesh: %d voxel quads, %d triangles after decimation, %.1f s' % (n_vox, len(merged.faces), time.time() - t0))
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
bpy.data.meshes.remove(tmp_m)
bpy.data.meshes.remove(tmp_k)
me.clear_geometry()                 # keeps the material slots; to_mesh keeps each face's material index
final.to_mesh(me)
for p_ in me.polygons:
    p_.use_smooth = p_.material_index in (MAT_EARTH, MAT_GLOW)
# collider: the touchable part, decimated
cb = final.copy()
cl = cb.faces.layers.int.get('collide')
if cl is not None:
    bmesh.ops.delete(cb, geom=[f for f in cb.faces if f[cl] == 0], context='FACES')
utm.data.clear_geometry()
cb.to_mesh(utm.data)
cb.free()
final.free()
n_coll_full = len(utm.data.polygons)
if n_coll_full > COLL_TARGET:
    md = utm.modifiers.new('dec', 'DECIMATE')
    md.ratio = COLL_TARGET / n_coll_full
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me_c = bpy.data.meshes.new_from_object(utm.evaluated_get(dg))
    utm.modifiers.clear()
    old = utm.data
    utm.data = me_c
    bpy.data.meshes.remove(old)
ok, open_edges, facing = verify(piece, lod)
stats.update(dict(fill=P.get('_fill_stats'), merge='voxel remesh', voxel=VOX, split=why, voxel_quads=n_vox, fused_band_verts=band,
                  tris_lod0=len(me.polygons), tris_collider=len(utm.data.polygons), catalog_facing_ok=facing,
                  opening_profile_points_found=ok, open_edges_lod0=open_edges, build_s=round(time.time() - t_all, 1)))
print(json.dumps(stats))
json.dump(stats, open(os.path.join(OUTDIR, 'stats_%s_v5.json' % P['name']), 'w'), indent=1)

mat, bsdf = preview_materials(img)
warm_up_materials()
_w = bpy.data.materials['TT_Water']
_wn = next(n for n in _w.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
_wn.inputs['Alpha'].default_value = 1.0
_wn.inputs['Base Color'].default_value = (0.012, 0.02, 0.022, 1)
_wn.inputs['Roughness'].default_value = 0.02
water.data.materials.append(_w)
if os.environ.get('CAVE_BLEND', '1') == '1':
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, P['name'] + '_v5.blend'))
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
