# TT kit: crouch and prone families, size transitions

Built 24 Nov 2026 by `Docs/blender/tunnelkit_build_cp.py` (copy-and-extension of `tunnelkit_build.py`, which is untouched).
Nothing here has been seen in Workbench or walked in play mode yet (the user is re-importing the tunnels). The standing kit is
unchanged. Plan for these pieces: `TunnelKit_CrawlPlan.md` (phase B), construction rules: `TunnelKit_Plan.md`.

## 1. Naming rule for the catalog classifier (exact)

| Prefab name | Size of every socket | Kind (as the existing keyword rules give it) |
|---|---|---|
| `TT_C_*` | C (crouch) | Straight_*, Turn90, Dogleg_L/R, Slope, Junction, End, Entry_Horizontal: the existing `Contains("Straight")`, `"Turn"`, `"Dogleg"`, `"Slope"`, `"End"`, `"Junction"`, `"Entry"` rules already give the right kind |
| `TT_P_*` | P (prone) | same |
| `TT_Trans_<A>_<B>` | socket 1 is size A, socket 2 is size B (A, B in `S`, `C`, `P`) | none of the keywords match: needs its own rule (a straight-like connector, kind STRAIGHT is fine; it does NOT break the line of sight) |
| everything else `TT_*` (no `_C_`, `_P_`, `_Trans_`) | S (standing), as today | unchanged |

Parse order: `name.IndexOf("TT_Trans_") == 0` first (then `A = name[9]`, `B = name[11]`), then `IndexOf("TT_C_") == 0`, then
`IndexOf("TT_P_") == 0`, else S. Mind the existing `AddSockets`: it sets `socket.m_iSize = piece.m_iSize` for every socket;
for `TT_Trans_*` it must instead use A for the socket whose bone is "1" and B for "2". The piece's own `m_iSize` can be A.
Entries (`TT_C_Entry_Horizontal`, `TT_P_Entry_Horizontal`) have one socket of their size and kind ENTRANCE; their prefab carries
`m_bEntrance 1` like `TT_Entry_Horizontal`. A transition is symmetrical: used from the far end it just converts the other way
(the generator already walks pieces both ways through sockets).

## 2. Profiles (Blender: x across, z up from the floor; Enfusion: x, y up)

All three have the same 11-point topology (floor, bulging walls, shoulder, near-flat roof), so a transition morphs between
them point by point. The roof is nearly flat within 0.3 m of the middle so shoulders have the same headroom as the head.

| | S (standing kit, unchanged) | C (crouch) | P (prone) |
|---|---|---|---|
| Earth opening, floor width | 1.40 m | 1.24 m | 1.04 m |
| Widest (wall bulge) | 1.48 m | 1.30 m | 1.08 m |
| Earth opening, height at the middle | 2.10 m | 1.64 m | 0.965 m |
| Timber lining at joints | 0.12 m deep | 0.02 m proud, flush look | 0.02 m proud |
| **Clear at a joint (after lining)** | 1.4 x 2.0 | **1.20 wide x 1.62 high** | **1.00 wide x 0.945 high** |
| Shell (earth round the opening) | 0.6 m | 0.6 m | 0.6 m |
| Sleeve (reach / sink in / thickness) | 0.25 / 0.1 / 0.3 | same | same |
| Roughness (wall / floor) | 0.2 / 0.035, both ways | 0.10 / 0.02, **outward only** | 0.05 / 0.012, **outward only** |
| Socket height above the floor | 1.0 m | **0.8 m** | **0.475 m** |

