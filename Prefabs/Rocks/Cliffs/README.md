# Cliffs for Enfusion Workbench — MatPBRMulti, guide set-up

Nine static cliffs, 50 m along the longest horizontal side, pivot at the base centre. Set up per the "Terrain-Klippen: Masken-Setup für MatPBRMulti" guide: **one UV set**, **one 4096 RGB mask per cliff**, the **original tiling PBR textures** as the four layers. No pre-baked colour, macro or global maps.

## Folder layout

```
_Layers/   shared by all cliffs, 4K, seamless
  CliffLayer_RockPorous_*     Material 1 (Base)        cracked_red_ground
  CliffLayer_Sand_*           Material 2 (MaskMap R)   sandy_gravel_02
  CliffLayer_Scree_*          Material 3 (MaskMap G)   red_laterite_soil_stones
  CliffLayer_SandstonePale_*  Material 4 (MaskMap B)   worn_rock_natural_01
    *_BCR.tif / *_NMO.tif           colour-graded to the reference look (recommended)
    *_RAW_BCR.tif / *_RAW_NMO.tif   untouched scans, only repacked (tint with Color N)
    *_DETAIL_MASK.tif               height map, usable as Mask N breakup noise
<Asset>/
  <Asset>.fbx             LOD0-LOD6 (one UV set, material <Asset>), UTM_ collider, OCC_ occluders
  <Asset>_MASK.tif        4096 RGB, linear: R sand on ledges, G scree in crevices/at the foot, B pale accents
  <Asset>_enfusion.blend  preview scene: Blender imitation of the MatPBRMulti set-up below
  <Asset>_report.json     UV stats, tiling, collider/occluder stats
```

## Import steps

1. Import `_Layers/*_BCR.tif` as colour (sRGB) and `*_NMO.tif`, `*_MASK.tif`, `*_DETAIL_MASK.tif` as linear.
2. Import the FBX. Import Settings → Physics → Geometry Params: set SurfaceProperties of the collider to a rock `.gamemat` (layer preset `RockFireView` comes from the FBX custom property `usage`).
3. Set the generated `<Asset>.emat` to MatPBRMulti and fill it as in the table of the asset (all LODs share it). Both MaskMap and the layers use UV set 1 (the only one).
4. Tune from close up, then check repetition from a distance (guide: raise base tiling until the close-up detail is right).

Common settings: Det Normal 1.0 (keep moderate on steep faces), Mask Sharpness / Mask Offset 0 to start; for crisper transitions put the layer's `_DETAIL_MASK` in Mask N and raise Mask Sharpness. Material 4 is rotated 90°.

## Per asset

