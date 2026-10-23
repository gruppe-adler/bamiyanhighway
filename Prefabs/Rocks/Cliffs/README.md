# Cliffs for Enfusion Workbench — MatPBRMulti, guide set-up

Twelve static cliffs (up to 50 m along the longest horizontal side, pivot at the base centre), plus six foot-less `_cut` variants for stacking (see below). Each has a ready-to-place prefab (`Cliff_Base_<Name>.et`, `Cliff_Cut_<Name>.et`, next to this file), and a second material on its open top surfaces that takes the terrain texture (see "Terrain slot"). Set up per the "Terrain-Klippen: Masken-Setup für MatPBRMulti" guide: **one UV set**, **one 4096 RGB mask per cliff**, the **original tiling PBR textures** as the four layers, plus one **global NMO** (rock-scale normal + ambient occlusion) per cliff for shadow depth. No pre-baked colour or macro maps.

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
  <Asset>_NMO.tif         4096, linear: normal from the 2M-tri source (DirectX RG), metalness 0 (B), AO ~2.5 m (A)
  <Asset>_enfusion.blend  preview scene: Blender imitation of the MatPBRMulti set-up below
  <Asset>_report.json     UV stats, tiling, collider/occluder stats
  Data/<Asset>.emat           MatPBRMulti for the rock (material 1)
  Data/<Asset>_terrain.emat   MatTerrainObject for the top surfaces (material 2, see "Terrain slot")
