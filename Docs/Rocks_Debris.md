# Small debris props for Enfusion Workbench (Meshy meshes, MatPBRMulti, cliff layers)

Eight ~15 cm sandstone debris pieces (loose rock clutter, not cliff-base boulders) built from the
Meshy `_generate` meshes in `~/Downloads/debris` (originals untouched), textured the same way as the cliffs and
the 1 m `Rock_*` debris: **one UV set**, a per-rock **RGB mask**, a per-rock **global NMO**, and tiling layers.
They reuse the 1 m rocks' base layer (`RockLayer_Rock05`) rather than importing their own copy.
Materials 2-4 are the **cliffs' own layers** at the cliffs' metre repeats. Material 1 is a real rock scan
(`RockLayer_Rock05`) colour-matched to the cliffs' base layer: the cliffs' `CliffLayer_RockPorous` is a
dried-mud scan that reads as clay this close up, this one keeps its colour but has rock grain and pits.

## Folder layout

```
<Asset>/
  <Asset>.fbx             LOD0-LOD4 (one UV set, material <Asset>), UTM_<Asset> collider (usage RockFireView)
  <Asset>_MASK.tif        RGB, linear: R sand (hollows, sheltered ledges), G grit in crevices, B pale sandstone accents
  <Asset>_NMO.tif         linear: normal from the Meshy mesh (DirectX RG), metalness 0 (B), AO 20 cm (A)
  <Asset>_enfusion.blend  preview scene: Blender imitation of the MatPBRMulti set-up below
  <Asset>_report.json     sizes, LODs, collider, UV and tiling numbers
previews/                 hero shots, all sides, near/mid/far distance, lineup with a scale bar
scripts/                  the pipeline (see scripts section)
```

No `_Layers/` folder here: Material 1 is `~/Downloads/rocks/enfusion/_Layers/RockLayer_Rock05_*`, already imported for the 1 m rocks. Materials 2-4 are **not** copied anywhere: use the `CliffLayer_Sand/Scree/SandstonePale` textures
already imported for the cliffs (`~/Downloads/cliffs/enfusion/_Layers`).

## Assets

All pieces are scaled to **0.15 m** along the longest horizontal side, pivot at the base centre (z = 0 = lowest point). Scatter in clusters at a cliff's foot or along paths; being this small, a handful per scene reads as clutter without costing much.

| Asset | Meshy source | Size (m) | LOD0-4 tris | Collider tris | Meshy detail not in LOD0 (mean / p95, carried by the NMO) | UV islands | Sand / grit / pale (share of surface) | Tiling 1 / 2 / 3 / 4 |
|---|---|---|---|---|---|---|---|---|
| Rock_Debris_DesertMonolith_A | `Meshy_AI_Desert_Monolith_20261026_generate_15dd0fd9/Meshy_AI_model.blend` | 0.15 × 0.12 × 0.08 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 1.22 / 1.7 mm | 5 | 1% / 1% / 0% | 0.145 / 0.107 / 0.088 / 0.071 |
| Rock_Debris_DesertMonolith_B | `Meshy_AI_Desert_Monolith_20261026_generate_1f3ca6c4/Meshy_AI_model.blend` | 0.13 × 0.15 × 0.09 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.46 / 1.3 mm | 4 | 2% / 2% / 7% | 0.147 / 0.109 / 0.089 / 0.072 |
| Rock_Debris_DesertMonolith_C | `Meshy_AI_Desert_Monolith_20261026_generate_269be7d0/Meshy_AI_model.blend` | 0.15 × 0.12 × 0.06 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.69 / 2.68 mm | 7 | 4% / 1% / 3% | 0.153 / 0.113 / 0.093 / 0.075 |
| Rock_Debris_DesertMonolith_D | `Meshy_AI_Desert_Monolith_20261026_generate_d00cebaf/Meshy_AI_model.blend` | 0.14 × 0.15 × 0.10 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.53 / 1.41 mm | 3 | 2% / 2% / 4% | 0.175 / 0.129 / 0.106 / 0.085 |
| Rock_Debris_DesertSlab | `Meshy_AI_Desert_Slab_20261026_generate_73fa19f6/Meshy_AI_model.blend` | 0.15 × 0.14 × 0.03 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.35 / 1.06 mm | 5 | 5% / 1% / 10% | 0.141 / 0.104 / 0.085 / 0.069 |
| Rock_Debris_DesertStone | `Meshy_AI_Desert_Stone_20261026_generate_6a72008f/Meshy_AI_model.blend` | 0.15 × 0.13 × 0.06 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.39 / 1.05 mm | 4 | 1% / 0% / 7% | 0.143 / 0.106 / 0.087 / 0.07 |
| Rock_Debris_WeatheredSandstoneBoulder | `Meshy_AI_Weathered_Sandstone_Boulder_20261026_generate_4873de80/Meshy_AI_model.blend` | 0.15 × 0.13 × 0.10 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 5.53 / 21.49 mm | 6 | 29% / 0% / 11% | 0.149 / 0.11 / 0.09 / 0.072 |
| Rock_Debris_WeatheredStoneChunk | `Meshy_AI_Weathered_Stone_Chunk_20261026_generate_418d9169/Meshy_AI_model.blend` | 0.15 × 0.14 × 0.09 | 1000 / 500 / 250 / 124 / 62 | 150, closed: True | 0.43 / 1.32 mm | 5 | 3% / 4% / 4% | 0.165 / 0.122 / 0.1 / 0.081 |

