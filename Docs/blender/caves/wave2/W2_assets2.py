"""W2_assets2: wave-2 assets (passages, crawl chambers, small chambers, junctions, grottos, dug-to-cave transitions).
See W2_assets.py for the conventions.  Dimensions follow Docs/CaveKit_Concept_30.md except where the physics of the clearances
needed more room (ramps of at most about 0.4 m/m into a crawl, standing mouths): the differences are written into Docs/CaveKit_Wave2.md.
"""
import math, random
import numpy as np
from W2_engine import *
from W2_assets import S_, add_openings, route, path_pts, BASE


def terraces(t, n, rise=0.45):
    """0..1 in n steps: flat treads, short risers"""
    t = np.clip(t, 0.0, 1.0) * n
    k = np.floor(np.minimum(t, n - 1e-6))
    f = t - k
    return (k + sm01((f - (1.0 - rise)) / rise)) / n


def scatter_rocks(cv, avoid, hw, n, rlo, rhi, region, seed, zr=(0.5, 0.9), tries=400):
    """breakdown blocks (ellipsoids sunk into the floor) that keep clear of the polyline `avoid` by `hw` + their radius"""
    rng = random.Random(seed)
    placed = []
    x0, x1, y0, y1 = region
    for _ in range(tries):
        if len(placed) >= n:
            break
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(rlo, rhi)
        d = 1e9
        for i in range(len(avoid) - 1):
            ax, ay = avoid[i]
            bx, by = avoid[i + 1]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
            d = min(d, math.hypot(x - ax - t * dx, y - ay - t * dy))
        if d < hw + r * 0.9:
            continue
        if any(math.hypot(x - a, y - b) < 0.8 * (r + rr) for a, b, rr in placed):
            continue
        placed.append((x, y, r))
        cv.add_rock(x, y, 0.15, r * rng.uniform(0.9, 1.2), r * rng.uniform(0.7, 1.0), rng.uniform(*zr) * r / 0.9 + 0.2, seed=rng.uniform(0, 50))
    return placed


# =====================================================================================================================
def squeeze_c():
    """TT_Cave_Pass_SqueezeC: standing ends, a gentle kink and 3.2 m of crouch (roof 1.78 m by design, route clearance must be >= 1.6 m)"""
    cv = Cave2D('TT_Cave_Pass_SqueezeC', 102, H0=2.8, wa=0.8, pa=2.4, k_corner=0.6, k_floor=0.5, wall_noise=(0.35, 0.14),
                head_noise=(0.10, 0.05), floor_noise=(0.03, 0.012))
    p = cv.add_path([(0, -6.4, 1.35), (0, -4.5, 1.35), (0.7, -1.2, 1.8), (-0.4, 2.0, 1.8), (0, 4.5, 1.35), (0, 6.4, 1.35)], smooth=0.9)
    L, m = p.L, p.L / 2
    cv.prof_head = (Profile([(0, 2.8), (m - 4.3, 2.8), (m - 1.6, 1.88), (m + 1.6, 1.88), (m + 4.3, 2.8), (L, 2.8)], L, 0.9), 2.6)
    add_openings(cv, [S_('S', 0.0, 0.0, 4.6, (0, -6.4)), S_('N', 0.0, 0.0, 4.6, (0, 6.4))])
    route(cv, 'main', path_pts(p), 'C', 1.3, 1.3)
    prm = dict(BASE, label='SqueezeC', seed=102, rx=3.0, ry=7.0, h=2.8, wall_amp=0.12, stalactites=4, hero=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.2, 0.7), fill=40, grid=0.10, voxel=0.05, vox5=0.035, budget=90000, coll=12000, crawl_mask=1, rho_scale=1.5,
               excl=0.45, knob_amp=0.06, knob2_amp=0.03, ledge_amp=0.04, floor_big=0.04)
    return cv, prm


