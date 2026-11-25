"""TT_Adapter_Cave: a 3 m entrance piece between the NEW standing tunnel ring (1.6 x 2.2, tunnelkit_build_clear.py) and the OLD cave
opening ring (1.4 x 2.1, the 11-point INNER of tunnelkit_build.py that every cave model still has).  Opening "1" (socket 1) = new ring
(joins a dug tunnel), opening "2" = old ring (joins a cave).  Built with the redesign builder's own morph/sweep/sleeve code, exact rings at both ends.
Run:  blender.exe --factory-startup -b --python tunnelkit_build_adapter.py        (env CL_OUT_DIR = where the FBX goes; default redesign_staging/adapter)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('CL_OUT_DIR', os.path.join(HERE, 'redesign_staging', 'adapter'))
KIT = os.path.join(HERE, 'tunnelkit_build_clear.py')
g = {'__name__': 'tunnelkit_adapter', 'CL_NORUN': True}
exec(compile(open(KIT, encoding='utf-8').read(), KIT, 'exec'), g)

# the old cave ring, the 11-point INNER of tunnelkit_build.py, as 24 points on its own edges (same count as the new ring so the two can be
# morphed): right half from the floor corner up to the crown (apex (0, 2.1) replaced by (+-0.02, 2.095): 5 mm), then mirrored
right = [(0.70, 0.00), (0.72, 0.40), (0.74, 0.80), (0.7267, 1.00), (0.7133, 1.20), (0.70, 1.40), (0.63, 1.59), (0.56, 1.78),
         (0.44, 1.90), (0.32, 2.02), (0.18, 2.055), (0.02, 2.095)]
K_RING = right + [(-x, z) for x, z in reversed(right)]
g['CLASSES']['K'] = dict(hw=0.74, H=2.10, r=0.0, mp=1.00, wall_amp=0.06, floor_amp=0.015)
_orig = g['ring_profile']
g['ring_profile'] = lambda cls: [tuple(p) for p in K_RING] if cls == 'K' else _orig(cls)
g['TRANS_KEYS'][('S', 'K')] = [('S', 0.0), ('S', 0.6), ('K', 2.4), ('K', 3.0)]
piece = g['build_trans']('S', 'K')
piece.name = 'TT_Adapter_Cave'
g['export'](piece)
print('ADAPTER DONE', flush=True)