Tiling = metres per UV unit ÷ the layer's repeat (2.0 / 2.7 / 3.3 / 4.1 m, as on the cliffs).

## Base layer `RockLayer_Rock05`

Source: polyhaven.com/a/rock_05 (CC0), 4K. The scan's linear albedo is scaled per channel so
its mean equals `CliffLayer_RockPorous`: [0.3028, 0.1177, 0.0631] (scan mean before: [0.2322, 0.1547, 0.0958]).
Roughness and NMO packing as the cliff layers. Chosen (on the 1 m rocks) from four options rendered on the same
rock: cliff base, rock_05 at 2.0 m, rock_05 at 1.2 m, rock_08.

## Import steps

1. Import `RockLayer_Rock05_BCR.tif` as colour (sRGB) and `_NMO.tif` as linear (once, shared across both batches),
   and per asset `<Asset>_MASK.tif` and `<Asset>_NMO.tif` as linear.
2. Import the FBX. Import Settings → Physics → Geometry Params: set the collider's SurfaceProperties to a rock
   `.gamemat` (layer preset `RockFireView` comes from the FBX custom property `usage`).
3. Set the generated `<Asset>.emat` to MatPBRMulti and fill it as in the example (all LODs share it).
4. GlobalNMOMap carries the Meshy relief and AO: start with **Global AO Power 1.0** and **Cavity From AO
   0.3-0.5**; keep Det Normal N on the layers around 1.0.

Example (`Rock_Debris_DesertMonolith_A`; tiling per asset in the table / report):

```
MatPBRMulti {
 MaskMap "Rock_Debris_DesertMonolith_A_MASK.edds"
 GlobalNMOMap "Rock_Debris_DesertMonolith_A_NMO.edds"
 BCR_1 "RockLayer_Rock05_BCR.edds"  NMO_1 "RockLayer_Rock05_NMO.edds"
 UVTransform_1 MatUVTransform { TilingU 0.145 TilingV 0.145 }   // 2.0 m repeat
 Enabled_2 1
 BCR_2 "CliffLayer_Sand_BCR.edds"  NMO_2 "CliffLayer_Sand_NMO.edds"
 UVTransform_2 MatUVTransform { TilingU 0.107 TilingV 0.107 }   // 2.7 m repeat
 Enabled_3 1
 BCR_3 "CliffLayer_Scree_BCR.edds"  NMO_3 "CliffLayer_Scree_NMO.edds"
 UVTransform_3 MatUVTransform { TilingU 0.088 TilingV 0.088 }   // 3.3 m repeat
 Enabled_4 1
 BCR_4 "CliffLayer_SandstonePale_BCR.edds"  NMO_4 "CliffLayer_SandstonePale_NMO.edds"
 UVTransform_4 MatUVTransform { TilingU 0.071 TilingV 0.071 Rotation 90 }   // 4.1 m repeat
}
```

