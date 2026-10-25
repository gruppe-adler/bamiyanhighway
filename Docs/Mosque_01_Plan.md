# Mosque_01 – Plan & Status

Updated at the end of every milestone (tick checklist, fill "State", adjust later milestones, commit).

| Milestone | Status | Last update |
|---|---|---|
| M0 Baseline & tooling | done | 2026-10-25 |
| M1 Proportions vs. reference | done (user accepted window placement; dome height edited by the user in `mosque_v4.blend`) | 2026-10-25 |
| M2 Surface imperfection | in progress: bevels, dome noise, new fine-grain layer textures; masks too uniform -> needs masking/second layer | 2026-10-25 |
| M3 Carpet & interior | vanilla `Carpet_03_green_mosque` (3x3 hall + 1 porch) + church doors; interior wall look open | 2026-10-25 |
| M4 Windows + destruction | prefabs built and verified via Workbench (35 destructible windows); shoot test by the user pending | 2026-10-25 |
| M5 Building destruction (damaged mesh + ruin) | not started | |
| M6 Portals & probes | lighting package exported + built; interior lighting still wrong (probe recapture needed) | 2026-10-25 |
| M7 Polish extras | open | |
| M8 Validation & wrap-up | open | |

## State after milestones

### M0 (partial, 2026-10-25)
- Source: `D:\gronom\Auftraege6\GruppeAdler\Moddingamiyan_highwaylender\mosque\mosque_bake.blend` (newest, Blender 4.5.14).
  No generator script inside the .blend (no text blocks); also `mosque_v2.blend`, `mosque.blend`, `window_panes.json`, `textures/`.
- Scene: `Mosque_LOD0` (6869 polys, 9701 verts, materials MOS_PLASTER/STONE/PAINT/WOOD/GOLD/CARPET), 21 `Pane_Body_*`, 16 `Pane_Drum_*`, `Boden`, `Sonne`.
- Bounding box: 20.0 x 25.74 x 22.46 m (X -10..10, Y -10..15.74 incl. porch/stairs, Z 0..22.46).
- Height profile (max radius per metre): body wall ~14.4 m radius at Z 5-6 (porch/roof area), drum ~5.5 m radius Z 9-15, dome closes Z 17-18, finial to 22.5.
- Body pane Z centre 2.9 (3.12 m tall, 1.51 wide), drum pane Z centre 9.54 (1.38 m tall, 1.0 wide).
- Open: Workbench/Blender reference screenshots, Portal Tools wiki, church socket naming.


---

# Mosque_01 – Realism & Gameplay Pass (Plan)

## Context
Mosque_01 (WIP, commit `6481de0`) is an octagonal hall + drum + dome built procedurally and exported as
`Prefabs/Structures/Mosque_01/Mosque_01.fbx/.xob` (18.9k tris LOD0, 17.8k collider tris, materials Plaster/Paint/Stone/Gold/Carpet/Wood,
layer textures in `_Layers/`). Windows are two shared pane prefabs (`Panes/Pane_Body` 1.51x3.115 m, `Pane_Drum` 1.0x1.38 m)
placed as plain GenericEntity children in `Mosque_01.et` (37 placements), plus one `ProbeHouse_Base` probe at (0, 2.8, 0).
Goal: get closer to the reference photo (Afghan village mosque: low octagonal body, striped plaster bands, arched white-framed
windows, ribbed dome on a windowed drum, gold finial) and make it a proper Enfusion building (destruction, window damage, interior lighting).

Known gaps found while exploring:
- No source `.blend`/generator script inside the addon (only the FBX). Blender MCP was not connected at planning time.
  -> Step 0 must locate or recreate the generator; otherwise edit the FBX imported into Blender.
- Panes are plain meshes with no hitzone/destruction. Root is `GenericEntity`, not a destructible building.
- Only one probe; Church reference uses `SCR_DestructibleBuildingEntity` + `SlotBoneMappings` for windows/doors (socket empties).

## Living-document rules (user requirement)
- This plan is copied to `Docs/Mosque_01_Plan.md` in the addon at the start of execution (committed with the work).
- At the end of **every milestone** (M0..M8): tick its checklist, fill "State after milestone" (what exists, measured numbers,
  tri counts, known issues, decisions changed), update later milestones if findings change them, and commit with the doc.
- A status table at the top of the doc is the single source of truth for "where are we".

## Milestones