def crack():
    """TT_Cave_Pass_Crack: a tall slot, walls leaning 0.3 m per metre, floor rising 6 degrees, a sideways pinch 2.7 m wide at the floor"""
    cv = Cave2D('TT_Cave_Pass_Crack', 106, H0=7.0, use_arch=False, k_corner=0.7, k_floor=0.3, wall_noise=(0.12, 0.05), head_noise=(0.5, 0.2),
                floor_noise=(0.05, 0.02), lean=(0.14, 0.0), wall_open_r=(1.5, 3.2), open_h=2.5, k_foot=0.5)
    pts = [(0, -8.4, 1.6), (0, -6.0, 1.5), (0.6, -3.0, 1.4), (0.8, -0.8, 1.35), (-0.2, 2.0, 1.3), (-0.5, 5.0, 1.4), (0, 7.2, 1.5), (0, 8.4, 1.6)]
    p = cv.add_path(pts, smooth=0.9)
    L = p.L
    rise = Profile([(0, 0.0), (2.4, 0.0), (L - 2.4, 1.5), (L, 1.5)], L, 1.2)
    cv.add_floor(lambda x, y, c: rise(c['s']))
    add_openings(cv, [S_('S', 0.0, 0.0, 5.0, (0, -8.4)), S_('N', 0.0, 1.5, 5.0, (0, 8.4))])
    route(cv, 'main', path_pts(p), 'W', 1.2, 0.9)
    prm = dict(BASE, label='Crack', seed=106, rx=2.4, ry=8.8, h=7.0, wall_amp=0.07, ribs=0.05, stalactites=6, hero=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.2, 0.8), fill=60, grid=0.10, voxel=0.05, vox5=0.04, budget=110000, coll=14000, rho_scale=1.2, excl=0.3,
               knob_amp=0.05, knob2_amp=0.03, col_span=7.0)
    return cv, prm


def flooded():
    """TT_Cave_Pass_Flooded (dry): a water-cut channel 0.55 m deep and 2 m wide between two 1.6 m ledges; ledge roof 1.85 m (crouch), channel walk"""
    cv = Cave2D('TT_Cave_Pass_Flooded', 105, wa=0.6, pa=2.2, k_corner=0.6, k_floor=0.5, wall_noise=(0.30, 0.12), head_noise=(0.10, 0.05),
                floor_noise=(0.03, 0.012), k_foot=1.0)
    p = cv.add_path([(0, -8.4, 1.4), (0, -5.5, 1.4), (0.5, -2.0, 2.6), (-0.5, 2.0, 2.6), (0, 5.5, 1.4), (0, 8.4, 1.4)], smooth=1.0)
    L = p.L
    cd = Profile([(0, 0.0), (3.2, 0.0), (6.6, 0.55), (L - 6.6, 0.55), (L - 3.2, 0.0), (L, 0.0)], L, 0.8)

    def chan(x, y, c):
        return 1.0 - sm01((c['d'] - 0.95) / 0.7)

    cv.add_floor(lambda x, y, c: -cd(c['s']) * chan(x, y, c))
    cv.p['H0'] = lambda x, y, c: 1.85 + 0.95 * (1.0 - sm01(cd(c['s']) / 0.55)) + cd(c['s']) * chan(x, y, c) + 0.0 * x
    cv.p['H0_open'] = True
    add_openings(cv, [S_('S', 0.0, 0.0, 5.6, (0, -8.4)), S_('N', 0.0, 0.0, 5.6, (0, 8.4))])
    route(cv, 'channel', path_pts(p), 'W', 1.2, 1.1)
    prm = dict(BASE, label='Flooded', seed=105, rx=3.4, ry=8.8, h=2.4, wall_amp=0.10, ribs=0.05, stalactites=4, straws=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.15, 0.5), fill=40, grid=0.10, voxel=0.05, vox5=0.04, budget=110000, coll=14000, crawl_mask=1, rho_scale=2.2, excl=0.5,
               knob_amp=0.05, knob2_amp=0.03, ledge_amp=0.03, floor_big=0.03)
    return cv, prm


