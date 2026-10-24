"""Pack Poly Haven (CC0) stone scans into MatPBRMulti layers: <name>_BCR.tif (sRGB colour + roughness A), <name>_NMO.tif (DirectX normal RG, metalness 0, AO A).
usage: blender -b --factory-startup -P make_stone_layers.py -- <scan root> <out _Layers dir>
scans: rock_2 -> CliffLayer_StoneTan, rock_01 -> CliffLayer_StoneDark (files <scan>/<scan>_{diff,nor_dx,arm}_4k.jpg)"""
import bpy, sys, os
import numpy as np

root, out_dir = sys.argv[sys.argv.index("--") + 1:][:2]
LAYERS = [("CliffLayer_StoneTan", "rock_2"), ("CliffLayer_StoneDark", "rock_01")]
ROUGH_MIN = 0.35
scene = bpy.context.scene
scene.view_settings.view_transform = 'Raw'
scene.view_settings.look = 'None'


def pixels(path, cs):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = cs
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def write_tiff(arr, path):
    h, w = arr.shape[:2]
    q = np.round(np.clip(arr, 0, 1) * 255) / 255
    img = bpy.data.images.new("out", w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(q.astype(np.float32).ravel())
    ims = scene.render.image_settings
    ims.file_format, ims.color_mode, ims.color_depth, ims.tiff_codec = 'TIFF', 'RGBA', '8', 'LZW'
    img.save_render(path, scene=scene)
    bpy.data.images.remove(img)


for name, scan in LAYERS:
    d = os.path.join(root, scan)
    diff = pixels(os.path.join(d, f"{scan}_diff_4k.jpg"), 'Non-Color')    # sRGB values as stored
    nor = pixels(os.path.join(d, f"{scan}_nor_dx_4k.jpg"), 'Non-Color')
    arm = pixels(os.path.join(d, f"{scan}_arm_4k.jpg"), 'Non-Color')
    rough = ROUGH_MIN + (1 - ROUGH_MIN) * np.clip(arm[..., 1], 0, 1)
    write_tiff(np.dstack([diff[..., :3], rough]), os.path.join(out_dir, f"{name}_BCR.tif"))
    write_tiff(np.dstack([nor[..., 0], nor[..., 1], np.zeros_like(rough), arm[..., 0]]), os.path.join(out_dir, f"{name}_NMO.tif"))
    lin = diff[..., :3].reshape(-1, 3).mean(0)
    print("L_LAYER", name, "mean sRGB", lin.round(3), "size", diff.shape[:2])
print("L_DONE")
