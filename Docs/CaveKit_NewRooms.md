# Cave kit: two new rooms (TT_Cave_Hall_TwoLevel, TT_Cave_Room_SwimThrough)

State 24 Nov 2026. Built with a fork of the v5 generator that runs from signed-distance shapes (new files only; nothing existing was edited).
Both pieces are exported (FBX + mask) and registered in Workbench; the user still has to let Workbench build them (steps at the end).

## Files

| Path | What |
|---|---|
| `Docs/blender/caves/newrooms/NR_shapes.py` | numpy shapes: `HallShape`, `SwimShape` (parameters, sockets, routes), marching-tetrahedra iso-surface |
| `Docs/blender/caves/newrooms/NR_overrides.py` | switches the v5 pipeline to these shapes (`NR_ROOM=hall|swim`); parameter list at the top |
| `Docs/blender/caves/newrooms/NR_v5.py`, `NR_v4.py`, `NR_room.py` | forks (snapshot 24 Nov 2026 15:10, with small hooks marked `NR hooks`) of cave_dripstone_v5/v4/room |
| `Docs/blender/caves/newrooms/NR_export.py`, `NR_finish.py` | forks of cave_export / cave_finish (water level into the info json and the prefab; the finish script also works before the first import) |
| `Docs/blender/caves/newrooms/NR_voxelize.py`, `NR_check.py`, `NR_preview.py` | verification (air intervals per column, walk graph, swim connectivity) and preview renders |
| `Assets/Tunnels/Cave/TT_Cave_Hall_TwoLevel.fbx`, `_MASK.tif`, `_info.json`, `Data/*.emat` | hall asset; `Prefabs/Tunnels/TT/TT_Cave_Hall_TwoLevel.et` |
| `Assets/Tunnels/Cave/TT_Cave_Room_SwimThrough.fbx`, `_MASK.tif`, `_info.json`, `Data/*.emat` | swim room; `Prefabs/Tunnels/TT/TT_Cave_Room_SwimThrough.et` |
| `Docs/blender/caves/previews/NR_*.png`, `NR_*_check_report.json`, `NR_*_build_stats.json` | previews, verification numbers, build stats |

Rebuild (about 6 min hall, 2 min swim; always `--factory-startup`, set `CAVE_OUT`, run one Blender at a time):
```
set NR_ROOM=hall   (or swim)   set CAVE_OUT=<scratch>   set CAVE_RENDER=0
blender --factory-startup -b --python Docs/blender/caves/newrooms/NR_v5.py
blender --factory-startup -b <CAVE_OUT>/NR_<Name>_v5.blend --python Docs/blender/caves/newrooms/NR_export.py     (writes into Assets/Tunnels/Cave)
```
Checks: `NR_voxelize.py` on the blend twice (`NR_OBJ=UTM_` and `NR_OBJ=<Name>_LOD0`, `NR_NPZ=out.npz`), then `python NR_check.py hall|swim coll.npz lod.npz` (needs scipy).

How it differs from the other rooms: the air volume and the rind come from a signed-distance field (marching tetrahedra, rind = exact offset of the air surface, 0.9 m walls, 1.5 m floors), not from a blob. The v4/v5 formation, roughening, voxel-merge and attribute steps are unchanged, except: `plug_floor_slits` is off (the offset shell has no folded skin, and the repair filled the swim bore with boxes), formation placement uses a floor function instead of a plane (two levels), and the collider is the inner skin only (outer skin dropped), decimated to 40k with the bore protected.

## TT_Cave_Hall_TwoLevel

Interior: 14.4 m wide, 57 m long, roof 10.8 m above the lower floor (pockets to 13.7 m); three side niches on the walls (bbox with rind, niches and stubs: 22.2 x 60.4 x 16.2 m; lower floor z = 0, gallery floor z = +5.4).
Two levels: the main floor, and a gallery (x -7..-1.3, y 3..28.6, about 6 m wide, 25 m long) 5.4 m above it, open to the hall (cliff edge on the east side, rimstone-like lip). Roof domed over both, 9 fat columns, about 270 stalactites, 170 stalagmites and 390 straws; two gour fields on the lower floor and two on the gallery (dry).

Sockets (empties "1", "2"; +Z out of the opening; INNER profile 1.4 x 2.1 m, size class S like every other room; Blender X right / Y forward / Z up; Enfusion x = X, y = Z + 1.0, z = Y):