def saddle():
    """TT_Cave_Crawl_Saddle: a low band cuts diagonally across a tall room: prone (1.1 m) at the west end, crouch (1.78 m) at the east end"""
    cv = Cave2D('TT_Cave_Crawl_Saddle', 92, H0=2.8, wa=1.6, pa=2.2, k_corner=0.9, k_floor=0.6, wall_noise=(0.40, 0.15), head_noise=(0.15, 0.08),
                floor_noise=(0.04, 0.015), k_foot=0.8)
    cv.add_ellipse(0.0, 0.0, 5.4, 7.6)
    rot = 20.0
    cv.add_zone(0.0, 0.3, 8.0, 1.6, rot, 1.72, fall=3.2, grad=0.06)        # hz(u) = 1.50 + 0.11 u: 1.05 m at u = -4.1, 1.95 m at u = +4.1
    cv.p['H0'] = 2.9
    add_openings(cv, [S_('S', -2.6, 0.0, 4.5, (-2.6, -6.6)), S_('N', 2.6, 0.0, 4.5, (2.6, 6.6))])
    # the floor: a gentle 2 percent slope
    cv.add_floor(lambda x, y, c: 0.015 * (y + 7.0) * 0.0 + 0.0 * x)
    route(cv, 'west_prone', [(-2.6, -6.0), (-3.2, -1.2), (-2.4, 0.8), (2.6, 6.0)], 'P', 1.3, 1.4, only=lambda x, y: (abs(y) > 4.0) or (x < -1.4) or ((abs(y) > 3.0) and x < 0.5))
    route(cv, 'east_crouch', [(-2.6, -6.0), (2.0, -1.0), (3.0, 1.0), (2.6, 6.0)], 'C', 1.3, 1.4, only=lambda x, y: (abs(y) > 4.2) or (x > 1.6))
    prm = dict(BASE, label='Saddle', seed=92, rx=5.0, ry=7.4, h=2.9, wall_amp=0.13, ribs=0.06, stalactites=8, stalagmites=2, pairs=2, hero=1, cracks=2,
               crack_len=(1.5, 3.0), len_st=(0.2, 0.9), fill=70, grid=0.10, voxel=0.05, vox5=0.04, budget=150000, coll=16000, crawl_mask=1,
               rho_scale=3.5, excl=0.6, knob_amp=0.07, knob2_amp=0.04, floor_big=0.04, relief=0.04, col_span=3.2)
    return cv, prm


def rubble():
    """TT_Cave_Crawl_Rubble: breakdown crawl: jammed blocks under a sagging slab, a crouch route (>= 1.6 m) that winds between the blocks and
    two prone spots (roof about 1.05 m) that shortcut it"""
    cv = Cave2D('TT_Cave_Crawl_Rubble', 93, H0=1.9, wa=1.3, pa=2.2, k_corner=0.7, k_floor=0.5, wall_noise=(0.35, 0.14), head_noise=(0.12, 0.06),
                floor_noise=(0.08, 0.03), k_foot=0.8)
    cv.add_ellipse(0.0, 0.0, 4.6, 4.8)
    cv.add_zone(2.8, 2.9, 1.6, 1.2, 30, 1.22, fall=1.6)                      # the slab sags toward the north-east corner
    cv.add_zone(-2.7, -2.9, 1.3, 1.1, -20, 1.22, fall=1.6)                    # and a second prone pocket
    cv.p['H0'] = 1.9
    cv.add_floor(lambda x, y, c: -0.04 * y)
    add_openings(cv, [S_('W', 0.0, 0.0, 3.4, (-4.0, 0.0)), S_('E', -1.0, 0.0, 3.4, (4.0, -1.0))])
    wind = [(-3.6, 0.0), (-2.2, -0.9), (-0.6, -0.2), (0.8, -1.5), (2.2, -1.2), (3.6, -1.0)]
    scatter_rocks(cv, wind, 1.3, 14, 0.45, 0.9, (-3.9, 3.9, -4.2, 4.2), 7, zr=(0.55, 0.9))
    route(cv, 'crouch', wind, 'C', 1.3, 1.1)
    prm = dict(BASE, label='Rubble', seed=93, rx=4.4, ry=4.6, h=2.0, wall_amp=0.14, ribs=0.06, stalactites=3, hero=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.15, 0.5), fill=40, grid=0.10, voxel=0.05, vox5=0.035, budget=110000, coll=14000, crawl_mask=1, rho_scale=3.0, excl=0.5,
               knob_amp=0.05, knob2_amp=0.03, ledge_amp=0.04, floor_big=0.05, relief=0.05, col_span=2.3)
    return cv, prm


