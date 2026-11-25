"""Dripstone rooms, v2: more detail on the floor and the ceiling, closer to real show caves.
Builds on cave_dripstone_room.py (exec'd for its helpers; nothing there is changed) and replaces:
  - shell resolution: voxel 0.12 m, then floor edges cut to FLOOR_EDGE and ceiling edges to CEIL_EDGE
  - ceiling: bedding-plane ledges, botryoidal knobs (two sizes), joint cracks (groove + calcite crust)
  - walls: fluted flowstone, ledges, knobs
  - floor: flowstone mounds, rimstone dam terraces (gours, scalloped lips, water per terrace), talus, pools
  - formations: carrot stalactites with straw tips, rows of stalactites and soda straws along the cracks,
    domed and ringed stalagmites, candle stalagmites, fluted columns, curtains (draperies), breakdown boulders
Run: blender --factory-startup -b --python cave_dripstone_v2.py   (env as the base script; CAVE_OUT = output folder)
"""
import os, math, random, time, json
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get('CAVE_BASE', os.path.join(_HERE, 'NR_room.py'))
_base = open(BASE, encoding='utf-8').read().split("\nif MODE == 'library':")[0]
exec(compile(_base, BASE, 'exec'), globals())

# ---------------------------------------------------------------------------------------------------------------------
# Settings

FLOOR_EDGE = float(os.environ.get('CAVE_FLOOR_EDGE', '0.07'))
CEIL_EDGE = float(os.environ.get('CAVE_CEIL_EDGE', '0.085'))
WALL_EDGE = float(os.environ.get('CAVE_WALL_EDGE', '0.18'))
GOUR_EDGE = float(os.environ.get('CAVE_GOUR_EDGE', '0.045'))
ATLAS_W, ATLAS_H = 1024, 1024
COLS, ROWS = ATLAS_W // TILE_W, ATLAS_H // TILE_H

COMMON = dict(voxel=0.12,
              ledge_amp=0.07, ledge_step=0.55,
              knob_amp=0.13, knob_r=0.42, knob2_amp=0.07, knob2_r=0.17,
              crack_depth=0.05, crust=0.05, cracks=4, crack_len=(1.8, 3.4), crack_density=10.0, straw_share=0.45,
              mound_amp=0.10, mound_r=0.75,
              gours=1, gour_R=(1.2, 1.8), gour_steps=5, gour_h=0.14, gour_lip=0.14,
              hero=4, curtains=2, boulders=2, candles=2)
EXTRA = {
    'A': dict(),
    'B': dict(cracks=6, crack_density=13.0, ledge_amp=0.09, knob_amp=0.10, hero=2, curtains=1, gours=1, boulders=3),
    'C': dict(gours=3, gour_R=(1.2, 1.9), gour_steps=6, cracks=3, curtains=1, hero=3, pools=1),
    'D': dict(curtains=5, cracks=3, ribs=0.22, ledge_amp=0.05, hero=3, gours=0),
    'E': dict(cracks=16, crack_len=(4.0, 9.0), crack_density=9.0, crack_depth=0.07, ledge_amp=0.10, ledge_step=0.9,
              knob_amp=0.16, knob_r=0.6, mound_r=1.1, mound_amp=0.14, gours=5, gour_R=(2.0, 3.2), gour_steps=7,
              gour_h=0.16, gour_lip=0.16, hero=18, curtains=7, boulders=22, candles=8, col_span=14.0, len_scale=1.8,
              floor_big=0.45, boulder_big=1.4, floor_grain=0.04, floor_step=0.07, bulge_amp=0.2, cluster_scale=2.2, cluster_p=0.75),
    'G': dict(cracks=4, crack_len=(2.0, 4.0), crack_density=9.0, knob_amp=0.1, hero=1, curtains=1, boulders=2, candles=1, gours=0,
              floor_big=0.06, bulge_amp=0.1, cluster_scale=1.0, col_span=4.5),
    'H': dict(cracks=3, crack_len=(1.5, 3.0), crack_density=11.0, hero=2, curtains=2, boulders=1, candles=3, gours=1, gour_R=(0.8, 1.2), gour_steps=4,
              floor_big=0.05, bulge_amp=0.1, cluster_scale=0.9, col_span=5.0),
    'I': dict(cracks=4, crack_len=(2.0, 4.5), crack_density=9.0, hero=3, curtains=1, boulders=3, candles=2, gours=1, gour_R=(1.0, 1.5), gour_steps=4,
              floor_big=0.12, bulge_amp=0.14, cluster_scale=1.4, col_span=6.0),
    # the crawl chamber: nothing may hang or stand where a prone body goes (formations only above 1.3 m, never on the routes)
    'F': dict(cracks=2, crack_len=(1.5, 3.0), crack_density=8.0, knob_amp=0.05, hero=0, curtains=0, boulders=0, scallop=0.06, candles=0, gours=0,
              floor_big=0.09, bulge_amp=0.05, cluster_scale=0.6, col_span=2.0, knob2_amp=0.03, ledge_amp=0.03),
}
P = dict(VARIANTS[VARIANT])
P.update(COMMON)
P.update(EXTRA.get(VARIANT, {}))
P['name'] = P.get('asset') or ('TT_Room_Drip_' + VARIANT)
P['_off'] = Vector((random.Random(P['seed']).uniform(-90, 90), random.Random(P['seed'] + 1).uniform(-90, 90),
                    random.Random(P['seed'] + 2).uniform(-90, 90)))
PIECE_KEEP = []
# ---- NR hooks (new rooms): defaults reproduce the old behaviour; NR_overrides.py replaces them ----
RHO = lambda x, y: math.sqrt((x / P['rx']) ** 2 + (y / P['ry']) ** 2)                 # 0 at the centre .. 1 at the wall (ellipse)
FLOORZ = lambda x, y: P.get('slope', 0.0) * y                                         # floor height before shaping (formations probe from above it)
FLOORV = lambda x, y: P.get('slope', 0.0) * y                                         # the same for numpy arrays
EXCLUDE = lambda x, y: False                                                          # no formations here (e.g. above a water-filled bore)
WATERMASK = lambda x, y: False                                                        # floor under water: no floor formations
WMASK = lambda c: 1.0                                                                 # scale of the wall/ceiling/floor roughening (a smooth bore)
COLL_TARGET = int(os.environ.get('CAVE_COLL_TARGET', '20000'))


def voro(q):
    """F1 distance of Blender's voronoi noise (one feature point per unit cell)"""
    return noise.voronoi(q)[0][0]


# ---------------------------------------------------------------------------------------------------------------------
# Planning before the shell is roughened: cracks (ceiling) and gour terraces (floor)

def plan_cracks(P):
    rng = random.Random(P['seed'] * 17 + 9)
    cracks = []
    for k in range(P['cracks'] * 3):
        if len(cracks) >= P['cracks']:
            break
        a = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.random()) * 0.55
        x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
        hd = rng.uniform(0, 2 * math.pi)
        L = rng.uniform(*P['crack_len'])
        step = 0.12
        p = Vector((x, y, 0)) - Vector((math.cos(hd), math.sin(hd), 0)) * L * 0.5
        h = hd
        pts = []
        for i in range(int(L / step) + 1):
            if (p.x / P['rx']) ** 2 + (p.y / P['ry']) ** 2 < 0.8:
                pts.append(p.copy())
            h += rng.gauss(0, 0.16)
            p = p + Vector((math.cos(h), math.sin(h), 0)) * step
        if len(pts) >= 6:
            cracks.append(pts)
    P['_cracks'] = cracks


def crack_dist(x, y):
    q = Vector((x, y, 0))
    best = 9.0
    for pts in P['_cracks']:
        # cheap reject on the crack's bounding box
        for i in range(0, len(pts) - 1):
            a = pts[i]
            if abs(a.x - x) > 0.6 or abs(a.y - y) > 0.6:
                continue
            best = min(best, seg_dist(q, a, pts[i + 1]))
    return best


def plan_gours(P):
    rng = random.Random(P['seed'] * 13 + 5)
    gours = []
    tries = 0
    while len(gours) < P['gours'] and tries < 600:
        tries += 1
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.38, 0.62)
        x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
        R = rng.uniform(*P['gour_R'])
        if path_dist(x, y) < R * 0.3 + 0.25:
            continue
        if any(math.hypot(x - g['x'], y - g['y']) < R + g['R'] for g in gours):
            continue
        if any(math.hypot(x - b['x'], y - b['y']) < R + b['r'] + 0.2 for b in P['_basins']):
            continue
        d = a + math.pi + rng.uniform(-0.5, 0.5)          # downhill = from the wall into the room
        steps = P['gour_steps']
        gours.append(dict(x=x, y=y, R=R, dx=math.cos(d), dy=math.sin(d), steps=steps, ds=2 * R / steps,
                          h=P['gour_h'] * rng.uniform(0.8, 1.2), lip=P['gour_lip'] * rng.uniform(0.8, 1.25),
                          seed=rng.uniform(0, 100)))
    P['_gours'] = gours


def gour_eval(g, x, y):
    """(dz, mask, terrace z) of one terrace field at (x, y)"""
    ux, uy = x - g['x'], y - g['y']
    q = math.hypot(ux, uy) / g['R']
    q *= 1 + 0.18 * noise.noise(Vector((x * 0.8, y * 0.8, g['seed'])))
    mask = smooth(clamp01((1 - q) / 0.3))
    if mask <= 0:
        return 0.0, 0.0, 0.0, False
    mask *= smooth(clamp01((path_dist(x, y) - 0.45) / 0.6))
    # distance from a source point uphill (outside the field): the dams are nested crescents opening uphill
    sx, sy = g['x'] - g['dx'] * g['R'] * 1.6, g['y'] - g['dy'] * g['R'] * 1.6
    rr_ = math.hypot(x - sx, y - sy)
    ang = math.atan2(y - sy, x - sx)
    s = rr_ - g['R'] * 1.6
    s += 0.10 * g['R'] * noise.noise(Vector((math.cos(ang) * 3.0, math.sin(ang) * 3.0, g['seed'] + 3)))   # lobes along each dam
    s += 0.12 * g['R'] * noise.noise(Vector((x * 1.1, y * 1.1, g['seed'] + 5))) + 0.03 * noise.noise(Vector((x * 6.0, y * 6.0, g['seed'] + 7)))
    t = (s + g['R']) / g['ds']
    idx = math.floor(t)
    f = t - idx
    inside = 0 <= idx < g['steps']
    zt = -min(max(idx, 0), g['steps'] - 1) * g['h']
    lip = 0.0
    ln = 0.8 + 0.2 * noise.noise(Vector((x * 6, y * 6, g['seed'] + 11)))
    if idx >= 0:
        lip = g['lip'] * math.exp(-((1 - f) / 0.12) ** 2) * ln
    fd = 0.22                                   # share of a terrace taken by the falling dam face below its lip
    if 1 <= idx < g['steps'] and f < fd:
        q = smooth(f / fd)
        lip += (g['h'] + g['lip'] * ln) * (1 - q) ** 1.6
    return mask * (zt + lip), mask, mask * zt, inside


def mounds(x, y):
    q = Vector((x, y, 0.37)) / P['mound_r'] + P['_off']
    b = smooth(clamp01(1 - voro(q) / 0.75))
    rho = RHO(x, y)
    wallness = smooth(clamp01((rho - 0.3) / 0.45))
    pm = smooth(clamp01((path_dist(x, y) - 0.55) / 0.8))
    m = 0.6 + 0.4 * noise.noise(Vector((x * 0.5, y * 0.5, 3.3)) + P['_off'])
    return P['mound_amp'] * (0.3 + 0.7 * wallness) * pm * m * b


def basin_z(b, x, y):
    dx, dy = x - b['x'], y - b['y']
    c, s = math.cos(b['rot']), math.sin(b['rot'])
    u, v = dx * c + dy * s, -dx * s + dy * c
    ang = math.atan2(v, u)
    k = 1 + 0.16 * noise.noise(Vector((math.cos(ang) * 2.2, math.sin(ang) * 2.2, b['x'] * 3.1))) \
          + 0.06 * noise.noise(Vector((math.cos(ang) * 6.0, math.sin(ang) * 6.0, b['y'] * 2.3)))
    rho = math.sqrt((u / b['r']) ** 2 + (v / (b['r'] * b['ar'])) ** 2) / k
    z = 0.0
    if rho < 1.0:
        z -= b['depth'] * (1 - rho * rho)
    z += b['lip'] * math.exp(-((rho - 1.0) / 0.2) ** 2)
    return z


