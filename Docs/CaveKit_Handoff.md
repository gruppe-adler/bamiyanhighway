# Cave kit (dripstone rooms) – handoff

State at 23 Nov 2026. Everything here is a prototype: nothing from it is in Workbench yet, except the cave textures and materials.

## Files

| Path | What it is |
|---|---|
| `Docs/blender/caves/cave_dripstone_room.py` | Base generator (first agent prototype): room shell, openings with the kit's exact INNER profile, pools, lathe formations, preview renders. Exec's the kit's helpers from `Docs/blender/tunnelkit_build.py`. |
| `Docs/blender/caves/cave_dripstone_v4.py` | Current generator. Exec's the base file for its helpers and overrides most of it (details below). |
| `Docs/blender/caves/pack_cave_textures.py` | Packs Poly Haven PBR sets into Enfusion BCR (RGB colour, A roughness) and NMO (RG DirectX normal, B metalness 0, A AO) TIFFs. Usage: `python -I pack_cave_textures.py <src dir> <out dir> '{"polyhaven_id": "Cave_Name"}'` |
| `Assets/Tunnels/Cave/Textures/*` | Eight CC0 2k sets (see `LICENSE.txt`): Cave_Wall, Cave_WallDark, Cave_Limestone, Cave_Flowstone, Cave_Dripstone, Cave_Floor, Cave_Riverbed, Cave_Mud. The first five plus Floor and Riverbed are imported. **Cave_Limestone, Cave_Dripstone and Cave_Mud still need importing in Workbench.** The TIFFs are large and could be deleted after import. |
| `Assets/Tunnels/Cave/Data/Cave_*.emat` | Dark MatPBRBasic per set (IBL/ambient 0). Made by `Docs/blender/cavekit_materials.py`. To be replaced by one MatPBRMulti. |
| `Scripts/Game/EoHTunnelGen/SP_TunnelExposureComponent.c` | On every TT piece: holds the camera's exposure underground (gain 0.08, entrances by depth), and `m_bKeepRendered` sets `EntityFlags.FEATURE` (no culling; the user confirmed it works). |

## Running

```
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --factory-startup -b --python Docs/blender/caves/cave_dripstone_v4.py
```
Environment:
- `CAVE_VARIANT`: A (cathedral), B (low hall), C (terraces), D (curtains).
- `CAVE_OUT`: output folder. **Always set it.** The default is the script's own folder, so without it the output lands in the addon.
- `CAVE_WELD`: 1 or 0. With 1, roots are welded into the rock (see below).
- `CAVE_VIEWS`: `close` renders only the close-ups; `all` renders the whole set.
- `CAVE_BLEND`: 1 saves a .blend.
- Also: `CAVE_RES`, `CAVE_LIGHT` (preview light scale), `CAVE_COLL_TARGET` (collider triangles, default 20000), and the edge lengths `CAVE_FLOOR_EDGE`, `CAVE_CEIL_EDGE`, `CAVE_WALL_EDGE`, `CAVE_GOUR_EDGE`.
- Always `--factory-startup`: the user's Blender profile has a broken add-on that hangs Blender.

## What v4 does

**Shell**
- Voxel 0.12 m, refined to 7 cm on the floor, 8.5 cm on the ceiling, 4.5 cm in the gour fields.
- Ceiling: bedding ledges, knobs at three sizes, stepped joint cracks.
- Walls: billow flowstone.
- Floor: mounds, crescent gour terraces with water, irregular pools, micro-gour ripples, cobbles, mud cracks.

**Formations**
- Kinds: carrot stalactites, rows of soda straws, domed and ringed stalagmites, candles, fluted columns, curtains, half-buried boulders.
- Each formation is planned before the shell is shaped, so the rock swells into a drape or mound round its root (`SKIRT_F` and `SKIRT_C`).
- Each has a tangent fillet at its root (`speleothem3`) that hugs the real rock.

**Drip rule:** every stalactite or straw leaves a deposit below. Depending on circumstances that's a stalagmite, a candle, or a drip mound shaped into the floor:
- the deposit lands off-centre and runs downslope
- the size ratio is log-normal
- a long fall makes a flat "fried-egg" stalagmite
- about 12% leave nothing, and drips into a pool leave nothing

Free-standing stalagmites get a stalactite or straw above them.

