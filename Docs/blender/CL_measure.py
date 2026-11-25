"""TT tunnel kit: clearance measurement on the EXPORTED FBX files (the engine's collider is the UTM_ mesh = the LOD0 mesh).
Reusable: standing, crouch (TT_C_*), prone (TT_P_*), transitions, any variant suffix (_A, _C ...).

Run (headless):
  set CL_DIR=<folder with the .fbx>   (default: the addon's Assets/Tunnels/TT)
  set CL_OUT=<json path>               (default: Docs/blender/previews/CL_measure.json next to this script's previews folder)
  set CL_ONLY=TT_Straight_4,TT_Turn90  (optional: only file names containing one of these)
  set CL_JOINTS=0                      (optional: skip the joint tests)
  blender --factory-startup -b --python Docs/blender/CL_measure.py

What it measures, per piece, on the final mesh, along the walking route (every 0.1 m; routes rebuilt from the plan geometry
of tunnelkit_build.py, so they hold for every variant of a shape: same plan, same sockets):
  * clear height: from the floor up to the roof, straight up/down at the route centre and 0.3 m to each side
  * clear width: wall to wall (rays +-right) at several heights above the floor (S: 0.2..1.4 m, C: 0.15..1.2, P: 0.1..0.55);
    also the width at head height (S 1.7 m) separately: the roof is arched, a head needs less
  * split into zones: joint (within 0.5 m of an opening along the route), doorway (chambers: the 0.5 .. 1.3 m behind a
    door), body (the rest). Chamber interiors measure height only.
  * floor: steepest step between neighbouring samples after removing the nominal slope, and the floor's spread
Also: LOD0 versus UTM_ collider identical?, open / non-manifold edges, sockets (position, outward direction, error against the
horizontal axis), and with CL_JOINTS: every socket joined to a copy of the piece's own other socket (and to every other
variant of the same shape in the folder): clearance across the joint (+-1 m), floor step, ring mismatch.
"""
import bpy, bmesh, math, os, json, sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
DIR = os.environ.get('CL_DIR', os.path.join(ADDON, 'Assets', 'Tunnels', 'TT'))
OUT = os.environ.get('CL_OUT', os.path.join(ADDON, 'Docs', 'blender', 'previews', 'CL_measure.json'))
ONLY = [s for s in os.environ.get('CL_ONLY', '').split(',') if s]
JOINTS = os.environ.get('CL_JOINTS', '1') != '0'
Z = Vector((0, 0, 1))
TURN_RADIUS = 1.8
ZF = {'S': [0.35, 0.5, 0.8, 1.1, 1.4], 'C': [0.25, 0.4, 0.7, 1.0], 'P': [0.15, 0.25, 0.4, 0.55]}
HEAD = {'S': 1.7, 'C': 1.45, 'P': 0.8}
MID = {'S': 0.9, 'C': 0.7, 'P': 0.4}


# --------------------------------------------------------------------------------------------------------- plan paths
def smooth(t):
    return t * t * (3 - 2 * t)


def d_smooth(t):
    return 6 * t * (1 - t)


def p_straight(length, step=0.1):
    n = max(1, math.ceil(length / step))
    return [(Vector((0, length * i / n, 0)), Vector((0, 1, 0))) for i in range(n + 1)]


def p_arc(radius, degrees=90, steps=60):
    out = []
    for i in range(steps + 1):
        a = math.radians(degrees) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    return out


def p_chicane(radius, across, right=True, steps=40):
    out = []
    for i in range(steps + 1):
        a = math.radians(90) * i / steps
        out.append((Vector((radius - radius * math.cos(a), radius * math.sin(a), 0)), Vector((math.sin(a), math.cos(a), 0))))
    n = max(1, math.ceil(across / 0.1))
    for i in range(1, n + 1):
        out.append((Vector((radius + across * i / n, radius, 0)), Vector((1, 0, 0))))
    for i in range(1, steps + 1):
        b = math.radians(90) * i / steps
        out.append((Vector((radius + across + radius * math.sin(b), 2 * radius - radius * math.cos(b), 0)), Vector((math.cos(b), math.sin(b), 0))))
    if not right:
        out = [(Vector((-p.x, p.y, p.z)), Vector((-t.x, t.y, t.z))) for p, t in out]
    return out