def floor_field2(x, y):
    off = P['_off']
    rho = RHO(x, y)
    phi = math.atan2(y / P['ry'], x / P['rx'])
    side = 0.35 + 0.65 * (0.5 + 0.5 * noise.noise(Vector((math.cos(phi) * 1.4, math.sin(phi) * 1.4, 3.1)) + off))
    z = P['talus'] * side * smooth(clamp01((rho - 0.62) / 0.38))
    wallness = smooth(clamp01((rho - 0.55) / 0.35))
    keep_walk = smooth(clamp01((path_dist(x, y) - 1.2) / 2.2))
    z += keep_walk * wallness * P.get('bank', 0.55) * (0.5 + 0.5 * noise.noise(Vector((x * 0.16, y * 0.16, 1.7)) + off))
    z += keep_walk * P.get('swell', 0.25) * noise.noise(Vector((x * 0.07, y * 0.07, 4.1)) + off)
    z += P['relief'] * noise.noise(Vector((x * 0.3, y * 0.3, 0.0)) + off)
    taken = 0.0
    for b in P['_basins']:
        if not P.get('nr_nobasinz'):
            z += basin_z(b, x, y)
        dx, dy = x - b['x'], y - b['y']
        taken = max(taken, smooth(clamp01((b['r'] * 1.25 - math.hypot(dx, dy)) / 0.4)))
    for g in P['_gours']:
        dz, mask, _, _ = gour_eval(g, x, y)
        z += dz
        taken = max(taken, mask)
    z += mounds(x, y) * (1 - taken)
    free_ = 1 - taken
    wallness = smooth(clamp01((rho - 0.6) / 0.3))
    q = Vector((x, y, 0.0))
    fr = z / 0.03 + 0.4 * noise.noise(q * 2.0 + off)
    z += 0.012 * math.exp(-((1 - (fr - math.floor(fr))) / 0.25) ** 2) * free_       # micro-gours along the contours
    z += 0.035 * smooth(clamp01(1 - voro(q / 0.16 + off) / 0.55)) ** 1.5 * wallness * free_   # cobbles
    dv = noise.voronoi(q / 0.35 + off * 0.3)[0]
    z -= 0.012 * math.exp(-((dv[1] - dv[0]) / 0.15) ** 2) * (1 - wallness) * free_          # mud cracks
    for o in P['_open']:
        d = math.hypot(x - o['base'].x, y - o['base'].y)
        z *= smooth(clamp01((d - 0.9) / 2.4))
    return z


# ---------------------------------------------------------------------------------------------------------------------
# Fine shaping (replaces the base roughen_cave and the kit's refine through the names finish() looks up)

def refine(bm):
    """Floor and ceiling cut finer than the walls; nothing near the openings"""
    for _ in range(8):
        bm.normal_update()
        long = []
        for e in bm.edges:
            fs = [f for f in e.link_faces if f.material_index == MAT_EARTH]
            if not fs:
                continue
            L = e.calc_length()
            if L <= GOUR_EDGE:
                continue
            nz = sum(f.normal.z for f in fs) / len(fs)
            lim = FLOOR_EDGE if nz > 0.55 else (CEIL_EDGE if nz < -0.35 else WALL_EDGE)
            if nz > 0.3:
                mx, my = (e.verts[0].co.x + e.verts[1].co.x) * 0.5, (e.verts[0].co.y + e.verts[1].co.y) * 0.5
                if any(math.hypot(mx - g['x'], my - g['y']) < g['R'] * 1.3 for g in P['_gours']):
                    lim = GOUR_EDGE
            if L > lim and keep_exact((e.verts[0].co + e.verts[1].co) * 0.5, PIECE_KEEP) > 0:
                long.append(e)
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='BEAUTY')


def ledge(c):
    # bedding ledges: the course height wanders a lot and the strength comes and goes (no brickwork on a long wall)
    s = (c.z + 1.6 * P['ledge_step'] * noise.noise(Vector((c.x * 0.16, c.y * 0.16, c.z * 0.3)) + P['_off'])) / P['ledge_step']      # courses tilt and wave, never ruled lines
    f = s - math.floor(s)
    strength = 0.25 + 0.75 * (0.5 + 0.5 * noise.noise(c * 0.3 + P['_off'] * 0.7 + Vector((4.1, 2.7, 8.3))))
    return P['ledge_amp'] * strength * (smooth(clamp01(f / 0.8)) - 0.5)


def knobs(c, popcorn=True):
    off = P['_off']
    k1 = smooth(clamp01(1 - voro((c + off) / P['knob_r']) / 0.7)) ** 1.5
    k2 = smooth(clamp01(1 - voro((c + off * 1.7) / P['knob2_r']) / 0.7)) ** 1.5
    m = max(0.0, 0.5 + 0.6 * noise.noise(c * 0.4 + off))
    k3 = smooth(clamp01(1 - voro((c + off * 2.3) / 0.075) / 0.6))
    return P['knob_amp'] * k1 * m + P['knob2_amp'] * k2 + (0.022 * k3 if popcorn else 0.0)


def crack_sd(x, y):
    """signed distance to the nearest crack (sign: which side of it)"""
    q = Vector((x, y, 0))
    best, side = 9.0, 1.0
    for pts in P['_cracks']:
        for i in range(0, len(pts) - 1):
            a = pts[i]
            if abs(a.x - x) > 0.9 or abs(a.y - y) > 0.9:
                continue
            b = pts[i + 1]
            dd = seg_dist(q, a, b)
            if dd < best:
                best = dd
                side = 1.0 if ((b - a).x * (q - a).y - (b - a).y * (q - a).x) >= 0 else -1.0
    return best * side


def crack_field(x, y):
    sd = crack_sd(x, y)
    d = abs(sd)
    if d > 1.2:
        return 0.0
    groove = -0.07 * math.exp(-(d / 0.09) ** 2)
    step = 0.06 * smooth(clamp01((sd + 0.05) / 0.1)) * math.exp(-(d / 0.8) ** 2)     # one lip of the joint hangs lower
    return groove + step + P['crust'] * math.exp(-(d / 0.22) ** 2)


# ---- skirts: where a formation grows out of the rock, the rock itself swells to meet it (planned before shaping) ----
SKIRT_F = {}     # floor: grid cell -> [(x, y, radius, height)]
SKIRT_C = {}     # ceiling
SK_CELL = 0.5


def add_skirt(grid, x, y, rad, hgt):
    """A skirt is registered in every grid cell its disc (2.5 radii) touches, so a lookup only reads one cell"""
    reach = 2.5 * rad
    x0, x1 = int(math.floor((x - reach) / SK_CELL)), int(math.floor((x + reach) / SK_CELL))
    y0, y1 = int(math.floor((y - reach) / SK_CELL)), int(math.floor((y + reach) / SK_CELL))
    item = (x, y, rad, hgt)
    for i in range(x0, x1 + 1):
        for j in range(y0, y1 + 1):
            grid.setdefault((i, j), []).append(item)


def skirt_at(grid, x, y):
    """Sum of the skirts' bumps, each a Gaussian that reaches exactly 0 at 2.5 radii (no cut-off edges)"""
    items = grid.get((int(math.floor(x / SK_CELL)), int(math.floor(y / SK_CELL))))
    if not items:
        return 0.0
    tot, top = 0.0, 0.0
    floor_e = math.exp(-6.25)
    for (sx, sy, rad, hgt) in items:
        d2 = (x - sx) ** 2 + (y - sy) ** 2
        if d2 >= 6.25 * rad * rad:
            continue
        h = hgt * (math.exp(-d2 / (rad * rad)) - floor_e) / (1 - floor_e)
        tot += h
        top = max(top, hgt)
    if top <= 0:
        return 0.0
    cap = 1.5 * top
    return cap * math.tanh(tot / cap)


def roughen_cave2(bm, keep):
    bm.normal_update()
    off = P['_off']
    moves = []
    for v in bm.verts:
        inside = [f for f in v.link_faces if f.material_index == MAT_EARTH]
        if not inside or any(f.material_index == MAT_WOOD for f in v.link_faces):
            continue
        w = keep_exact(v.co, keep) * WMASK(v.co)
        if w <= 0:
            continue
        n = Vector()
        for f in inside:
            n += f.normal * f.calc_area()
        if n.length < 1e-9:
            continue
        n.normalize()
        c = v.co
        wf = smooth(clamp01((n.z - 0.45) / 0.3))
        wc = smooth(clamp01((-n.z - 0.2) / 0.35))
        ww = max(0.0, 1.0 - wf - wc)
        base = 0.6 * noise.noise(c * 0.5 + off) + 0.3 * noise.noise(c * 1.4 + off * 0.7) + 0.1 * noise.noise(c * 4.0 + off * 1.3)
        d = Vector()
        if wf > 0:
            dz = (floor_field2(c.x, c.y) + skirt_at(SKIRT_F, c.x, c.y) + 0.012 * base + 0.006 * noise.noise(c * 9.0 + off)
                  + P.get('floor_big', 0.0) * noise.noise(Vector((c.x * 0.13, c.y * 0.13, 0.0)) + off * 0.6)
                  + P.get('floor_grain', 0.0) * (noise.noise(Vector((c.x * 1.5, c.y * 1.5, 0.0)) + off * 0.3) + 0.5 * noise.noise(Vector((c.x * 4.0, c.y * 4.0, 0.0)) + off * 0.8))
                  + P.get('floor_step', 0.0) * smooth(clamp01((noise.noise(Vector((c.x * 0.22, c.y * 0.22, 0.0)) + off * 0.45) * 6.0) % 1.0)))      # shelves
            d += Vector((0, 0, dz * wf))
        if wc > 0 or ww > 0:
            kn = knobs(c)
            ld = ledge(c)
            sk = skirt_at(SKIRT_C, c.x, c.y)
            if wc > 0:
                head = 0.35 + 0.65 * smooth(clamp01((path_dist(c.x, c.y) - 0.8) / 0.9))
                vault = P.get('vault', 0.7) * noise.noise(c * 0.09 + off * 0.3)
                if vault > 0:
                    vault *= 0.5            # a sag, held back above all by `head` below
                scal = P.get('scallop', 0.0) * 1.2 * (0.5 - abs(noise.noise(c * 1.7 + off * 0.5)))      # flow scallops, ~0.5 m
                dc = 0.5 * base * P['wall_amp'] + kn * head + crack_field(c.x, c.y) + 0.6 * ld + scal * head - 1.0 * vault * (1.0 if vault < 0 else head)
                if dc > 0:
                    dc *= head
                d += n * ((dc + sk) * wc)
            if ww > 0:
                rib = 1.2 * (0.5 - abs(noise.noise(Vector((c.x * 2.0, c.y * 2.0, c.z * 0.35)) + off * 0.5)))
                # zones of ~10 m: smooth fluted flowstone sheets, ordinary rock, angular blocky rock; so no wall has one texture
                zone = noise.noise(c * 0.085 + off * 0.4)
                zs = smooth(clamp01((-zone - 0.04) / 0.18))             # flowstone sheet: quiet, with vertical flutes
                zb = smooth(clamp01((zone - 0.10) / 0.18))              # blocky: sharp creases
                bulge = P.get('bulge_amp', 0.8 * P['wall_amp']) * noise.noise(c * 0.13 + off * 0.9)       # ~8 m bulges and hollows
                flute = 0.07 * (0.5 - abs(noise.noise(Vector((c.x * 3.4, c.y * 3.4, c.z * 0.20)) + off * 0.8)))
                crease = 1.3 * (0.5 - abs(noise.noise(c * 0.75 + off * 0.3)))
                dw = (base * P['wall_amp'] * (0.55 - 0.4 * zs) + bulge + zs * flute + zb * 0.55 * P['wall_amp'] * crease
                      + rib * P['ribs'] * (1 - 0.6 * zs) + ld * (1 + 0.8 * zb) * (1 - 0.7 * zs)
                      + 0.3 * knobs(c, False) * (1 - zs) + 0.6 * sk)       # walls: no popcorn (the normal map has it)
                d += n * (dw * ww)
        moves.append((v, d * w))
    for v, dd in moves:
        v.co += dd
    bm.normal_update()


def calcite_mask(co, nz):
    """0 bare rock .. 1 calcite (flowstone): skirts, crack crusts, gour rims and pools, mounds"""
    x, y = co.x, co.y
    if nz > 0.3:
        m = skirt_at(SKIRT_F, x, y) / 0.06
        for g in P['_gours']:
            m = max(m, gour_eval(g, x, y)[1] * 1.2)
        m = max(m, mounds(x, y) / max(P['mound_amp'], 1e-6) * 0.5)
        for b in P['_basins']:
            m = max(m, smooth(clamp01((b['r'] * 1.25 - math.hypot(x - b['x'], y - b['y'])) / 0.4)))
    else:
        m = skirt_at(SKIRT_C, x, y) / 0.06
        dcr = crack_dist(x, y)
        m = max(m, math.exp(-(dcr / 0.25) ** 2) * 0.6)
        if nz > -0.2:
            m *= 0.6
    m += 0.15 * noise.noise(co * 1.7 + P['_off'])
    return clamp01(m)