## How it was made / known limits

- **LOD0:** the Meshy mesh is decimated to the LOD0 target (voxel-remeshed first at a few mm, which keeps
  decimation from folding thin triangles in pebble-filled crevices into black wedges / culling holes).
  A few Meshy "_generate" sources are hollow, double-skinned meshes (an inner surface facing the cavity as well
  as the outer one, e.g. `Rock_DesertMonolith_F`: 43% of its raw faces face the cavity). For those, LOD0 is built
  from the flood-filled voxel solid instead (ignores face-normal consistency) and snapped onto the outer surface;
  diagnostics (deviation, flipped-face share) compare against only the outer-labelled source faces, not the raw
  double-skinned mesh. Detection is read-only and automatic (`rock_a_meshy.py`'s `classify_shell`), no manual flag.
- **UVs:** charts on the piece's big folds, conformal, average island scale, pack.
- **Mask** (R/G/B as on the cliffs): sand where up-facing hollows and sheltered ledges collect it plus a light
  dust film, grit from crevice-scale AO, pale sandstone in noise patches plus worn convex edges. Meshy
  `_generate` meshes carry no colour, so the mask comes from shape alone.
- **AO** is the piece's own (no ground plane): sinking it a few cm and in-engine SSAO cover the contact.
- **No occluders** (too small to be worth it); collider is a closed low-tri trimesh.
- Not checked inside Workbench (Windows-only); the Blender preview imitates the shader.

## Scripts

`scripts/prep_batch.sh <root_dir> <assets_file> <size_m> <lod0_tris> [AssetName...]` (import `rock_a_meshy.py`,
LOD0 + UVs `rock_b_lod0.py`, mask/NMO bake `rock_m_bake.py` with `rockmat.py`), then
`scripts/final_batch.sh <export_dir> <assets_file> <size_m> [AssetName...]` (export `rock_c_export.py`, renders
`rock_clay.py`, `check_normals.py`), `compose_previews.sh <export_dir> <assets_file> [grid_cols]`,
`rock_lineup.py -- <out.jpg> <enfusion_dir> <assets_file> [bar_m] [az] [el]`, `rock_layers.py` (base layers),
`rock_readme.py <export_dir> <assets_file> <rocks|debris>` (this file). Asset list: `debris_assets.txt`.
WORK_DIR defaults to `~/rocks_work` (shared scratch space for both batches; asset names don't collide).

## Imported into the addon (2026-10-26)
18 rocks under `Prefabs/Rocks/Debris/` (10 Meshy 1 m `Rock_*`, 8 small 0.15 m `Rock_Debris_*`), each with `<Asset>.et` (red) and `<Asset>_Sandstone.et`.
The sandstone variant inherits the red prefab and only swaps the material: `Data/<Asset>_Sandstone.emat` uses the Cream layers and `Color 0.15 0.15 0.15 1`, as on the cliffs.
New layers in `Debris/_Layers/`: `RockLayer_Rock05_{BCR,NMO}` plus `RockLayer_Rock05Cream_BCR` (Rock05 with the mean colour and contrast of `CliffLayer_RockPorousCream`).
`.meta` files are hand-written with new GUIDs; Workbench builds `.xob`/`.edds` on the next open. Not checked in the engine.
Skipped: the second README copy (`README (1).md`, the 0.15 m batch's README, merged here), `_enfusion.blend` previews, `RockLayer_Rock08`, `DETAIL_MASK` tifs, `scripts/`.
Deleted as not nice: all six sculpted Rock_CliffDebris_*.