def bubble():
    """TT_Cave_Chamber_Bubble: a phreatic bubble, 7 x 6 x 3.4 m, smooth walls, almost bare, a shallow bowl in the floor"""
    cv = Cave2D('TT_Cave_Chamber_Bubble', 86, H0=3.6, wa=1.6, pa=2.0, k_corner=1.3, k_floor=0.9, wall_noise=(0.18, 0.06), head_noise=(0.08, 0.03),
                floor_noise=(0.03, 0.01), k_foot=1.0)
    cv.add_ellipse(0.0, 0.0, 3.6, 3.1)
    cv.add_floor(lambda x, y, c: -0.3 * bump(x, y, 0.0, 0.0, 1.2, 1.1, 0.0, 2.2))
    add_openings(cv, [S_('S', 0.8, 0.0, 1.6, (0.8, -2.7)), S_('E', -0.6, 0.0, 1.6, (3.2, -0.6))])
    route(cv, 'main', [(0.8, -2.6), (0.5, -1.0), (1.8, -0.7), (3.1, -0.6)], 'W', 1.3, 1.1)
    prm = dict(BASE, label='Bubble', seed=86, rx=3.6, ry=3.1, h=3.5, wall_amp=0.05, ribs=0.0, stalactites=0, hero=1, cracks=1, crack_len=(1.2, 2.0),
               len_st=(0.2, 0.6), fill=20, grid=0.08, voxel=0.045, vox5=0.03, budget=100000, coll=9000, rho_scale=3.0, excl=0.8,
               knob_amp=0.04, knob2_amp=0.02, knob_r=0.25, ledge_amp=0.02, floor_big=0.03, relief=0.03, col_span=3.5, cluster_scale=0.6)
    return cv, prm


def cleft():
    """TT_Cave_Chamber_Cleft: a wall cleft you move through sideways: leaning walls, rubble floor rising 6 degrees, three openings (S, N, a high side hole)"""
    cv = Cave2D('TT_Cave_Chamber_Cleft', 87, H0=6.0, use_arch=False, k_corner=0.7, k_floor=0.3, wall_noise=(0.25, 0.10), head_noise=(0.45, 0.2),
                floor_noise=(0.10, 0.04), lean=(0.12, 0.0), wall_open_r=(1.5, 3.2), open_h=2.5, k_foot=0.6)
    p = cv.add_path([(0, -5.6, 1.6), (0, -3.6, 1.5), (0.3, -1.0, 1.35), (0.3, 1.8, 1.6), (0.2, 4.0, 1.5), (0.3, 5.6, 1.6)], smooth=0.9)
    L = p.L
    rise = Profile([(0, 0.0), (2.0, 0.0), (L - 2.0, 1.2), (L, 1.2)], L, 1.2)
    cv.add_floor(lambda x, y, c: rise(c['s']))
    cv.add_ellipse(2.5, 2.4, 1.7, 1.9)                                         # the side pocket with the high hole
    cv.add_floor(lambda x, y, c: 1.15 * sm01((x - 1.0) / 2.6) * bump(x, y, 2.5, 2.4, 1.7, 1.9, 0.0, 1.0))
    add_openings(cv, [S_('S', 0.0, 0.0, 3.0, (0, -5.6)), S_('N', 0.3, 1.2, 3.0, (0.3, 5.6)), S_('E', 2.4, 1.9, 1.6, (3.9, 2.4))])
    route(cv, 'main', path_pts(p), 'W', 1.2, 0.9, sock=(0, 1))
    route(cv, 'high', [(0, -5.4), (0.3, -1.0), (0.4, 1.8), (2.4, 2.4), (3.7, 2.4)], 'W', 1.2, 0.9, sock=(0, 2))
    prm = dict(BASE, label='Cleft', seed=87, rx=3.4, ry=6.4, h=6.0, wall_amp=0.07, ribs=0.05, stalactites=3, hero=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.2, 0.8), fill=40, grid=0.10, voxel=0.05, vox5=0.04, budget=110000, coll=14000, rho_scale=1.2, excl=0.3, knob_amp=0.05,
               knob2_amp=0.03, col_span=6.5, talus=0.0, relief=0.06)
    return cv, prm