def p_slope(length, rise, steps=80):
    return [(Vector((0, length * i / steps, rise * smooth(i / steps))), Vector((0, 1, 0))) for i in range(steps + 1)]


def resample(samples, step=0.1):
    """a polyline of (pos, tangent) every `step` m"""
    out = []
    for (a, ta), (b, tb) in zip(samples[:-1], samples[1:]):
        n = max(1, math.ceil((b - a).length / step))
        for k in range(n):
            t = k / n
            tan = ta * (1 - t) + tb * t
            out.append((a + (b - a) * t, Vector((tan.x, tan.y, 0)).normalized()))
    out.append((samples[-1][0].copy(), Vector((samples[-1][1].x, samples[-1][1].y, 0)).normalized()))
    return out


SLOPE_RISE = {'S': 1.2, 'C': 1.0, 'P': 0.8}


def classify(name):
    """(size class, base shape) from a file stem: TT_C_Straight_4 -> ('C', 'Straight_4'); TT_Straight_4_A -> ('S', 'Straight_4')"""
    n = name[3:]
    if name.startswith('TT_Trans_'):
        return 'T', n
    cls = 'S'
    if n.startswith('C_'):
        cls, n = 'C', n[2:]
    elif n.startswith('P_'):
        cls, n = 'P', n[2:]
    for suf in ('_A', '_B', '_C', '_D'):
        if n.endswith(suf) and not n.endswith('_C_C'):
            # Dogleg_L / Curve_5 etc. never end in these, so a trailing _A/_C is a variant
            n = n[:-2]
            break
    return cls, n


def routes_for(name, sockets):
    """[(class, [(pos, tangent)], kind)] kind 'corridor' | 'chamber'. Sockets: [(floor pos, outward)] from the FBX."""
    cls, base = classify(name)
    out = []
    if cls == 'T':
        s = p_straight(3.0)
        parts = {'Trans_S_C': [('S', 0.0, 0.9), ('C', 1.8, 3.0)], 'Trans_C_P': [('C', 0.0, 1.0), ('P', 1.8, 3.0)],
                 'Trans_S_P': [('S', 0.0, 0.55), ('P', 2.45, 3.0)]}[base]
        for c, y0, y1 in parts:
            out.append((c, [(p, t) for p, t in s if y0 - 1e-6 <= p.y <= y1 + 1e-6], 'corridor'))
        return out
    if base.startswith('Straight_'):
        L = {'1': 1.0, '2': 2.0, '4': 4.0, 'Narrow': 4.0, 'Wide': 5.0}[base.split('_', 1)[1]]
        out.append((cls, p_straight(L), 'corridor'))
    elif base.startswith('Curve_'):
        a = int(base.split('_')[1])
        out.append((cls, resample(p_arc(4.0 / math.radians(a), a)), 'corridor'))
    elif base == 'Turn90':
        out.append((cls, resample(p_arc(TURN_RADIUS)), 'corridor'))
    elif base == 'Turn90_Wide':
        out.append((cls, resample(p_arc(3.0)), 'corridor'))
    elif base.startswith('Dogleg_'):
        out.append((cls, resample(p_chicane(TURN_RADIUS, 1.0, base.endswith('R'))), 'corridor'))
    elif base == 'Slope':
        out.append((cls, resample(p_slope(4.0, SLOPE_RISE[cls])), 'corridor'))
    elif base == 'End':
        out.append((cls, p_straight(0.7), 'corridor'))
    elif base == 'Entry_Horizontal':
        out.append((cls, p_straight(5.0), 'corridor'))
    elif base == 'Entry_Incline':
        p0 = sockets[0][0]
        pts = [(p0 + Vector((0, y, 0)), Vector((0, 1, 0))) for y in [i * 0.1 for i in range(0, 11)]]
        pts += [(p0 + Vector((0, 1.0 + d, d)), Vector((0, 1, 0))) for d in [i * 0.1 for i in range(1, 41)]]
        out.append((cls, pts, 'incline'))
    elif base in ('Junction', 'Room'):
        centre = Vector((0, 0, 0))
        for i in range(len(sockets)):
            for j in range(i + 1, len(sockets)):
                pts = []
                for k in (i, j):
                    pos, o = sockets[k]
                    pts.append(pos)
                    pts.append(pos - o * 1.2)       # the wall plane (stub 0.6 + wall 0.6)
                    if k == i:
                        pts.append(centre)
                # socket i -> wall i -> centre -> wall j -> socket j
                a = [sockets[i][0], sockets[i][0] - sockets[i][1] * 1.2, centre, sockets[j][0] - sockets[j][1] * 1.2, sockets[j][0]]
                line = []
                for u, v in zip(a[:-1], a[1:]):
                    n = max(1, math.ceil((v - u).length / 0.1))
                    t = (v - u).normalized()
                    line += [(u + (v - u) * (k / n), t) for k in range(n)]
                line.append((a[-1], (a[-1] - a[-2]).normalized()))
                out.append((cls, line, 'chamber'))
    return out


