import json,glob,os
for f in sorted(glob.glob('results/W2_uv_*.json')):
    d=json.load(open(f))
    for ob in d['objects']:
        for k,v in ob.items():
            if k.endswith('UVMask'): print(os.path.basename(f)[6:-5], ob['name'][-12:], v['tris_zero_uv_area'], v['tris_in_overlap'], v['tris_uv_winding_neg'])