def jct_tri():
    """TT_Cave_Jct_Tri: an asymmetric three-way chamber over breakdown: the west half 1.2 m lower in four steps of 0.3 m, one roof drop"""
    cv = Cave2D('TT_Cave_Jct_Tri', 111, H0=3.5, wa=1.8, pa=2.2, k_corner=1.0, k_floor=0.6, wall_noise=(0.45, 0.16), head_noise=(0.2, 0.08),
                floor_noise=(0.05, 0.02), k_foot=0.9)
    cv.add_ellipse(-0.4, 0.0, 6.0, 5.2)
    cv.add_floor(lambda x, y, c: -1.2 * terraces((-x - 0.2) / 4.2, 4))
    cv.add_zone(1.5, 2.4, 1.8, 1.5, 0.0, 2.35, fall=2.0)
    add_openings(cv, [S_('S', 0.5, 0.0, 3.0, (0.5, -4.7)), S_('E', -1.0, 0.0, 3.5, (5.3, -1.0)), S_('W', 2.0, -1.2, 3.5, (-5.6, 2.0))])
    route(cv, 'S_E', [(0.5, -4.5), (2.0, -1.5), (5.2, -1.0)], 'W', 1.3, 1.2, sock=(0, 1))
    route(cv, 'S_W', [(0.5, -4.5), (-1.5, -0.5), (-3.0, 1.0), (-5.4, 2.0)], 'W', 1.3, 1.2, sock=(0, 2))
    route(cv, 'E_W', [(5.2, -1.0), (1.0, 0.2), (-3.0, 1.2), (-5.4, 2.0)], 'W', 1.3, 1.2, sock=(1, 2))
    prm = dict(BASE, label='Tri', seed=111, rx=6.0, ry=5.2, h=3.5, wall_amp=0.15, ribs=0.08, stalactites=14, stalagmites=4, pairs=3, hero=2, columns=1,
               cracks=3, crack_len=(1.8, 3.5), len_st=(0.3, 1.2), boulders=0, fill=110, grid=0.10, voxel=0.06, vox5=0.04, budget=170000, coll=16000,
               rho_scale=3.5, excl=0.6, floor_big=0.08, relief=0.05, col_span=3.6, talus=0.12, bank=0.1)
    return cv, prm