# ------------------------------------------------------------------------------------------------------------ loading
def import_fbx(path):
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path)
    return [bpy.data.objects[k] for k in bpy.data.objects.keys() if k not in before]


def world_tris(obj, matrix=None):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    m = obj.matrix_world if matrix is None else matrix @ obj.matrix_world
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def tree_of(bm):
    return BVHTree.FromBMesh(bm)


def load_piece(path):
    name = os.path.splitext(os.path.basename(path))[0]
    objs = import_fbx(path)
    lod = [o for o in objs if o.type == 'MESH' and 'LOD0' in o.name]
    utm = [o for o in objs if o.type == 'MESH' and o.name.startswith('UTM_')]
    # earlier pieces still loaded make the importer name them "1.001" ...: sort on the number before the dot
    sock = sorted([o for o in objs if o.type == 'EMPTY' and o.name.split('.')[0].isdigit()], key=lambda o: int(o.name.split('.')[0]))
    return dict(name=name, objs=objs, lod=lod[0] if lod else None, utm=utm[0] if utm else None, sock=sock)


def sockets_of(piece, mp_height):
    res = []
    for e in piece['sock']:
        mw = e.matrix_world
        out = mw.to_3x3() @ Vector((0, 0, 1))
        res.append((Vector(mw.translation) - Z * mp_height, out))
    return res


def remove(piece):
    for o in piece['objs']:
        d = o.data
        bpy.data.objects.remove(o)
        if d is not None and hasattr(d, 'vertices') and d.users == 0:
            bpy.data.meshes.remove(d)


# ----------------------------------------------------------------------------------------------------------- measuring
def zone_of(kind, line, idx, socks):
    pos = line[idx][0]
    ds = min(((pos.x - s.x) ** 2 + (pos.y - s.y) ** 2) ** 0.5 for s, _ in socks) if socks else 9
    if kind == 'corridor':
        # along the route from either end
        a = sum((line[i + 1][0] - line[i][0]).length for i in range(idx))
        tot = sum((line[i + 1][0] - line[i][0]).length for i in range(len(line) - 1))
        return 'joint' if (a <= 0.5 + 1e-6 or tot - a <= 0.5 + 1e-6) else 'body'
    if ds <= 0.5 + 1e-6:
        return 'joint'
    if ds <= 1.15:
        return 'doorway'
    return 'chamber'