roughen = roughen_cave2


# ---------------------------------------------------------------------------------------------------------------------
# Formations

def sides_for(r):
    return 14 if r > 0.12 else (10 if r > 0.05 else 7)


def speleothem2(kind, length, r, seed, tile, atlas, sides=8, rings=9, bend=0.0, bake=True):
    """Closed lathe solid along +Z (root at 0, buried EMBED m; tip at `length`).
    kind: stalactite | straw | stalagmite | candle | column. Material MAT_GLOW, UVs into atlas tile `tile`."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    e = EMBED / length
    info = {}
    ringv = []
    phase = rnd.uniform(0, 6.28)
    nflute = rnd.randint(6, 11)
    flute = rnd.uniform(0.05, 0.12)
    ring_n = rnd.uniform(5, 9)
    ring_amp = rnd.uniform(0.03, 0.08)
    tipr = min(r * 0.4, rnd.uniform(0.006, 0.01))
    mite_e = rnd.uniform(0.5, 0.95)                 # stalagmite top: 0.5 = blunt dome, 0.95 = pointed
    mite_blunt = mite_e < 0.7
    st_e = rnd.uniform(1.15, 2.3)                   # stalactite taper: low = tapers late (a rod), high = a cone
    waist = rnd.uniform(0.32, 0.68)                 # where a column is thinnest
    lump = 0.10 if kind == 'stalactite' else 0.14
    for i in range(rings):
        t = i / rings
        if kind == 'column':
            s = clamp01((t - e) / max(1 - 2 * e, 0.05))
            rad = r * (1 + 0.7 * (2 * abs(s - 0.5)) ** 2.2) * (1 + 0.10 * math.sin(s * 23 + phase))
            rad *= 1 + 0.5 * math.exp(-s / 0.08) + 0.5 * math.exp(-(1 - s) / 0.08)
        else:
            s = clamp01((t - e) / max(1 - e, 0.05))
            if kind == 'stalagmite':
                rad = r * max(0.0, 1 - s ** 2.4) ** 0.5
                rad *= 1 + ring_amp * (0.5 + 0.5 * math.sin(s * ring_n * 2 * math.pi + phase)) ** 3 * (1 - 0.6 * s)
                rad *= 1 + 1.0 * math.exp(-s / 0.10)
            elif kind == 'candle':
                rad = r * max(0.0, 1 - s ** 7) ** 0.45 * (1 + 0.06 * math.sin(s * 31 + phase))
                rad *= 1 + 0.7 * math.exp(-s / 0.08)
            elif kind == 'straw':
                rad = r * (1.35 if s > 0.88 else 1.0)
            else:
                rad = 1.3 * r * (1 - s) ** st_e * (1 + 0.05 * math.sin(s * 26 + phase) * (1 - s))
                rad = max(rad, tipr * (1.0 if s < 0.96 else 0.6))
                rad *= 1 + 0.9 * math.exp(-s / 0.07)
        cx = bend * math.sin(clamp01(t - e) * math.pi * 0.9)
        cy = bend * 0.4 * math.sin(clamp01(t - e) * math.pi * 1.3)
        row = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + 0.25 * t
            if kind == 'straw':
                rr = rad
            else:
                rr = rad * (1 + lump * noise.noise(Vector((math.cos(a), math.sin(a), t * 3.0)) * 1.3 + off))
                if kind == 'column':
                    rr *= 1 + flute * math.cos(nflute * a + 2.0 * s)
                elif r > 0.08:
                    rr *= 1 + 0.5 * flute * math.cos(nflute * a + 1.3 * s) * (1 - s)
            vt = bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), t * length))
            info[vt] = (k, i)
            row.append(vt)
        ringv.append(row)
    apex = None
    if kind != 'column':
        apex = bm.verts.new((bend * math.sin(clamp01(1 - e) * math.pi * 0.9), bend * 0.4 * math.sin(clamp01(1 - e) * math.pi * 1.3), length))
        info[apex] = (None, rings)
    for i in range(rings - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((ringv[i][k], ringv[i][k2], ringv[i + 1][k2], ringv[i + 1][k]))
    top = ringv[-1]
    if apex is not None:
        for k in range(sides):
            bm.faces.new((top[k], top[(k + 1) % sides], apex))
    else:
        bm.faces.new(list(reversed(top)))
    bm.faces.new(list(reversed(ringv[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    lathe_uvs(bm, uvl, info, sides, rings, tile)
    for f in bm.faces:
        f.material_index = MAT_GLOW
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    if bake and atlas is not None:
        bake_tile(bm, uvl, atlas, seed)
    return bm


def fillet_of(kind, r, Lvis):
    if kind == 'straw':
        return 0.0
    if kind == 'candle':
        return min(0.6 * r + 0.02, 0.08, 0.3 * Lvis)
    if kind == 'stalagmite':
        return min(0.8 * r + 0.03, 0.16, 0.35 * Lvis)
    return min(1.2 * r + 0.04, 0.26, 0.4 * Lvis)


def speleothem3(kind, Lvis, r, seed, tile, atlas, sides=8, n_body=9, bend=0.0, bake=True):
    """Closed lathe solid, root on the rock surface at the origin, growing along +Z to the tip at Lvis (a column: to its
    other root at Lvis). The part below 0 (above Lvis for a column) is buried. Near each root the radius grows by a
    tangent fillet of size f, so the side meets the rock flat instead of at a crease. Returns (bm, f)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    f = fillet_of(kind, r, Lvis)
    phase = rnd.uniform(0, 6.28)
    nflute = rnd.randint(6, 11)
    flute = rnd.uniform(0.05, 0.12)
    ring_n = rnd.uniform(5, 9)
    ring_amp = rnd.uniform(0.03, 0.08)
    tipr = min(r * 0.4, rnd.uniform(0.006, 0.01))
    mite_e = rnd.uniform(0.5, 0.95)                 # stalagmite top: 0.5 = blunt dome, 0.95 = pointed
    mite_blunt = mite_e < 0.7
    st_e = rnd.uniform(1.15, 2.3)                   # stalactite taper: low = tapers late (a rod), high = a cone
    waist = rnd.uniform(0.32, 0.68)                 # where a column is thinnest
    lump = 0.10 if kind == 'stalactite' else 0.14
    fil = [f * (1 - math.cos(k / 6 * math.pi / 2)) for k in range(1, 7)] if f > 0 else []
    small = sides <= 5                      # a cheap formation: buried 4 cm only, no cap under it (hidden in the rock)
    ds = [-0.04 if small else -EMBED, 0.0] + fil[:-1]
    start = f
    if kind == 'straw':
        ds = [-0.05, 0.0, Lvis * 0.88]                  # a thin tube: ~20 triangles
    elif kind == 'column':
        end = Lvis - f
        ds += [start + (end - start) * k / n_body for k in range(0, n_body + 1)]
        ds += [Lvis - x for x in reversed(fil[:-1])] + [Lvis, Lvis + EMBED]
    else:
        ds += [start + (Lvis - start) * k / n_body for k in range(0, n_body)]
        if kind == 'stalagmite' and not small and mite_blunt:
            ds += [Lvis * 0.955, Lvis * 0.99]
    rings = len(ds)

    def prof(s):
        if kind == 'column':
            u = (s - waist) / (waist if s < waist else (1 - waist))        # -1..0..1 around the waist
            return r * (0.8 + 1.15 * abs(u) ** 1.7) * (1 + 0.10 * math.sin(s * 23 + phase))
        if kind == 'stalagmite':
            # a rounded top (blunt ones are nearly domed), slender to sturdy, slightly irregular
            rad = r * (max(0.0, 1 - s) ** mite_e + 0.05 * (1 - s))
            return rad * (1 + 0.5 * ring_amp * (0.5 + 0.5 * math.sin(s * ring_n * 2 * math.pi + phase)) ** 3) * (1 + 0.10 * math.sin(s * 13 + phase))
        if kind == 'candle':
            return r * max(0.0, 1 - s ** 7) ** 0.45 * (1 + 0.06 * math.sin(s * 31 + phase))
        if kind == 'straw':
            return r * (1.35 if s > 0.88 else 1.0)
        rad = 1.3 * r * (1 - s) ** st_e * (1 + 0.05 * math.sin(s * 26 + phase) * (1 - s))
        return max(rad, tipr * (1.0 if s < 0.96 else 0.6))

    def ext(d):
        """the fillet's extra radius at distance d from the nearest root"""
        if f <= 0:
            return 0.0
        if d <= 0:
            return f
        if d >= f:
            return 0.0
        return f - math.sqrt(max(0.0, f * f - (f - d) ** 2))

    info = {}
    ringv = []
    for i, d in enumerate(ds):
        s = clamp01(d / Lvis)
        dn = d if kind != 'column' else min(d, Lvis - d)
        r0 = prof(s)
        e_ = ext(dn)
        t = s
        cx = bend * math.sin(s * math.pi * 0.9)
        cy = bend * 0.4 * math.sin(s * math.pi * 1.3)
        row = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + 0.25 * t
            if kind == 'straw':
                rr = r0
            else:
                rr = r0 * (1 + lump * noise.noise(Vector((math.cos(a), math.sin(a), t * 3.0)) * 1.3 + off))
                if kind == 'column':
                    rr *= 1 + flute * math.cos(nflute * a + 2.0 * s)
                elif r > 0.08:
                    rr *= 1 + 0.5 * flute * math.cos(nflute * a + 1.3 * s) * (1 - s)
                rr += e_ * max(0.4, 1 + 0.3 * noise.noise(Vector((math.cos(a), math.sin(a), 0.5)) * 1.2 + off) + 0.25 * math.cos(a - phase))
            vt = bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), d))
            info[vt] = (k, i)
            row.append(vt)
        ringv.append(row)
    apex = None
    if kind != 'column':
        apex = bm.verts.new((bend * math.sin(math.pi * 0.9), bend * 0.4 * math.sin(math.pi * 1.3), Lvis))
        info[apex] = (None, rings)
    for i in range(rings - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((ringv[i][k], ringv[i][k2], ringv[i + 1][k2], ringv[i + 1][k]))
    top = ringv[-1]
    if apex is not None:
        for k in range(sides):
            bm.faces.new((top[k], top[(k + 1) % sides], apex))
    else:
        bm.faces.new(list(reversed(top)))
    bm.faces.new(list(reversed(ringv[0])))                  # (3 triangles; a closed mesh is worth more than saving them)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    lathe_uvs(bm, uvl, info, sides, rings, tile)
    for fc in bm.faces:
        fc.material_index = MAT_GLOW
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    if bake and atlas is not None:
        bake_tile(bm, uvl, atlas, seed)
    return bm, f



def lathe_uvs(bm, uvl, info, sides, rings, tile):
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
            us.append(1.0 if (wraps and k == 0) else k / sides)
        known = [u for u in us if u is not None]
        mean = sum(known) / len(known) if known else 0.5
        for l, u in zip(f.loops, us):
            k, i = info[l.vert]
            uu = mean if u is None else u
            vv = 1.0 if k is None else i / rings
            l[uvl].uv = ((c0 + 0.04 + 0.92 * uu) / COLS, (r0 + 0.02 + 0.96 * vv) / ROWS)


def curtain(tree, x0, y0, heading, length, height, seed, tile, atlas, bake=True):
    """A drapery: a thin wavy sheet hanging from the ceiling along `heading`, bottom edge ragged. World coordinates."""
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6.28)
    dvec = Vector((math.cos(heading), math.sin(heading), 0))
    perp = Vector((-dvec.y, dvec.x, 0))
    nu = max(10, int(length / 0.04))
    nv = max(6, int(height / 0.07))
    wl = rnd.uniform(0.22, 0.34)
    tops, hs, cols = [], [], []
    last = None
    for i in range(nu + 1):                             # start from the first place the roof is found
        q_ = Vector((x0, y0, 0)) + dvec * (i / nu - 0.5) * length
        pr0 = probe(tree, q_.x, q_.y)
        if pr0:
            last = pr0[1]
            break
    for i in range(nu + 1):
        u = i / nu
        p = Vector((x0, y0, 0)) + dvec * (u - 0.5) * length
        pr = probe(tree, p.x, p.y)
        cz = pr[1] if pr else last
        if cz is None:
            return None
        last = cz
        hg = height * (0.15 + 0.85 * math.sin(math.pi * u) ** 0.8) * (1 + 0.18 * noise.noise(Vector((u * 2.0, seed * 0.01, 0.5))))
        hg *= 1 + 0.06 * math.sin(u * length / 0.09 * math.pi) ** 2      # small rounded scallops on the hem
        tops.append((p, cz))
        hs.append(hg)
    # the attachment line follows the roof, but smoothly (a running mean over ~0.2 m)
    raw = [cz for _, cz in tops]
    k = 3
    tops = [(tops[i][0], sum(raw[max(0, i - k):i + k + 1]) / len(raw[max(0, i - k):i + k + 1])) for i in range(len(tops))]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    F, B = [], []
    info = {}
    for i in range(nu + 1):
        u = i / nu
        p, cz = tops[i]
        fr, br = [], []
        for j in range(nv + 1):
            vv = j / nv
            z = cz + EMBED - vv * (hs[i] + EMBED)
            amp = 0.015 + 0.17 * vv ** 0.8
            fold = amp * (0.6 * math.sin(u * length / wl * 2 * math.pi + ph) + 0.3 * math.sin(u * length / (wl * 0.43) * 2 * math.pi + 2.1 * ph)
                          + 0.25 * noise.noise(Vector((u * 8, vv * 2, seed * 0.01))))
            th = 0.035 * (1.0 - 0.55 * vv) + 0.004 + 0.06 * max(0.0, 1.0 - vv / 0.14) ** 2
            ctr = Vector((p.x, p.y, z)) + perp * fold
            a = bm.verts.new(ctr + perp * th * 0.5)
            b = bm.verts.new(ctr - perp * th * 0.5)
            info[a] = (u, vv)
            info[b] = (u, vv)
            fr.append(a)
            br.append(b)
        F.append(fr)
        B.append(br)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((F[i][j], F[i + 1][j], F[i + 1][j + 1], F[i][j + 1]))
            bm.faces.new((B[i][j], B[i][j + 1], B[i + 1][j + 1], B[i + 1][j]))
    for i in range(nu):
        bm.faces.new((F[i][0], B[i][0], B[i + 1][0], F[i + 1][0]))
        bm.faces.new((F[i][nv], F[i + 1][nv], B[i + 1][nv], B[i][nv]))
    for j in range(nv):
        bm.faces.new((F[0][j], F[0][j + 1], B[0][j + 1], B[0][j]))
        bm.faces.new((F[nu][j], B[nu][j], B[nu][j + 1], F[nu][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    c0, r0 = tile
    for f in bm.faces:
        f.material_index = MAT_GLOW
        for l in f.loops:
            u, vv = info[l.vert]
            l[uvl].uv = ((c0 + 0.04 + 0.92 * u) / COLS, (r0 + 0.02 + 0.96 * vv) / ROWS)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    if bake and atlas is not None:
        bake_tile(bm, uvl, atlas, seed)
    return bm


def boulder(x, y, fz, size, seed):
    rnd = random.Random(seed)
    bm = bmesh.new()
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    except TypeError:
        bmesh.ops.create_icosphere(bm, subdivisions=3, diameter=1.0)
    sx, sy, sz = size, size * rnd.uniform(0.6, 1.0), size * rnd.uniform(0.4, 0.7)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    rot = rnd.uniform(0, 6.28)
    for v in bm.verts:
        d = v.co.normalized()
        # chunky: a few flattened facets from voronoi cells plus lumps
        f = 1 + 0.18 * noise.noise(d * 1.6 + off) + 0.07 * noise.noise(d * 4.0 + off)
        f -= 0.12 * smooth(clamp01(1 - voro(d * 1.4 + off) / 0.5))
        p = Vector((d.x * sx * f, d.y * sy * f, d.z * sz * f))
        p = Matrix.Rotation(rot, 3, 'Z') @ p
        v.co = p + Vector((x, y, fz + sz * 0.12))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.material_index = MAT_EARTH
    return bm


def probe_raw(tree, x, y, z0=1.0):
    """Floor and ceiling heights above (x, y), whatever way the surfaces face (for the void mesh before shaping)"""
    if EXCLUDE(x, y):
        return None
    z0 = z0 + FLOORZ(x, y)
    up = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, 1)))
    dn = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)))
    if up[0] is None or dn[0] is None:
        return None
    return dn[0].z, up[0].z


