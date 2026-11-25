"""W2_assets: the wave-2 cave assets as parameter sets for the W2 shape engine (W2_engine.py).

Every builder returns (cave, params): `cave` is a Cave2D (footprint, floor, headroom, openings, routes, extras) and `params` the
overrides for the dripstone generator's parameter dict (formation counts, resolutions, budgets).  Seeds are fixed: the same numbers
give the same cave.  Coordinates: Blender space like the kit (X right, Y forward, Z up, standing floors at z = 0; openings are
axis aligned: S/N = -Y/+Y, W/E = -X/+X).

Movement modes and the clearances they must keep along the whole route (measured by W2_check.py on the collider):
  W walk >= 2.0 m, C crouch >= 1.6 m (EoH C opening 1.571), P prone >= 0.92 m (EoH P opening 0.899); route width >= 1.3 m for C and P, 1.2 for W.
"""
import math
import numpy as np
from W2_engine import *

SOCKET_W, SOCKET_H = 1.4, 2.1


def S_(side, along, dz=0.0, pf=4.0, xy=None, dug=False):
    """an opening: side of the piece, lateral position, floor height, probe distance, mouth position"""
    return dict(side=side, along=along, dz=dz, pf=pf, xy=xy, dug=dug)


def add_openings(cv, ops):
    for o in ops:
        cv.add_opening(o['side'], o['along'], o['dz'], o['pf'], o['xy'])
        cv.openings[-1]['dug'] = o.get('dug', False)


def route(cv, name, pts, mode, width=1.3, hw=1.2, sock=None, to=None, only=None):
    """a walking line for the checker and for keeping formations off it: points (x, y), mode W/C/P; sock = (opening i, opening j),
    or `to` = a target point instead of the second opening; `only` = predicate (x, y) restricting the cells the route may use"""
    cv.routes[name] = dict(pts=[tuple(p) for p in pts], mode=mode, w=width, sock=sock or (0, len(cv.openings) - 1), to=to, only=only)
    cv.route_hw[name] = hw


def path_pts(p, step=0.5):
    n = max(2, int(p.L / step) + 1)
    ss = np.linspace(0, p.L, n)
    xs, ys = p.xy_at(ss)
    return list(zip(xs.tolist(), ys.tolist()))


BASE = dict(rx=4.0, ry=4.0, h=3.0, depth=1.5, p=2.7, wobble=0.08, pools=0, pool_r=(1.0, 1.4), pool_depth=(0.2, 0.3), lip=(0.06, 0.1),
            talus=0.0, relief=0.03, ribs=0.06, wall_amp=0.12, stalactites=0, stalagmites=0, columns=0, pairs=0, straws=0, len_st=(0.2, 1.0),
            cracks=0, crack_len=(1.5, 3.0), crack_density=8.0, hero=0, curtains=0, boulders=0, candles=0, gours=0, bank=0.0, swell=0.0,
            floor_big=0.05, bulge_amp=0.08, cluster_scale=1.0, col_span=5.0, ledge_amp=0.05, knob_amp=0.08, knob2_amp=0.04, grid=0.10, voxel=0.06,
            fill=60, vox5=0.03, budget=110000, coll=6000, excl=0.5, rho_scale=1.4, crawl_mask=0, min_clear=0.0, label='W2')


# =====================================================================================================================
def squeeze_p():
    """TT_Cave_Pass_SqueezeP: standing ends, a diagonal jog (no sight line) and 3.5 m of prone crawl, roof 1.22 m by design."""
    cv = Cave2D('TT_Cave_Pass_SqueezeP', 103, H0=2.75, wa=0.7, pa=2.4, k_corner=0.5, k_floor=0.5, wall_noise=(0.30, 0.12),
                head_noise=(0.08, 0.04), floor_noise=(0.03, 0.012), wall_open_r=(1.5, 3.2))
    p = cv.add_path([(0, -7.4, 1.35), (0, -5.0, 1.35), (-1.8, -2.4, 1.8), (1.8, 2.4, 1.8), (0, 5.0, 1.35), (0, 7.4, 1.35)], smooth=0.9)
    L, m = p.L, p.L / 2
    cv.prof_head = (Profile([(0, 2.75), (m - 5.4, 2.75), (m - 1.85, 1.22), (m + 1.85, 1.22), (m + 5.4, 2.75), (L, 2.75)], L, 0.9), 2.5)
    add_openings(cv, [S_('S', 0.0, 0.0, 5.6, (0, -7.4)), S_('N', 0.0, 0.0, 5.6, (0, 7.4))])
    route(cv, 'main', path_pts(p), 'P', 1.3, 1.3)
    prm = dict(BASE, label='SqueezeP', seed=103, rx=3.3, ry=7.8, h=2.7, wall_amp=0.10, ribs=0.05, stalactites=2, hero=0, cracks=1, crack_len=(1.5, 2.5),
               straws=0, len_st=(0.15, 0.5), fill=30, grid=0.10, voxel=0.05, vox5=0.03, budget=100000, coll=16000, crawl_mask=1, min_clear=0.92,
               rho_scale=1.5, excl=0.45, knob_amp=0.05, knob2_amp=0.03, ledge_amp=0.03, floor_big=0.04)
    return cv, prm




ASSETS = {'squeezep': squeeze_p}


def build(key):
    if key not in ASSETS:
        import W2_assets2, W2_assets3
        ASSETS.update(W2_assets2.ASSETS)
        ASSETS.update(W2_assets3.ASSETS)
    return ASSETS[key]()