def measure(tree, cls, route, socks):
    cls_r, line, kind = route
    zs = ZF[cls_r]
    mid = MID[cls_r]
    res = {}
    # precompute cumulative arc for corridor zones (cheap enough)
    arc = [0.0]
    for i in range(len(line) - 1):
        arc.append(arc[-1] + (line[i + 1][0] - line[i][0]).length)
    tot = arc[-1]
    floors = []
    for idx, (pos, tan) in enumerate(line):
        right = tan.cross(Z).normalized()
        if kind in ('corridor', 'incline') and tot > 0.5 and (arc[idx] < 0.03 or tot - arc[idx] < 0.03):
            continue                       # exactly in the open end plane the rays graze the rim: not a measurement
        if kind == 'chamber' and socks and min(((pos.x - s_.x) ** 2 + (pos.y - s_.y) ** 2) ** 0.5 for s_, _ in socks) < 0.03:
            continue                       # in the open end plane
        if kind == 'incline':
            # the shaft is cut by the ground at the top (pivot z 0): the roof is gone there, nothing to measure
            if pos.z > -2.4:
                continue
            zone = 'joint' if arc[idx] <= 0.5 + 1e-6 else 'body'
        elif kind == 'corridor':
            zone = 'joint' if (arc[idx] <= 0.5 + 1e-6 or tot - arc[idx] <= 0.5 + 1e-6) else 'body'
        else:
            zone = zone_of(kind, line, idx, socks)
        zones = [zone]
        if kind == 'corridor' and tot >= 3.2 and min(arc[idx], tot - arc[idx]) >= 1.5:
            zones.append('mid')            # the middle of a piece (1.5 m from each end): where the variants differ
        recs = [res.setdefault(z_, dict(h=1e9, hb=1e9, w=1e9, wh=1e9, wmax=0.0, hmax=0.0, at={})) for z_ in zones]
        floor_c = None
        tilt = kind == 'incline' and (pos.z - line[0][0].z) > 0.05
        nvec = Vector((0, -1, 1)).normalized()            # the stairs' normal (45 degrees): the headroom is measured square to the slope
        for off in (0.0, -0.3, 0.3):
            if tilt:
                o = pos + right * off + nvec * 0.3            # clear of the steps (their treads stand up to 0.25 above the nose line)
                hit = tree.ray_cast(o, nvec, 30.0)[0]
                if hit is None:
                    if off == 0.0:
                        floor_c = pos.z
                    continue                  # near the bottom the square ray leaves through the entrance: no roof to measure
                h = (hit - o).length + 0.3
                if off == 0.0:
                    floor_c = pos.z
                    upv = tree.ray_cast(pos + right * 0.0071 + tan * 0.0137 + Z * 0.4, Z, 30.0)[0]          # vertical headroom over the highest tread of the step
                    if os.environ.get('CL_DEBUG'):
                        print('UPV', [round(x, 2) for x in pos], upv and [round(x, 2) for x in upv], flush=True)
                    if upv is not None:
                        for r in recs:
                            r['hv'] = min(r.get('hv', 1e9), round(upv.z - pos.z - 0.25, 3))
                    for r in recs:
                        r['hmax'] = max(r['hmax'], h)
                        if h < r['h']:
                            r['h'], r['at']['h'] = h, [round(x, 2) for x in pos]
                else:
                    for r in recs:
                        if h < r['hb']:
                            r['hb'], r['at']['hb'] = h, [round(x, 2) for x in pos]
                continue
            q = pos + right * off + tan * 0.0137 + right * 0.0071 + Z * mid        # off the mesh's edges: a ray exactly along one can slip through
            up = tree.ray_cast(q, Z, 30.0)
            dn = tree.ray_cast(q, -Z, 30.0)
            h = 0.0 if (up[0] is None or dn[0] is None) else up[0].z - dn[0].z
            if off == 0.0:
                floor_c = None if dn[0] is None else dn[0].z
                for r in recs:
                    r['hmax'] = max(r['hmax'], h)
                    if h < r['h']:
                        r['h'], r['at']['h'] = h, [round(x, 2) for x in pos]
            else:
                for r in recs:
                    if h < r['hb']:
                        r['hb'], r['at']['hb'] = h, [round(x, 2) for x in pos]
        floors.append((zone, floor_c, pos.z))
        if floor_c is None or zone == 'chamber':
            continue
        for zf, key in [(z, 'w') for z in zs] + [(HEAD[cls_r], 'wh')]:
            q = Vector((pos.x, pos.y, floor_c + zf)) + tan * 0.0137
            a_ = tree.ray_cast(q, right, 6.0)
            b_ = tree.ray_cast(q, -right, 6.0)
            w = 0.0 if (a_[0] is None or b_[0] is None) else (a_[0] - b_[0]).length
            if w == 0.0 and os.environ.get('CL_DEBUG'):
                print('WDBG', [round(x, 2) for x in pos], round(zf, 2), 'right', [round(x, 2) for x in right], 'hits', a_[0] and [round(x, 2) for x in a_[0]], b_[0] and [round(x, 2) for x in b_[0]], flush=True)
            for r in recs:
                if key == 'w' and zf == zs[min(2, len(zs) - 1)]:
                    r['wmax'] = max(r['wmax'], w)
                if w < r[key]:
                    r[key] = w
                    r['at'][key] = ([round(x, 2) for x in pos], round(zf, 2))
    # floor: step between neighbours after removing the nominal height; deviation from nominal
    fl = {}
    for i in range(1, len(floors)):
        z0, f0, n0 = floors[i - 1]
        z1, f1, n1 = floors[i]
        if f0 is None or f1 is None:
            continue
        step = abs((f1 - n1) - (f0 - n0))
        e = fl.setdefault(z1, dict(step=0.0, dev_min=1e9, dev_max=-1e9))
        e['step'] = max(e['step'], step)
        e['dev_min'] = min(e['dev_min'], f1 - n1)
        e['dev_max'] = max(e['dev_max'], f1 - n1)
    for z, r in res.items():
        r.update({k: round(v, 3) for k, v in fl.get(z, {}).items()})
        for k in ('h', 'hb', 'w', 'wh'):
            r[k] = None if r[k] > 1e8 else round(r[k], 3)
        r['wmax'], r['hmax'] = round(r['wmax'], 3), round(r['hmax'], 3)
    return res