def probe_n(tree, x, y, z0=1.0):
    """Floor and ceiling of the finished shell with their normals (into the room)"""
    if EXCLUDE(x, y):
        return None
    z0 = z0 + FLOORZ(x, y)
    up = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, 1)))
    dn = tree.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)))
    if up[0] is None or dn[0] is None or up[1].z > -0.3 or dn[1].z < 0.3:
        return None
    return dn[0].z, up[0].z, dn[1].normalized(), up[1].normalized()


def plan_specs(P, void_bm):
    """Every formation's place, kind and size, decided on the unshaped void, so their skirts go into the shell"""
    tree = BVHTree.FromBMesh(void_bm)
    rng = random.Random(P['seed'] * 7 + 3)
    placed = {'c': [], 'f': []}
    specs = []
    curtains = []
    rocks = []
    used = []

    # formations grow in clusters (along cracks and drip lines), with bare stretches between them
    n_cl = max(3, int((P['stalactites'] + P['stalagmites'] + P['pairs'] * 2) / 9))
    clusters = []
    for k in range(n_cl):
        if P['_cracks'] and rng.random() < 0.6:
            pts = P['_cracks'][rng.randrange(len(P['_cracks']))]
            q = pts[rng.randrange(len(pts))]
            clusters.append((q.x, q.y, rng.uniform(0.7, 2.2) * P.get('cluster_scale', 1.0)))
        else:
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.random()) * 0.8
            clusters.append((rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a), rng.uniform(1.0, 3.2) * P.get('cluster_scale', 1.0)))

    def site(maxrho=0.82, need=1.6):
        for _ in range(80):
            if rng.random() < P.get('cluster_p', 0.7):
                cx, cy, cs = clusters[rng.randrange(len(clusters))]
                x, y = rng.gauss(cx, cs), rng.gauss(cy, cs)
                if (x / P['rx']) ** 2 + (y / P['ry']) ** 2 > maxrho ** 2:
                    continue
            else:
                a = rng.uniform(0, 2 * math.pi)
                rr = math.sqrt(rng.random()) * maxrho
                x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
            pr = probe_raw(tree, x, y)
            if pr and pr[1] - pr[0] > need:
                return x, y, pr[0], pr[1]
        return None

    def apart(x, y, r):
        # a stalagmite is not exactly below its stalactite: the drop splashes, the air moves
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.3, 1.6) * r + rng.uniform(0.0, 0.12)
        return x + d * math.cos(a), y + d * math.sin(a)

    def free(x, y, r, gap=0.25, where='cf'):
        return all(math.hypot(x - px, y - py) > r + pr + gap for w in where for px, py, pr in placed[w])

    def in_water(x, y):
        return any(gour_eval(g, x, y)[1] > 0.25 for g in P['_gours']) or \
            any(math.hypot(x - b['x'], y - b['y']) < b['r'] * 1.1 for b in P['_basins']) or WATERMASK(x, y)

    def spec(kind, x, y, L, r, down, collide, sides=None, rings=9, bend=0.0):
        specs.append(dict(kind=kind, x=x, y=y, L=L, r=r, down=down, collide=collide, sides=sides or sides_for(r),
                          rings=rings, bend=bend, seed=rng.randint(0, 10 ** 6)))
        for w in (('c', 'f') if kind == 'column' else (('c',) if down else ('f',))):
            placed[w].append((x, y, r))
        if kind == 'straw':
            return
        # a broad, low flowstone drape round the root; the formation's own fillet does the tangent join
        if kind in ('stalactite', 'column'):
            add_skirt(SKIRT_C, x, y, 3.4 * r + 0.16, min(0.35 * r + 0.02, 0.09))
        if kind in ('stalagmite', 'candle', 'column'):
            add_skirt(SKIRT_F, x, y, 2.4 * r + 0.1, min(0.16 * r + 0.012, 0.05))

    def lim_down(x, y, span):
        return span - 2.25 if path_dist(x, y) < 1.15 else span - 0.5

    for _ in range(P['columns']):
        for _try in range(40):
            s = site(0.68, 2.2)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            if span > P.get('col_span', 7.8) or path_dist(x, y) < P.get('col_clear', 1.4) or in_water(x, y):
                continue
            r = rng.uniform(0.12, 0.27) * (0.8 + 0.1 * span)
            if free(x, y, r * 1.9, 0.5):
                spec('column', x, y, span, r, False, True, sides=16, rings=28, bend=rng.uniform(-0.05, 0.05))
                break
    for _ in range(P['hero']):
        for _try in range(40):
            s = site(0.8, 2.4)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            if path_dist(x, y) < 1.3:
                continue
            L = min(rng.uniform(1.1, 2.6) * P.get('len_scale', 1.0), span - 0.7)
            if L < 0.8:
                continue
            r = L / rng.uniform(6.5, 12.0)
            if free(x, y, r * 1.6, 0.3, 'c'):
                spec('stalactite', x, y, L, r, True, (span - L) < 2.3, rings=20, bend=rng.uniform(-0.05, 0.05))
                if rng.random() < 0.6 and not in_water(x, y):
                    H = min(rng.uniform(0.25, 0.6) * span, span - L - 0.3)
                    if H > 0.25:
                        r2 = max(0.05, H / rng.uniform(3.4, 6.5))
                        x2, y2 = apart(x, y, r2)
                        if free(x2, y2, r2 * 1.2, 0.2, 'f') and path_dist(x2, y2) > 1.0:
                            spec('stalagmite', x2, y2, H, r2, False, True, rings=18)
                break
    for _ in range(P['pairs']):
        for _try in range(40):
            s = site(0.75, 2.8)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            if path_dist(x, y) < 1.0 or in_water(x, y):
                continue
            L1 = min(rng.uniform(0.3, 0.55) * span, lim_down(x, y, span))
            H = rng.uniform(0.12, 0.28) * span
            if span - L1 - H < 0.4:
                H = max(0.2, span - L1 - 0.4)
            r1, r2 = max(0.04, L1 / rng.uniform(4.5, 7)), max(0.045, H / rng.uniform(3.4, 6.0))
            if L1 > 0.3 and free(x, y, max(r1, r2) * 1.5):
                spec('stalactite', x, y, L1, r1, True, L1 > span - 2.3, rings=16, bend=rng.uniform(-0.04, 0.04))
                if rng.random() < 0.65:
                    x2, y2 = apart(x, y, r2)
                    if free(x2, y2, r2 * 1.2, 0.15, 'f') and path_dist(x2, y2) > 0.9 and not in_water(x2, y2):
                        spec('stalagmite', x2, y2, H, r2, False, True, rings=16)
                break
    for _ in range(P['curtains']):
        for _try in range(60):
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(0.55, 0.78)
            x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
            if path_dist(x, y) < 1.3:
                continue
            pr = probe_raw(tree, x, y)
            if not pr:
                continue
            span = pr[1] - pr[0]
            length = rng.uniform(1.2, 2.4)
            height = min(rng.uniform(0.6, 1.5), span - 0.7)
            if height < 0.4 or not free(x, y, length * 0.5, 0.2, 'c'):
                continue
            heading = a + rng.uniform(-0.35, 0.35)
            curtains.append(dict(x=x, y=y, heading=heading, length=length, height=height, a=a, seed=rng.randint(0, 10 ** 6)))
            placed['c'].append((x, y, length * 0.5))
            dv = Vector((math.cos(heading), math.sin(heading), 0))
            for k in range(int(length / 0.15) + 1):
                p = Vector((x, y, 0)) + dv * (k * 0.15 - length * 0.5)
                add_skirt(SKIRT_C, p.x, p.y, 0.22, 0.07)
            break
    for ci, pts in enumerate(P['_cracks']):
        n_here = 0
        dist = 0.0
        nxt = rng.uniform(0.0, 0.2)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            seg = (b - a).length
            while nxt <= dist + seg:
                u = (nxt - dist) / seg
                p = a.lerp(b, u)
                perp = Vector((-(b - a).y, (b - a).x, 0)).normalized()
                p = p + perp * rng.gauss(0, 0.04)
                nxt += rng.uniform(0.5, 1.5) / P['crack_density']
                pr = probe_raw(tree, p.x, p.y)
                if not pr:
                    continue
                span = pr[1] - pr[0]
                if rng.random() < P['straw_share']:
                    L = min(math.exp(rng.gauss(math.log(0.22), 0.5)), 0.7, lim_down(p.x, p.y, span))
                    r = rng.uniform(0.006, 0.009)
                    kind = 'straw'
                else:
                    L = min(math.exp(rng.gauss(math.log(0.25), 0.6)), 1.4, lim_down(p.x, p.y, span))
                    r = max(0.018, L / rng.uniform(5.0, 9.0))
                    kind = 'stalactite'
                if L < 0.06 or not free(p.x, p.y, r, 0.012, 'c'):
                    continue
                spec(kind, p.x, p.y, L, r, True, False if kind == 'straw' else (span - L) < 2.3,
                     rings=4 if kind == 'straw' else (8 if r < 0.05 else 12), bend=rng.uniform(-0.02, 0.02))
                n_here += 1
            dist += seg
        used.append((ci, n_here))
    # soda straws: dense rows a few centimetres apart along each crack
    for ci, pts in enumerate(P['_cracks']):
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            seg = (b - a).length
            perp = Vector((-(b - a).y, (b - a).x, 0)).normalized()
            u = rng.uniform(0, 0.05)
            while u < seg:
                p = a.lerp(b, u / seg) + perp * rng.gauss(0, 0.03)
                u += rng.uniform(0.035, 0.08)
                if rng.random() > 0.75:
                    continue
                pr = probe_raw(tree, p.x, p.y)
                if not pr:
                    continue
                span = pr[1] - pr[0]
                L = min(max(math.exp(rng.gauss(math.log(0.16), 0.55)), 0.05), 0.6, lim_down(p.x, p.y, span))
                if L < 0.05 or not free(p.x, p.y, 0.005, 0.004, 'c'):
                    continue
                spec('straw', p.x, p.y, L, rng.uniform(0.0045, 0.0065), True, False, sides=4, rings=4)
    for _ in range(P['stalactites']):
        for _try in range(40):
            s = site(0.85, 1.8)
            if not s:
                continue
            x, y, fz, cz = s
            span = cz - fz
            lo_, hi_ = P['len_st']
            L = min(lo_ * (hi_ / lo_) ** (rng.random() ** 1.7), lim_down(x, y, span))
            if L < min(0.2, lo_):
                continue
            r = max(0.03, L / rng.uniform(5, 12))
            if free(x, y, r * 1.3, 0.12, 'c'):
                spec('stalactite', x, y, L, r, True, (span - L) < 2.3, rings=12 if r < 0.08 else 16, bend=rng.uniform(-0.04, 0.04))
                break
    for _ in range(P['boulders']):
        for _try in range(40):
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(0.55, 0.86)
            x, y = rr * P['rx'] * math.cos(a), rr * P['ry'] * math.sin(a)
            if path_dist(x, y) < 0.9 or any(gour_eval(g, x, y)[1] > 0.25 for g in P['_gours']):
                continue
            size = rng.uniform(0.3, 0.7) * (1.0 + P.get('boulder_big', 0.0) * rng.random() ** 2)
            if free(x, y, size, 0.2, 'f'):
                rocks.append(dict(x=x, y=y, size=size, seed=rng.randint(0, 10 ** 6)))
                placed['f'].append((x, y, size))
                add_skirt(SKIRT_F, x, y, size * 1.25, 0.07)      # sediment and flowstone banked round it
                break
    for _ in range(P['stalagmites']):
        for _try in range(40):
            s = site(0.8, 2.0)
            if not s:
                continue
            x, y, fz, cz = s
            if path_dist(x, y) < 0.9 or in_water(x, y):
                continue
            H = min(rng.uniform(0.3, 1.2), cz - fz - 1.2)
            if H < 0.25:
                continue
            r = H / rng.uniform(3.4, 6.5) + 0.03
            if free(x, y, r * 1.3, 0.25, 'f'):
                spec('stalagmite', x, y, H, r, False, True, rings=16)
                # its drip source above: a stalactite (most of the time) or just a straw
                span = cz - fz
                Ls = min(rng.uniform(0.12, 0.55), lim_down(x, y, span), span - H - 0.4)
                if Ls > 0.06 and free(x, y, 0.02, 0.01, 'c'):
                    if rng.random() < 0.8:
                        spec('stalactite', x, y, Ls, max(0.02, Ls / rng.uniform(5.0, 8.0)), True, (span - Ls) < 2.3, rings=10)
                    else:
                        spec('straw', x, y, min(Ls, 0.4), rng.uniform(0.0045, 0.0065), True, False, sides=4, rings=4)
                break
    for _ in range(P['candles']):
        s = site(0.8, 2.0)
        if not s:
            continue
        x, y, fz, cz = s
        if path_dist(x, y) < 1.0 or in_water(x, y):
            continue
        for k in range(rng.randint(2, 4)):
            xx, yy = x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3)
            pr = probe_raw(tree, xx, yy)
            if not pr:
                continue
            H = min(rng.uniform(0.25, 0.85), pr[1] - pr[0] - 1.2)
            r = rng.uniform(0.035, 0.07)
            if H > 0.2 and free(xx, yy, r, 0.04, 'f'):
                spec('candle', xx, yy, H, r, False, True, sides=10, rings=14)
    # the drip rule: a deposit straight below every drip point
    drips = 0
    mounds_ = 0
    for s in list(specs):
        if not s['down'] or s['kind'] not in ('stalactite', 'straw'):
            continue
        x, y = s['x'], s['y']
        if any(o_['kind'] in ('stalagmite', 'candle', 'column') and math.hypot(o_['x'] - x, o_['y'] - y) < 0.12 for o_ in specs):
            continue                                    # already has one
        if rng.random() < 0.12:
            continue                                    # this drip mostly evaporates on the way: no deposit
        pr0 = probe_raw(tree, x, y)
        if not pr0:
            continue
        span = pr0[1] - pr0[0]
        fall = max(0.2, span - s['L'])
        # where it lands: splashes scatter more on a long fall, and the water runs on down a sloping floor
        e_ = 0.004
        gx = (floor_field2(x + e_, y) - floor_field2(x - e_, y)) / (2 * e_)
        gy = (floor_field2(x, y + e_) - floor_field2(x, y - e_)) / (2 * e_)
        slope = math.hypot(gx, gy)
        jit = min(0.03 + 0.02 * fall, 0.12)
        fx = x + max(-0.15, min(0.15, rng.gauss(0, jit))) - (gx / slope * min(0.25, 0.6 * slope) if slope > 1e-4 else 0.0)
        fy = y + max(-0.15, min(0.15, rng.gauss(0, jit))) - (gy / slope * min(0.25, 0.6 * slope) if slope > 1e-4 else 0.0)
        if in_water(fx, fy):
            continue                                    # drips into a pool: nothing grows
        on_path = path_dist(fx, fy) < 0.55
        # how much builds up below relative to above varies a lot (fast drips: little stalactite, big stalagmite)
        size = s['L'] if s['kind'] == 'stalactite' else 0.12
        ratio = math.exp(rng.gauss(math.log(0.75), 0.65))
        H = min(ratio * size, span - s['L'] - 0.35, 1.6)
        if not on_path and H > 0.08:
            if fall < 1.0 and H < 0.6 and rng.random() < 0.6:
                kind, r = 'candle', rng.uniform(0.03, 0.06)              # short fall: slim candle
            else:
                kind = 'stalagmite'
                flat = clamp01((fall - 1.5) / 3.0)                          # long fall: broad, flat "fried egg"
                r = max(0.04, H / rng.uniform(3.4, 6.0)) * (1 + 0.35 * flat)
                H *= 1 - 0.25 * flat
            if free(fx, fy, r * 1.15, 0.06, 'f'):
                spec(kind, fx, fy, H, r, False, True, sides=10 if kind == 'candle' else None, rings=14)
                drips += 1
                continue
        # small or crowded drip: a drip mound / splash cup in the floor itself, trailing downslope if it slopes
        hgt = min(0.012 + 0.07 * size * ratio, 0.07) * (0.35 if on_path else 1.0)
        rad = (0.06 + 0.12 * min(size, 1.0)) * (1 + 0.3 * clamp01((fall - 1.5) / 3.0))
        add_skirt(SKIRT_F, fx, fy, rad, hgt)
        if slope > 0.05:
            for k in (1, 2):
                add_skirt(SKIRT_F, fx - gx / slope * rad * 0.9 * k, fy - gy / slope * rad * 0.9 * k, rad * (1 - 0.2 * k), hgt * (0.6 - 0.2 * k))
        mounds_ += 1
    P['_drip_stats'] = dict(stalagmites_below=drips, drip_mounds=mounds_)
    return specs, curtains, rocks, used


