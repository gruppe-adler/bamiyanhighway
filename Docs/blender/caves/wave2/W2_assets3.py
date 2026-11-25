"""W2_assets3: wave-3 assets (Pillars, Hall_Lake, Ledge_Cascade, Ledge_Collapse, Pass_GalleryCrawl).  See W2_assets.py / W2_assets2.py."""
import math, random
import numpy as np
from W2_engine import *
from W2_assets import S_, add_openings, route, path_pts, BASE
from W2_assets2 import terraces, scatter_rocks


def _dist_poly(x, y, pts):
    d = 1e9
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
        d = min(d, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return d


def pillars():
    """TT_Cave_Room_Pillars: a forest of 16 columns under a low roof (3.6 m), floor rising 3 percent to the north; every gap between neighbours is >= 1.4 m"""
    cv = Cave2D('TT_Cave_Room_Pillars', 85, H0=3.7, wa=1.6, pa=2.2, k_corner=1.0, k_floor=0.6, wall_noise=(0.40, 0.15), head_noise=(0.15, 0.06),
                floor_noise=(0.05, 0.02), k_foot=0.9)
    cv.add_ellipse(0.0, 0.0, 7.6, 7.0)
    cv.add_floor(lambda x, y, c: 0.03 * y)
    ops = [S_('S', -1.5, -0.2, 3.0, (-1.5, -6.6)), S_('E', 2.0, 0.06, 3.0, (7.0, 2.0)), S_('N', 1.0, 0.2, 3.0, (1.0, 6.6))]
    add_openings(cv, ops)
    rng = random.Random(851)
    cols = []
    mouths = [(-1.5, -6.6), (7.0, 2.0), (1.0, 6.6)]
    for _ in range(4000):
        if len(cols) >= 16:
            break
        x, y = rng.uniform(-6.8, 6.8), rng.uniform(-6.4, 6.4)
        r = rng.uniform(0.28, 0.42)
        if (x / 7.6) ** 2 + (y / 7.0) ** 2 > 1.0 or cv.W2(np.array([x]), np.array([y]))[0] < 1.4 + 1.25 * r:
            continue
        if any(math.hypot(x - mx, y - my) < 3.4 for mx, my in mouths):
            continue
        if any(math.hypot(x - a, y - b) < 1.25 * (r + rr) + 1.5 for a, b, rr in cols):
            continue
        cols.append((x, y, r))
    for k, (x, y, r) in enumerate(cols):
        cv.add_column(x, y, r, seed=k * 3.1)
    route(cv, 'S_N', [(-1.5, -6.4), (-1.0, 0.0), (1.0, 6.4)], 'W', 1.3, 1.1, sock=(0, 2))
    route(cv, 'S_E', [(-1.5, -6.4), (2.0, 0.0), (6.8, 2.0)], 'W', 1.3, 1.1, sock=(0, 1))
    route(cv, 'E_N', [(6.8, 2.0), (2.0, 3.0), (1.0, 6.4)], 'W', 1.3, 1.1, sock=(1, 2))
    prm = dict(BASE, label='Pillars', seed=85, rx=7.6, ry=7.0, h=3.7, wall_amp=0.12, ribs=0.06, stalactites=10, stalagmites=3, pairs=6, hero=1, cracks=3,
               crack_len=(1.8, 3.5), len_st=(0.2, 0.8), fill=100, grid=0.10, voxel=0.06, vox5=0.04, budget=170000, coll=20000, rho_scale=3.5, excl=0.7,
               floor_big=0.05, relief=0.04, col_span=3.8, columns=0)
    prm['n_cols'] = len(cols)
    return cv, prm


def lake():
    """TT_Cave_Hall_Lake: a basin hall: a dry 16 x 10 m basin 2.2 m deep in seven terraces (0.31 m steps), a rim walk 6-7 m wide, a raised north ledge (+2.0 m) and an east mouth (+1.2 m)"""
    cv = Cave2D('TT_Cave_Hall_Lake', 84, H0=8.0, wa=4.5, pa=2.2, k_corner=1.4, k_floor=0.9, wall_noise=(0.7, 0.25), head_noise=(0.5, 0.2),
                floor_noise=(0.06, 0.02), k_foot=1.2, wall_open_r=(1.5, 4.0))
    cv.add_ellipse(0.0, 0.0, 15.0, 11.0)
    cv.add_floor(lambda x, y, c: -2.2 * terraces(bump(x, y, 0.0, 0.0, 8.0, 5.0, 0.0, 5.0), 7, 0.5))
    cv.add_floor(lambda x, y, c: 1.2 * sm01((x - 8.5) / 5.5) * sm01((y + 2.0) / 5.0))
    cv.add_floor(lambda x, y, c: 2.0 * sm01((y - 0.0) / 11.0) * sm01((-x + 4.0) / 11.0))
    add_openings(cv, [S_('S', 0.0, 0.0, 6.0, (0.0, -10.3)), S_('E', 3.0, 1.2, 8.0, (14.2, 3.0)), S_('N', -4.0, 2.0, 6.0, (-4.0, 10.3)), S_('W', 2.0, 0.0, 8.0, (-14.2, 2.0))])
    route(cv, 'S_E', [(0, -10.0), (6.0, -7.5), (11.0, -2.0), (14.0, 3.0)], 'W', 1.3, 1.3, sock=(0, 1))
    route(cv, 'S_W', [(0, -10.0), (-6.0, -7.5), (-11.0, -2.0), (-14.0, 2.0)], 'W', 1.3, 1.3, sock=(0, 3))
    route(cv, 'S_N', [(0, -10.0), (-8.0, -6.0), (-11.0, 3.0), (-4.0, 10.0)], 'W', 1.3, 1.3, sock=(0, 2))
    route(cv, 'W_E_rim_north', [(-14.0, 2.0), (-10.0, 6.5), (0.0, 8.0), (10.0, 6.0), (14.0, 3.0)], 'W', 1.3, 1.3, sock=(3, 1))
    prm = dict(BASE, label='Lake', seed=84, rx=15.0, ry=11.0, h=8.0, wall_amp=0.2, ribs=0.12, stalactites=30, stalagmites=8, pairs=8, hero=5, columns=3, cracks=6,
               crack_len=(3.0, 6.0), crack_density=9.0, len_st=(0.4, 2.2), fill=200, grid=0.20, voxel=0.12, vox5=0.07, budget=260000, coll=36000,
               rho_scale=7.0, excl=0.9, floor_big=0.12, relief=0.08, col_span=8.0, len_scale=1.4, cluster_scale=1.8, talus=0.2, bank=0.2)
    return cv, prm


def cascade():
    """TT_Cave_Ledge_Cascade: a flowstone cascade pours 4.5 m down the north end of the hall into gour steps; upper gallery (N, +4.5 m), low mouth (S), side mouth on the steps (E, +0.65 m)"""
    cv = Cave2D('TT_Cave_Ledge_Cascade', 96, H0=6.0, wa=2.6, pa=2.2, k_corner=1.2, k_floor=0.8, wall_noise=(0.5, 0.2), head_noise=(0.3, 0.12),
                floor_noise=(0.08, 0.03), k_foot=1.0)
    cv.add_ellipse(0.0, 0.0, 6.6, 6.6)
    cv.add_floor(lambda x, y, c: 4.5 * np.clip((y + 3.4) / 8.4, 0.0, 1.0) + 0.12 * perlin(x * 2.2, y * 0.9, 1.7) * np.clip((y + 3.4) / 8.4, 0.0, 1.0))
    add_openings(cv, [S_('N', -2.0, 4.5, 3.0, (-2.0, 5.9)), S_('S', 1.0, 0.0, 3.0, (1.0, -5.9)), S_('E', -2.2, 0.65, 3.0, (6.0, -2.2))])
    cv.gours = [dict(x=0.5, y=-3.6, R=2.3, dx=0.0, dy=-1.0, steps=6, ds=2 * 2.3 / 6, h=0.14, lip=0.14, seed=3.0)]
    route(cv, 'up', [(1.0, -5.6), (0.0, -1.0), (-1.0, 2.5), (-2.0, 5.6)], 'W', 1.3, 1.3, sock=(1, 0))
    route(cv, 'S_E', [(1.0, -5.6), (3.0, -3.5), (5.8, -2.2)], 'W', 1.3, 1.2, sock=(1, 2))
    prm = dict(BASE, label='Cascade', seed=96, rx=6.6, ry=6.6, h=6.0, wall_amp=0.16, ribs=0.2, stalactites=12, stalagmites=3, pairs=4, hero=3, curtains=3,
               cracks=3, crack_len=(2.0, 4.0), len_st=(0.3, 1.2), fill=100, grid=0.12, voxel=0.07, vox5=0.045, budget=200000, coll=19000,
               rho_scale=4.0, excl=0.7, floor_big=0.10, relief=0.06, col_span=6.0, gours=1, gour_R=(2.0, 2.4), gour_steps=6, gour_h=0.14, talus=0.0)
    return cv, prm


def collapse():
    """TT_Cave_Ledge_Collapse: a collapse chamber: the floor is a cone of boulders rising 5.8 m to the east wall under a breakdown dome (bare rock); S, N and W mouths low, an E mouth at the crest (+4.2 m)"""
    cv = Cave2D('TT_Cave_Ledge_Collapse', 95, H0=6.0, use_arch=False, k_corner=1.3, k_floor=0.9, wall_noise=(0.7, 0.25), head_noise=(0.0, 0.0),
                floor_noise=(0.10, 0.04), k_foot=1.2, wall_open_r=(1.5, 4.0))
    cv.add_ellipse(0.0, 0.0, 12.0, 12.6)
    cx, cy = 8.0, 0.5

    def cone(x, y):
        return 5.8 * np.clip(1.0 - np.hypot(x - cx, y - cy) / 12.0, 0.0, 1.0)

    cv.add_floor(lambda x, y, c: cone(x, y))
    cv.p['H0'] = lambda x, y, c: np.maximum(2.3, 10.4 * arch(c['W2'] / 5.0, 2.2) - cone(x, y)) + 0.6 * perlin(x / 4.0 + 3, y / 4.0, 5.5) * 0.0
    add_openings(cv, [S_('S', 0.0, 0.0, 6.0, (0.0, -12.0)), S_('N', 0.0, 0.0, 6.0, (0.0, 12.0)), S_('W', -2.0, 0.0, 6.0, (-11.4, -2.0)),
                      S_('E', 0.5, 4.16, 3.0, (11.2, 0.5))])
    sw = [(0.0, -11.5), (2.5, -8.5), (6.5, -7.5), (9.5, -4.5), (7.0, -2.2), (10.2, -0.6), (11.0, 0.5)]
    ring = [(0.0, -11.5), (-6.0, -4.0), (-6.5, 4.0), (0.0, 11.5)]
    wn = [(-11.0, -2.0), (-6.0, -3.0), (0.0, -6.0), (4.0, -6.0)]
    route(cv, 'S_E_crest', sw, 'W', 1.3, 1.5, sock=(0, 3))
    route(cv, 'S_N', ring, 'W', 1.3, 1.5, sock=(0, 1))
    route(cv, 'W_to_S', wn + [(0.0, -11.5)], 'W', 1.3, 1.5, sock=(2, 0))
    scatter_rocks(cv, sw + ring + wn, 1.6, 70, 0.55, 1.9, (-2.0, 11.0, -11.0, 11.0), 95, zr=(0.5, 0.9))
    prm = dict(BASE, label='Collapse', seed=95, rx=12.0, ry=12.6, h=10.0, wall_amp=0.25, ribs=0.15, stalactites=6, stalagmites=0, pairs=0, hero=2, cracks=4,
               crack_len=(3.0, 6.0), len_st=(0.3, 1.4), fill=40, grid=0.20, voxel=0.12, vox5=0.07, budget=280000, coll=40000, rho_scale=6.0, excl=0.9,
               floor_big=0.05, relief=0.03, col_span=10.0, knob_amp=0.1, talus=0.0)
    return cv, prm


def gallery_crawl():
    """TT_Cave_Pass_GalleryCrawl: a long wide crawl gallery with rest pockets: prone stretches (roof 1.12 m), a crouch stretch (1.75 m), rest pockets (1.95 m), standing ends"""
    cv = Cave2D('TT_Cave_Pass_GalleryCrawl', 104, H0=2.8, wa=0.8, pa=2.3, k_corner=0.6, k_floor=0.5, wall_noise=(0.35, 0.14), head_noise=(0.08, 0.04),
                floor_noise=(0.04, 0.015), k_foot=1.0)
    pts = [(0, -15.0, 1.4), (0.2, -11.0, 1.9), (0.9, -7.0, 2.4), (-0.4, -3.0, 2.1), (-0.8, 1.0, 2.6), (0.6, 5.0, 2.2), (0.8, 9.0, 2.4), (-0.3, 12.5, 2.0), (0, 15.0, 1.4)]
    p = cv.add_path(pts, smooth=1.2)
    L = p.L
    u = L / 30.6                                   # control points given for a 30.6 m path
    ctrl = [(0, 2.8), (2.4, 2.8), (5.6, 1.22), (9.2, 1.22), (11.2, 2.0), (12.8, 2.0), (15.0, 1.88), (17.8, 1.88), (20.0, 1.22), (23.6, 1.22),
            (25.2, 2.0), (26.6, 2.0), (28.4, 2.8), (30.6, 2.8)]
    cv.prof_head = (Profile([(a * u, b) for a, b in ctrl], L, 0.9), 3.2)
    cv.add_floor(lambda x, y, c: 0.0 * x)
    add_openings(cv, [S_('S', 0.0, 0.0, 6.0, (0, -15.0)), S_('N', 0.0, 0.0, 6.0, (0, 15.0))])
    route(cv, 'main', path_pts(p), 'P', 1.3, 1.5)
    prm = dict(BASE, label='GalleryCrawl', seed=104, rx=3.6, ry=15.5, h=2.8, wall_amp=0.10, ribs=0.05, stalactites=6, hero=0, cracks=2, crack_len=(1.5, 2.5),
               len_st=(0.15, 0.5), fill=60, grid=0.10, voxel=0.06, vox5=0.04, budget=180000, coll=20000, crawl_mask=1, rho_scale=2.4, excl=0.5,
               knob_amp=0.05, knob2_amp=0.03, ledge_amp=0.03, floor_big=0.04)
    return cv, prm


ASSETS = {'pillars': pillars, 'lake': lake, 'cascade': cascade, 'collapse': collapse, 'gallerycrawl': gallery_crawl}