| Asset | Size (m) | LOD0 tris | UV islands | 1 UV unit | Mask px/m | Tiling base / R / G / B | Collider | Occluders |
|---|---|---|---|---|---|---|---|---|
| Cliff_CrimsonBadlandsRidge | 50.0 × 41.3 × 19.1 | 195,000 | 734 | 108.85 m | 37.6 | 54.4 / 40.3 / 33.0 / 26.5 | 19,914 tris, decimate, dev. 0.023 m mean | 28.5 × 4.0 × 17.5; 1.5 × 22.5 × 13.5 |
| Cliff_CrimsonMesaCitadel | 50.0 × 40.9 × 22.1 | 195,000 | 806 | 106.37 m | 38.5 | 53.2 / 39.4 / 32.2 / 25.9 | 19,926 tris, decimate, dev. 0.025 m mean | 33.0 × 6.0 × 15.5; 34.5 × 19.5 × 6.5 |
| Cliff_CrimsonSpires | 50.0 × 42.4 × 22.2 | 194,932 | 631 | 105.01 m | 39.0 | 52.5 / 38.9 / 31.8 / 25.6 | 20,000 tris, decimate, dev. 0.022 m mean | 34.0 × 3.0 × 15.5; 0.5 × 26.5 × 13.5; 38.5 × 13.0 × 6.5 |
| Cliff_DesertFortress | 50.0 × 47.0 × 17.0 | 194,912 | 655 | 106.86 m | 38.3 | 53.4 / 39.6 / 32.4 / 26.1 | 19,944 tris, decimate, dev. 0.026 m mean | 33.5 × 13.0 × 10.0; 31.5 × 1.0 × 16.0; 0.5 × 26.0 × 12.5 |
| Cliff_ErodedCanyonWall | 50.0 × 41.8 × 12.7 | 172,134 | 4804 | 100.45 m | 40.8 | 50.2 / 37.2 / 30.4 / 24.5 | 19,960 tris, decimate, dev. 0.024 m mean | 14.0 × 9.0 × 12.5; 9.0 × 7.5 × 13.0; 10.0 × 3.5 × 13.0 |
| Cliff_ErodedDesertCliffs | 50.0 × 47.1 × 15.8 | 194,999 | 857 | 111.69 m | 36.7 | 55.8 / 41.4 / 33.8 / 27.2 | 19,910 tris, decimate, dev. 0.027 m mean | 35.0 × 13.5 × 11.0; 0.5 × 24.5 × 14.0; 34.0 × 0.5 × 15.0 |
| Cliff_ErodedDesertEscarpment | 50.0 × 41.5 × 16.9 | 194,999 | 719 | 105.34 m | 38.9 | 52.7 / 39.0 / 31.9 / 25.7 | 19,964 tris, decimate, dev. 0.024 m mean | 34.0 × 3.0 × 15.0; 31.0 × 19.0 × 7.0 |
| Cliff_ErodedSandstoneWall | 50.0 × 37.9 × 12.8 | 194,822 | 643 | 87.89 m | 46.6 | 43.9 / 32.6 / 26.6 / 21.4 | 19,942 tris, decimate, dev. 0.021 m mean | 23.5 × 0.5 × 12.5; 8.0 × 8.0 × 13.0; 7.5 × 9.5 × 13.0 |
| Cliff_HorseshoeRidge | 50.0 × 48.2 × 15.4 | 167,612 | 6515 | 159.23 m | 25.7 | 79.6 / 59.0 / 48.3 / 38.8 | 19,906 tris, voxel hull 0.2 m, dev. 0.082 m mean | 25.0 × 6.0 × 13.8; 4.5 × 18.5 × 8.8 |

Tiling = metres per UV unit ÷ repeat, with repeats of 2.0 m (base), 2.7 m (sand), 3.3 m (scree) and 4.1 m (pale sandstone): no common divisor, so the layers don't line up. At 4K every layer is ≥1000 px/m.

## Example `.emat` block (first asset)

```
MatPBRMulti {
 MaskMap "Cliff_CrimsonBadlandsRidge_MASK.edds"
 BCR_1 "CliffLayer_RockPorous_BCR.edds"  NMO_1 "CliffLayer_RockPorous_NMO.edds"
 UVTransform_1 MatUVTransform { TilingU 54.4 TilingV 54.4 }   // 2.0 m repeat
 Enabled_2 1
 BCR_2 "CliffLayer_Sand_BCR.edds"  NMO_2 "CliffLayer_Sand_NMO.edds"
 UVTransform_2 MatUVTransform { TilingU 40.3 TilingV 40.3 }   // 2.7 m repeat
 Enabled_3 1
 BCR_3 "CliffLayer_Scree_BCR.edds"  NMO_3 "CliffLayer_Scree_NMO.edds"
 UVTransform_3 MatUVTransform { TilingU 33.0 TilingV 33.0 }   // 3.3 m repeat
 Enabled_4 1
 BCR_4 "CliffLayer_SandstonePale_BCR.edds"  NMO_4 "CliffLayer_SandstonePale_NMO.edds"
 UVTransform_4 MatUVTransform { TilingU 26.5 TilingV 26.5 Rotation 90 }   // 4.1 m repeat
}
```

## How it was made / known limits

- UVs: seams on the cliff's large folds (charts from smoothed surface direction), Conformal unwrap, charts that drift in scale or stretch are cut in half and re-unwrapped, then Average Islands Scale + Pack (no Smart UV Project). Island borders are texture seams for the tiling layers; check them from close up.
- Mask: baked (Emit, 16 px margin) from the procedural Blender material in `../*_pbr.blend`: R from slope + rock height + dust, G from high-poly AO in crevices × noise plus the foot, B from noise-driven patches. Paint over it in Texture Paint with pure channel colours if needed.
- Canyon Wall and Horseshoe Ridge were hollow double-skinned Meshy meshes; the hidden inner skin was removed before decimation, their colliders come from a 20 cm voxel hull.
- Not checked inside Workbench (Windows-only); the Blender preview is an imitation of the shader.