def jct_star():
    """TT_Cave_Jct_Star: a five-way hub on two levels: a 1 m basin in the middle with a ramp ring, a high east mouth (+2.0 m), a crouch approach from the west"""
    cv = Cave2D('TT_Cave_Jct_Star', 113, H0=5.0, wa=2.2, pa=2.2, k_corner=1.1, k_floor=0.7, wall_noise=(0.5, 0.18), head_noise=(0.25, 0.1),
                floor_noise=(0.05, 0.02), k_foot=1.0)
    cv.add_ellipse(0.0, 0.0, 6.9, 7.0)
    nk = cv.add_path([(-11.2, 0.0, 1.45), (-8.4, 0.0, 1.45), (-5.5, 0.0, 1.9)], smooth=0.5)
    cv.add_floor(lambda x, y, c: -0.9 * bump(x, y, -1.6, 0.0, 2.2, 2.2, 0.0, 3.4))
    cv.add_floor(lambda x, y, c: 1.8 * bump(x, y, 5.2, 1.6, 2.2, 2.4, 0.0, 10.0))
    cv.add_zone(-9.0, 0.0, 2.6, 1.6, 0.0, 1.88, fall=3.0)
    add_openings(cv, [S_('S', -1.5, 0.0, 3.0, (-1.5, -6.6)), S_('N', 2.0, 0.0, 3.0, (2.0, 6.6)), S_('E', -5.0, 0.0, 3.0, (4.4, -5.0)),
                      S_('E', 1.6, 1.8, 3.0, (5.5, 1.6)), S_('W', 0.0, 0.0, 3.0, (-11.2, 0.0))])
    route(cv, 'S_N', [(-1.5, -6.4), (0.0, -2.0), (1.0, 3.0), (2.0, 6.4)], 'W', 1.3, 1.2, sock=(0, 1))
    route(cv, 'S_E', [(-1.5, -6.4), (1.5, -5.6), (4.2, -5.0)], 'W', 1.3, 1.2, sock=(0, 2))
    route(cv, 'S_Ehigh', [(-1.5, -6.4), (3.0, -2.5), (3.0, -1.0), (5.3, 1.6)], 'W', 1.3, 1.2, sock=(0, 3))
    route(cv, 'S_Wcrawl', [(-1.5, -6.4), (-4.0, -2.0), (-6.0, 0.0), (-11.0, 0.0)], 'C', 1.3, 1.3, sock=(0, 4))
    prm = dict(BASE, label='Star', seed=113, rx=7.0, ry=7.0, h=5.0, wall_amp=0.15, ribs=0.08, stalactites=18, stalagmites=5, pairs=4, hero=3, columns=2,
               cracks=3, crack_len=(2.0, 4.0), len_st=(0.3, 1.4), fill=120, grid=0.12, voxel=0.07, vox5=0.045, budget=190000, coll=24000,
               rho_scale=4.0, excl=0.6, floor_big=0.08, relief=0.05, col_span=5.0, talus=0.1, bank=0.1, crawl_mask=1)
    return cv, prm


def sump():
    """TT_Cave_Grotto_Sump: a dry basin ending at a sealed low arch where water would stand: floor steps down 1.0 m in four steps of 0.25 m, the roof comes down to the floor at the far end"""
    cv = Cave2D('TT_Cave_Grotto_Sump', 122, H0=3.6, wa=1.8, pa=2.2, k_corner=1.0, k_floor=0.6, wall_noise=(0.35, 0.14), head_noise=(0.2, 0.08),
                floor_noise=(0.04, 0.015), k_foot=0.9)
    cv.add_ellipse(0.0, 0.2, 4.4, 4.7)
    cv.add_floor(lambda x, y, c: -1.0 * terraces((y + 0.6) / 3.2, 4) * (0.35 + 0.65 * (1.0 - sm01((np.abs(x) - 2.6) / 1.8))))
    cv.add_zone(0.0, 5.4, 5.5, 1.4, 0.0, 0.2, fall=2.4)
    add_openings(cv, [S_('S', 0.0, 0.0, 3.0, (0.0, -4.4))])
    route(cv, 'to_basin', [(0.0, -4.2), (0.0, 0.0), (0.2, 1.4)], 'W', 1.3, 1.3, sock=(0, 0), to=(0.0, 1.3))
    gs = []
    prm = dict(BASE, label='Sump', seed=122, rx=4.4, ry=4.7, h=3.6, wall_amp=0.14, ribs=0.08, stalactites=12, stalagmites=3, pairs=3, hero=2, cracks=3,
               crack_len=(1.5, 3.0), len_st=(0.3, 1.2), fill=90, grid=0.10, voxel=0.05, vox5=0.035, budget=150000, coll=12000, rho_scale=3.0, excl=0.6,
               floor_big=0.06, relief=0.04, col_span=3.6, talus=0.0)
    return cv, prm


