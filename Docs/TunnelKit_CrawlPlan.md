# Crouch and prone connectors for the TT tunnel kit: plan

Status: plan only, 23 Nov 2026. Nothing here is built.

## 1. What the EoH pack measured (Docs/EoH_TunnelPack_Measurements.txt, the OPEN lines)

| Size | Opening (width x height) | Floor / roof around the pivot | Pieces in the pack |
|---|---|---|---|
| Standing (S) | 1.21 x 2.16 m | -1.146 / +1.018 | straights 3.5 / 7.5 m, Left/Right90, L/R bend (10 m long, 2.5 m shift), U-turn, up/down slope, water trap |
| Crouching (C) | 1.295 x 1.571 m | -0.829 / +0.742 | same set, plus up-turn (stairs) |
| Prone (P) | 1.295 x 0.899 m | -0.468 / +0.431 | straights 3.5 / 7.5 m, Left/Right90 (the rest are shared with C) |

Also: the pack joins sizes through doorway pieces in room walls (`C_Doorway`, `P_Doorway`, opening about 1.29 x 1.58) and has per-size masks. Our kit's standing opening is 1.4 x 2.1 m (`INNER` in `tunnelkit_build.py`), a little wider and lower than EoH's, with a different joint (sleeves, frame).

## 2. Decision to confirm first: what is a "connector"?
- **A. Squeeze (recommended first step).** A short piece (6 to 10 m) with a standing opening at BOTH ends whose middle narrows to crouch or prone size. The generator needs no size logic for it: it is just another corridor piece with a weight. Players can see it from the standing tunnel, and AI or heavy kit has to take another way round.
- **B. Full crouch / prone corridors** (own straights, turns, slopes, ends) joined to the standing network through reducer pieces. More work, gives whole crawl branches and loop shortcuts.
- **Recommendation:** A now, B later, and B first used for the remerging loops you asked for (a crawl shortcut between two parts of the maze is a good loop).

## 3. Profiles (Blender, `Docs/blender/tunnelkit_build.py`)
1. Replace the single `INNER` by profiles of the same 11-point topology: `INNER_S` (as now), `INNER_C` (1.30 x 1.57), `INNER_P` (1.30 x 0.90). Same topology is what makes morphing between them possible.
2. Derive `OUTER`, the sleeves and the timber frame from each profile with the existing `offset()` function. Frames get thinner on C and P (a frame 0.12 m deep eats a lot of a 0.9 m opening).
3. Add `sweep_morph(samples, profiles_per_sample)`: like `sweep`, but with the profile blended along the path (smoothstep over about 1.5 m). The earlier `breathe()` scales cannot do this, because the heights change by different factors.
4. The organic wall noise (`roughen`) keeps its fade at the openings, and its amplitude must be cut on P (a 0.1 m swell is a 11 percent height change there).

## 4. Pieces
**Phase A (squeezes, standing sockets at both ends):**
- `TT_Squeeze_C_6`, `TT_Squeeze_P_6`: 6 m straight, narrowing over 1.5 m, 3 m at crawl size, widening again. Walkable collider.
- `TT_Squeeze_P_Bend`: the same with a 45 degree jog in the middle so there is no line of sight through it.

**Phase B (full kit, per size C and P):** `TT_C_Straight_4`, `TT_C_Turn90`, `TT_C_Slope`, `TT_C_End`, same for P (P has no slope: crawl up a ramp is fine, so the slope is shared with C if collision allows); reducers `TT_Reduce_SC`, `TT_Reduce_CP`, `TT_Reduce_SP` (each 3 to 4 m, usable in both directions); a crawl junction is not needed (use a room).

## 5. Catalog and generator changes (`Scripts/WorkbenchGame/EoHTunnelGen`)
- `SP_TunnelCatalog.ClassifyTT`: today every TT piece is size S. Read the size from the name (`TT_C_`, `TT_P_`), and give the reducers one size per socket. Needs a per-socket size table (the EoH kit gets it from its doorway roles).
- Phase A needs only the classification `Squeeze` = kind STRAIGHT (does not break sight, except the bend variant), weight a new setting "Squeeze weight", and a rule not to place two squeezes in a row.
- Phase B: `TryCorridor` already filters pieces by `open.m_iSize`, `PickSize()` already exists for room doors (`m_fCrouchWeight`, `m_fProneWeight`). Missing: a reducer step. Proposal: a composite "connector" unit in the generator: [reducer, 2 to 6 crawl pieces, reducer] placed as one attempt (all or nothing), so the network always returns to standing size.
- Rooms: TT rooms only have standing openings (`TryRoomDirect` needs equal sizes); a crawl branch ends in a reducer and then the room.
- Remerging loops (your request): the same composite connector, with its end docked onto an existing free opening.