**Texture rule (the user's):** a formation starts with the rock's own look and fades into its own look past its fillet, over about 35 cm. Vertex attributes:
- `Calcite`: rock to flowstone
- `Tip`: rock look to formation look
- `Tip2`: whitening toward the tip

**Weld (`CAVE_WELD=1`)**
- Cuts the rock under each root, drops the buried ring, zips the root ring to the hole edge, then does a wide volume-preserving smooth.
- Topology is correct for 21 of 72 roots in room A.
- 51 are skipped, mostly overlapping neighbours in the crack rows.
- Dark slivers remain round the junctions. Most likely they're zipper folds made worse by the smoothing; not proven.
- **Decision:** replace the weld with the remesh plan below.

**Collider:** the visual mesh minus untouchable formations, decimated to 20k triangles. Not checked at the joints.

**Budgets:** LOD0 is 140–280k triangles per room. That needs a level-of-detail pass before going in-game.

**Known nit:** 1–3 non-manifold edges where the voxel shell touches itself.

## Lighting, decided 23 Nov 2026: the vanilla interior approach (replaces the hold/grade/flashlight-boost scripting)

The vanilla coal mine shaft uses only the engine: materials take ambient light like characters do, and one house probe
per interior (`ProbeHouse_Base`, brightness down, `VisiblePercentBlack 90`, `VisiblePercentWhite 55`). The user tested
`LVDiffuseBrightness`/`LVReflectionBrightness` -16 and it works well. Now applied to everything:
- cave and tunnel materials: no `DiffuseIBL/SpecularIBL/Ambient 0` lines (only `DisableFog` stays on the cave material)
- cave rooms: a house probe child at -16 sized to the room (`cave_finish.py`); tunnel pieces: generator places its own
  `TT_TunnelProbe*.et` (-16, EoH's four sizes), so EoH is no longer needed
- `SP_TunnelExposureComponent`: `m_bExposureControl` off by default, so only the no-cull flag runs; the hold, grade,
  per-soldier probe, flashlight boost and diag menu stay in the file, switched off, for later
- the room must be fully below the terrain with closed openings, or daylight and the terrain surface brighten it

## Done (23 Nov 2026): v5, the real merge (`Docs/blender/caves/cave_dripstone_v5.py`)

Built on room A only so far.

**What it does**
- **Remeshed:** the room shell, the formations and the boulders become one surface, voxel-remeshed at 2.5 cm, decimated to 320k triangles, then smoothed with volume kept round every root.
- **Kept exact, outside the remesh:**
  - the joint stubs, sleeves and frames, so the openings stay at the exact profile (11/11 verified)
  - the soda straws and the smallest stalactites, which still hug the rock
- **Attributes:** material, `collide`, `Calcite`, `Tip` and `Tip2` come back from the pre-remesh mesh. UVs are world-space box projection.
- **Collider:** 20k triangles.

**Result**
- No open edges; the old shell pinches are gone too.
- 332k triangles in LOD0.
- Build time 86 s.
- Previews: `Docs/blender/caves/previews/v5_compare_stalactite.png` (unwelded against v5) and `v5_stalagmite.png`. Every root flows seamlessly.

**Still to do**
- Check one bright fleck at a junction in the stalactite close-up.
- Run rooms B–D.
- Build the MaskMap: a second UV set plus a mask texture from `Calcite`, `Tip` and `Tip2`, then the MatPBRMulti emat.
- Export to Workbench as a prefab (a 4-material FBX, then `tunnelkit_finish` style).
- LOD and budget pass.

## The remesh plan v5 implements (kept for reference)

1. **Build:** as v4 with `CAVE_WELD=0` (fillets hug the rock).
2. **Split components:**
   - The room shell, all formation components and the boulders go into one object.
   - Joint stubs, sleeves and timber frames (the components near the sockets) stay out untouched, so the openings stay exact.
   - Cut the room's opening holes about 5 cm larger (the `prism(... offset(INNER, 0.001))` in `build_room`), so remesh shrinkage stays hidden inside the stubs.
3. **Remesh:** voxel remesh the object at about 3–4 cm, then decimate to the triangle budget.
4. **Smooth:** volume-preserving Laplacian smoothing near the formation roots (the tutorial's "expand, smooth, fatten"), so the unions become concave flows.
5. **Transfer attributes:** for each new vertex, find the nearest point on the pre-remesh mesh (BVH) and take that face's material, `collide`, `Calcite`, `Tip` and `Tip2`, interpolated barycentrically.
6. **Recompute UVs:** world-space box UVs (`box_uv`, `UV_EARTH`), and `Col` by material.
7. **Reattach:** join the kept stub, sleeve and frame components back on. Rebuild the collider. Verify the profile, which must still give 11/11 per opening.

## Material plan: MatPBRMulti (user decision: nothing baked except the mask)

Verified in the vanilla paks (777 MatPBRMulti materials), and as of this handoff no vanilla one blends layers by vertex colour:
- **Layers:** `BCR_1..4`, `NMO_1..4`, `Color_n`, `UVTransform_n`, `Roughness_n`, `Metalness_n`, `Enabled_n`.
- **Per-layer detail masks:** `Mask_n`, `MaskSharpness_n`, `MaskOffset_n`, `MaskUVScale_n`. Vanilla uses `Assets/_SharedData/DetailMask/*`.
- **Global mask:** `MaskMap` on `UVSrcGlobalMaps "UV set 2"`.
- **Dirt:** `Dirt*` (BCRMap, MaskMap, Opacity, LayerSharpness, Color, Roughness, UVTransform).
- **Mud:** `Mud*`.

Plan:
- Layer 1: Cave_Limestone or Cave_Wall.
- Layer 2 (mask R = Calcite): Cave_Flowstone.
- Layer 3 (mask G = Tip): Cave_Dripstone, tinted warm.
- Layer 4 (mask B = Tip2 or damp): Cave_WallDark.
- Dirt: Cave_Mud.
- Every layer tiles on UV set 1, world-space box UVs, so it runs continuously across the joints.
- The only generated texture is `MaskMap`. It needs a second, unique UV set: unwrap (smart project or lightmap pack), then write the `Calcite`/`Tip`/`Tip2` attributes into a 2k–4k texture.

## Other open items

- **Curtains:** still look crumpled (layered sine folds on a sheet). Better: shape them into the wall itself as displacement.
- **Water:** removed from the room prefabs and from the export on 23 Nov 2026; the user adds their own. The pools stay as dry basins. `fix_water`/`water_material` are still in `cave_finish.py` but switched off. Untested options:
  - vanilla `MatWaterPool`/`MatRiver` on a plain mesh
  - `BaseWorld.RegisterWaterBody` for swimming
  - the sea cavern and the river pieces, both still recipes only
- **Glow:** the flowstone "shine-through" was an emissive thickness map. Dropped for now (nothing baked). It could come back as a MatPBRMulti layer or not at all.
- **Spline-driven tunnel generator:** implemented 23 Nov 2026 and compiles; not yet run on a real spline.
  - Files: `Scripts/Game/EoHTunnelGen/SP_TunnelSplinePointData.c` (per-point override; subclasses `ShapePointDataScriptBase` with plain attributes, like vanilla) and `Scripts/WorkbenchGame/EoHTunnelGen/SP_TunnelSpline.c`. Steering and stopping at the spline's end are in `SP_TunnelGrower.c`; the plugin has a "Spline tolerance" setting.
  - Select the entry and the spline(s), then Generate.
  - Limits: 90° pieces make diagonal splines into staircases; records don't store the splines.
  - Scripts reload via the World Editor menu `Game > Reload Game Scripts` (`wb_reload` doesn't work here).
- **Concept doc on blueprints** (markers, routing, caverns): the user pasted it. A spline replaces the markers.
- **Reference photos:** about 23 from Wikimedia Commons, used for the review. They were in the scratchpad (`cave_refs`), so they may be gone.

---
## Update 2026-11-24 (session: first wave)
**New variants in `cave_dripstone_room.py` (`VARIANTS`)** - `asset=` gives the model its own name (otherwise `TT_Room_Drip_<variant>`):
- `F` `TT_Cave_Room_CrawlSlab`: prone chamber, lens cross-section (`sink` sinks the blob so the floor cuts it below the equator -> sloped walls), `ceil_tilt`, `neck` (standing-height wedge at each opening, roof 0.3 m/m down to 1.05 m; the voxel remesh unions it; for necked rooms void + holes are ONE boolean cutter with `use_self`, outer shell built from the remeshed void). Measured: headroom map `_headroom_map.py` (scratchpad) + crawl flood fill (>=0.95 m).
- `G` `TT_Cave_Pass_Meander` (18 m winding passage, 2 openings), `H` `TT_Cave_Room_Grotto` (dead-end chamber, 1 opening).
- Not yet: Saddle, Rubble, Island junction, Squeeze, Breakthrough (see `CaveKit_Concept_30.md`).
**v4 changes driven by the critic agent:** wall zones (flowstone sheet / normal / blocky), 8 m bulge band, `floor_big`, clustered formation sites (`cluster_p`, `cluster_scale`), offset stalagmites (`apart`), skewed stalactite lengths, blunt/domed stalagmite tops, waisted columns, `scallop`.
**Generator themes (uncompiled, untested):** `SP_TunnelTheme` (DUG/CAVE/MIX) via `SP_TunnelCatalog.ThemeOf(name)`: `TT_Cave_*`/`TT_Room_Drip*` = cave, `Brk_` = mix, rest dug. `ThemeWeight` multiplies corridor weights and thins room picks (setting `Theme switch`, default 0.15). `TT_Cave_Pass_*` classify as BEND. Rooms with one way in (grotto) only at dead ends.
**Trap:** `split_for_remesh` must find joint stubs by box distance to the socket (< 0.3 m), not by centre.
