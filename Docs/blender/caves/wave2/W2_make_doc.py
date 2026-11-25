"""W2_make_doc: writes Docs/CaveKit_Wave2.md from the result files in wave2/results (stats, check, report json) and the notes below.
  python -I Docs/blender/caves/wave2/W2_make_doc.py        (plain Python, run again after every asset)
"""
import os, sys, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
RES = os.path.join(HERE, 'results')
sys.path.insert(0, HERE)
import W2_assets as A
A.build('crack')

ORDER = ['squeezep', 'breakthrough', 'squeezec', 'crack', 'flooded', 'saddle', 'rubble', 'bubble', 'cleft', 'tri', 'star', 'sump', 'grottocrawl', 'hole',
         'cutting', 'pillars', 'lake', 'cascade', 'collapse', 'gallerycrawl']
SKIPPED = [('TT_Cave_Grotto_Jewel', 'skipped on purpose: the existing TT_Cave_Room_Grotto is the same asset (a small round dead-end chamber, one standing opening, crowded with formations)'),
           ('TT_Cave_Ledge_Rift', 'not mine (the new-rooms agent builds it with TwoLevel / SwimThrough)'),
           ('TT_Cave_Hall_Cathedral{Head,Mid,Foot}', 'not needed: Drip_E is the single long cathedral')]
NOTES = json.load(open(os.path.join(HERE, 'W2_notes.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'W2_notes.json')) else {}


def load(name, kind):
    p = os.path.join(RES, 'W2_%s_%s.json' % (kind, name))
    return json.load(open(p)) if os.path.exists(p) else None


rows, secs = [], []
for key in ORDER:
    try:
        cv, prm = A.build(key)
    except Exception as e:
        continue
    name = cv.name
    st, ck, rp = load(name, 'stats'), load(name, 'check'), load(name, 'report')
    note = NOTES.get(key, {})
    status = note.get('status', 'not built' if st is None else 'built')
    size = '%.1f x %.1f x %.1f' % tuple(rp['bbox_m']) if rp else '-'
    routes = ''
    if ck:
        parts = []
        for rn, r in ck['routes'].items():
            if 'route_clear_height' in r:
                parts.append('%s %s: %.2f m high, %.2f m wide%s%s' % (rn, r['mode'], r['route_clear_height'], r['route_clear_width'], (', centre %.2f m' % r['route_centre_height']) if 'route_centre_height' in r else '', '' if r.get('PASS') else ' FAIL'))
        routes = '; '.join(parts)
    leak = ('sealed' if ck['leak_test'].get('sealed') else 'LEAK') if ck and ck.get('leak_test') else '-'
    rows.append('| `%s` | %s | %s | %s | %s | %s |' % (name, status, size, '%dk / %dk' % (rp['tris_lod0'] // 1000, rp['tris_collider'] // 1000) if rp else '-', routes or '-', leak))
    s = ['### `%s`' % name, '', note.get('what', cv.__doc__ if False else ''), '']
    s.append('Status: **%s**.' % status)
    if st:
        s.append('Budgets: LOD0 %d triangles, collider %d, build %.0f s, remesh voxel %.3f m, opening profile points %s.' % (st['tris_lod0'], st['tris_collider'], st['build_s'], st['voxel'], ' / '.join(st['opening_profile_points_found'])))
    if rp:
        s += ['', 'Sockets (model space, Blender: X right, Y forward, Z up; floor-centre position; direction = outward):', '',
              '| # | floor centre (x, y, z) | out | clear (w x h) | standing height |', '|---|---|---|---|---|']
        for sk in rp['sockets']:
            s.append('| %d | %.2f, %.2f, %.2f | %.0f, %.0f | 1.40 x 2.10 | 2.10 |' % (sk['id'], *sk['floor_centre'], *sk['out']))
    if ck:
        s += ['', 'Measured (collider UTM, 0.1 m columns): ']
        for rn, r in ck['routes'].items():
            if 'route_clear_height' not in r:
                s.append('- route `%s`: %s' % (rn, r.get('error')))
                continue
            s.append('- route `%s` (mode %s, needs %.2f m high and %.1f m wide): clearance %.2f m%s, widest corridor %.2f m, length %s m (straight %s), min headroom on the shortest path %s m; metres by mode W %s / C %s / P %s; steepest floor %s deg, biggest step %s m. %s' % (
                rn, r['mode'], r['req_height'], r['req_width'], r['route_clear_height'], (' (centre line %.2f m)' % r['route_centre_height']) if 'route_centre_height' in r else '', r['route_clear_width'], r.get('length_m'), r.get('straight_m'),
                r.get('min_headroom_on_path'), r.get('metres_W_ge2.0'), r.get('metres_C_1.6_2.0'), r.get('metres_P_0.92_1.6'), r.get('max_slope_deg'),
                r.get('max_step_between_cells_m'), 'PASS' if r.get('PASS') else '**FAIL**'))
        lk = ck.get('leak_test', {})
        s.append('- leak test (voxel %s m, openings plugged): %s, flood volume %s m3; false-hope cells (0.35-0.92 m) %s m2' % (lk.get('voxel'), 'SEALED' if lk.get('sealed') else '**LEAK**', lk.get('flood_volume_m3'), ck.get('false_hope_cells_m2')))
    uv = load(name, 'uv')
    if uv:
        parts = []
        for ob in uv['objects']:
            for k, v in ob.items():
                if k.endswith('UVMask'):
                    parts.append('%s: zero-area %d, overlapping %d, negative winding %d' % (ob['name'], v['tris_zero_uv_area'], v['tris_in_overlap'], v['tris_uv_winding_neg']))
        s.append('- UV2 (mask) check of the exported FBX (`W2_uvcheck.py`, 1024 raster): ' + '; '.join(parts))
    if note.get('issues'):
        s += ['', 'Known issues: ' + note['issues']]
    secs.append('\n'.join(s))

head = open(os.path.join(HERE, 'W2_doc_head.md'), encoding='utf-8').read() if os.path.exists(os.path.join(HERE, 'W2_doc_head.md')) else '# Cave kit wave 2\n'
out = [head.rstrip(), '', '## Asset table', '', '| asset | status | size (m, bbox incl. stubs) | tris LOD0 / collider | measured routes (clear height, width) | sealed |', '|---|---|---|---|---|---|'] + rows
out += ['', '### Not built / skipped', ''] + ['- `%s`: %s' % x for x in SKIPPED]
out += ['', '## Assets', ''] + ['\n\n'.join(secs)]
tail = open(os.path.join(HERE, 'W2_doc_tail.md'), encoding='utf-8').read() if os.path.exists(os.path.join(HERE, 'W2_doc_tail.md')) else ''
out += ['', tail]
open(os.path.join(ADDON, 'Docs', 'CaveKit_Wave2.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
print('wrote Docs/CaveKit_Wave2.md with', len(rows), 'assets')