Why the numbers: the lining of the standing kit (0.12 m deep) would eat 12 percent of a prone opening, so on C and P the
lining is a 2 cm lip and the earth opening is made 2 cm taller and 2 cm wider on each side than the clear size asked for
(1.2 x 1.6 and 1.0 x 0.92). The wall noise only moves the wall, roof and floor away from the void on C and P, so the
inside is never smaller than the profile, whatever the noise does; the ray casts below confirm it. Same plan geometry as the
standing kit everywhere: turn radius 1.8 m, dogleg 4.6 m sideways over 3.6 m (so the generator's grid and any "TT_Turn90 =
1.8, 1.8" assumption hold for C and P too). Slopes are gentler than the standing one: C rises 1.0 m over 4 m, P 0.8 m over
4 m (eased at both ends: steepest 21 and 17 degrees; the standing slope's 1.2 m is 24).

**Opening sizes at every joint of a family are identical** (the ring check below is exact), and each transition side uses
its neighbour's profile, so any opening of a size fits any opening of that size, standing kit included (the S profile here was
checked against the real `TT_Straight_2.fbx`: all 11 inner and 11 outer points of its opening ring match to 0.00000 m).

## 3. Socket convention (memory points)

- Empties named `1`, `2`, `3` in the FBX (becomes bones via `ExportSceneHierarchy 1`, as the standing kit).
- **Position: on the centre line of the opening, in the end plane, at HALF THE OPENING'S HEIGHT above the floor**: S 1.0 m (the
  standing kit's existing value), C 0.8 m, P 0.475 m. This is the EoH convention too (its C and P sockets sit at the middle of the
  opening: C_Straight bounds -0.855 .. +0.745 with the socket at -0.05, P_Straight -0.484 .. +0.433 with the socket at -0.023).
  Reason it has to be this and not the standing kit's flat "1.0 m": the catalog's `OutwardOf` traces from the socket along the axis and
  needs the point to be in the void (1.0 m is inside the 0.965 m prone roof's earth), and the generator's probe placement uses
  `socket y + 0.3` as an inside point (0.775 m is inside every P opening).
- **Direction: the empty's local +Z (the arrow) points out of the piece**, horizontal, along the tunnel axis at that end. The
  catalog derives the direction from the bounds anyway (`OutwardOf`), the arrow agrees with it to 0.000 degrees.
- Floors are at piece-local y 0 (Enfusion) at every opening, so with sockets at half height, **two sockets of different size
  differ in socket y by the difference of the half heights** (S/C 0.2 m, C/P 0.325 m, S/P 0.525 m): the generator should
  place the next piece with the usual "socket on socket" rule; the floor stays level (the transitions have a flat floor). Note
  `SP_TunnelGenPlugin` (probe code, about line 1497) treats a 2-socket piece as a straight when the two socket heights differ by
  less than 0.3 m: transitions S/P and C/P are therefore not "straight" there and get one probe per socket instead, which is fine.
- Socket order: opening 1 is at the origin facing -Z (Enfusion; -Y in Blender); `TT_Trans_<A>_<B>`: 1 is size A, 2 is size B.

Socket positions in Enfusion coordinates (x, y up, z) in the piece's own space:

| Piece | Sockets (number: position, size); direction is out of the piece along the axis |
|---|---|
| TT_C_Straight_4 | 1: (0, 0.8, 0) facing -Z; 2: (0, 0.8, 4) facing +Z |
| TT_C_Straight_2 | 1: (0, 0.8, 0); 2: (0, 0.8, 2) |
| TT_C_Turn90 | 1: (0, 0.8, 0) facing -Z; 2: (1.8, 0.8, 1.8) facing +X |
| TT_C_Dogleg_L / _R | 1: (0, 0.8, 0) facing -Z; 2: (-4.6 / +4.6, 0.8, 3.6) facing +Z |
| TT_C_Slope | 1: (0, 0.8, 0); 2: (0, 1.8, 4) (rise 1.0) |
| TT_C_Junction | 1: (0, 0.8, -2.6) facing -Z; 2: (2.6, 0.8, 0.6) facing +X; 3: (-2.6, 0.8, -0.7) facing -X |
| TT_C_End | 1: (0, 0.8, 0) facing -Z (dead end 1.6 m deep) |
| TT_C_Entry_Horizontal | 1: (0, 0.8, 5) facing +Z; pivot = mouth floor centre, mouth has no socket (like TT_Entry_Horizontal) |
| TT_P_* | the same list with 0.475 instead of 0.8; junction: 1: (0, 0.475, -2.4), 2: (2.4, 0.475, 0.5), 3: (-2.4, 0.475, -0.6); slope 2: (0, 1.275, 4) |
| TT_Trans_S_C, _C_P, _S_P | 1: (0, h<sub>A</sub>, 0) facing -Z; 2: (0, h<sub>B</sub>, 3) facing +Z, h = 1.0 / 0.8 / 0.475 for S / C / P |

## 4. The pieces

| Piece | Triangles | Bounds (x, z min..max; Enfusion) | Notes |
|---|---|---|---|
| TT_{C,P}_Straight_4 | 5734 / 4330 | z -0.25..4.25 | swells to 1.12 (C) / 1.10 (P) wide in the middle, never narrower |
| TT_{C,P}_Straight_2 | 3726 / 2902 | z -0.25..2.25 | exact profile all along |
| TT_{C,P}_Turn90 | 6500 / 4878 | x -1.55..2.05 | radius 1.8, turns right (from the other end: left) |
| TT_{C,P}_Dogleg_L/_R | 8514 / 6360 | x -6.15..1.55 (L) | 4.6 m sideways, no change of heading, chicane (two 90 degree bends and 1 m across) |
| TT_{C,P}_Slope | 5926 / 4578 | y up to +1.0 / +0.8 | eased both ends; steepest C 21, P 17 degrees |
| TT_{C,P}_Junction | 9870 / 8620 | C 5.7 x 5.0 m, P 5.3 x 4.6 m | chamber 2.8 x 2.8 x 1.9 m (C), 2.4 x 2.4 x 1.15 m (P), 3 openings, none in line |
| TT_{C,P}_End | 2948 / 2300 | z -0.25..2.2 | dead end 1.6 m deep |
| TT_{C,P}_Entry_Horizontal | 5548 / 4166 | z 0..5.25 | mouth flares over 1.2 m (C: +50 percent wide, +30 high; P: +60 / +50), timber frame at the mouth, 5 m long, pivot at the mouth |
| TT_Trans_S_C | 5628 | z -0.25..3.25, 3.0 m long | S for 0.9 m, ramp 0.9 m, C for 1.2 m |
| TT_Trans_C_P | 4850 | same | C 1.0 m, ramp 0.8 m, P 1.2 m |
| TT_Trans_S_P | 5718 | same | S 0.55 m, ramp 0.7 m, C 0.5 m, ramp 0.7 m, P 0.55 m (a two-stage funnel) |

Transitions: the profile morphs (smoothstep) over each ramp, the floor stays level, the roof comes down. A timber lining sits
on the plateau side of every ramp end (0.15 m long, the profile's own lining), so each step reads as a timbered step; the shell
swells by up to 0.25 m over a ramp's middle to keep the earth thick where the roof falls steeply. Both ends are exact plateaus
with the usual sleeve and joint lining of their profile. Light-tightness: same construction as the standing kit (solid shells,
sleeves, closed ends).

## 5. Verification (computed, headless Blender, `Docs/blender/previews/CP_stats.json`)

Method: every piece is built, finished (triangulated, split into TT_Earth/Wood/Ground, refined, roughened as exported) and then
tested on that final mesh:

- **Clearance**: ray casts along the route (every 0.1 m; a junction along each door-to-door route): straight up and down from
  a point at the middle of the opening at the route and 0.3 m to each side (height), and left/right at four heights from 0.12 to
  0.62 of the opening (width), in the piece's final mesh including lining and sleeve.
- **Closedness**: boundary edges, edges with more than two faces, non-triangles, loose edges per piece.
- **Sockets**: the empties' position and arrow, the floor and roof under/over the socket, nothing in the way outward.
- **Joints**: each opening joined to a 2 m straight of its size (`TT_Straight_2` of the standing profile for S sides) and,
  for two-socket pieces of one size, a second copy of the piece itself: the vertices of the opening rings at the joint plane must
  coincide, each sleeve's reach past the plane is measured, and 4680 random rays per joint from points on the axis round the plane
  measure the earth between the void and the open air.

| Piece | Min height at the route | Min height 0.3 m left/right | Min width | Open edges |
|---|---|---|---|---|
| all `TT_C_*` (also in transitions' C parts) | **1.616** (slope; 1.62 elsewhere) | 1.607 | 1.212 (1.213 turns) | 0 |
| all `TT_P_*` | **0.942** (slope; 0.945 elsewhere) | 0.931 | 1.003 | 0 |
| TT_Trans_S_C | 1.62 (C side; the S side is 2.0 at the lining) | 1.611 | 1.188 inside the ramp (1.20 at the joint) | 0 |
| TT_Trans_C_P, TT_Trans_S_P | 0.945 (P plateau) | 0.936 | 1.003 | 0 |
| TT_C_Entry_Horizontal / TT_P_Entry_Horizontal | 1.62 / 0.945 | 1.611 / 0.936 | 1.212 / 1.003 | 0 |

(The targets were: C at least 1.6 high and P at least 0.92 high everywhere: met by 0.016 m and 0.022 m. Widths 1.2 and 1.0:
met; the S/C ramp is 1.188 m wide at one cross-section in the middle of the morph, 1 cm under 1.2, the others pass.)
Every one of the 21 pieces has 0 open edges, 0 edges with more than two faces, 0 non-triangle faces, positive signed volume
(normals out).

Sockets (all 40 checked): the arrow's local +Z equals the socket's outward direction to 0.0000 degrees, the point lies on the
floor +0.8 / +0.475 / +1.0 m (measured 0.80 / 0.475 / 1.00, slopes 0.798 .. 0.802), the roof is 0.82 / 0.47 / 0.98 m above it
(the opening's height), and a ray out of the opening along +Z escapes (nothing in the way) at every socket.

Joints (52 joint tests, 243,360 rays): ring mismatch 0.000000 m at every joint, except TT_P_Dogleg_L/_R socket 2 where one
side carries two extra vertices on the opening's outline (0.125 m: a collinear vertex from the edge subdivision, no gap);
**each sleeve reaches exactly 0.250 m past the joint plane into its partner and the partner's reaches 0.250 m back** (so the
copies overlap by exactly the sleeve length, 0.25 + 0.25 m of overlapped earth, no gap); no ray escaped to the open air by any
route other than an opening (0 of 243,360 at joints; 0 of 17,440 single-piece rays); the thinnest earth a ray had to cross
between the void and the open air at a joint was 0.415 m (shell 0.6 m minus noise). Single pieces: thinnest earth 0.46 to 0.59
m except TT_Trans_S_P where one grazing ray measured 0.085 m (a second run of the same piece alone found 0.47 as its minimum, so
it is a ray along a lining corner, not a thin wall; look at that piece's funnel in play mode). A small number of rays
(62 in 243,360 at joints, 5 in 17,440 single piece, mostly near the doors of the junctions) hit overlapping or coincident surfaces
and could not be classified (folded double surface 1 to 10 cm at the junction doors where a stub's start overlaps the chamber
wall's hole): no light path, but the junction doors are the place to look first at a first import.

Not verified: any engine behaviour (collider, capsule, lighting, import). Everything above is geometry in Blender.

## 6. Files

- `Docs/blender/tunnelkit_build_cp.py`: the builder (parameters at the top: profiles `S_PTS/C_PTS/P_PTS`, `PROF`, `SLOPE_RISE`,
  `JUNCTION`, `ENTRY`, `TRANS_KEYS`, `TURN_RADIUS`, `END_VOID`); deterministic (the noise is Blender's fixed Perlin; the test's random
  rays use a fixed seed). Env: `CP_EXPORT=0` (no FBX), `CP_ONLY=Trans_` (subset), `CP_VERIFY=0`.
  `blender --factory-startup -b --python Docs/blender/tunnelkit_build_cp.py`
- `Docs/blender/tunnelkit_finish_cp.py`: writes/patches the `.xob.meta` and the prefabs of the 21 new pieces only.
- `Docs/blender/CP_preview.py`: the renders. `Docs/blender/previews/CP_*.png` (profiles, transitions in section, family plans,
  views from inside), `CP_stats.json` (all numbers above), `CP_build.log`.
- `Assets/Tunnels/TT/TT_{C,P}_*.fbx`, `TT_Trans_*.fbx` (21 FBX) with `.xob.meta`; `Prefabs/Tunnels/TT/<same names>.et` + `.et.meta`.

## 7. Import steps for the user

The FBXs and metas are ready. The `.xob`, `.txo` do not exist until Workbench builds them. In order:

1. Start Workbench (project Shashpul) and let it scan. The new `.fbx` files carry a pre-written `.xob.meta` (resource GUID, material
   remap TT_Earth/TT_Wood/TT_Ground to `Assets/Tunnels/TT/Data/*.emat`, collider surface `dirt.gamemat`, `ExportSceneHierarchy 1`),
   so the prefabs (which reference those GUIDs) resolve. In the Resource Browser open `Assets/Tunnels/TT`, select the new FBXs
   (`TT_C_*`, `TT_P_*`, `TT_Trans_*`) and **right-click, Register Resource / Reimport** (the menu wording may differ in your Workbench build) (or open one and press the import
   button); wait for "Build ok". Check that `.xob` appeared next to each FBX.
2. If Workbench ignores the pre-written meta, delete the new `.xob.meta` files (the 21 new names only), register the FBXs the normal
   way (Resource Browser: right-click, Register / `ExportFBXResource`, all Ok), then run
   `python Docs/blender/tunnelkit_finish_cp.py` from the addon root: it patches the metas Workbench wrote (materials -> the TT emats,
   collider surfaces -> dirt, `ExportSceneHierarchy 1`) and rewrites the prefabs to the new xob GUIDs. Re-register the FBXs once more
   after the patch so the changes are built (this is the same order as the standing kit: register, patch, re-register).
3. Check one import: open `TT_Trans_S_P.xob` in the Resource Browser: the three materials must show the mud and timber, the
   collision tab shows `UTM_TT_Trans_S_P`, and the "Bones"/memory points list must show `1` and `2` (if not, `ExportSceneHierarchy` was lost: re-run step 2).
4. Reload scripts if the classifier was changed (`Game > Reload Game Scripts`), World Editor: Generator plugin, kit "TT test kit",
   **Rebuild catalog**, then "Verify catalog". Expected per piece: sockets with the heights in section 3, size classes by the naming rule in section 1.
5. Walk-through before trusting the sizes: place `TT_C_Straight_4`, `TT_P_Straight_4`, `TT_Trans_S_C`, `TT_Trans_C_P`,
   joined to standing pieces, and walk and crouch/prone through in play mode. This is the only way to know whether the engine's crouch
   and prone capsules pass 1.6 m and 0.92 m (the EoH pieces' 1.571 m and 0.899 m are our only evidence); if a capsule is blocked widen
   `C_PTS`/`P_PTS` by the missing centimetres, rebuild (`tunnelkit_build_cp.py`), re-import.

## 8. Not done / open

- Not imported or walked in Workbench (no Workbench use by request). Capsule fit, slope walkability (21 / 17 degrees), the
  lighting of low pieces, and prefab collision on 0.945 m ceilings are untested.
- No `Straight_1`, `Curve_*`, `Turn90_Wide`, rooms or `Entry_Incline` in C and P (not asked).
- The junction doors have a short folded double surface where the stub overlaps the hole (check visually); `TT_Trans_S_P` had one
  grazing ray at 0.085 m earth (see section 5).
- The generator was not changed: sockets per size, the classifier and the "never go standing -> prone without a transition" rule
  are for the main session.