def grotto_crawl():
    """TT_Cave_Grotto_Crawl: a secret nook at the end of a 6 m prone neck (roof 1.12 m by design)"""
    cv = Cave2D('TT_Cave_Grotto_Crawl', 123, H0=2.8, wa=0.7, pa=2.4, k_corner=0.5, k_floor=0.5, wall_noise=(0.30, 0.12), head_noise=(0.08, 0.04),
                floor_noise=(0.03, 0.012), k_foot=0.8)
    p = cv.add_path([(0, -8.4, 1.35), (0, -5.0, 1.35), (0.4, -1.5, 1.75), (0, 1.5, 1.8)], smooth=0.9)
    cv.add_ellipse(0.0, 3.4, 2.5, 2.1)
    L = p.L
    cv.prof_head = (Profile([(0, 2.8), (2.0, 2.8), (5.4, 1.22), (L + 6, 1.22)], L + 6, 0.9), 3.5)
    cv.prof_head_ext = True
    add_openings(cv, [S_('S', 0.0, 0.0, 5.6, (0, -8.4))])
    route(cv, 'neck', path_pts(p), 'P', 1.3, 1.3, sock=(0, 0), to=(0.0, 3.2))
    prm = dict(BASE, label='GrottoCrawl', seed=123, rx=3.0, ry=6.2, h=2.8, wall_amp=0.10, ribs=0.05, stalactites=2, hero=0, cracks=1, crack_len=(1.2, 2.0),
               len_st=(0.15, 0.4), fill=20, grid=0.10, voxel=0.05, vox5=0.03, budget=80000, coll=12000, crawl_mask=1, rho_scale=1.8, excl=0.45,
               knob_amp=0.04, knob2_amp=0.02, ledge_amp=0.03, floor_big=0.03)
    return cv, prm


def brk_breakthrough():
    """TT_Brk_Breakthrough: a dug tunnel (the new dug kit's ring 1.6 x 2.2 m, no timber, 6.6 m) breaks into a cave chamber; the floor drops 0.6 m over rubble"""
    cv = Cave2D('TT_Brk_Breakthrough', 131, H0=3.1, wa=1.8, pa=2.2, k_corner=1.0, k_floor=0.6, wall_noise=(0.40, 0.15), head_noise=(0.2, 0.08),
                floor_noise=(0.12, 0.05), k_foot=0.8, wall_open_r=(1.5, 3.2))
    cv.add_ellipse(0.0, 8.4, 3.9, 4.5)
    cv.add_path([(0.0, 1.6, 1.15), (0.0, 4.8, 2.3)], smooth=0.0)
    cv.add_floor(lambda x, y, c: -0.6 * sm01((y - 3.2) / 3.2))
    cv.add_dug(0.0, -6.5, 3.6, 0.0)
    cv.dug_frames = []                       # no timber in the new dug kit
    add_openings(cv, [S_('S', 0.0, 0.0, 3.0, (0, -6.4), dug=True), S_('N', 0.0, -0.6, 5.0, (0, 12.4))])
    route(cv, 'main', [(0, -6.2), (0, 0.0), (0.3, 5.0), (0, 12.2)], 'W', 1.2, 1.1)
    prm = dict(BASE, label='Breakthrough', seed=131, rx=3.9, ry=13.0, h=3.1, wall_amp=0.14, ribs=0.08, stalactites=8, stalagmites=2, pairs=2, hero=1, cracks=2,
               crack_len=(1.5, 3.0), len_st=(0.2, 0.9), fill=60, grid=0.10, voxel=0.05, vox5=0.04, budget=130000, coll=14000, rho_scale=3.0, excl=0.6,
               floor_big=0.08, relief=0.06, col_span=3.4, talus=0.15, bank=0.1, crawl_mask=0)
    cv.p['dug_note'] = True
    return cv, prm