def build_specs(P, shell_bm, specs, curtains_p, rocks_p, atlas):
    """The meshes, on the finished shell: lengths re-checked against the real floor and ceiling, root normals kept
    for blending the shading into the rock"""
    tree = BVHTree.FromBMesh(shell_bm)
    out = []         # (bm, matrix, collide, kind, roots) roots: [(point, axis_dir, surface_normal, blend_len)]
    rocks = []
    meta = dict(curtains=[])
    order = sorted(specs, key=lambda s: -s['r'] * max(s['L'], 0.1))   # big ones get their own glow tiles first
    for s in order:
        pr = probe_n(tree, s['x'], s['y'])
        if not pr:
            continue
        fz, cz, nf, nc = pr
        span = cz - fz
        kind = s['kind']
        L = s['L']
        if kind == 'column':
            L = span
        elif s['down']:
            lim = span - 2.25 if path_dist(s['x'], s['y']) < 1.15 else span - 0.5
            L = min(L, lim)
        else:
            L = min(L, span - 1.0)
        if L < 0.05:
            continue
        bake = False
        nb = max(4, s['rings'] - 4)
        bm, fil = speleothem3(kind, L, s['r'], s['seed'], atlas.next_tile(), atlas, sides=s['sides'], n_body=nb, bend=s['bend'], bake=bake)
        if kind == 'column':
            m = Matrix.Translation((s['x'], s['y'], fz))
            roots = [(Vector((s['x'], s['y'], fz)), Vector((0, 0, 1)), nf, fil),
                     (Vector((s['x'], s['y'], cz)), Vector((0, 0, -1)), nc, fil)]
        elif s['down']:
            m = Matrix.Translation((s['x'], s['y'], cz)) @ Matrix.Rotation(math.pi, 4, 'X')
            roots = [(Vector((s['x'], s['y'], cz)), Vector((0, 0, -1)), nc, fil)]
        else:
            m = Matrix.Translation((s['x'], s['y'], fz))
            roots = [(Vector((s['x'], s['y'], fz)), Vector((0, 0, 1)), nf, fil)]
        out.append((bm, m, s['collide'], kind, roots, s['sides']))
    for c in curtains_p:
        bake = atlas.n < COLS * ROWS
        cb = curtain(tree, c['x'], c['y'], c['heading'], c['length'], c['height'], c['seed'], atlas.next_tile(), atlas, bake)
        if cb is None:
            continue
        out.append((cb, Matrix.Identity(4), True, 'curtain', 'curtain', 0))
        pr = probe_n(tree, c['x'], c['y'])
        top = pr[1] if pr else P['h']
        meta['curtains'].append((Vector((c['x'], c['y'], top - c['height'] * 0.5)), Vector((-math.cos(c['a']), -math.sin(c['a']), 0))))
    for r in rocks_p:
        dn = tree.ray_cast(Vector((r['x'], r['y'], 1.2 + FLOORZ(r['x'], r['y']))), Vector((0, 0, -1)))
        if dn[0] is None:
            continue
        rocks.append(boulder(r['x'], r['y'], dn[0].z - 0.08, r['size'], r['seed']))
    return out, rocks, meta


# ---------------------------------------------------------------------------------------------------------------------
# Water: the base basins plus one sheet per gour terrace

def gour_water(P, bm, tree=None):
    cell = 0.05
    for g in P['_gours']:
        n = int(2 * g['R'] / cell) + 2
        for i in range(n):
            for j in range(n):
                x = g['x'] - g['R'] + (i + 0.5) * cell
                y = g['y'] - g['R'] + (j + 0.5) * cell
                dz, mask, zt, inside = gour_eval(g, x, y)
                if mask < 0.5 or not inside:
                    continue
                level = zt + 0.6 * g['lip'] * mask
                if tree is not None:
                    hit = tree.ray_cast(Vector((x, y, level + 0.6)), Vector((0, 0, -1)), 2.0)
                    fz = hit[0].z if hit[0] is not None else 9.0
                else:
                    fz = floor_field2(x, y)
                if fz > level + 0.015:      # reaches a little under the shore, which hides its edge
                    continue
                h = cell * 0.5
                vs = [bm.verts.new((x - h, y - h, level)), bm.verts.new((x + h, y - h, level)),
                      bm.verts.new((x + h, y + h, level)), bm.verts.new((x - h, y + h, level))]
                bm.faces.new(vs)


def basin_water(P, bm, tree):
    cell = 0.05
    for b in P['_basins']:
        level = b['lip'] * 0.45
        R = b['r'] * 1.35
        n = int(2 * R / cell) + 2
        for i in range(n):
            for j in range(n):
                x = b['x'] - R + (i + 0.5) * cell
                y = b['y'] - R + (j + 0.5) * cell
                dx, dy = x - b['x'], y - b['y']
                c_, s_ = math.cos(b['rot']), math.sin(b['rot'])
                u_, v_ = dx * c_ + dy * s_, -dx * s_ + dy * c_
                if (u_ / b['r']) ** 2 + (v_ / (b['r'] * b['ar'])) ** 2 > 1.3 ** 2:
                    continue
                hit = tree.ray_cast(Vector((x, y, level + 0.6)), Vector((0, 0, -1)), 2.0)
                if hit[0] is None or hit[0].z > level + 0.015:
                    continue
                h = cell * 0.5
                vs = [bm.verts.new((x - h, y - h, level)), bm.verts.new((x + h, y - h, level)),
                      bm.verts.new((x + h, y + h, level)), bm.verts.new((x - h, y + h, level))]
                bm.faces.new(vs)