| # | role | Blender pos (floor) | memory point (Enfusion) | dir | floor height |
|---|---|---|---|---|---|
| 1 | upper entrance, north end, on the gallery | (-4.40, 30.12, +5.40) | (-4.40, 6.40, 30.12) | +Z | +5.40 m |
| 2 | lower entrance, south end, main floor | (1.20, -29.79, 0.00) | (1.20, 1.00, -29.79) | -Z | 0.00 m |

Descents (collider measured with `NR_check.py`, floor slope over a 1.2 m baseline; the walk graph needs 1.8 m headroom, slope <= 35 deg, steps <= 0.5 m):
- Main cascade down the west wall: from the gallery's south end (y = +3) to the floor at y = -16, flowstone ridge 4 m wide with two landings (design slope <= 22 deg). Measured: max 32 deg on single lumps, 95th percentile 23 deg, horizontal length 18 m, drop 5.4 m, walkable width across it min 4.1 m / median 5.0 m, min headroom 2.2 m, max step 0.12 m. Connected from socket 1 to socket 2 with the rubble slope blocked.
- Rubble slope (steeper, shorter) from the gallery's east edge at y = +22 to the floor at (5.4, 8): design 23 deg average. Measured: max 29 deg on the descent, 95th percentile 27 deg, width min 2.6 m / median 4.1 m. Also connected from socket 1 to socket 2 with the cascade blocked.
- Walkable area (>= 1.8 m headroom, <= 35 deg): gallery 91 m2, lower floor 231 m2 (formations excluded), 525 m2 reachable from socket 1.
- Floor continuity: of 14254 interior columns of the render mesh, none lacks air except 59 under fat columns and boulders; the 8 columns that a "floor 0.6 m below design" test flags are closed pockets between the rind and nothing (not connected to the room).

Budgets: LOD0 187k tris (LOD1 75k, LOD2 26k), collider 40k tris. Openings 11/11 profile points, 0 open edges, catalog facing ok. Mask check healthy (1.5 % of corners off by > 0.5).

## TT_Cave_Room_SwimThrough

Two dripstone chambers (each about 12 x 8 m, ceiling 6.6 m / 5.4 m above the entrance floor) joined only by a smooth, curved, water-cut bore (S-bend in plan, 10.1 m long between the chamber walls, 12.8 m including the funnels). Each chamber has a shore that drops into a basin; the bore leaves the basin's far wall at depth. Rock between the chambers is the surrounding terrain (the piece only has the 0.9 m rind round the bore); there is no air or wading connection.

**Water level: Blender z = -1.0 m = piece space y = -1.0 (entrance and exit floor = 0.0).** Marker: empty `WaterLevel` in the blend (`NR_TT_Cave_Room_SwimThrough_v5.blend`), the key `water_level` in `TT_Cave_Room_SwimThrough_info.json`, and a child entity named `WaterLevel` at (0, -1.0, 0) in the prefab. It is deliberately NOT an FBX empty: `SP_TunnelCatalog.AddSockets` makes a socket of every FBX bone, so a bone would become a third socket. To flood: a water volume with its surface at y = -1.0 over x -8.5..8.5, z -13.7..13.7 (the whole piece footprint; the rock walls hold it).

Sockets:

| # | role | Blender pos (floor) | memory point (Enfusion) | dir | floor height |
|---|---|---|---|---|---|
| 1 | entrance, south | (0.00, -13.65, 0.00) | (0.00, 1.00, -13.65) | -Z | 0.00 m (1.0 m above water) |
| 2 | exit, north | (-0.60, 13.63, 0.00) | (-0.60, 1.00, 13.63) | +Z | 0.00 m (1.0 m above water) |