def merge_zones(parts):
    out = {}
    for res in parts:
        for z, r in res.items():
            o = out.setdefault(z, dict(r))
            if o is r:
                continue
            for k in ('h', 'hb', 'w', 'wh'):
                if r.get(k) is not None and (o.get(k) is None or r[k] < o[k]):
                    o[k] = r[k]
                    o['at'][k] = r['at'].get(k)
            o['wmax'] = max(o.get('wmax', 0), r.get('wmax', 0))
            o['hmax'] = max(o.get('hmax', 0), r.get('hmax', 0))
            o['step'] = max(o.get('step', 0), r.get('step', 0))
            o['dev_min'] = min(o.get('dev_min', 9), r.get('dev_min', 9))
            o['dev_max'] = max(o.get('dev_max', -9), r.get('dev_max', -9))
    return out


def open_top(hit):
    """The incline's open top: the shaft's footprint on the ground plane, with slack (the mouth of an entry has no such limit)"""
    return abs(hit.x) < 2.4 and -5.0 < hit.y < 5.0


def piece_leaks(tree, routes, socks, extra, mid):
    """Rays from the void along the routes, random directions: an escape must leave through an opening (a socket's plane, or the
    extra ones: an entry's mouth / top). Returns (rays, leaks)"""
    import random
    rng = random.Random(11)
    planes = [(p, o, 4.0) for p, o in socks] + list(extra)
    rays = leaks = 0
    for cls_r, line, kind in routes:
        for idx in range(4, len(line) - 3, 5):
            pos = line[idx][0]
            o = pos + Z * (mid + rng.uniform(-0.1, 0.4))
            if any(l < 0 for _, _, l in extra) and o.z > -0.3:
                continue                      # above the ground cut of the incline: not inside any more
            for _ in range(60):
                d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
                rays += 1
                if tree.ray_cast(o, d, 300.0)[0] is not None:
                    continue
                ok = False
                for pp, oo, lim in planes:
                    dn = d.dot(oo)
                    if dn <= 1e-6:
                        continue
                    t = (pp - o).dot(oo) / dn
                    if t < 0:
                        continue
                    hit = o + d * t
                    if (lim > 0 and ((hit - pp) - oo * (hit - pp).dot(oo)).length < lim) or (lim < 0 and open_top(hit)):
                        ok = True
                        break
                if not ok:
                    leaks += 1
    return rays, leaks