def brk_hole():
    """TT_Brk_Hole: a dug stub (4.4 m), a ragged hole climbed over three 0.27 m rubble steps, a 3 m crouch squeeze (roof 1.78 m by design), then cave passage"""
    cv = Cave2D('TT_Brk_Hole', 132, H0=2.8, wa=0.9, pa=2.3, k_corner=0.7, k_floor=0.5, wall_noise=(0.35, 0.14), head_noise=(0.12, 0.06),
                floor_noise=(0.08, 0.03), k_foot=0.8, wall_open_r=(1.5, 3.2))
    p = cv.add_path([(0, -2.4, 1.5), (0, 0.4, 1.5), (0.3, 3.4, 1.7), (-0.3, 6.5, 1.7), (0, 9.5, 1.5), (0, 11.4, 1.4)], smooth=0.8)
    L = p.L
    st = Profile([(0, 0.0), (L, 0.0)], L)
    cv.add_floor(lambda x, y, c: 0.81 * terraces((c['s'] - 0.8) / 3.0, 3, 1.0))
    cv.prof_head = (Profile([(0, 2.5), (2.6, 2.5), (4.4, 2.5), (6.2, 1.88), (9.0, 1.88), (11.2, 2.8), (L, 2.8)], L, 0.8), 2.5)
    cv.add_dug(0.0, -7.0, -1.6, 0.0)
    cv.dug_frames = []                       # no timber in the new dug kit
    add_openings(cv, [S_('S', 0.0, 0.0, 3.0, (0, -6.9), dug=True), S_('N', 0.0, 0.81, 4.5, (0, 11.4))])
    route(cv, 'main', [(0, -6.6), (0, -1.0)] + path_pts(p)[2:], 'C', 1.3, 1.2)
    prm = dict(BASE, label='Hole', seed=132, rx=3.0, ry=10.0, h=2.8, wall_amp=0.14, ribs=0.08, stalactites=4, hero=0, cracks=1, crack_len=(1.5, 2.5),
               len_st=(0.2, 0.7), fill=40, grid=0.10, voxel=0.05, vox5=0.035, budget=110000, coll=14000, crawl_mask=1, rho_scale=1.5, excl=0.45,
               knob_amp=0.05, knob2_amp=0.03, floor_big=0.05, relief=0.05, col_span=2.9)
    return cv, prm


def brk_cutting():
    """TT_Brk_Cutting: a dug straight (10 m, kit profile, timber frames) with a cave pocket opening off its east wall; the cave floor is 0.3 m lower"""
    cv = Cave2D('TT_Brk_Cutting', 133, H0=3.0, wa=1.4, pa=2.2, k_corner=0.9, k_floor=0.6, wall_noise=(0.35, 0.14), head_noise=(0.18, 0.07),
                floor_noise=(0.05, 0.02), k_foot=0.7, wall_open_r=(1.5, 3.2))
    cv.add_ellipse(5.0, 0.4, 3.2, 2.7)
    cv.add_path([(0.3, 0.4, 1.25), (2.2, 0.4, 1.3)], smooth=0.0)
    cv.add_floor(lambda x, y, c: -0.3 * sm01((x - 0.8) / 1.4))
    cv.add_dug(0.0, -5.7, 5.7, 0.0)
    cv.dug_frames = []                       # no timber in the new dug kit
    add_openings(cv, [S_('S', 0.0, 0.0, 3.0, (0, -5.6), dug=True), S_('N', 0.0, 0.0, 3.0, (0, 5.6), dug=True), S_('E', 0.4, -0.3, 4.0, (7.9, 0.4))])
    route(cv, 'dug_through', [(0, -5.4), (0, 5.4)], 'W', 1.2, 1.0, sock=(0, 1))
    route(cv, 'into_cave', [(0, -5.4), (0, -0.5), (1.5, 0.4), (4.0, 0.4), (7.7, 0.4)], 'W', 1.2, 1.1, sock=(0, 2))
    prm = dict(BASE, label='Cutting', seed=133, rx=4.0, ry=6.2, h=3.0, wall_amp=0.14, ribs=0.08, stalactites=6, stalagmites=2, pairs=2, hero=1, cracks=2,
               crack_len=(1.5, 3.0), len_st=(0.2, 0.8), fill=50, grid=0.10, voxel=0.05, vox5=0.04, budget=120000, coll=14000, rho_scale=3.0, excl=0.6,
               floor_big=0.06, relief=0.04, col_span=3.2)
    return cv, prm


ASSETS = {'squeezec': squeeze_c, 'crack': crack, 'flooded': flooded, 'saddle': saddle, 'rubble': rubble, 'bubble': bubble, 'cleft': cleft,
          'tri': jct_tri, 'star': jct_star, 'sump': sump, 'grottocrawl': grotto_crawl, 'breakthrough': brk_breakthrough, 'hole': brk_hole,
          'cutting': brk_cutting}