## 6. Gameplay checks
- Walk it in play mode: capsule heights are not known to me. EoH's 1.57 m and 0.90 m interiors are the starting point; if the engine's crouch capsule is higher than the real clearance, widen the profile before changing anything else.
- Slopes and stairs: crawling up a slope steeper than about 20 degrees may not work in the engine; keep slopes shallow on C and P.
- Light: connectors are short, our -16 probes cover them; the corridor probe prefab is 4.4 m high, fine.
- Culling: pieces carry the no-cull flag like the others.

## 7. Order of work
1. Profiles and `sweep_morph` in Blender, preview all three sizes next to each other (an hour of work, the rest depends on it).
2. Phase A pieces, export, import, `tunnelkit_finish.py` (prefabs, materials, scene hierarchy), classify, rebuild catalog, generate, walk through.
3. Tune widths and heights from the walk-through.
4. Phase B kit and the composite connector in the generator.
5. Use the connector for remerging loops.
6. Wide crawl chambers (section 7b) from the cave generator, after the profiles exist.

## 7b. Wide crawl chambers (the user's addition, 23 Nov 2026)
Areas where you have to go prone but that are wider than one person (3 to 10 m across), shaped like caves inside the asset: sloping floor, sloping ceiling, or both, so they don't read as a lowered box.

- **How:** these are rooms, so they come out of the cave generator (`Docs/blender/caves`, v4/v5 with the voxel merge), not the corridor kit. New variant family `Crawl` with a low void: height 1.1 to 1.6 m, ceiling dropping to 0.85 to 0.95 m in places (prone only) and rising to 1.4 m in pockets (crouch / kneel pockets, so it is not monotone).
- **Slopes:** the generator already has a `slope` (the whole shell sheared along Y, floor and ceiling together). Add `ceil_slope` (tilts only the ceiling: shear weighted by how far up each vertex is), and a floor cross-slope (shear along X). So floor only, ceiling only, or both, and a ceiling that closes down toward one side.
- **Organic shape:** the same alcoves, pockets and drops as the new organic rooms, scaled to the low height; floor banks and flowstone, mud and rubble instead of tall formations. Stalactites only where the ceiling is above 1.1 m and never over the crawl way; small formations (soda straws, drip mounds) are fine.
- **A guaranteed way through:** the traversal check (`traverse_check` in v4) gets a crawl mode: along the lines between the openings the headroom must stay at or above 0.85 m and the corridor at least 1.2 m wide (the check only measures the centre line today: add samples 0.5 m to each side), no step over 0.3 m. Rebuild with another seed until it passes.
- **Openings:** crawl size (the `INNER_C` / `INNER_P` profiles from section 3), so the room is entered through a crawl corridor or a reducer; the opening code in `build_room` takes the profile as a parameter (it uses `INNER` directly today).
- **Catalog and generator:** the room's sockets carry size C or P, and the generator joins them only to crawl corridors or reducers (size matching exists). Used as the target of a composite connector, or placed in the middle of a crawl branch.
- **Materials, lighting, collision:** same `MatPBRMulti` material and -16 house probe; the collider keeps 20 to 30k triangles. The visual mesh can be much cheaper than the big caves (small area).
- **Test first:** one chamber 6 x 8 m with a floor slope of 4 degrees and a ceiling slope the other way, a prone way through, a kneeling pocket; walk it in play mode before building more.

## 8. Questions for you
1. Phase A first (squeezes only), or straight to the full kit?
2. Crouch and prone both, or only one of them for now?
3. Should crawl passages be optional per network (a setting), or always possible?
4. Do AI units need to be able to pass (that decides whether squeezes may be on the main route)?

---
## Status: fine-adjustment pieces (done in Blender, not yet imported)
`TT_Curve_5`, `TT_Curve_10`, `TT_Curve_15` (4 m arc, bend to the right; entered from the other end they bend left) and `TT_Straight_1`, `TT_Straight_2`
are in `Docs/blender/tunnelkit_build.py` (list `FINE`). Checked headlessly: closed meshes, all 11 profile points at both ends.
Exported with `TT_ONLY=fine` (only those five). Next: import in Workbench -> run `tunnelkit_finish.py` -> Rebuild catalog.
Generator side: catalog sets the Curve far-socket direction to the real angle, kind STRAIGHT, weight x0.1 so they are used for fitting
rather than everywhere; connect mode grid check uses 5 degree steps when `TT_Curve_5` is in the catalog.