def closedness(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    open_e = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    multi = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    vol = 0.0
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        for i in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    n = len(obj.data.polygons)
    bm.free()
    return dict(tris=n, open_edges=open_e, multi_edges=multi, signed_volume=round(vol, 2))


def lod_vs_utm(piece):
    a, b = piece['lod'], piece['utm']
    if a is None or b is None:
        return dict(ok=False, why='missing')
    if len(a.data.vertices) != len(b.data.vertices) or len(a.data.polygons) != len(b.data.polygons):
        return dict(ok=False, why='different counts', lod=len(a.data.vertices), utm=len(b.data.vertices))
    d = max(((a.matrix_world @ v1.co) - (b.matrix_world @ v2.co)).length for v1, v2 in zip(a.data.vertices, b.data.vertices))
    return dict(ok=d < 1e-5, max_dev=round(d, 7))


def materials_of(piece):
    me = piece['lod'].data
    used = {}
    for p in me.polygons:
        used[p.material_index] = used.get(p.material_index, 0) + 1
    return {(me.materials[i].name if i < len(me.materials) and me.materials[i] else str(i)): n for i, n in used.items()}


# ------------------------------------------------------------------------------------------------------------- joints
def join_matrix(pos_a, out_a, pos_b, out_b):
    th = math.atan2(-out_a.y, -out_a.x) - math.atan2(out_b.y, out_b.x)
    R = Matrix.Rotation(th, 4, 'Z')
    return Matrix.Translation(pos_a - R @ pos_b) @ R


def joint_test(pa, ia, sa, pb, ib, sb, cls_a):
    pos_a, out_a = sa[ia]
    pos_b, out_b = sb[ib]
    M = join_matrix(pos_a, out_a, pos_b, out_b)
    bm = world_tris(pa['lod'])
    bm2 = world_tris(pb['lod'], M)
    # ring mismatch: a fan of rays in the joint plane (0.005 m inside each piece), from the axis: the distance to the void's wall
    # in piece A against the same in piece B (each alone). Identical rings give 0
    right = out_a.cross(Z).normalized()
    ta, tb = tree_of(bm), tree_of(bm2)
    mid = {'S': 0.9, 'C': 0.7, 'P': 0.4}.get(cls_a, 0.9)
    worst = 0.0
    for k in range(120):
        ang = 2 * math.pi * k / 120 + 0.0087
        d = right * math.cos(ang) + Z * math.sin(ang)
        oa = pos_a + right * 0.0137 + Z * mid - out_a * 0.005        # off the axis: a ray exactly along a mesh edge can slip through
        ob = pos_a + right * 0.0137 + Z * mid + out_a * 0.005
        ha = ta.ray_cast(oa, d, 6.0)[0]
        hb = tb.ray_cast(ob, d, 6.0)[0]
        if ha is None or hb is None:
            continue
        dd = abs((ha - oa).length - (hb - ob).length)
        if dd > 0.05 and os.environ.get('CL_DEBUG'):
            print('RINGDBG', pa['name'], ia + 1, pb['name'], 'ang', k * 3, 'ha', [round(x, 3) for x in ha], 'hb', [round(x, 3) for x in hb], 'oa', [round(x, 3) for x in oa], 'out', [round(x, 3) for x in out_a], flush=True)
        worst = max(worst, dd)
    # how far each piece's sleeve reaches past the joint plane into the partner
    def reach(b, sign):
        return max(((v.co - pos_a).dot(out_a) * sign for v in b.verts
                    if abs((v.co - pos_a).dot(out_a)) < 1.0 and ((v.co - pos_a) - out_a * (v.co - pos_a).dot(out_a)).length < 2.5), default=0.0)
    reach_a, reach_b = reach(bm, 1.0), reach(bm2, -1.0)
    # the other openings of the pair (to tell light leaking through a gap from rays leaving through an opening)
    free = [(p, o, 2.6) for i, (p, o) in enumerate(sa) if i != ia] + [(M @ p, (M.to_3x3() @ o).normalized(), 2.6) for i, (p, o) in enumerate(sb) if i != ib]
    if 'Entry_Incline' in pa['name']:
        free.append((Vector((0, 0, 0)), Vector((0, 0, 1)), -1.0))          # the shaft's open top (pivot on the ground)
    me = bpy.data.meshes.new('CL_pair')
    bm2.to_mesh(me)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    tree = tree_of(bm)
    bm.free()
    bm2.free()
    # route along the axis through the joint, +-0.5 m (bends curve away further out)
    line = [(pos_a + out_a * (-0.5 + 0.05 * i), out_a) for i in range(21)]
    cl = cls_a if cls_a in ZF else 'S'
    r = measure(tree, cl, (cl, line, 'corridor'), [])
    # the zone logic marks +-0.5 of the two ends: for this short route everything within 0.5 of the ends is 'joint', the middle 'body';
    # take the whole thing as one
    merged = merge_zones([r])
    allv = dict(h=min(z['h'] for z in merged.values()), hb=min(z['hb'] for z in merged.values()),
                w=min(z['w'] for z in merged.values()), wh=min(z['wh'] for z in merged.values()),
                step=max(z.get('step', 0) for z in merged.values()))
    # light: random rays from the void round the joint; one that escapes must leave through a free opening of the pair
    import random
    rng = random.Random(7)
    leaks = 0
    for k in range(400):
        o = pos_a + out_a * rng.uniform(-0.6, 0.6) + right * rng.uniform(-0.3, 0.3) + Z * rng.uniform(0.5, 1.2)
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        if tree.ray_cast(o, d, 200.0)[0] is not None:
            continue
        ok = False
        for p, oo, lim in free:
            dn = d.dot(oo)
            if dn <= 1e-6:
                continue
            t = (p - o).dot(oo) / dn
            if t < 0:
                continue
            hit = o + d * t
            lat = ((hit - p) - oo * (hit - p).dot(oo)).length
            if (lim > 0 and lat < lim) or (lim < 0 and open_top(hit)):
                ok = True
                break
        if not ok:
            leaks += 1
    return dict(leaks_of_400=leaks, reach_a=round(reach_a, 3), reach_b=round(reach_b, 3), **dict(a=pa['name'], sock_a=ia + 1, b=pb['name'], sock_b=ib + 1, ring_mismatch=round(worst, 5), **{k: round(v, 3) for k, v in allv.items()}))


# ----------------------------------------------------------------------------------------------------------------- run
def main():
    files = sorted(f for f in os.listdir(DIR) if f.lower().endswith('.fbx'))
    if ONLY:
        files = [f for f in files if any(s in f for s in ONLY)]
    pieces = {}
    result = dict(dir=DIR, pieces=[], joints=[])
    for f in files:
        path = os.path.join(DIR, f)
        pc = load_piece(path)
        cls, base = classify(pc['name'])
        mp = {'S': 1.0, 'C': 0.8, 'P': 0.475, 'T': 1.0}[cls]
        socks_mp = sockets_of(pc, mp)
        if cls == 'T':
            # transitions: socket 1 is size A, socket 2 size B: heights differ; floors are all at z 0
            a, b = pc['name'].split('_')[2:4]
            hs = {'S': 1.0, 'C': 0.8, 'P': 0.475}
            socks = [(Vector((e.matrix_world.translation.x, e.matrix_world.translation.y, e.matrix_world.translation.z - hs[k])),
                      e.matrix_world.to_3x3() @ Vector((0, 0, 1))) for e, k in zip(pc['sock'], (a, b))]
        else:
            socks = socks_mp
        pc['socks'], pc['cls'], pc['base'] = socks, cls, base
        pc['scls'] = [pc['name'].split('_')[2], pc['name'].split('_')[3]] if cls == 'T' else [cls] * len(socks)
        bm = world_tris(pc['utm'] or pc['lod'])
        tree = tree_of(bm)
        bm.free()
        parts = []
        routes = routes_for(pc['name'], socks)
        for rt in routes:
            parts.append(measure(tree, cls, rt, socks))
        zones = merge_zones(parts)
        extra = []
        if pc['base'] == 'Entry_Horizontal':
            extra = [(Vector((0, 0, 0)), Vector((0, -1, 0)), 5.0)]
        elif pc['base'] == 'Entry_Incline':
            extra = [(Vector((0, 0, 0)), Vector((0, 0, 1)), -1.0)]
        rays, leaks = piece_leaks(tree, routes, socks, extra, MID[cls if cls in MID else 'S'])
        info = dict(light=dict(rays=rays, leaks=leaks), name=pc['name'], cls=cls, closed=closedness(pc['lod']), lod_vs_utm=lod_vs_utm(pc), materials=materials_of(pc),
                    zones=zones, sockets=[dict(pos=[round(x, 4) for x in p], out=[round(x, 4) for x in o],
                                               up_error_deg=round(math.degrees(math.asin(min(1.0, abs(o.z) / max(o.length, 1e-9)))), 4))
                                          for p, o in socks])
        result['pieces'].append(info)
        pieces[pc['name']] = pc
        print(pc['name'], json.dumps({z: (v['h'], v['hb'], v['w'], v['wh']) for z, v in zones.items()}), flush=True)
    if JOINTS:
        for name, pc in pieces.items():
            if pc['cls'] == 'T' or pc['lod'] is None or pc['base'] in ('Junction', 'Room', 'Entry_Incline', 'Entry_Horizontal', 'End'):
                continue
            n = len(pc['socks'])
            for i in range(n):
                j = 0 if i != 0 else (1 if n > 1 else 0)
                if n == 1:
                    continue
                result['joints'].append(joint_test(pc, i, pc['socks'], pc, j, pc['socks'], pc['cls']))
            # every other variant of the same shape (same class and base), socket 2 of one onto socket 1 of the other
            for other, po in pieces.items():
                if other == name or po['cls'] != pc['cls'] or po['base'] != pc['base'] or n != 2:
                    continue
                result['joints'].append(joint_test(pc, 1, pc['socks'], po, 0, po['socks'], pc['cls']))
        # every opening of every piece against the plain straight 2 of its size
        for name, pc in pieces.items():
            for i in range(len(pc['socks'])):
                pn = {'S': 'TT_Straight_2', 'C': 'TT_C_Straight_2', 'P': 'TT_P_Straight_2'}[pc['scls'][i]]
                if pn in pieces and pn != name:
                    part = pieces[pn]
                    result['joints'].append(joint_test(pc, i, pc['socks'], part, 0, part['socks'], pc['scls'][i]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as fh:
        json.dump(result, fh, indent=1)
    print('measure ->', OUT)


main()
