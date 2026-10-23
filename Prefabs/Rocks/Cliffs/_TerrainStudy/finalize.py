"""python -I finalize.py <npy_dir>  -> writes TerrainCandidate_<Name>_BCR.tif / _NMO.tif (RGBA 8-bit, LZW) next to this script"""
import numpy as np, sys, os
from PIL import Image
d=sys.argv[1]; here=os.path.dirname(os.path.abspath(__file__))
for nm in ['FootDebris','DustyTransition','CliffMatch']:
    for k,suf in (('bcr','BCR'),('nmo','NMO')):
        a=np.load(f'{d}/{nm}_{k}.npy'); assert a.shape==(4096,4096,4)
        Image.fromarray(a,'RGBA').save(f'{here}/TerrainCandidate_{nm}_{suf}.tif',compression='tiff_lzw',dpi=(72,72))
        print('wrote',nm,suf)
