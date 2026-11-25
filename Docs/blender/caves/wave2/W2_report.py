"""W2_report: facts about a built asset for the doc (run in Blender on W2_<name>_v5.blend): sockets (floor-centre position, outward direction),
bounding boxes, triangle counts, collider size.  Writes W2_report_<name>.json next to the blend (CAVE_OUT).
  blender --factory-startup -b W2_<name>_v5.blend --python W2_report.py      env: W2_ASSET  CAVE_OUT
"""
import os, sys, json
import bpy
from mathutils import Vector

HERE = os.environ.get('W2_DIR', r"c:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Docs\blender\caves\wave2")
sys.path.insert(0, HERE)
import W2_assets as WA

shape, prm = WA.build(os.environ['W2_ASSET'])
NAME = shape.name
OUT = os.environ.get('CAVE_OUT', os.path.dirname(bpy.data.filepath))
lod = bpy.data.objects[NAME + '_LOD0']
utm = bpy.data.objects['UTM_' + NAME]
rep = dict(name=NAME)
rep['bbox_m'] = [round(v, 2) for v in lod.dimensions]
rep['bbox_min'] = [round(min(v.co[k] for v in lod.data.vertices), 2) for k in range(3)]
rep['bbox_max'] = [round(max(v.co[k] for v in lod.data.vertices), 2) for k in range(3)]
rep['tris_lod0'] = len(lod.data.polygons)
rep['tris_collider'] = len(utm.data.polygons)
rep['materials'] = [m.name for m in lod.data.materials if m]
socks = []
for o in sorted([o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.isdigit()], key=lambda o: int(o.name)):
    p = o.matrix_world.translation
    out = o.matrix_world.to_3x3() @ Vector((0, 0, 1))
    out.z = 0
    out.normalize()
    socks.append(dict(id=int(o.name), floor_centre=[round(p.x, 2), round(p.y, 2), round(p.z - 1.0, 2)], out=[round(out.x, 2), round(out.y, 2)]))
rep['sockets'] = socks
json.dump(rep, open(os.path.join(OUT, 'W2_report_%s.json' % NAME), 'w'), indent=1)
print('REPORT', json.dumps(rep))
