# Poly Haven (CC0) sets -> Enfusion BCR (RGB colour, A roughness) and NMO (RG DirectX normal, B metalness 0, A occlusion) TIFFs
import os, sys, json
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
SRC = sys.argv[1]
OUT = sys.argv[2]
SETS = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
os.makedirs(OUT, exist_ok=True)
sheet = []
for src, name in SETS.items():
    d = os.path.join(SRC, src)
    diff = Image.open(os.path.join(d, 'diff.jpg')).convert('RGB')
    size = diff.size
    rough = Image.open(os.path.join(d, 'rough.jpg')).convert('L').resize(size)
    ao = Image.open(os.path.join(d, 'ao.jpg')).convert('L').resize(size)
    nor = np.asarray(Image.open(os.path.join(d, 'nor.jpg')).convert('RGB').resize(size)).copy()
    nor[..., 1] = 255 - nor[..., 1]                      # OpenGL -> DirectX: green flipped
    bcr = np.dstack([np.asarray(diff), np.asarray(rough)])
    nmo = np.dstack([nor[..., 0], nor[..., 1], np.zeros(nor.shape[:2], np.uint8), np.asarray(ao)])
    Image.fromarray(bcr, 'RGBA').save(os.path.join(OUT, name + '_BCR.tif'), compression='tiff_lzw')
    Image.fromarray(nmo, 'RGBA').save(os.path.join(OUT, name + '_NMO.tif'), compression='tiff_lzw')
    print(name, size, 'rough mean %.0f' % np.asarray(rough).mean(), 'ao mean %.0f' % np.asarray(ao).mean())
    sheet.append(diff.resize((320, 320)))
strip = Image.new('RGB', (320 * len(sheet), 320))
for i, im in enumerate(sheet):
    strip.paste(im, (i * 320, 0))
strip.save(os.path.join(SRC, 'sheet.png'))
open(os.path.join(OUT, 'LICENSE.txt'), 'w').write(
    'Source textures: Poly Haven (https://polyhaven.com), CC0 1.0 public domain.\n'
    'Cave_Flowstone = marble_rock_02, Cave_Wall = rock_face_03, Cave_WallDark = dark_rock_02,\n'
    'Cave_Floor = dry_riverbed_rock, Cave_Riverbed = river_small_rocks (2k, repacked as BCR / NMO).\n')