def all_water(P, tree=None):
    ob, n = pool_water(P)
    bm = bmesh.new()
    if tree is None:
        bm.from_mesh(ob.data)
    else:
        basin_water(P, bm, tree)
    gour_water(P, bm, tree)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    n = len(ob.data.polygons)
    bm.free()
    return ob, n


# ---------------------------------------------------------------------------------------------------------------------
# Assemble

def box_uv(f, uvl):
    nrm = f.normal
    ax = max(range(3), key=lambda i: abs(nrm[i]))
    u_ax, v_ax = [(1, 2), (0, 2), (0, 1)][ax]
    for l in f.loops:
        co = l.vert.co
        l[uvl].uv = (co[u_ax] * UV_EARTH, co[v_ax] * UV_EARTH)


WELD = os.environ.get('CAVE_WELD', '1') == '1'
DBG = {}


def weld_root(bm, NV, sides, column, ri, axis, sn, kd, shell_vs, L):
    """Make one root of a formation part of the rock: cut the rock open under it, drop the buried ring, bridge the
    root ring into the hole's edge, smooth the band. Checks everything before cutting; returns 'ok' or why not."""
    wl, uvl, col, clay = L
    rings = (len(NV) - (0 if column else 1)) // sides
    if rings < 4:
        return 'small'
    if ri == 0:
        root, buried, nxt = NV[sides:2 * sides], NV[0:sides], NV[2 * sides:3 * sides]
    else:
        root = NV[(rings - 2) * sides:(rings - 1) * sides]
        buried = NV[(rings - 1) * sides:rings * sides]
        nxt = NV[(rings - 3) * sides:(rings - 2) * sides]
    if any(not v.is_valid for v in root + buried + nxt):
        return 'invalid'
    ring_edges = []
    for k in range(sides):
        e = bm.edges.get((root[k], root[(k + 1) % sides]))
        if e is None:
            if not DBG.get('ring'):
                DBG['ring'] = 1
                print('DBG ring_edges', column, ri, sides, len(NV), rings, [tuple(round(c_, 3) for c_ in u.co) for u in root[:3]],
                      [len(u.link_edges) for u in root[:4]])
            return 'ring_edges'
        ring_edges.append(e)
    c = sum((v.co for v in root), Vector()) / sides
    a1 = axis.orthogonal().normalized()
    a2 = axis.cross(a1)
    pol = []
    for v in root:
        d = v.co - c
        d = d - axis * d.dot(axis)
        pol.append((math.atan2(d.dot(a2), d.dot(a1)), d.length))
    pol.sort()

    def r_at(ang):
        for i in range(len(pol)):
            a0, r0 = pol[i - 1]
            a1_, r1 = pol[i]
            lo = a0 if i > 0 else a0 - 2 * math.pi
            if lo <= ang <= a1_:
                u = (ang - lo) / max(a1_ - lo, 1e-6)
                return r0 + (r1 - r0) * u
        a0, r0 = pol[-1]
        a1_, r1 = pol[0]
        u = (ang - a0) / max(a1_ + 2 * math.pi - a0, 1e-6) if ang >= a0 else (ang + 2 * math.pi - a0) / max(a1_ + 2 * math.pi - a0, 1e-6)
        return r0 + (r1 - r0) * u

    rmax = max(r for _, r in pol)
    inside = []
    for (co, idx, dist) in kd.find_range(c, rmax + 0.25):
        v = shell_vs[idx]
        if not v.is_valid or v[wl]:
            continue
        d = v.co - c
        h = d.dot(axis)
        if abs(h) > 0.3:
            continue
        dp = d - axis * h
        if dp.length < r_at(math.atan2(dp.dot(a2), dp.dot(a1))) + 0.012:
            inside.append(v)
    if not inside:
        return 'no_rock_verts'
    inside_s = set(inside)
    for _grow in range(4):
        F_in = set(f for v in inside_s for f in v.link_faces)
        rim = set(u for f in F_in for u in f.verts) - inside_s
        tight = []
        for u in rim:
            d = u.co - c
            d = d - axis * d.dot(axis)
            if d.length < r_at(math.atan2(d.dot(a2), d.dot(a1))) + 0.02:
                tight.append(u)
        if not tight:
            break
        inside_s.update(u for u in tight if not u[wl])
        if any(u[wl] for u in tight):
            return 'conflict'
    F_in = set(f for v in inside_s for f in v.link_faces)
    if any(f.material_index != MAT_EARTH for f in F_in):
        return 'mixed'
    E_b = list(set(e for f in F_in for e in f.edges if sum(1 for g in e.link_faces if g in F_in) == 1))
    if any(len(e.link_faces) != 2 for e in E_b):
        return 'nonmanifold'
    deg = {}
    for e in E_b:
        for v in e.verts:
            deg[v] = deg.get(v, 0) + 1
    if any(dg != 2 for dg in deg.values()):
        return 'not_simple'
    E_bs = set(E_b)
    start = E_b[0]
    seen = {start}
    cyc = [start.verts[0], start.verts[1]]
    v = start.verts[1]
    prev = start
    while True:
        nx = next((e for e in v.link_edges if e in E_bs and e is not prev), None)
        if nx is None or nx is start:
            break
        seen.add(nx)
        prev = nx
        v = nx.other_vert(v)
        if v is cyc[0]:
            break
        cyc.append(v)
    if len(seen) != len(E_b):
        return 'multi_loop'
    V_in = set(u for f in F_in for u in f.verts)
    E_in = set(e for f in F_in for e in f.edges)
    if len(V_in) - len(E_in) + len(F_in) != 1:
        return 'not_disc'
    # the hole's edge must be outside the root ring all round (else the bridge would fold)
    for u in deg:
        d = u.co - c
        d = d - axis * d.dot(axis)
        if d.length < r_at(math.atan2(d.dot(a2), d.dot(a1))) + 0.003:
            return 'tight'
        if any(f.material_index != MAT_EARTH for f in u.link_faces):
            return 'rim_mixed'
    bverts = list(deg.keys())
    if any(not u.is_valid for u in root) or any(not u.is_valid for u in cyc):
        return 'root_gone'

    def ang(u):
        d = u.co - c
        return math.atan2(d.dot(a2), d.dot(a1)) % (2 * math.pi)

    a_ref = ang(root[0])

    def tt(u):
        return (ang(u) - a_ref) % (2 * math.pi)

    R = list(root)
    if tt(R[1]) > math.pi:                         # make the ring run with increasing angle
        R = [R[0]] + list(reversed(R[1:]))
    H = list(cyc)
    steps = [((tt(H[(k + 1) % len(H)]) - tt(H[k])) + math.pi) % (2 * math.pi) - math.pi for k in range(len(H))]
    if sum(steps) < 0:
        H.reverse()
    k0 = min(range(len(H)), key=lambda k: tt(H[k]))
    H = H[k0:] + H[:k0]
    tr = [tt(u) for u in R] + [2 * math.pi]
    th = [tt(u) for u in H]
    for k in range(1, len(th)):                    # the hole must go round once, monotonically (star-shaped)
        if th[k] < th[k - 1] - 1e-4:
            return 'not_star'
    th.append(th[0] + 2 * math.pi)
    # --- cut, drop, bridge
    bmesh.ops.delete(bm, geom=list(F_in), context='FACES')
    bmesh.ops.delete(bm, geom=buried, context='VERTS')
    hole_edges = [e for e in E_b if e.is_valid]
    ring_edges = [e for e in ring_edges if e.is_valid]
    R2 = R + [R[0]]
    H2 = H + [H[0]]
    n, m = len(R), len(H)
    i = j = 0
    new_faces = []
    while i < n or j < m:
        if j >= m or (i < n and tr[i + 1] <= th[j + 1]):
            tri = (R2[i], R2[i + 1], H2[j])
            i += 1
        else:
            tri = (R2[i], H2[j + 1], H2[j])
            j += 1
        if len(set(tri)) < 3:
            continue
        try:
            new_faces.append(bm.faces.new(tri))
        except ValueError:
            pass
    if not new_faces:
        return 'bridge_empty'
    tri = bmesh.ops.triangulate(bm, faces=new_faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    new_faces = list(tri['faces'])
    for f in new_faces:
        f.normal_update()
    if sum(f.normal.dot(sn) for f in new_faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=new_faces)
    for f in new_faces:
        f.material_index = MAT_EARTH
        f[clay] = 1
        for l_ in f.loops:
            l_[col] = EARTH_COL
    # formation side: the root ring and the fillet rings above it (up to 6)
    fil_rings = []
    for k_ in range(1, 7):
        idx_ = (1 + k_) if ri == 0 else (rings - 2 - k_)
        if 0 <= idx_ < rings:
            fil_rings += NV[idx_ * sides:(idx_ + 1) * sides]
    # rock side: two rings of vertices beyond the hole's rim
    ring1 = set(w for u in bverts if u.is_valid for e in u.link_edges for w in e.verts if w.is_valid) - set(bverts) - set(root)
    ring2 = set(w for u in ring1 for e in u.link_edges for w in e.verts if w.is_valid) - ring1 - set(bverts) - set(root)
    ring1 = set(u for u in ring1 if not u[wl] or u in bverts)
    ring2 = set(u for u in ring2 if not u[wl])
    band = [u for u in set(root) | set(fil_rings) | set(bverts) | ring1 | ring2 if u.is_valid]
    for _ in range(7):
        bmesh.ops.smooth_laplacian_vert(bm, verts=band, lambda_factor=0.5, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    for u in bverts:
        if u.is_valid:
            u[wl] = 1
    for f in new_faces:
        f.normal_update()
        box_uv(f, uvl)
    open_ = sum(1 for f in new_faces for e in f.edges if len(e.link_faces) != 2)
    if open_:
        if DBG.get('open', 0) < 3:
            DBG['open'] = DBG.get('open', 0) + 1
            print('DBG open after bridge', open_, 'ring', len(ring_edges), 'hole', len(hole_edges), 'faces', len(new_faces))
        return 'ok_open'
    return 'ok'



def traverse_check(me):
    """Can a player walk between the openings? Along straight lines from the room's middle to each opening and between
    the openings: the least headroom, the steepest floor, the biggest step in floor height between samples"""
    if P.get('nr_skip_traverse'):
        return {}
    bm = bmesh.new()
    bm.from_mesh(me)
    tree = BVHTree.FromBMesh(bm)
    bases = [o['base'] for o in P['_open']]
    lines = [(Vector((0, 0, 0)), b) for b in bases]
    for i in range(len(bases)):
        for j in range(i + 1, len(bases)):
            lines.append((bases[i], bases[j]))
    worst_head, worst_slope, worst_step = 99.0, 0.0, 0.0
    samples = 0
    for a, b in lines:
        n = max(2, int(math.hypot(b.x - a.x, b.y - a.y) / 0.5))
        prev = None
        for k in range(n + 1):
            x = a.x + (b.x - a.x) * k / n
            y = a.y + (b.y - a.y) * k / n
            pr = probe_n(tree, x, y)
            if not pr:
                prev = None
                continue
            fz, cz, nf, nc = pr
            samples += 1
            worst_head = min(worst_head, cz - fz)
            worst_slope = max(worst_slope, math.degrees(math.acos(max(-1.0, min(1.0, nf.z)))))
            if prev is not None:
                worst_step = max(worst_step, abs(fz - prev))
            prev = fz
    bm.free()
    res = dict(samples=samples, min_headroom=round(worst_head, 2), max_floor_slope_deg=round(worst_slope, 1), max_step_per_half_m=round(worst_step, 2))
    if worst_head < 2.0 or worst_slope > 45 or worst_step > 0.6:
        res['WARNING'] = 'a way between openings may be blocked or too steep'
    return res


def assemble2(P):
    global PIECE_KEEP
    t0 = time.time()
    piece, V2 = build_room(P)
    plan_gours(P)
    plan_cracks(P)
    specs, curtains_p, rocks_p, used = plan_specs(P, V2)
    PIECE_KEEP = piece.sockets + piece.fades
    objs = finish(piece)
    print('shell finished in %.1f s' % (time.time() - t0))
    P['_traverse'] = traverse_check(objs[0].data)
    print('traverse:', P['_traverse'])
    lod, utm = objs[0], objs[1]
    me = lod.data
    shell_tris = len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    col = bm.loops.layers.color['Col']
    uvl = bm.loops.layers.uv.verify()
    clay = bm.faces.layers.int.new('collide')
    calc = bm.verts.layers.float.new('calcite')
    bm.normal_update()
    for f in bm.faces:
        f[clay] = 1
    for v in bm.verts:
        if any(f.material_index == MAT_EARTH for f in v.link_faces):
            v[calc] = calcite_mask(v.co, v.normal.z)
    atlas = Atlas()
    t1 = time.time()
    forms, rocks, meta = build_specs(P, bm, specs, curtains_p, rocks_p, atlas)
    meta['cracks_used'] = used
    print('formations: %d built + baked in %.1f s' % (len(forms), time.time() - t1))
    counts = {}
    spl_tris = 0
    blend_target = {}       # BMVert -> (surface normal, weight of the formation's own normal)
    shell_tree = BVHTree.FromBMesh(bm)
    hugged = 0
    wl = bm.verts.layers.int.new('welded')
    tipl = bm.verts.layers.float.new('tip')
    tip2l = bm.verts.layers.float.new('tip2')
    bm.verts.ensure_lookup_table()
    shell_vs = list(bm.verts)
    kd = KDTree(len(shell_vs))
    for i_, v_ in enumerate(shell_vs):
        kd.insert(v_.co, i_)
    kd.balance()
    weld_stats = {}
    picks = []
    pending = []
    fidl = bm.faces.layers.int.new('fid')
    hug_info = {}           # fillet vertex -> (formation id, axis, own, rock height it was fitted to)
    fid_n = 0
    for fbm, m, collide, kind, roots, sides in forms:
        bmesh.ops.transform(fbm, matrix=m, verts=fbm.verts[:])
        tmp = bpy.data.meshes.new('tmp')
        fbm.to_mesh(tmp)
        n_before = len(bm.faces)
        nv_before = len(bm.verts)
        bm.from_mesh(tmp)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        NV = list(bm.verts[nv_before:])
        NF = list(bm.faces[n_before:])
        fid_n += 1
        for f in NF:
            f[fidl] = fid_n
        for f in NF:
            f.material_index = MAT_EARTH if WELD else MAT_GLOW       # one material with the rock
            f[clay] = 1 if collide else 0
            for l in f.loops:
                l[col] = EARTH_COL if WELD else (1.0, 1.0, 1.0, 1.0)
        root_calc = 1.0
        if roots != 'curtain':
            far = max(1e-3, max(min((v.co - pt).dot(ax) for (pt, ax, sn_, fl_) in roots) for v in NV))
            near_ = kd.find(roots[0][0])
            if near_[1] is not None:
                root_calc = shell_vs[near_[1]][calc]
        for v in NV:
            v[calc] = root_calc                     # the rock's own flowstone mask, carried up the formation
            if roots == 'curtain':
                v[tipl] = 1.0
                v[tip2l] = 0.2
                continue
            dmin, fil_ = min(((v.co - pt).dot(ax), fl_) for (pt, ax, sn_, fl_) in roots)
            v[tipl] = smooth(clamp01((dmin - 0.8 * fil_) / 0.35))      # rock look first, own look after the fillet
            v[tip2l] = 0.0 if kind == 'column' else clamp01(dmin / far) ** 1.6
            if kind == 'straw':
                v[tipl] = 1.0
                v[tip2l] = 0.85
                continue
            pick = None
            for (pt, axis, sn, fil) in roots:
                dd = (v.co - pt).dot(axis)
                if pick is None or dd < pick[0]:
                    pick = (dd, pt, axis, sn, fil)
            dd, pt, axis, sn, fil = pick
            if fil <= 0 or dd >= fil:
                continue
            own = smooth(clamp01(dd / fil))
            origin = Vector((v.co.x, v.co.y, pt.z)) + axis * 1.2
            hit = shell_tree.ray_cast(origin, -axis, 3.0)
            if hit[0] is not None:
                v.co.z += (hit[0].z - pt.z) * (1.0 - own)
                blend_target[v] = (hit[1].normalized(), own)
                hug_info[v] = (fid_n, axis.copy(), own, hit[0].z)
                hugged += 1
            else:
                blend_target[v] = (sn, own)
        pick = None
        if roots != 'curtain' and kind != 'straw':
            pt0, ax0, sn0, fl0 = roots[0]
            pick = dict(kind=kind, r=fl0, pt=pt0.copy(), sn=sn0.copy(), axis=ax0.copy(), welded=False)
            picks.append(pick)
        pending.append((NV, NF, sides, kind, roots, pick, fid_n))
        spl_tris += sum(1 for f in NF if f.is_valid)
        counts[kind] = counts.get(kind, 0) + 1
        bpy.data.meshes.remove(tmp)
        fbm.free()
    rock_tris = 0
    for rb in rocks:
        tmp = bpy.data.meshes.new('tmp')
        rb.to_mesh(tmp)
        n_before = len(bm.faces)
        bm.from_mesh(tmp)
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        for f in bm.faces[n_before:]:
            f.material_index = MAT_EARTH
            f[clay] = 1
            box_uv(f, uvl)
            for l in f.loops:
                l[col] = EARTH_COL
                l.vert[calc] = 0.25
        rock_tris += len(bm.faces) - n_before
        bpy.data.meshes.remove(tmp)
        rb.free()
    counts['boulder'] = len(rocks)
    # weld: every formation root becomes part of the rock (now that nothing more gets appended)
    welded_ids = set()
    for NV, NF, sides, kind, roots, pick, fid_ in pending:
        welded_here = False
        if WELD and roots != 'curtain' and kind != 'straw':
            for ri, (pt, ax, sn_, fl_) in enumerate(roots):
                res_ = weld_root(bm, NV, sides, kind == 'column', ri, ax, sn_, kd, shell_vs, (wl, uvl, col, clay))
                weld_stats[res_] = weld_stats.get(res_, 0) + 1
                welded_here = welded_here or res_ == 'ok'
            if welded_here:
                for v in NV:
                    if v.is_valid:
                        v[wl] = 1
                        blend_target.pop(v, None)
        if WELD:
            for f in NF:
                if f.is_valid:
                    box_uv(f, uvl)
        if pick is not None:
            pick['welded'] = welded_here
        if welded_here:
            welded_ids.add(fid_)
    # the welds smoothed the rock round them: fit the fillets that were not welded to the rock as it is now
    rehugged = 0
    if WELD and welded_ids:
        bm.verts.index_update()
        coords = [v.co.copy() for v in bm.verts]
        polys = [[u.index for u in f.verts] for f in bm.faces if f[fidl] == 0 or f[fidl] in welded_ids]
        rock_tree = BVHTree.FromPolygons(coords, polys)
        for v, (fid_, ax_, own_, z_old) in hug_info.items():
            if fid_ in welded_ids or not v.is_valid:
                continue
            hit = rock_tree.ray_cast(v.co + ax_ * 1.2, -ax_, 3.0)
            if hit[0] is None:
                continue
            dz = hit[0].z - z_old
            if abs(dz) > 1e-5:
                v.co.z += dz * (1.0 - own_)
                if v in blend_target:
                    blend_target[v] = (hit[1].normalized(), blend_target[v][1])
                rehugged += 1
    weld_stats['refitted_verts'] = rehugged
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(60) and any(f_.material_index == MAT_WOOD for f_ in e.link_faces))
    glow_mat = bpy.data.materials.get('TT_CalciteGlow') or bpy.data.materials.new('TT_CalciteGlow')
    # the calcite mask as a colour attribute (preview reads it; in game it would need a layered material, unverified)
    bm.verts.index_update()
    calc_vals = [v[calc] for v in bm.verts]
    tip_vals = [v[tipl] for v in bm.verts]
    tip2_vals = [v[tip2l] for v in bm.verts]
    bt_idx = {v.index: val for v, val in blend_target.items() if v.is_valid}
    me.clear_geometry()
    bm.to_mesh(me)
    if 'TT_CalciteGlow' not in [m_.name for m_ in me.materials]:
        me.materials.append(glow_mat)
    for p in me.polygons:
        p.use_smooth = p.material_index in (MAT_EARTH, MAT_GLOW)
    ca = me.color_attributes.new('Calcite', 'FLOAT_COLOR', 'POINT')
    for i, val in enumerate(calc_vals):
        ca.data[i].color = (val, val, val, 1.0)
    ta = me.color_attributes.new('Tip', 'FLOAT_COLOR', 'POINT')
    for i, val in enumerate(tip_vals):
        ta.data[i].color = (val, val, val, 1.0)
    tb = me.color_attributes.new('Tip2', 'FLOAT_COLOR', 'POINT')
    for i, val in enumerate(tip2_vals):
        tb.data[i].color = (val, val, val, 1.0)
    # root normals: the formation's own normal fades in from the rock's over its first blend length
    try:
        loop_n = [cn.vector.copy() for cn in me.corner_normals]
    except AttributeError:
        me.calc_normals_split()
        loop_n = [l.normal.copy() for l in me.loops]
    for li, l in enumerate(me.loops):
        bt = bt_idx.get(l.vertex_index)
        if bt:
            sn, wgt = bt
            loop_n[li] = (sn * (1 - wgt) + loop_n[li] * wgt).normalized()
    me.normals_split_custom_set(loop_n)
    cb = bm.copy()
    cl = cb.faces.layers.int['collide']
    cb.faces.ensure_lookup_table()
    bmesh.ops.delete(cb, geom=[f for f in cb.faces if f[cl] == 0], context='FACES')
    utm.data.clear_geometry()
    cb.to_mesh(utm.data)
    utm.data.materials.clear()
    for mt in me.materials:
        utm.data.materials.append(mt)
    coll_tris_full = len(utm.data.polygons)
    if coll_tris_full > COLL_TARGET:
        md = utm.modifiers.new('dec', 'DECIMATE')
        md.ratio = COLL_TARGET / coll_tris_full
        md.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(utm.evaluated_get(dg))
        utm.modifiers.clear()
        old = utm.data
        utm.data = me2
        bpy.data.meshes.remove(old)
    coll_tris = len(utm.data.polygons)
    cb.free()
    bm.free()
    img = None                                     # nothing baked: the look comes from the layered material
    water, water_tris = all_water(P, shell_tree)
    stats = dict(name=P['name'], variant=VARIANT, label=P['label'], tris_shell=shell_tris, tris_formations=spl_tris,
                 tris_boulders=rock_tris, tris_lod0=len(me.polygons), tris_collider=coll_tris, tris_collider_before_decimate=coll_tris_full, tris_water=water_tris,
                 formations=counts, cracks=used, gours=len(P['_gours']), pools=len(P['_basins']),
                 blended_root_verts=len(blend_target), hugged_verts=hugged, weld=weld_stats, traverse=P.get('_traverse'), drip=P.get('_drip_stats'), build_s=round(time.time() - t0, 1), bbox=[round(x, 2) for x in lod.dimensions])
    P['_meta'] = meta
    P['_picks'] = picks
    return piece, objs, water, img, stats, V2


# ---------------------------------------------------------------------------------------------------------------------
# Preview look closer to show-cave photos (warm calcite, wet sheen), rock -> calcite by the 'Calcite' attribute

LIGHT_SCALE = float(os.environ.get('CAVE_LIGHT', '0.6'))
_add_light_base = add_light
_setup_render_base = setup_render


def add_light(name, kind, loc, energy, color, size=0.1):
    return _add_light_base(name, kind, loc, energy * LIGHT_SCALE, color, size)


def setup_render(res):
    sc = _setup_render_base(res)
    try:
        sc.eevee.use_gtao = True
    except Exception:
        pass
    for vt in ('AgX', 'Filmic'):
        try:
            sc.view_settings.view_transform = vt
            try:
                sc.view_settings.look = 'AgX - Punchy' if vt == 'AgX' else 'None'
            except TypeError:
                pass
            break
        except TypeError:
            continue
    return sc


def warm_up_materials():
    def recolour(name, lo, hi, rough):
        m = bpy.data.materials.get(name)
        if not m:
            return None
        for n in m.node_tree.nodes:
            if n.type == 'VALTORGB':
                n.color_ramp.elements[0].color = (*lo, 1)
                n.color_ramp.elements[1].color = (*hi, 1)
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Roughness'].default_value = rough
            if n.type == 'BUMP':
                n.inputs['Strength'].default_value = 0.35
        return m
    m = recolour('TT_Earth', (0.10, 0.075, 0.055), (0.30, 0.22, 0.15), 0.7)
    mg = recolour('TT_CalciteGlow', (0.70, 0.48, 0.26), (0.98, 0.84, 0.60), 0.28)
    if mg:
        nt = mg.node_tree
        ramp_n = next(n for n in nt.nodes if n.type == 'VALTORGB')
        bsdf_g = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        uvn = nt.nodes.new('ShaderNodeUVMap')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(uvn.outputs['UV'], sep.inputs['Vector'])
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = ROWS
        nt.links.new(sep.outputs['Y'], mul.inputs[0])
        frc = nt.nodes.new('ShaderNodeMath')
        frc.operation = 'FRACT'
        nt.links.new(mul.outputs[0], frc.inputs[0])
        grad = nt.nodes.new('ShaderNodeValToRGB')
        grad.color_ramp.elements[0].position = 0.1
        grad.color_ramp.elements[0].color = (1.0, 0.76, 0.46, 1)       # root: the flowstone colour round it (x the ramp)
        grad.color_ramp.elements[1].position = 0.97
        grad.color_ramp.elements[1].color = (0.96, 0.93, 0.86, 1)      # tip: white, wet calcite
        nt.links.new(frc.outputs[0], grad.inputs['Fac'])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.inputs['Factor'].default_value = 0.85
        nt.links.new(grad.outputs['Color'], mx.inputs['A'])
        nt.links.new(ramp_n.outputs['Color'], mx.inputs['B'])
        nt.links.new(mx.outputs['Result'], bsdf_g.inputs['Base Color'])
    if m:
        nt = m.node_tree
        ramp = next(n for n in nt.nodes if n.type == 'VALTORGB')
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        att = nt.nodes.new('ShaderNodeAttribute')
        att.attribute_name = 'Calcite'
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        calcite = nt.nodes.new('ShaderNodeRGB')
        calcite.outputs[0].default_value = (0.88, 0.64, 0.36, 1)
        nt.links.new(att.outputs['Fac'], mix.inputs['Factor'])
        nt.links.new(ramp.outputs['Color'], mix.inputs['A'])
        nt.links.new(calcite.outputs[0], mix.inputs['B'])
        nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        att2 = nt.nodes.new('ShaderNodeAttribute')
        att2.attribute_name = 'Tip'
        att3 = nt.nodes.new('ShaderNodeAttribute')
        att3.attribute_name = 'Tip2'
        tco = nt.nodes.new('ShaderNodeTexCoord')
        sc_ = nt.nodes.new('ShaderNodeVectorMath')
        sc_.operation = 'MULTIPLY'
        sc_.inputs[1].default_value = (9.0, 9.0, 0.8)                 # streaks running down the formation
        nt.links.new(tco.outputs['Object'], sc_.inputs[0])
        streak = nt.nodes.new('ShaderNodeTexNoise')
        streak.inputs['Scale'].default_value = 1.0
        streak.inputs['Detail'].default_value = 4.0
        nt.links.new(sc_.outputs['Vector'], streak.inputs['Vector'])
        sramp = nt.nodes.new('ShaderNodeValToRGB')
        sramp.color_ramp.elements[0].color = (0.62, 0.42, 0.22, 1)
        sramp.color_ramp.elements[1].color = (0.92, 0.76, 0.52, 1)
        nt.links.new(streak.outputs['Fac'], sramp.inputs['Fac'])
        whiten = nt.nodes.new('ShaderNodeMix')
        whiten.data_type = 'RGBA'
        white = nt.nodes.new('ShaderNodeRGB')
        white.outputs[0].default_value = (0.95, 0.92, 0.84, 1)
        nt.links.new(att3.outputs['Fac'], whiten.inputs['Factor'])
        nt.links.new(sramp.outputs['Color'], whiten.inputs['A'])
        nt.links.new(white.outputs[0], whiten.inputs['B'])
        mix2 = nt.nodes.new('ShaderNodeMix')
        mix2.data_type = 'RGBA'
        nt.links.new(att2.outputs['Fac'], mix2.inputs['Factor'])
        nt.links.new(mix.outputs['Result'], mix2.inputs['A'])
        nt.links.new(whiten.outputs['Result'], mix2.inputs['B'])
        nt.links.new(mix2.outputs['Result'], bsdf.inputs['Base Color'])
        rmix = nt.nodes.new('ShaderNodeMapRange')
        nt.links.new(att.outputs['Fac'], rmix.inputs['Value'])
        rmix.inputs['To Min'].default_value = 0.65
        rmix.inputs['To Max'].default_value = 0.32
        nt.links.new(rmix.outputs['Result'], bsdf.inputs['Roughness'])


def extra_views(P, lod, water):
    lod.hide_render = False
    water.hide_render = False
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.name.startswith('area'):
            o.hide_render = True
    torch = bpy.data.objects['torch']
    torch.data.energy = 260 * LIGHT_SCALE
    torch.hide_render = False
    fill = bpy.data.objects['fill']
    fill.hide_render = False
    spot = add_light('show', 'POINT', (0, 0, 0.3), 180, (1.0, 0.78, 0.5), 0.15)
    rx, ry, h = P['rx'], P['ry'], P['h']
    shots = []
    # ceiling cracks: the busiest one, from below at an angle
    if P['_cracks']:
        used = sorted(P['_meta']['cracks_used'], key=lambda t: -t[1])
        pts = P['_cracks'][used[0][0]]
        mid = pts[len(pts) // 2]
        dirv = (pts[-1] - pts[0]).normalized()
        side = Vector((-dirv.y, dirv.x, 0))
        cam = make_cam('cam7', mid - side * 1.6 + Vector((0, 0, 1.5)), mid + Vector((0, 0, h * 0.75)), 24)
        torch.location = cam.location + Vector((0.2, 0, 0.1))
        spot.location = mid + side * 1.0 + Vector((0, 0, 0.4))
        shoot(cam, f'{P["name"]}_view7_ceiling')
        shots.append('view7_ceiling')
    if P['_gours']:
        g = P['_gours'][0]
        c = Vector((g['x'], g['y'], 0))
        away = Vector((g['dx'], g['dy'], 0))
        cam = make_cam('cam8', c + away * (g['R'] + 0.9) + Vector((0, 0, 1.35)), c - away * 0.4 + Vector((0, 0, -0.1)), 22)
        torch.location = cam.location + Vector((0.3, 0, 0.2))
        spot.location = c + away * 0.4 + Vector((0, 0, 0.7))
        shoot(cam, f'{P["name"]}_view8_gours')
        shots.append('view8_gours')
    if P['_meta']['curtains']:
        ctr, inward = P['_meta']['curtains'][0]
        cam = make_cam('cam9', ctr + inward * 2.2 + Vector((0, 0, -0.2)), ctr, 24)
        torch.location = cam.location + Vector((0.2, 0, 0.1))
        spot.location = ctr + inward * 0.6 + Vector((0, 0, -0.9))
        shoot(cam, f'{P["name"]}_view9_curtain')
        shots.append('view9_curtain')
    # floor detail without gours: low view across the floor from an opening
    o = P['_open'][0]
    cam = make_cam('cam10', o['base'] - o['out'] * 0.6 + Vector((0, 0, 1.1)), Vector((0, 0, 0.1)), 20)
    torch.location = cam.location + Vector((0.2, 0, 0.3))
    spot.location = Vector((0, 0, 0.5))
    shoot(cam, f'{P["name"]}_view10_floor')
    shots.append('view10_floor')
    return shots


def closeups(P, lod, water):
    """Close-ups of one stalactite root and one stalagmite root (the same ones whether welded or not), shaded and
    with the triangles drawn over"""
    picks = P['_picks']

    def choose(kinds, rmin, rmax, up):
        best = None
        for pk in picks:
            if pk['kind'] not in kinds or not (rmin <= pk['r'] <= rmax):
                continue
            if (pk['sn'].z > 0.7) != up or abs(pk['sn'].z) < 0.7:
                continue
            if path_dist(pk['pt'].x, pk['pt'].y) < 0.6:
                continue
            if best is None or pk['r'] > best['r']:
                best = pk
        return best
    shots = []
    st = choose(('stalactite',), 0.06, 0.3, False)
    sg = choose(('stalagmite',), 0.06, 0.35, True)
    sg_alts = sorted([pk for pk in picks if pk['kind'] in ('stalagmite', 'candle') and pk['sn'].z > 0.7], key=lambda pk: -pk['r'])
    lod.hide_render = False
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            o.hide_render = True
    torch = add_light('ctorch', 'POINT', (0, 0, 0), 120, (1.0, 0.8, 0.55), 0.05)
    fill = add_light('cfill', 'POINT', (0, 0, 0), 30, (0.6, 0.7, 1.0), 0.3)
    wire = lod.copy()
    wire.data = lod.data
    bpy.context.scene.collection.objects.link(wire)
    wm = wire.modifiers.new('wire', 'WIREFRAME')
    wm.thickness = 0.0025
    wm.use_replace = True
    wm.use_even_offset = False
    wmat = bpy.data.materials.new('wire')
    wmat.use_nodes = True
    wb = next(n for n in wmat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    wb.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
    wb.inputs['Roughness'].default_value = 1.0
    wire.data = lod.data.copy()
    wire.data.materials.clear()
    wire.data.materials.append(wmat)
    for p_ in wire.data.polygons:
        p_.material_index = 0
    wire.hide_render = True
    jobs = [('stalactite', st, True)] + [('stalagmite', pk_, False) for pk_ in ([sg] if sg else []) + sg_alts]
    done_ = set()
    for name, pk, below in jobs:
        if not pk or name in done_:
            continue
        dist = 0.9 + 3.0 * pk['r']
        look = pk['pt'] + Vector((0, 0, -0.10 if below else 0.10))
        dg_ = bpy.context.evaluated_depsgraph_get()
        tree_ = BVHTree.FromObject(lod, dg_)
        to_c = Vector((-pk['pt'].x, -pk['pt'].y, 0))
        base_a = math.atan2(to_c.y, to_c.x) if to_c.length > 1e-3 else 0.0
        cam_loc = None
        side = Vector((math.cos(base_a), math.sin(base_a), 0))
        for k_ in range(16):                                   # towards the room first, then round
            a_ = base_a + (k_ // 2 + 1) * 0.35 * (1 if k_ % 2 else -1) if k_ else base_a
            side = Vector((math.cos(a_), math.sin(a_), 0))
            cand = pk['pt'] + side * dist + Vector((0, 0, -0.55 if below else 0.5))
            surf = look + side * (pk['r'] * 1.4 + 0.04)          # a point just off the formation's surface
            dv = cand - surf
            hit_ = tree_.ray_cast(surf + dv.normalized() * 0.01, dv.normalized(), dv.length)
            if hit_[0] is None:
                cam_loc = cand
                break
        if cam_loc is None:
            continue
        cam = make_cam('close_' + name, cam_loc, look, 32)
        torch.location = cam_loc + Vector((0.15, -0.2, 0.15))
        fill.location = pk['pt'] + side * -0.8 + Vector((0, 0, -0.3 if below else 0.4))
        tag = 'weld' if WELD else 'noweld'
        wire.hide_render = True
        shoot(cam, f'{P["name"]}_close_{name}_{tag}')
        wire.hide_render = False
        shoot(cam, f'{P["name"]}_close_{name}_{tag}_wire')
        wire.hide_render = True
        shots.append((name, pk['welded']))
        done_.add(name)
    return shots



# ---------------------------------------------------------------------------------------------------------------------

piece, objs, water, img, stats, V2 = assemble2(P)
lod = objs[0]
ok, open_edges, facing = verify(piece, lod)
stats['catalog_facing_ok'] = facing
stats['opening_profile_points_found'] = ok
stats['open_edges_lod0'] = open_edges
print(json.dumps(stats))
json.dump(stats, open(os.path.join(OUTDIR, 'stats_%s.json' % P['name']), 'w'), indent=1)
mat, bsdf = preview_materials(img)
warm_up_materials()
_w = bpy.data.materials['TT_Water']
_wn = next(n for n in _w.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
_wn.inputs['Alpha'].default_value = 1.0
_wn.inputs['Base Color'].default_value = (0.012, 0.02, 0.022, 1)
_wn.inputs['Roughness'].default_value = 0.02
try:
    _w.surface_render_method = 'DITHERED'
except Exception:
    pass
water.data.materials.append(bpy.data.materials['TT_Water'])
if os.environ.get('CAVE_BLEND', '1') == '1':
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, P['name'] + '.blend'))
if RENDER:
    set_glow(bsdf, 0.0)
    _sg = set_glow
    set_glow = lambda b, s: _sg(b, 0.0 if s == 1.0 else s)      # lit views without emission; view4 keeps its compare
    if os.environ.get('CAVE_VIEWS', 'all') == 'close':
        setup_render(RES)
        for o_ in bpy.data.objects:
            if o_.type == 'EMPTY' or o_.name.startswith('UTM_'):
                o_.hide_render = True
        print('CLOSEUPS', closeups(P, lod, water))
    else:
        render_room(P, lod, water, bsdf)
        _sg(bsdf, 0.0)
        extra_views(P, lod, water)
        print('CLOSEUPS', closeups(P, lod, water))
print('DONE')