Numbers (collider, 0.2 m columns, `NR_check.py swim`):
- (a) Walk/wade from socket 1 (floors down to 1.2 m under water, 45 deg): reaches 46 m2 of the entrance chamber and its shore down to z = -1.1 (y <= -7.3), the basin surface included; reaches nothing of the exit chamber (0 nodes beyond y = 4.4) and not socket 2. Air above water is not connected between the chambers (the bore is submerged).
- (b) Swim connectivity (all void, sphere radius 0.9 m): entrance pool and exit pool connect; the largest sphere that passes has diameter 2.08 m (bore interior clearance 2.2-2.5 m, the narrowest point is the funnel into the chambers). Bore roof at most z = -2.38 (1.38 m under the water level); mouth roofs at the chamber walls -1.78 (A, 0.78 m below) and -1.98 (B, 0.98 m below).
- (c) The exit shore (floor within 0.45 m of the water level, y > 4.4) is walkable (dry floors, <= 35 deg, headroom 1.8 m) to socket 2: 51 of 65 shore nodes are in socket 2's component.
- Air above the pools: median 6.6 m over submerged floor, at least 0.3 m at the odd overhang corner (min over the central 8 m). No formation roots under water and none in the bore (no formations in the rock zone |y| < 4.9; the bore wall roughness is scaled to 12 percent near the centre line).
- No bypass: the chambers are separate voids; the only connection is the bore. Dead ends: none needed.
- Budgets: LOD0 167k tris (LOD1 67k, LOD2 23k), collider 40k (bore protected in the decimation). Openings 11/11, 0 open edges, facing ok.

## Known issues

- Previews were rendered from the last-but-one swim build (the bore was then 0.15 m higher); geometry otherwise the same. The preview water plane in `NR_swim_entrance_chamber_with_preview_water.png` is preview only.
- Materials/lighting are the cave MatPBRMulti set as on the other rooms (mask channel assumption unverified, as noted in the handoff). Not looked at in the engine yet.
- The hall's walls are plainer than the cathedral's (more relief would need `wall_amp` and a rebuild); the rubble slope carries many cone-shaped small stalagmites, the descent width is unaffected.
- Local slope lumps up to 32-34 deg exist on both descents (formation skirts, mounds); averages are well under 30 deg.
- The preview cameras for the bore are approximate; the funnels at the bore ends are 1.6 m radius.
- `TT_Cave_*` names are classified as cave by the generator's theme rule; check that "Rebuild TT catalog" lists both with two sockets each and that the hall is taken as a large room.

## What the user has to do

1. Workbench has the FBX and mask registered (metas created, `.xob.meta` pre-patched with scene hierarchy and material assigns), but has not built the xobs. In the Resource Browser right-click `Assets/Tunnels/Cave/TT_Cave_Hall_TwoLevel.fbx` and `TT_Cave_Room_SwimThrough.fbx` -> Import / Register (or `touch` the FBX); import the two `_MASK.tif` the same way (the old trick: Register on the tif makes the edds.meta). Click OK on any dialog; check that each model shows memory points `1` and `2` only.
2. After the import, from the addon root: `python Docs/blender/caves/newrooms/NR_finish.py TT_Cave_Hall_TwoLevel` and `... TT_Cave_Room_SwimThrough` (sets the collision surface, rewrites the prefab; safe to rerun).
3. Re-import the textures if the mask looks wrong (stale NMO/MASK is the usual cause).
4. World Editor tool "Entrance Snap (hover)": "Rebuild TT catalog", then click-place the pieces.
5. Swim room: place a water volume with its surface at the prefab's `WaterLevel` height (piece y = -1.0).

## UV repair result (main session, 2026-11-25)
The mask-UV (UV set 2, `UVMask`) defect that showed as small triangular missing-texture patches in `TT_Cave_Hall_TwoLevel` is repaired in the
re-exported FBXs (hall 24 Nov 21:52, swim room 22:06); checked with `newrooms/NR_uvcheck.py` / `NR_uvzero.py`:

| asset | LOD | zero-area UV tris | overlapping tris | negative winding |
|---|---|---|---|---|
| TT_Cave_Hall_TwoLevel | LOD0 / LOD1 / LOD2 | 0 / 0 / 0 (was 1741 / 800 / 255) | 0 / 0 / 0 (was 454 / 199 / 121) | 0 / 0 / 0 (was 0 / 118 / 106) |
| TT_Cave_Room_SwimThrough | LOD0 / LOD1 / LOD2 | 0 / 1 / 1 | 0 / 2 / 0 | 0 / 0 / 0 |

Extremely stretched mask triangles (texel density below 5% of the median): hall 1393 -> 298, swim room 184. Cause was collapsed UV2 at the formation cones (see `CaveKit_NewRooms_UVDefect.md`).
