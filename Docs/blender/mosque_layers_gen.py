"""Generate real fine-grain tileable layer textures (the original base layers were nearly flat: colour std 1-4) with multi-octave detail from 1 mm to 10 cm
when one tile = 1 m (2048 px -> 0.5 mm/texel).  Overwrites MosqueLayer_{PlasterBase,StoneBase,PaintWhite,BandPaint}_{BCR,NMO}.tif.
usage (addon root): python Docs/blender/mosque_layers_gen.py"""
import os
import numpy as np
from PIL import Image
STRENGTH = float(os.environ.get("NOISE_STRENGTH", "0.5"))   # global subtlety of the layer noise: 1.0 = previous (too strong), 0.0 = flat
N = 2048; OUT = "Prefabs/Structures/Mosque_01/_Layers/"
fx = np.fft.fftfreq(N)[:, None]; fy = np.fft.fftfreq(N)[None, :]; F = np.sqrt(fx ** 2 + fy ** 2); F[0, 0] = 1.0

def noise(power, seed, fmin=0.0, fmax=0.5):
    """periodic noise, amplitude spectrum ~ f^-power, band limited, unit std"""
    w = np.random.default_rng(seed).standard_normal((N, N)); S = np.fft.fft2(w) * F ** (-power)
    S[(F < fmin) | (F > fmax)] = 0; S[0, 0] = 0
    a = np.real(np.fft.ifft2(S)); return a / a.std()

def blur1(a):
    return (a * 4 + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 8

def make(name, base, seed, fine, mid, big, pits, rough, bump):
    h_fine = noise(0.35, seed, 0.06, 0.5)              # 1-4 px grain (sand)
    h_mid = noise(1.0, seed + 1, 0.01, 0.12)           # 4-50 px blotches (0.2-2.5 cm)
    h_big = noise(1.2, seed + 2, 0.002, 0.02)          # 2.5-25 cm cloudiness
    w = np.random.default_rng(seed + 3).standard_normal((N, N)); pit = blur1(((w > pits) * 1.0))   # sparse dark pits
    fine, mid, big, bump = fine * STRENGTH, mid * STRENGTH, big * STRENGTH, bump * (0.4 + 0.6 * STRENGTH)
    lum = 1 + fine * h_fine + mid * h_mid + big * h_big - 0.35 * STRENGTH * pit
    tint = noise(1.0, seed + 4, 0.002, 0.03) * 0.012
    rgb = np.stack([base[0] * (lum + tint), base[1] * lum, base[2] * (lum - tint)], -1)
    bcr = np.dstack([np.clip(rgb, 0, 255), np.clip(rough + 18 * h_fine - 40 * STRENGTH * pit, 120, 255)[..., None]]).astype(np.uint8)
    height = 0.55 * h_fine + 0.9 * h_mid + 0.5 * h_big - 1.6 * STRENGTH * pit
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5; gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5
    nx = np.clip(128 - gx * bump, 0, 255); ny = np.clip(128 - gy * bump, 0, 255)
    nmo = np.dstack([nx, ny, np.zeros((N, N)), np.clip(255 - 70 * STRENGTH * pit - 8 * np.abs(h_mid), 150, 255)]).astype(np.uint8)
    Image.fromarray(bcr, "RGBA").save(OUT + f"MosqueLayer_{name}_BCR.tif"); Image.fromarray(nmo, "RGBA").save(OUT + f"MosqueLayer_{name}_NMO.tif")
    print(name, "colour std", bcr[..., :3].mean(2).std().round(1))

make("PlasterBase", (158, 140, 120), 11, fine=0.060, mid=0.055, big=0.035, pits=3.4, rough=205, bump=34)
make("StoneBase",   (170, 163, 152), 21, fine=0.075, mid=0.070, big=0.045, pits=3.0, rough=225, bump=44)
make("PaintWhite",  (190, 183, 172), 31, fine=0.040, mid=0.035, big=0.025, pits=3.7, rough=215, bump=22)
make("BandPaint",   (89, 59, 33),    41, fine=0.060, mid=0.050, big=0.030, pits=3.5, rough=200, bump=30)