### M0 – Baseline & tooling (no visual change)
- Connect Blender MCP; find/recreate generator; confirm FBX round trip and export settings (LODs, collider, UV, socket naming).
- Snapshot baseline: tri counts, dimensions, screenshots from the reference camera angle (Blender + Workbench) into `Docs/mosque_refs/`.
- Fetch the Portal Tools wiki page (WebFetch) and the Church socket/bone naming for reuse in later milestones.
- State update: baseline numbers, tool status, decision on source of truth for the model.

### M1 – Proportions vs. reference (do first; everything else depends on it)
- Calibrate the photo: use window as scale (assumed ~1.2 m wide x ~2.0 m tall; verify) and derive wall height, band heights,
  drum height, dome radius, finial height, window spacing and count per octagon side.
- Overlay reference as background image in Blender (matched camera) and compare. Expected: body wall lower than now
  (user's impression), windows wider-spaced in 3 per face groups, arched tops.
- Adjust generator parameters; regenerate; re-place panes (`Mosque_01.et` positions are derived from pane parameters – regenerate the list).
- Record the before/after table (wall height, drum height, dome radius, window pitch).
- State update: final dimension table.

### M2 – Surface imperfection (dome, edges, plaster)
- Dome: low-amplitude multi-octave noise displacement on the high-poly dome (<= 1-2 cm), slightly uneven rib bands
  (inset/outset varying), subtle sag/wave between ribs; keep silhouette smooth enough for LODs.
- Edges (best practice): bevel all hard edges with small varying radii (not uniform), slight non-orthogonal vertex jitter on
  walls/roof parapet (mm-cm), uneven band thickness, chipped corners on stone steps/frames.
- Bake high->low detail into the normal map (`Mosque_01_NMO`) for fine plaster chips and trowel marks rather than geometry.
- Texture layer work in `_Layers/`: plaster colour variation, band edge wear, dust streaks under sills, roof stains, grime
  (`MosqueLayer_Grime`) driven by AO/curvature masks. Keep within existing material set.
- Check LOD tris stay near 18.9k/9.5k/4.7k/1.9k; re-export report.
- State update: noise parameters, tri deltas, screenshots.

### M3 – Carpet & interior
- Interior floor carpet matching the photo (repeating prayer-niche pattern in rows, brown/black on red/tan): new tileable BCR/NMO
  in `Data/Mosque_01_Carpet.emat` (material exists; check what it currently does) with its own UV island; slight height offset
  (~1 cm) and worn edge; optional separate mesh so it is not in the collider.
- Optional: wall base trim, interior ceiling/dome underside surface, mihrab niche detail.
- State update: UV/texel density, material changes.

### M4 – Windows: geometry, glass, destruction
- Rework panes to arched frames with white frame + glass (matches photo), separate frame/glass materials (`Mosque_01_Glass.emat`).
- Convert each pane into a real destructible window prefab, modelled on the Vanilla church windows
  (`Win_ChurchSmall_E_A_*`, read via copied override files as before): glass hitzone, intact/broken states or
  glass-shatter effect, collider on glass only.
- Hang panes on sockets instead of hand-typed coords: add `socket_win*` empties in the FBX (naming/orientation as in church)
  and use `SlotBoneMappings` (needs M5 root entity).
- State update: pane prefab list, hitzone settings, test result.

### M5 – Building destruction (damaged + ruin)
- Convert root to `SCR_DestructibleBuildingEntity` (child prefab of the church pattern: `SCR_DestructibleBuildingComponent`, RplComponent,
  Hierarchy, Occluder, MapDescriptor, `m_aInteriorQueryBoundingBoxes` for the hall + drum).
- Damaged state: texture/decal swap or alternate mesh with cracked dome and missing plaster patches; destroyed state:
  `Mosque_01_Ruin.et` (collapsed dome, remaining wall stubs/rubble, collider simplified) spawned via `SCR_TimedPrefab`
  (same effect set as church: dust/brick particles, sounds - reuse church paths, mosque material = brick/plaster).
- Hitzone values scaled for a larger building (church MaxHealth 50000 as starting point).
- Needs: second FBX/xob for ruin, `.et` for ruin. Decide whether damaged state is shader-only (cheaper) -> default: shader/texture swap.
- State update: states implemented, hitzone numbers.

### M6 – Lighting: portals and probes
- Blender 4.5 Enfusion Blender Tools: Portal Tools (per wiki): add portal planes in the FBX at exterior door and at
  each window opening used for visibility (octagon: doors + drum windows), define interior rooms/volumes as the tool requires,
  export with the model. Verify exact property names from the wiki page fetched in M0.
- Probe: keep `ProbeHouse_Base` at hall centre; evaluate second probe (0, ~9, 0) in the dome; also tune `ProbeHouse_Base`
  overrides (priority, `VisibleDistance`, `FarPlane` 50 m) if the dome looks wrong. Verify in Workbench at several times of day.
- Remove stray copies (`Prefabs/Structures/Core/`, `Cultural/`) – not needed, only reference copies of Vanilla.
- State update: portal count, probe placement, screenshots day/night.

### M7 – Pro-polish extras (proposals, pick which to keep)
- Gold finial with crescent and slight tilt; copper/gold wear.
- Roof details: vent pipe (visible in photo), parapet lip, drainage spouts, water stains.
- Entrance: marble stairs with herringbone pattern as in photo, carpet under porch, columned porch.
- Surrounding props prefab: low stone wall, shoe rack, ablution tap, tree placements, ground decal blend matching terrain.
- Static sound (call to prayer ambience is optional), map descriptor icon, `SCR_MapDescriptorComponent` main type.
- Layered texture trim sheet reuse and texel-density audit; LOD/draw-distance tuning (`LODFactors`).
- Interior props: lamp/chandelier (light entities, off by default), prayer mats.

### M8 – Validation & wrap-up
- `wb_validate` / `mod_validate`, collision check (walk inside, bullets pass windows), destruction test in Play mode,
  perf check (draw calls, tris), `wb_cleanup` of MCP handler scripts, final doc update, commit.

## Critical files
- `Prefabs/Structures/Mosque_01.et` – root prefab, probe, pane placements (to be regenerated/converted).
- `Prefabs/Structures/Mosque_01/Mosque_01.fbx|.xob`, `Panes/*`, `Data/*.emat`, `_Layers/*.tif`.
- Reference copies (read-only): `Prefabs/Structures/Cultural/Churches/ChurchSmall_E_01/*`, `Prefabs/Structures/Core/ProbeHouse_Base.et`.
- New: `Docs/Mosque_01_Plan.md`, `Mosque_01_Ruin.et`, new pane prefabs.

## Verification
Per milestone: Blender camera screenshot vs. reference overlay (M1-M3), Workbench screenshot in World Editor (all), Play-mode
tests (destruction, windows, lighting at day/night), tri/LOD numbers from `Mosque_01_export_report.json`, `mod_validate`.

## Decisions (from user)
- Generator script / .blend exists outside the addon: M0 first asks for its path and works on it directly.
- Damaged state = separate damaged mesh (`Mosque_01_Damaged.xob`: cracked/partly broken dome, missing plaster, broken window frames),
  plus ruin prefab for destroyed state. M5 updated accordingly (swap via destruction phase/prefab replacement).

## Still open
- Which M7 extras to keep.

### Interim work (2026-10-25, before M1) – drum windows + bevel, in `mosque_v3.blend`
- Drum wall (z 8.79-12.06) rebuilt: 96-segment tube with 16 real arched openings (0.70 x 1.25 m, sill z 9.55), flat reveals,
  raised arch frames (+sill) instead of the soft blobby frames and wedge-shaped sills. Welded to the old base/cornice rings.
- `Pane_Drum` mesh rescaled to 0.74 x 1.29 m (circular arch kept), panes moved to r=5.16, z=9.53. **Pane xob/prefab must be re-exported.**
- Body edges (876 edges, angle > 50 deg, length > 0.4 m, z < 8.8) beveled: 3 cm, 2 segments. Drum/dome untouched.
- Tris LOD0: ~18.9k -> 23.6k (tris from bevel will need LOD/budget review in M2).
- New drum faces got UVs by projecting from the nearest old surface (colour continuity), but baked MASK/NMO textures must be re-baked.
- Non-manifold edges: 1746 (frame backs are open by design; check the rest in M2).
- Not yet done: FBX/XOB export, Workbench check, drum window rows vs. reference count (photo suggests fewer/smaller windows – decide in M1).

### Rebuild v4 (2026-10-25) – replaces the interim drum/bevel work; script: `Docs/blender/mosque_rebuild.py`
Runs on `mosque_bake.blend`, saves `mosque_v4.blend` (reproducible, all steps in one script).
- Wall lowered: wall top 8.34 -> 5.65 m (everything above shifted down 2.69 m; wall z 2.9..8.34 compressed). Total height 22.46 -> 19.77 m.
- Body windows (sides 1-7): 1.20 x 2.05 m (was 1.51 x 3.12), pitch 1.65 m (was 2.38), edge margin ~1.35 m (was 0.47 m); arched frame, sill ledge, bands at z 1.9-2.5 and cornice at 5.35-5.65.
- Drum (16 windows): 0.70 x 1.25 m openings, cleaner frames, panes scaled/placed; drum z shifted -2.69.
- Bevel 3 cm / 2 segments on 727 body edges; LOD0 ~20.9k tris.
- Panes: `Pane_Body` (1.24 x 2.09) and `Pane_Drum` (0.74 x 1.29) meshes changed -> must be re-exported; `Mosque_01.et` pane coords are outdated and must be regenerated from the Blender pane objects.
- Porch (side 0) was only vertically compressed, not rebuilt: check proportions (door height).
- Open: UVs of new faces are projected from old surface, MASK/NMO must be re-baked; export FBX/XOB; Workbench check; window count per side vs. photo; interior/ carpet height.

### Export + pipeline (2026-10-25)
Scripts in `Docs/blender/`: `mosque_rebuild.py` (v4 build), `mosque_export.py` (FBX LOD0-3 + UTM collider + panes, names/materials as in the old FBX),
`mosque_et_panes.py` (regenerates the 35 pane children in `Mosque_01.et` from Blender), `mosque_mask_ribs.py` (paints dome ribs + wall stripe into `Mosque_01_MASK.tif` R = BandPaint layer).
- Final v4 numbers: wall top 5.65 m, drum wall 1.9 m with 14 windows 0.75 x 1.10 m (one on the porch axis), dome stretched x1.22 (h/w ~0.6 as in photo), dome noise 2.5 cm, 8 ribs (R channel), tris LOD0..3 = 20642 / 10318 / 5159 / 2063.
- Exported: `Mosque_01.fbx`, `Panes/Pane_Body.fbx`, `Panes/Pane_Drum.fbx`; `Mosque_01.et` panes regenerated; MASK R channel edited. NMO (AO) not rebaked.
- Known: stripes on the drum are not painted (new drum UVs overlap dome islands); the lower body band exists, one extra stripe at z 3.45-3.9.
- Waiting for: in-engine check by the user (Workbench re-import), then M3 carpet, M4/M5 destruction, M6 portals.

## Findings & rules (state 2026-10-25, evening)

**Export rules (hard requirements, verified in Workbench):**
1. **Triangulate everything on export.** Enfusion triangulates n-gons itself and breaks concave ones: walls with window holes went transparent, stair sides disappeared. The old FBX was triangles only. `mosque_export.py` adds a Triangulate modifier to every exported object (LODs, collider, panes, carpet).
2. LODs: planar dissolve (3 deg, keep UV/material borders) first, then collapse to 50/25/10 % of LOD0. Plain collapse thinned thin shells.
3. Object/material names exactly like the old FBX: `Mosque_01_LOD0..3`, `UTM_Mosque_01`, `Mosque_01_<Plaster|Stone|Paint|Wood|Gold|Carpet>`, panes `Mosque_01_Glass` / `Mosque_01_PaneFrame`. White `Col` layer only (drop helper layer `Zone`).
4. Never leave overlapping coplanar duplicates: the original roof had two duplicate layers (z-fight, bevel failed) -> roof slab is rebuilt.
5. UV: new faces must not borrow UVs by nearest-surface projection (zero-area UVs -> broken tangents, patches on dome/drum). Final solution: re-unwrap and re-bake MASK + NMO (in progress, `mosque_bake.py`).

**Textures (MatPBRMulti):** `Mosque_01_MASK`: R = BandPaint layer (stripes, ribs, rings), G = worn layer, B = grime layer (scales in emat); `Mosque_01_NMO`: RG = flat normal, B = 0, A = baked AO. 1 UV unit = 87.65 m, layer tilings are relative to that, so keep that density when re-packing.

**Lighting package (BI wiki "Enfusion Blender Tools: Portal Tools", EBT sources):**
- Sockets: empties `socket_win...` / `socket_door...` (windows at their centre, local X = width, Z = up, Y = normal; size can be in the name `win_130x182`).
- Portals `PRT_NN` planes at every opening (EBT: `ebt.generate_portals`; needs a collider object with custom property `usage` = `BuildingFireView`; portal material comes from Workbench via net API (works from Blender, port 5775). Allowed sizes: widths 45/55/70/90/100/130/141/150/170/195/340/400 cm, heights 72/142/182/245/340/350 cm, margin 5 cm; other sizes need a manual portal material.
- Portal volumes `PRTVOL_NN` (room volumes, convex, dummyvolume material), probe volumes `BOXVOL_NN` (box volumes for the `GameEnvironmentProbeEntity`), `BSP_NN` (basic BSP geometry, no self intersection, dummyvolume material). Model QA warns "Missing Probe Volume / BSP / Portal / sockets" if they are absent. Without BOXVOL/PRTVOL/portals the probe does nothing and the interior stays bright (observed).
- Stored in the same FBX; EBT own exporter (`ebt.export_fbx`) can register the xob in Workbench.

**Window destruction (needs data from the user):** vanilla window prefabs live in the .pak; to read them the user copies them into the addon ("override"). Needed: `Win_ChurchSmall_E_A_74x159_B.et`, its glass child prefab and the base prefab.

**User feedback log:** missing left porch column (re-added both columns), solid right porch wall removed (not in reference), wall transparent (triangulation), dome painting off (stale MASK G/B, ribs gaps, stray paint), carpet not symmetric (new aligned tile + own mesh), interior too bright (lighting package pending), interior wall texture inadequate (re-bake), stairs missing sides (triangulation/LOD), roof needs light bevels (roof rebuilt with 2.5 cm bevel).

### Status 2026-10-25 (late): full re-unwrap + bake, carpet, lighting package exported
Scripts (all in `Docs/blender/`, run order): `mosque_rebuild.py` -> `mosque_bake.py` (headless: `blender --factory-startup -b mosque_v4.blend --python mosque_bake.py`, ~90 s, writes MASK/NMO tifs and `mosque_v4_baked.blend`) -> in interactive Blender open `mosque_v4_baked.blend`, run `mosque_carpet.py`, `mosque_lighting.py`, `mosque_export.py`; `mosque_et_panes.py` only when pane positions change.
- **Texture/UV mismatch lesson:** the MASK/NMO tifs and the FBX UVs must always come from the same bake; exporting only one of them garbles the whole model (seen in Workbench). Always run bake -> export together.
- New unique UV layout (smart project + concave pack, 1.5 % texel padding), density 95.5 m/uv instead of 87.65 -> the emat tilings (Plaster, Paint, Stone, Wood, Gold) were multiplied by 1.09 to keep the layer scale. MASK: R stripes/ribs/rings (procedural by world position), G worn, B grime (noise + height), NMO alpha = Cycles AO (24 samples, 3.5 m distance).
- Carpet: own mesh `Mosque_01_CarpetFloor` (hall octagon + porch rect, 3.5 m tile = 4x4 prayer niches, symmetric), own emat (MatPBRBasic, reuses the carpet layer textures, 1024 px new design), xob.meta + prefab entity written by hand.
- Lighting objects in the FBX: 36 sockets (`socket_win1_NN` body, `socket_win2_NN` drum, `socket_door_ext_01`), 36 portals `PRT_NN` (materials `PRT_130x182_ARCH_A_EM_` for body, `PRT_70x142_A_EM_` for drum windows; the entrance portal has no standard material -> assign manually), `PRTVOL_01/02` (hall, drum+dome), `BOXVOL_01..08` (probe volumes), `BSP_01..08`.
- Probe: the existing `ProbeHouse_Base` child stays; check that it uses the BOXVOL volumes.
- Open: destructible windows (needs vanilla glass prefabs, see below), damaged/ruin meshes, interior wall look, door portal material, verify everything in Workbench.

**Vanilla window anatomy (from `Win_ChurchSmall_E_A_74x159_B_Mosque.et` the user copied):** window = `Building` entity with `MeshObject` (frame xob) + `RigidBody`, `SlotBoneMappings` mapping xob bones/sockets to glass prefabs `Glass_ChurchSmall_E_74x159_01..04.et` (separate destructible glass pieces, children of the window). To copy this for the mosque I need `Glass_ChurchSmall_E_74x159_01.et` (+ base) as local copies.

### Status 2026-10-25 (night): import works, lighting package builds, destructible windows prepared (untested)
**Workbench import workflow that works (do not hand-write xob.meta):** export FBX from Blender, then call Workbench's own handler from Blender:
`workbench.call_function(info, "ExportFBXResource", {"resourcePath": <abs fbx>, "exportMorphs": False, "exportSceneHierarchy": True, "exportSkinning": False, "materialOverrides": []})` (info from `EnfusionBlenderTools.ebt.ebt_utils.get_workbench_connection_info()`). It regenerates the xob.meta with VolumeParams (BOXVOL), GeometryParams and resolves `dummyvolume_D3975B51F51E6BD5` to `{D3975B51F51E6BD5}Common/Materials/dummyvolume.emat`. Afterwards fix material assigns in the meta text (script `mosque_windows_prefabs.py` does it for the windows).
**Findings from the bisect (what made "Build failed" with no message):** 8 overlapping `BSP_` boxes. Fixed: two non-overlapping convex prisms `BSP_01` (hall), `BSP_02` (drum+dome). Sockets, PRT, PRTVOL, BOXVOL are fine.
**Portal materials:** Workbench creates empty local emats for `PRT_*` names; they must be class `MatLightPortal` (written to `Data/PRT_*.emat`). Before that fix the portal planes rendered as visible default planes (suspected cause of the black "jalousie" on the middle windows).
**Sharpness:** MASK is 4096 px at ~2.3 cm/texel; stripe edges were soft. `MaskSharpness_2 9` added to `Mosque_01_Plaster.emat` (layer 2 = band paint) to get crisp edges.
**Windows (new, untested in engine):** `Prefabs/Structures/Mosque_01/Windows/`: `Win_Mosque_Body|Drum.et` (class `Building`, frame xob + child glass prefab), `Glass_Mosque_Body|Drum.et` (inherits `DestructibleGlass_Base.et`, `SCR_DestructionMultiPhaseComponent` with phase model `*_dst.xob` = shard mesh). `Mosque_01.et` now places 35 `Win_Mosque_*` instances instead of plain pane meshes. Old `Panes/` files are unused now and can be deleted once the new windows are verified.
**Vanilla carpet:** the user suggested `Prefabs/Props/Furniture/Carpet_03_green_mosque.et` (copy of vanilla `Carpet_03_base`); can be placed in the hall instead of / in addition to the own carpet mesh.

**Open issue list (user feedback, to triage):** texture sharpness, black patches on middle windows, interior wall look, door portal material (no standard size), dome/drum shading check after re-bake, damaged + ruin meshes, probe/portal verification in game, vanilla carpet decision.

### Status 2026-10-25 (late night): quality pass after the first in-engine review
Implemented in scripts (rebuild/bake/lighting/prefab writer), exported and registered; to be verified by the user in Workbench:
- z-fighting above the entrance fixed (old porch fascia removed, porch slab cut at y=9.56); stray right stair side face removed; roof rim bevelled.
- Dome: old floating 3D ribs flattened, radial noise, painted ribs on the same azimuths (22.5 + 45k deg). Layer tilings x4 (grime layer excluded) for finer grain; `MaskSharpness_2 9` for crisp stripes.
- Volumes inset 5-8 cm (no more poking through roof); BSP = 2 prisms; portals use `MatLightPortal` emats registered with their own .emat.meta.
- Own carpet mesh removed (it rendered black); vanilla `Carpet_03_green_mosque` placed 3x3 in the hall + 1 in the porch (real size unknown: set CARPET_SCALE when running `mosque_windows_prefabs.py`); church door leaves (`Door_ChurchSmall_E_01_left_EXT_COV_mosque`) at the entrance, old door leaves deleted from the mesh. Workbench shows a modal dialog "Deleted materials Mosque_01_Wood" once (expected, click OK).
- Hall prefab has 48 children (35 destructible windows, 10 carpets, 2 doors, probe). Glass prefab verified through Workbench: SCR_WindowHitZone + shatter particle + `_dst` phase model.
- Still open: interior lighting (probe needs a recapture in Workbench, check BOXVOL usage), exact carpet size, right door leaf prefab (left one is rotated 180 deg), damaged/ruin states, dome black patches re-check after the new AO bake.

### Lesson (2026-10-25, late): never close "holes" blindly
Fan-filling every small boundary loop closed the entrance between the front pillars (a loop of 5-8 edges that was an intentional opening). Rule: after any automatic hole filling run a ray test through the doors/openings (`Docs/blender/` snippets in the plan history) and compare with the openings list: entrance (x -2..2, z 1-3.7 at y=13), 36 windows. The cleanup is now: remove duplicate verts (1e-4) + dissolve degenerate, repair invalid n-gons by `fix_ngons`, close only loops that sit inside walls.


## CURRENT STATE (2026-10-25, end of session 1) - read this first after a context reset

### Files and pipeline (all scripts in `Docs/blender/`)
Source of truth for geometry: `D:\gronom\Auftraege\2016\GruppeAdler\Modding\bamiyan_highway\blender\mosque\mosque_v4.blend` (NOT regenerated any more; the user edited the dome height there; my patches since then were applied directly to it).
Original source: `mosque_bake.blend` (same folder). `mosque_rebuild.py` regenerates v4 from it (do NOT run it any more, it would overwrite the user's dome edit and my patches).
Run order for every change:
1. (optional) patch `mosque_v4.blend` in the interactive Blender (user or me).
2. Headless bake: PowerShell `Start-Process blender.exe -ArgumentList '--factory-startup','-b','<...>\mosque_v4.blend','--python','\"<addon>\Docs\blender\mosque_bake.py\"'` with `-RedirectStandardOutput/-RedirectStandardError` (quote the script path, ~80 s). Cleans the mesh (`mosque_ngon_fix.py`), flattens ribs, re-unwraps, writes `Mosque_01_MASK.tif` + `Mosque_01_NMO.tif`, saves `mosque_v4_baked.blend`.
3. Interactive Blender: open `mosque_v4_baked.blend`; run `mosque_lighting.py` (sockets, portals, PRTVOL/BOXVOL/BSP), then `mosque_export.py` split at "# panes:" with `LIGHTING=(...)` set, then Workbench net API `ExportFBXResource` for `Mosque_01.fbx` (exportSceneHierarchy True).
4. `python Docs/blender/mosque_fix_meta.py` (portal emats = `MatLightPortal`, collider surface) and `python Docs/blender/mosque_windows_prefabs.py <panes.json>` (hall prefab `Prefabs/Structures/Mosque_01.et`: 35 `Win_Mosque_*` windows, 9+1 vanilla carpets, 2 church door leaves, probe). panes.json = window transforms dumped from Blender (scratchpad).
Windows (`Windows/`): `mosque_windows.py` exports frame/glass/dst FBX; metas via `ExportFBXResource` with materialOverrides (glass `{0A11BCBCE1D63AB2}Assets/Structures/BuildingsParts/Windows/Data/window_glass_uneven_EXT.emat`, frame `{5D11FDD2580C842A}.../Panes/Data/Mosque_01_PaneFrame.emat`).
Textures: `mosque_layers_gen.py` generated new fine-grain `PlasterBase/StoneBase/PaintWhite/BandPaint` BCR+NMO (1 tile = 1 m, tilings 87.65 base / 43.8 worn in the emats).
Enfusion MCP (`wb_*`) is connected to the user's Workbench (use `wb_resources getInfo`, `rebuild`; do not leave test entities in the world).

### Accepted by the user
Window placement/size, roof hole fixed, windows no longer half black, window sills (bevels), entrance free again, textures better than before (but too uniform).

### Open issues, in priority order
1. **Corner slits at the two side-0 junctions** (x = +-3.7, y = 8.93): the new wall tube (sides 1-7) meets the old porch-side wall; the band/cornice ends leave a ~2 cm dark slit (see red circles in the last screenshots: left end of the cornice strip under the roof, and the lower band next to the right porch pillar). Planned fix: vertical corner posts (quoins, ~0.18 x 0.22 m, z 0.93-5.65, centred on the outer corner at r = 9.69, angle 67.5 / 112.5 deg) added to `mosque_v4.blend`, or rebuild the side-0 wall with the same tube profile. Do NOT fan-fill loops again (that blocked the entrance once); always ray-test the entrance (x -2..2, z 1-3.7 at y 13) and windows after geometry patches.
2. **Door threshold z-fighting**: the only +z faces at the threshold are the hall floor (z 0.90, x +-1.15, y 8.43-8.93) and a thin strip (z 0.937, x +-3.42, y 8.94-8.95); doors stand at y(Enfusion)=0.95, carpets 0.945 / 0.96. Likely culprit: floor 0.90 vs porch floor 0.94 vs door base or the old stone sill; next step: raise/lower door base by +-2 cm, remove the 1 cm strip, check the door prefab collider.
3. **Texture too uniform**: add masking (worn on exposed edges/top surfaces, drips under sills/roof edge, damp near the ground, AO-driven grime) and a second detail layer; consider an 8k MASK/NMO if still blocky.
4. **Interior lighting**: probe needs recapture in Workbench; check that BOXVOL volumes are used; interior brightness differs between sun/shade.
5. Damaged and ruin meshes (M5), real size of `Carpet_03` (CARPET_SCALE env var), right door leaf prefab (now left leaf rotated 180 deg), portal material for the entrance (uses `PRT_195x182_A_EM_`).

### Rules learned (also in memory `mosque-pipeline-lessons`)
Triangulate everything; never remove materials from the FBX (modal dialog freezes Workbench); BSP = non-overlapping prisms; keep MASK/NMO and FBX UVs from the same bake; use `ExportFBXResource` instead of hand-written metas; run ray tests after every automatic geometry repair.


### Status 2026-10-25 (session 2, pass 1) - exported + registered, awaiting user check in Workbench
- User removed the raised dome paint faces from `mosque_v4.blend`; ribs are now mask-only (azimuth stripes in `mosque_bake.py`). `FLATTEN_RIBS = False` in the bake (flattening would smooth the user's dome imperfections).
- Corner posts (0.24 x 0.26 m, 2 cm bevel, z 0.934-5.50) added at the two side-0 octagon corners; threshold patch raised 0.90 -> 0.934 (flush with porch slab); door leaves: DOOR_SCALE 1.14, hinges +-1.15 (leaves previously overlapped ~6 cm at x=0 -> suspected z-fight). Backup: `mosque_v4_pre_posts.blend`.
- Bake: AO-driven masks (convex edge wear, crevice grime, top dust, wall drips, macro patchiness) in G/B channels; B clip 0.6.
- Ray test after export: entrance 119 rays / 0 blocked, 35 windows / 0 blocked. Exported, `ExportFBXResource` OK, metas fixed, hall prefab rewritten.
- To verify by user: corner slits, threshold flicker, texture variation, dome ribs painted on plain dome.

### Status 2026-10-25 (session 2, pass 2)
- Painted-on dome ribs looked jagged -> ribs are now real geometry: 8 strips (az 25.3+45k, half width 3.2 deg, bisected so edges are clean), extruded 1.2 cm along the dome normal, top edges inset 8 mm (visual bevel), material MOS_PAINT. `RIB_PAINT=False` in the bake. Conforms to the user's dome surface.
- Texture subtlety: `NOISE_STRENGTH` env var in `mosque_layers_gen.py` (default 0.5; 1.0 = previous strong look). Regenerates the `_Layers` tifs; Workbench reconverts. Wear/grime mask strength is in `mosque_bake.py` section 4b (G2/B2 weights).

### Status 2026-10-25 (session 2, pass 3)
- Dome ribs rebuilt: z 9.0-14.45, r>0.55 (reach rim and apex), material PLASTER + vertex attribute `Rib` (top verts = 1) -> the bake paints them with the brown band layer (mask R). Note: bmesh `extrude_face_region` keeps the original faces as a flipped bottom cap; do not delete them blindly.
- Layer noise `NOISE_STRENGTH=0.3`.
- Left entry pilaster front face (x -3.2, y 9.35) set to MOS_PAINT (white) like the right one.
- Closed drum/dome cap removed: two up-facing faces at z 8.772 (24.3 + 8.1 m2) sat on a ring of down-facing faces (8.768, r 5.0-5.9, 4 mm apart = z-fight) and hid the dome interior. Now rays from the hall reach the dome interior at z 11.5-14.2.
- Open: hall carpets render black in the engine (vanilla Carpet_03 copy: check material/size/scale), dome interior lighting (probe/BOXVOL), ring boundary at z 8.77 (r 5.0/5.9) left open.

### Status 2026-10-25 (session 2, pass 4)
- Dome ribs: painted-by-mask version was pixelated -> ribs are now their own material `MOS_RIB` -> `Mosque_01_Rib.emat` (MatPBRMulti, BandPaint layer only, no mask/AO), raised 2 cm with 7 mm inset edges. `mosque_fix_meta.py` writes the emat after every `ExportFBXResource`.
- Dome rim ledge top restored (annulus r 4.96-5.91 at z 8.79).
- Gold: `Faucet_01_golden.emat` (set in `mosque_fix_meta.py`).
- Doors: left leaf at x -1.15, RIGHT leaf prefab (`..._right_EXT_COV_mosque`) at x +1.15, both yaw 0 (church does the same with sockets door_ext_01/02), so both open the same way.
- Interior black carpets/dome = lighting (probe) problem per user, not geometry. Next: probe recapture / BOXVOL check.
- Hall ceiling: a leftover full octagon face (235 m2 at z 5.65) covered the dome opening and overlapped the real ceiling ring (8 trapezoids, hole r 4.96) -> deleted (z-fight + closed dome). Rays from the hall now reach the dome. Door: right leaf prefab yaw 180 at x +1.15.
- User confirmed: doors (left prefab yaw 0 at x -1.15, right prefab yaw 180 at x +1.15) and carpets are fine now.