Cliff_Base_<Name>.et / Cliff_Cut_<Name>.et   prefabs (MeshObject + RigidBody, layer preset BuildingFireView), one folder up from the assets
_Tools/split_terrain_slot.py                 Blender script that adds the terrain slot and vertex colours to an FBX
```

Prefab names group by kind: all `Cliff_Base_*` are the full cliffs, all `Cliff_Cut_*` are the stackable variants.

## Import steps

1. Import `_Layers/*_BCR.tif` as colour (sRGB) and `*_NMO.tif`, `*_MASK.tif`, `*_DETAIL_MASK.tif`, `<Asset>_NMO.tif` as linear.
2. Import the FBX. Import Settings → Physics → Geometry Params: set SurfaceProperties of the collider to a rock `.gamemat` (layer preset `RockFireView` comes from the FBX custom property `usage`).
3. Set the generated `<Asset>.emat` to MatPBRMulti and fill it as in the table of the asset (all LODs share it). Both MaskMap and the layers use UV set 1 (the only one).
4. Tune from close up, then check repetition from a distance (guide: raise base tiling until the close-up detail is right).

### Global NMO (shadow depth)

Put `<Asset>_NMO.edds` into **GlobalNMOMap** (it uses UV set 1 — the only set — so leave its UV source empty). It restores the rock-scale relief lost by decimating 2M → 195k tris and, through its alpha, the ambient occlusion that keeps crevices and recesses dark instead of sky-lit. Then, in *Basic material modifiers*:

- **Global AO Power** (default 0.9): how strongly that AO darkens ambient light. Start at 1.0; raise towards 1.5 for deeper shadows.
- **Cavity From AO** (default 0): also darkens the albedo in occluded spots. Start around 0.3–0.5 if crevices still look lifted.
- Keep **Det Normal N** on the layers moderate (≈1.0); the global map now carries the large forms.

Both values are starting points: their exact effect in Workbench wasn't measurable from here.

Common settings: Det Normal 1.0 (keep moderate on steep faces), Mask Sharpness / Mask Offset 0 to start; for crisper transitions put the layer's `_DETAIL_MASK` in Mask N and raise Mask Sharpness. Material 4 is rotated 90°.

## `_cut` variants (stacking)

`Cliff_<Name>_cut` is the wall cliff without its broad foot: LOD0 cut horizontally at the lowest height where the footprint is back within 15% of the wall's own footprint (30–40% of the height), the cut capped flat, every loose island removed (one connected piece in every LOD and in the collider). The pivot sits on the cap, so z=0 is the stacking plane. Scale is the parent's: one metre in the cut piece is one metre in the full cliff, so the longest side is under 50 m (Size column). Everything else is built as for the full cliffs (own UVs, 4096 MASK and NMO, LODs, collider, occluders); the shared `_Layers` apply, only the tiling numbers differ (table). The bottom edge carries no scree apron — the mask's foot rules refer to the original ground — so the seam reads as plain rock where it sits on the piece below. Horseshoe Ridge has no `_cut` variant (not a wall). Sheets: `previews/<Asset>_cut_*` and `previews/cut/_cut_variants_overview.jpg`.

| Variant | Cut at (m above the original base) | Share of height | Loose island faces removed |
|---|---|---|---|
| Cliff_CrimsonBadlandsRidge_cut | 6.88 of 19.12 | 36% | 116 |
| Cliff_CrimsonMesaCitadel_cut | 8.84 of 22.1 | 40% | 74 |
| Cliff_DesertFortress_cut | 6.63 of 17.04 | 39% | 20 |
| Cliff_ErodedCanyonWall_cut | 4.13 of 12.64 | 33% | 0 |
| Cliff_ErodedDesertCliffs_cut | 5.62 of 15.75 | 36% | 851 |
| Cliff_ErodedDesertEscarpment_cut | 6.38 of 16.87 | 38% | 272 |

## Per asset

| Asset | Size (m) | LOD0 tris | UV islands | 1 UV unit | Mask px/m | Tiling base / R / G / B | Collider | Occluders |
|---|---|---|---|---|---|---|---|---|
| Cliff_CrimsonBadlandsRidge | 50.0 × 41.3 × 19.1 | 195,000 | 734 | 108.85 m | 37.6 | 54.4 / 40.3 / 33.0 / 26.5 | 19,914 tris, decimate, dev. 0.023 m mean | 28.5 × 4.0 × 17.5; 1.5 × 22.5 × 13.5 |
| Cliff_CrimsonBadlandsRidge_cut | 40.1 × 28.6 × 12.2 | 113,034 | 1399 | 81.13 m | 50.5 | 40.6 / 30.0 / 24.6 / 19.8 | 20,000 tris, decimate, dev. 0.014 m mean | 28.5 × 3.5 × 10.9; 2.5 × 16.0 × 10.9 |
| Cliff_CrimsonMesaCitadel | 50.0 × 40.9 × 22.1 | 195,000 | 806 | 106.37 m | 38.5 | 53.2 / 39.4 / 32.2 / 25.9 | 19,926 tris, decimate, dev. 0.025 m mean | 33.0 × 6.0 × 15.5; 34.5 × 19.5 × 6.5 |
| Cliff_CrimsonMesaCitadel_cut | 41.3 × 24.1 × 13.3 | 103,202 | 1157 | 74.32 m | 55.1 | 37.2 / 27.5 / 22.5 / 18.1 | 20,000 tris, decimate, dev. 0.014 m mean | 32.5 × 2.5 × 8.4; 10.0 × 8.0 × 12.4 |
| Cliff_DesertFortress | 50.0 × 47.0 × 17.0 | 194,912 | 655 | 106.86 m | 38.3 | 53.4 / 39.6 / 32.4 / 26.1 | 19,944 tris, decimate, dev. 0.026 m mean | 33.5 × 13.0 × 10.0; 31.5 × 1.0 × 16.0; 0.5 × 26.0 × 12.5 |
| Cliff_DesertFortress_cut | 42.9 × 32.8 × 10.4 | 110,776 | 1271 | 84.61 m | 48.4 | 42.3 / 31.3 / 25.6 / 20.6 | 20,000 tris, decimate, dev. 0.017 m mean | 30.0 × 1.5 × 9.5; 0.5 × 21.5 × 7.5 |
| Cliff_ErodedCanyonWall | 50.0 × 41.8 × 12.6 | 194,148 | 165 | 80.83 m | 50.7 | 40.4 / 29.9 / 24.5 / 19.7 | 20,000 tris, decimate, dev. 0.014 m mean | 14.5 × 8.5 × 12.5; 8.5 × 8.0 × 13.0; 17.0 × 4.5 × 11.0 |
| Cliff_ErodedCanyonWall_cut | 47.0 × 36.2 × 8.5 | 126,410 | 401 | 70.46 m | 58.1 | 35.2 / 26.1 / 21.4 / 17.2 | 20,000 tris, decimate, dev. 0.009 m mean | 14.0 × 9.0 × 8.5; 9.0 × 7.5 × 9.0; 11.5 × 3.0 × 9.0 |
| Cliff_ErodedDesertCliffs | 50.0 × 47.1 × 15.8 | 194,999 | 857 | 111.69 m | 36.7 | 55.8 / 41.4 / 33.8 / 27.2 | 19,910 tris, decimate, dev. 0.027 m mean | 35.0 × 13.5 × 11.0; 0.5 × 24.5 × 14.0; 34.0 × 0.5 × 15.0 |
| Cliff_ErodedDesertCliffs_cut | 44.9 × 36.9 × 10.1 | 112,706 | 1727 | 87.98 m | 46.6 | 44.0 / 32.6 / 26.7 / 21.5 | 20,000 tris, decimate, dev. 0.018 m mean | 31.5 × 8.5 × 8.5; 0.5 × 23.0 × 9.0 |
| Cliff_ErodedDesertEscarpment | 50.0 × 41.5 × 16.9 | 194,999 | 719 | 105.34 m | 38.9 | 52.7 / 39.0 / 31.9 / 25.7 | 19,964 tris, decimate, dev. 0.024 m mean | 34.0 × 3.0 × 15.0; 31.0 × 19.0 × 7.0 |
| Cliff_ErodedDesertEscarpment_cut | 44.0 × 29.8 × 10.5 | 100,272 | 1024 | 81.1 m | 50.5 | 40.6 / 30.0 / 24.6 / 19.8 | 20,000 tris, decimate, dev. 0.014 m mean | 33.0 × 3.0 × 9.0; 1.0 × 17.0 × 8.5 |
| Cliff_ErodedSandstoneWall | 50.0 × 37.9 × 12.8 | 194,822 | 643 | 87.89 m | 46.6 | 43.9 / 32.6 / 26.6 / 21.4 | 19,942 tris, decimate, dev. 0.021 m mean | 23.5 × 0.5 × 12.5; 8.0 × 8.0 × 13.0; 7.5 × 9.5 × 13.0 |
| Cliff_HorseshoeRidge | 50.0 × 48.0 × 15.4 | 132,338 | 964 | 98.58 m | 41.5 | 49.3 / 36.5 / 29.9 / 24.0 | 20,000 tris, decimate, dev. 0.018 m mean | 26.5 × 5.0 × 14.4; 3.5 × 21.0 × 8.9 |
| Cliff_DesertMesaFragment | 48.5 × 22.0 × 25.1 | 194,788 | 1653 | 99.67 m | 41.1 | 49.8 / 36.9 / 30.2 / 24.3 | 19,984 tris, decimate, dev. 0.028 m mean | 39.5 × 10.0 × 20.5 |
| Cliff_DesertMonolith | 44.0 × 45.1 × 39.1 | 163,890 | 1047 | 134.82 m | 30.4 | 67.4 / 49.9 / 40.9 / 32.9 | 20,000 tris, decimate, dev. 0.030 m mean | 27.5 × 28.5 × 35.5 |
| Cliff_ErodedSandstoneWall02 | 48.4 × 21.3 × 26.8 | 179,560 | 370 | 84.17 m | 48.7 | 42.1 / 31.2 / 25.5 / 20.5 | 20,000 tris, decimate, dev. 0.017 m mean | 39.5 × 0.5 × 23.0 |
| Cliff_MesaOfStoneFaces | 49.4 × 20.6 × 29.2 | 194,666 | 260 | 95.63 m | 42.8 | 47.8 / 35.4 / 29.0 / 23.3 | 20,000 tris, decimate, dev. 0.019 m mean | 40.0 × 7.5 × 25.5 |

Tiling = metres per UV unit ÷ repeat, with repeats of 2.0 m (base), 2.7 m (sand), 3.3 m (scree) and 4.1 m (pale sandstone): no common divisor, so the layers don't line up. At 4K every layer is ≥1000 px/m.

## Terrain slot (second material on the top surfaces)

Every cliff FBX carries two materials: `<Asset>` (the rock, `MatPBRMulti`) and `<Asset>_terrain` (`Data/<Asset>_terrain.emat`, a `MatTerrainObject` child of `Common/Materials/default_MatTerrainObj_TerrShadows.emat`). The second slot covers the open, flat tops of the cliff and shows the terrain texture that is painted underneath, so the plateau reads as ground instead of bare rock. The `<Asset>.xob.meta` maps the source material `<material>_terrain` to that emat (a second `MaterialAssignClass`); after changing an FBX, reimport it and check that the `.xob` lists both materials.

**Blend.** The terrain slot fades from terrain to rock with vertex colour: `MaterialBlendUseVertexColor R` and `MaterialBlendUseTerrainDistance 1` in the emat. In the terrain faces R is 0 on the plateau (shows the terrain) and rises to 1 at the soft edge (shows the emat's own BCR/NMO, which should look like the rock). **All rock faces carry white (1.0).** The vertex colour multiplies the `MatPBRMulti` colour as well, so writing 0 there turns the cliff black.

**Which faces.** Made by `_Tools/split_terrain_slot.py` from the original FBX (usage and defaults are in the file header): smoothed up-facing at least 0.7, above 40% of the cliff's height, ambient occlusion (the global NMO alpha) at least 0.7 so crack interiors, lips and overhangs stay on the rock, islands of at least 20 m2. The plateau is then blurred mostly sideways into a smooth field, which gives rounded blend contours instead of the faceted ones a shortest-path distance along mesh edges produces. The terrain slot covers the faces where the field is above a small threshold; coarser LODs follow LOD0 per vertex. Terrain slot area is about 360–1,340 m2 per cliff (6–15% of the surface); Desert Monolith and Desert Mesa Fragment have the largest summits.

**Terrain emat.** All cliffs use the Sandstone Pale layer (`CliffLayer_SandstonePale_BCR/NMO`) with that layer's tiling from the cliff's table and rotation 90, `Color 0.791 0.703 0.703 1` and `ClutterThresholdAngle 20`. `Color` clamps at 1 in Workbench, so it can only darken; if the rock beside it is lighter, use a lighter texture, not a value above 1.

**Clutter.** Clutter from the terrain surface painted under a cliff also appears on the terrain slot, and on steep faces it stands crooked. `ClutterThresholdAngle 20` in every `<Asset>_terrain.emat` keeps it off anything steeper than that. If it is still not enough, `_Tools/split_terrain_slot.py` has an optional `FZMIN` slope gate (off by default) that removes the steeper faces from the terrain slot itself.

**Known limits.**
- A material border follows triangles: the terrain/rock edge steps at about 0.3 m on LOD0 and at the triangle size on coarser LODs.
- The terrain slot has no mask and no global NMO, so where the soft edge ends in plain rock BCR there can be a tone step against the masked rock, and its crevices lack the cliff's ambient occlusion. That is why the tops are restricted to open, lit areas.
- What the terrain slot picks up is the terrain texture under the cliff's footprint; if that differs from the ground around the cliff, paint it.

## Terrain surfaces for painting (`Terrains/Common/Surfaces/`)

Two `TerrainMaterial` surfaces built straight from the cliff layers, so the painted ground has the cliff's own grain:

| Surface | BCR | NHO | `ScaleUV` / `MiddleScaleUV` | Paint |
|---|---|---|---|---|
| `CliffFootDebris.emat` | `CliffLayer_RockPorous_T_BCR` | `CliffLayer_RockPorous_NHO` | 2 / 12 | 0–4 m around the cliff foot |
| `CliffDustyTransition.emat` | `CliffLayer_Sand_T_BCR` | `CliffLayer_Sand_NHO` | 2.7 / 16 | about 3–15 m out, bridging to the map ground |

- **NHO** files sit in `_Layers/` (`CliffLayer_RockPorous_NHO.tif`, `CliffLayer_Sand_NHO.tif`, 2048): R, G = normal from the layer's NMO, **B = height** (the layer's `_DETAIL_MASK`, stretched to 0..1), A = ambient occlusion. Import as linear, like the NMO files.
- **`_T_BCR`** files (`CliffLayer_RockPorous_T_BCR.tif`, `CliffLayer_Sand_T_BCR.tif`, 2048, colour sRGB) are the layer BCRs prepared for ground use: the slow row and column brightness drift is removed (the Sand layer drifted about 8x more than the rock layer, which showed as stripes from a distance once the tile repeats every few metres) and they are half the resolution. The cliffs keep using the untouched `_BCR` files.
- **Colour.** `Color` is tinted by eye against the cliff wall (foot about `0.55 0.53 0.44`, dust `0.7 0.55 0.5`); check both in the same light as the wall. The middle pair reuses the same textures at a larger scale with `MiddleColor` equal to `Color`.

**What went wrong on the way (so it is not repeated).**
- **`SatMapBlend`: keep it at 0.** At 0.3 the satellite colour washed the whole surface pale pink, and no `Color` value could fix it (the blue channel stayed high even with `Color` blue at 0.012).
- **NHO height channel.** With the layers' NMO in the NHO slot (B = metalness = 0), two surfaces blended as speckles and dark dashes appeared along the tile borders. With a real height in B the overlap blends cleanly. The B = height, A = occlusion layout is a working assumption that behaved correctly in Workbench; it was not checked against BI documentation (the wiki pages return 403 here).
- **Baked or remixed textures** (a mesh-UV BCR baked from the four layers, and blended "terrain candidate" textures built from the layers) looked blurry or patchy against the cliff and were abandoned and deleted. The cliff layers used directly, with a colour tint, match the cliff far better.
- Middle maps were added last and have not yet been judged from a distance.

## Example `.emat` block (first asset)

```
MatPBRMulti {
 MaskMap "Cliff_CrimsonBadlandsRidge_MASK.edds"
 GlobalNMOMap "Cliff_CrimsonBadlandsRidge_NMO.edds"
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
- Mask: baked (Emit, 16 px margin) from the procedural Blender material in `../*_pbr.blend`: R from slope + rock height + dust, G from high-poly AO in crevices × noise plus the foot, B from broad noise patches on inclined and lower faces (~13% of the surface; no vertical streaks). Paint over it in Texture Paint with pure channel colours if needed.
- Pale sandstone layer (B) is graded to ~1.6× the rock's brightness and warm red-brown (`#b07a5e` average), so the patches read as lighter sandstone, not chalk.
- Canyon Wall and Horseshoe Ridge are hollow, double-skinned Meshy meshes: their LOD0 is rebuilt from the flood-filled voxel solid (12 cm), shrink-wrapped onto the outer surface, then decimated. Source surface outside it by more than 10 cm: none on Canyon Wall; on Horseshoe Ridge 16% of the source area, almost all of it the source's ground plate in the bottom 0.5 m (0.4% higher up). Horseshoe Ridge also has a few long, downward-facing triangles under overhangs 0.5–1.3 m above its base: sink it at least 1.5 m into the terrain.
- Checked for every cliff: FBX re-import (collider closed, OCC_ quads), share of inward-facing faces (≤0.4%, small scattered faces, i.e. no back-face-culling holes), back-face-culled renders from six sides, UV stretch/density, and long thin triangles measured against the 2M-tri source (above 0.3 m only on Horseshoe Ridge, see above).
- The rock material and the terrain slot were checked in Workbench on Crimson Badlands Ridge; the other cliffs use the same set-up but were checked less. The Blender preview is an imitation of the shader.
