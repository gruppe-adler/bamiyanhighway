# Tunnel test kit (TT_) — plan

Goal: our own, very simple tunnel pieces that can't leak light, and a maze rule set so nobody can see further than
about 20 m underground (the engine culls what's below the terrain beyond that). The EoH Modular Tunnel Pack leaked sun
at its joints however we covered them (masks, light-blocker planes, dark probes).

## Pieces (one tunnel size: 1.4 m wide, 2.1 m high inside, flat floor)

| Piece | What it is |
|---|---|
| TT_Straight_4 | 4 m straight |
| TT_Turn90 | 90° turn, radius 2.5 m (entered from the other end it turns the other way) |
| TT_Dogleg_L / _R | 5 m long, 1.8 m sideways shift: breaks the line of sight without changing direction |
| TT_Slope | 1.2 m rise over 4 m, eased at both ends (reversed it goes down) |
| TT_Junction | small chamber, three openings, none in line with another |
| TT_Room | 6 x 6 m room, 2.6 m high, three staggered openings |
| TT_End | dead end |
| TT_Entry_Horizontal | mouth into a hillside: flared opening, then the tunnel |
| TT_Entry_Incline | 45° stair shaft, its top cut level with the ground |

## Light blocking, built into every piece

1. **Solid shells.** Every piece is a closed solid of earth: inner tunnel surface, outer surface 0.6 m further out, ends
   closed with rings. No single-sided faces; thick enough that shadow-map bias can't leak through.
2. **Sleeves over every joint.** Each opening carries a sleeve reaching 0.25 m past the joint over the neighbour's
   shell (and 0.25 m back over its own). Two joined pieces' sleeves overlap: there's no straight path from the earth to
   the inside at any joint. Both ends are identical, so any opening fits any opening.
3. **Timber frames at the joints.** 12 cm deep, 15 cm long, on each piece's own side of the joint: a seam that isn't
   quite perfect reads as two timbers meeting.
4. **Materials with no sky light.** The tunnel mod's EoH_Tunnel_Mud and EoH_Tunnel_Wood (image-based light 0, ambient
   0, double-sided, no fog).

## Sight lines under 20 m

- In the pieces: straights at most 4 m; doglegs; the junction's and the room's openings are never in line.
- In the generator: at most about 12 m of tunnel between view-breaking pieces (turn, dogleg, junction, room, slope with
  a full roof's rise). Anything else is refused once the run is used up.

## Pipeline

1. `Docs/blender/tunnelkit_build.py` builds every piece from a few numbers (profile, shell, sleeve, frame) and exports
   one FBX per piece to `Assets/Tunnels/TT/`: `<Name>_LOD0` + `UTM_<Name>` (collider = the same mesh), triangles only,
   materials `TT_Earth` and `TT_Wood`, memory points (empties) `1`, `2`, ... at each opening, 1 m above the floor.
2. Register in Workbench, patch each `.xob.meta`: materials -> the tunnel mod's emats, collider -> dirt gamemat.
3. Prefabs `Prefabs/Tunnels/TT/<Name>.et`: GenericEntity + MeshObject + RigidBody (BuildingFireView, static), like the
   Graben pieces.
4. The generator gets a kit switch (EoH pack / TT kit), the sight-line rule, and direct room attachment (TT rooms have
   the corridor profile at their openings, no doorways needed).
5. Test: generate in the test world, check at noon, low sun, and down the longest runs.

## Status 2026-11-22 (evening)

Done, not yet seen in Workbench:
- `Docs/blender/tunnelkit_build.py`: all 10 pieces build; every one is a closed solid (0 open edges, checked in Blender);
  room and junction checked hollow with clear openings by ray casts. Exported to `Assets/Tunnels/TT/*.fbx`, imported with
  `ExportFBXResource` (all Ok).
- `Docs/blender/tunnelkit_finish.py`: `Data/TT_Earth.emat` (the tunnel mod's mud: no sky light) and `TT_Wood.emat`,
  collider surface dirt, prefabs `Prefabs/Tunnels/TT/*.et`. Resource DB rebuilt; `TT_Turn90.et` resolves.
- Generator: "Kit" setting (EoH pack / TT test kit, separate catalogs `$profile:SP_TunnelCatalog_TT.txt`), TT rooms and
  the junction attach straight onto tunnels, "Longest straight run" rule (default 12 m: after that only a turn, dogleg,
  U-turn, climbing turn, ladder or room may follow). No light-blocking planes or dark probes for the TT kit.

Next:
1. Ctrl+Shift+R; generator Kit = TT test kit; Rebuild catalog; Verify catalog (every piece with a straight on each
   opening). Unknown until then: whether the FBX empties ("1", "2", ...) come through as bones (memory points). If not,
   the catalog reports "no sockets" and the sockets have to come from geometry instead.
2. Place TT_Entry_Horizontal or TT_Entry_Incline on the ground (pivot: mouth floor / hole centre on the ground), select it,
   Generate. Check light at noon and at a low sun; walk the longest runs.
3. Rebuild the kit after changing numbers: in Blender `TT_EXPORT=True; exec(open(...tunnelkit_build.py).read())`, then
   ExportFBXResource for each FBX, then `python Docs/blender/tunnelkit_finish.py`.
