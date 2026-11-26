# TT tunnel kit: clearance measurement and redesign (Phase 1 + Phase 2)

Written 24 Nov 2026 by the clearance agent. Brief with the user's decisions: `Docs/TunnelKit_Redesign_Brief.md`.
**Phase 2 is installed**: the 55 FBX of the kit are in `Assets/Tunnels/TT` (the 39 existing pieces overwritten in place, 16 new variant files), the
`.xob.meta` files are patched / written, 16 new prefabs exist. Nothing was imported or walked in Workbench (not allowed for this work).
Originals (FBX, `.xob.meta`, prefabs) are backed up outside the addon: scratchpad `TT_backup_all` of the agent session
(`C:\Users\nomisum\AppData\Local\Temp\claude\c81b5a423a7fadec\bd5cc9f6-c8d9-403d-8517-af6f265bb797\scratchpad\TT_backup_all`). Existing `.et` prefabs were not touched.

## 1. The complaint, measured ("I get stuck", "doorways a tiny bit wider")

Method: `Docs/blender/CL_measure.py` imports the exported FBX files and ray-casts the final mesh (the collider `UTM_` is the same mesh as
`_LOD0`: checked, 0.0 m difference on all files). Routes are the pieces' plan paths every 0.1 m (junction/room: door to door through the middle; the
incline: up the stairs). Height = floor to roof straight up/down at the route centre / 0.3 m to either side (band). Width = wall to wall at 0.35 - 1.4 m
above the floor (crouch 0.25 - 1.0, prone 0.15 - 0.55; the arched roof is measured separately as head width at 1.7 m). Zones: **joint** = within
0.5 m of an opening, **body** = the rest, **doorway** = 0.5 .. 1.15 m behind a chamber door, **mid** = at least 1.5 m from both ends.
The measuring rays are offset 1 cm off the mesh's own edges (a ray exactly along an edge can slip through; this produced spurious zero widths in a first version).

Measured on the old kit (before; full table in section 3):

| Piece (old) | Joint: height / band +-0.3 | Joint: width | Head width 1.7 m (joint) | Body: height / band | Body: width |
|---|---|---|---|---|---|
| Straight 1/2/4, Curve 5/10/15, Slope | 1.976 / 1.87 | **1.144** | 0.923 | 2.09 - 2.10 / 2.00 - 2.03 | 1.38 - 1.41 |
| Turn90, Turn90_Wide | 1.975 / 1.87 (turn 1.82) | **1.145** | 0.923 | 2.10 / 2.02 | 1.39 - 1.41 |
| Dogleg L / R | 1.975 / 1.87 (1.80 inner side) | **1.145** | 0.924 | 2.05 - 2.09 / 1.99 | **1.29 - 1.30** |
| Straight_Narrow | 1.976 / 1.87 | 1.144 | 0.923 | **1.894 / 1.71** | **0.96** |
| Junction / Room doors | 1.976 / 1.87 | **1.144** | 0.923 | doorway 2.05 - 2.07 / 1.97 - 2.01 | doorway 1.34 - 1.36 |
| Crouch / prone, transitions S side | 1.62 / 0.945 clear | 1.21 / 1.01 (S side 1.144) | | | |

No floor step at any joint (0.002 m), sleeves reach exactly 0.25 m both ways, 0 open edges. A build of the old builder with the noise switched off
gave the nominal numbers and separated the causes.

### Root causes, in order of effect

1. **The timber frames (FRAME_T 0.12 m into the tunnel) at every opening.** They pull the opening from 1.40 x 2.10 to **1.144 wide x 1.976 high**
   (at +-0.3 m from the centre the roof is only 1.87 m, 1.80 on turn and dogleg joints; at head height the opening is **0.92 m wide**), also in the doors of
   Junction and Room. 25 cm of width and 12 cm of height lost over 15 cm of length, 30 cm where two frames meet: the stuck-at-joints and the "doorways too narrow".
2. **TT_Straight_Narrow**: 0.96 m wide x 1.89 m high in the middle (squeeze factors 0.78 / 0.9 plus noise).
3. **Two-sided wall noise (WALL_AMP 0.2) in the dogleg bodies**: 1.29 - 1.30 wide against nominal 1.40, roof 2.05 - 2.09 against 2.10. Elsewhere the noise hides behind the swelling factors (under 0.02 m).
4. **Door stubs of Junction / Room**: same profile as the corridors, with noise 1.34 - 1.36 wide x 2.05 - 2.07 high behind the frame zone.
5. **Not causes**: slope, turn radius 1.8, floor lip at joints, collider/visual mismatch, sleeves.

## 2. What changed (decisions of the user, 24 Nov 2026, folded in)

Builder: `Docs/blender/tunnelkit_build_clear.py` (own rewrite; the old `tunnelkit_build.py` / `_cp.py` untouched). Installer: `Docs/blender/CL_install.py`.
Measurement: `Docs/blender/CL_measure.py`; tables: `Docs/blender/CL_report.py`; renders: `Docs/blender/CL_preview.py`.

- **No wood anywhere.** No frames, no `TT_Wood`. The FBX have two material slots, `TT_Earth` (0) and `TT_Ground` (1); the old ones had Earth 0, Wood 1, Ground 2.
  The Entry_Incline steps are earth. `.xob.meta`: the `TT_Wood` assignment is removed, the collider surface list has 2 dirt entries. `Data/TT_Wood.emat` stays (unused).
- **Rounded floor-wall junction** (quarter-circle fillet 0.30 walk, 0.15 crouch, 0.10 prone) in every profile; chambers (Junction, Room) have all edges rounded
  (0.30 / 0.20 / 0.12), their door holes start 0.55 m inside so the rounded floor can't leave a lip across a door. Profile = flat floor, fillet, straight wall, elliptical shoulder, **flat crown 0.6 m wide** (so the clear height holds at the centre +-0.3 m).
- **Rings (identical at every opening of a class)**: walk **1.6 x 2.2**, crouch **1.4 x 1.64**, prone **1.2 x 0.965** (clear = earth profile, no lining).
- **Variation between the joints** (smooth, back to the ring at both ends: the first 0.5 m exact in width, then a ramp over 1.0 m; the height reaches 2.32 within 0.5 m, then follows its curve; a slow wobble with phase from the piece name). Nominal clear sizes, before the noise adds:
  standard 1.7 - 2.1 wide x 2.35 - 2.65 high, **A (neck) 1.32 wide x 2.33 - 2.43 high with NO wall noise (a true 1.3 m neck)**, **C (wide) 2.35 - 2.85 wide x 2.65 - 3.05 high**; crouch 1.55 +-0.12 wide, prone 1.32 +-0.10, heights fixed.
  Wall noise elsewhere only moves surfaces away from the void (walk 0.12 / floor 0.03; crouch 0.10 / 0.02; prone 0.05 / 0.012).
  The ceiling rising 12 cm over the first 0.5 m at each joint is accepted by the user.
- **Bends widen to the outside only** (the inside wall stays where the ring puts it: radius 1.8 holds, no plan change).
- **Variants** `_A` and `_C` (new files and prefabs) for Straight_4, Curve_5, Curve_10, Curve_15, Turn90, Dogleg_L, Dogleg_R, Slope: 16 new pieces. Straight_1 and Straight_2: single standard pieces.
  - `TT_Straight_Narrow` = the `_A` dimensions (4 m, no noise, own name and prefab); `TT_Straight_Wide` = the `_C` dimensions, 5 m long as before.
  - `TT_Turn90_Wide` keeps its radius 3.0 (sockets (3, 3)) and takes the `_C` dimensions; `TT_Turn90_C` is the tight radius 1.8 (sockets (1.8, 1.8)) widened to the outside of the bend only.
- **Junction doors staggered** (so there is no straight view from one side door to the other): chamber 3.2 wide x **4.2 deep** (was 3.2), 2.8 high (was 2.4); doors S x 0, E y +1.0 (openings 0.2 .. 1.8), W y -0.9 (-1.7 .. -0.1).
  **New socket positions** (Enfusion x, y up, z; direction out of the piece along the axis):

  | Piece | Socket 1 (S door, facing -Z) | Socket 2 (E door, facing +X) | Socket 3 (W door, facing -X) |
  |---|---|---|---|
  | TT_Junction (walk) new | (0, 1.0, **-3.3**) | (2.8, 1.0, **+1.0**) | (-2.8, 1.0, **-0.9**) |
  | TT_Junction old | (0, 1.0, -2.8) | (2.8, 1.0, +0.6) | (-2.8, 1.0, -0.7) |
  | TT_C_Junction new (chamber 2.8 x 3.8 x 1.9) | (0, 0.8, -3.1) | (2.6, 0.8, +0.9) | (-2.6, 0.8, -0.8) |
  | TT_C_Junction old | (0, 0.8, -2.6) | (2.6, 0.8, +0.6) | (-2.6, 0.8, -0.7) |
  | TT_P_Junction new (chamber 2.4 x 3.2 x 1.15) | (0, 0.475, -2.8) | (2.4, 0.475, +0.75) | (-2.4, 0.475, -0.7) |
  | TT_P_Junction old | (0, 0.475, -2.4) | (2.4, 0.475, +0.5) | (-2.4, 0.475, -0.6) |

  **Junctions already placed in maps must be re-snapped** (the S socket moved 0.5 m, the E and W sockets 0.3 - 0.4 m). The Room's doors (6 x 6 m, S -1.5, E +1.5, N +1.8) did not move (the room is 3.0 m high now, was 2.6).
- **All crouch and prone pieces** (TT_C_*, TT_P_*: Straight_4, Straight_2, Turn90, Dogleg_L/R, Slope, Junction, End, Entry_Horizontal) rebuilt with the new rings, no wood, fillets; the three transitions rebuilt for the new rings (S side = the walk ring 1.6 x 2.2).
- **Unchanged**: every piece's name, length and plan geometry (turn radius 1.8, dogleg 4.6 over 3.6, slopes 1.2 / 1.0 / 0.8 rise, entries 5 m), socket names, positions and +Z-out directions (except the three junctions above; checked on all 55 files against the old ones: 0.001 m tolerance), the incline's pivot.

## 3. Results, before / after (`Docs/blender/previews/CL_before_all.json`, `CL_after_full.json`)

### Piece table (before -> after; height / band = floor to roof at the route centre / 0.3 m to either side; widths: minimum wall to wall at 0.35-1.4 m above the floor; mid = 1.5 m from both ends)

| Piece | Joint height / band | Joint width | Body height / band | Body width | Mid width min .. max | Mid height min .. max |
|---|---|---|---|---|---|---|
| TT_Curve_10 | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.61 | 2.03 .. 2.26 | 2.46 .. 2.69 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.14 | 2.10 / 2.02 | 1.40 | - .. - | - .. - |
| TT_Curve_10_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.32 | 1.32 .. 1.32 | 2.33 .. 2.39 |
| TT_Curve_10_C | 2.21 / 2.21 | 1.59 | 2.33 / 2.33 | 1.61 | 2.58 .. 2.98 | 2.71 .. 2.87 |
| TT_Curve_15 | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.61 | 1.87 .. 2.23 | 2.58 .. 2.70 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.14 | 2.10 / 2.02 | 1.40 | - .. - | - .. - |
| TT_Curve_15_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.32 | 1.32 .. 1.32 | 2.39 .. 2.43 |
| TT_Curve_15_C | 2.21 / 2.21 | 1.59 | 2.33 / 2.33 | 1.62 | 2.50 .. 2.73 | 2.92 .. 3.11 |
| TT_Curve_5 | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.61 | 1.91 .. 2.25 | 2.55 .. 2.70 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.14 | 2.10 / 2.02 | 1.40 | - .. - | - .. - |
| TT_Curve_5_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.32 | 1.32 .. 1.32 | 2.36 .. 2.43 |
| TT_Curve_5_C | 2.21 / 2.21 | 1.59 | 2.33 / 2.33 | 1.62 | 2.57 .. 2.96 | 2.91 .. 3.09 |
| TT_Dogleg_L | 2.21 / 2.21 | 1.59 | 2.33 / 2.32 | 1.61 | 1.78 .. 2.19 | 2.42 .. 2.73 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.15 | 2.05 / 1.99 | 1.30 | - .. - | - .. - |
| TT_Dogleg_L_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.22 | 1.32 | 1.32 .. 1.32 | 2.33 .. 2.43 |
| TT_Dogleg_L_C | 2.21 / 2.21 | 1.59 | 2.33 / 2.33 | 1.63 | 2.37 .. 2.94 | 2.68 .. 3.14 |
| TT_Dogleg_R | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.62 | 1.75 .. 2.20 | 2.45 .. 2.69 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.15 | 2.09 / 1.99 | 1.29 | - .. - | - .. - |
| TT_Dogleg_R_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.23 | 1.32 | 1.32 .. 1.32 | 2.33 .. 2.43 |
| TT_Dogleg_R_C | 2.21 / 2.21 | 1.59 | 2.34 / 2.33 | 1.63 | 2.38 .. 2.96 | 2.67 .. 3.10 |
| TT_End | 2.20 / 2.20 | 1.59 | - / - | - | - .. - | - .. - |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | - / - | - | - .. - | - .. - |
| TT_Entry_Horizontal | 2.22 / 2.22 | 1.59 | 2.33 / 2.33 | 1.62 | 1.85 .. 1.97 | 2.50 .. 2.61 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.10 / 2.03 | 1.40 | - .. - | - .. - |
| TT_Entry_Incline | 2.21 / 2.20 | 1.59 | 1.93 / 1.93 | 1.67 | 1.67 .. 2.15 | 1.93 .. 2.76 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 1.86 / 1.80 | 1.45 | - .. - | - .. - |
| TT_Junction | 2.20 / 2.20 | 1.59 | 2.20 / 2.20 | 1.60 | 1.60 .. 1.79 | 2.20 .. 2.31 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.07 / 2.01 | 1.36 | - .. - | - .. - |
| TT_Room | 2.20 / 2.20 | 1.59 | 2.20 / 2.20 | 1.60 | 1.60 .. 1.79 | 2.20 .. 2.31 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.05 / 1.97 | 1.34 | - .. - | - .. - |
| TT_Slope | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.60 | 1.90 .. 2.24 | 2.41 .. 2.54 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.14 | 2.09 / 2.00 | 1.40 | - .. - | - .. - |
| TT_Slope_A | 2.21 / 2.21 | 1.59 | 2.32 / 2.31 | 1.32 | 1.32 .. 1.33 | 2.33 .. 2.39 |
| TT_Slope_C | 2.21 / 2.21 | 1.59 | 2.32 / 2.32 | 1.60 | 2.46 .. 2.85 | 2.96 .. 3.15 |
| TT_Straight_1 | 2.22 / 2.22 | 1.59 | - / - | - | - .. - | - .. - |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | - / - | - | - .. - | - .. - |
| TT_Straight_2 | 2.22 / 2.22 | 1.59 | 2.38 / 2.38 | 1.64 | 1.64 .. 1.87 | 2.38 .. 2.67 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.10 / 2.02 | 1.38 | - .. - | - .. - |
| TT_Straight_4 | 2.22 / 2.22 | 1.59 | 2.34 / 2.34 | 1.62 | 1.96 .. 2.24 | 2.40 .. 2.49 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.10 / 2.03 | 1.41 | - .. - | - .. - |
| TT_Straight_4_A | 2.22 / 2.22 | 1.59 | 2.32 / 2.32 | 1.32 | 1.32 .. 1.32 | 2.33 .. 2.38 |
| TT_Straight_4_C | 2.22 / 2.22 | 1.59 | 2.36 / 2.36 | 1.66 | 2.49 .. 2.81 | 2.72 .. 3.02 |
| TT_Straight_Narrow | 2.22 / 2.22 | 1.59 | 2.32 / 2.32 | 1.32 | 1.32 .. 1.32 | 2.35 .. 2.42 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 1.89 / 1.72 | 0.96 | - .. - | - .. - |
| TT_Straight_Wide | 2.22 / 2.22 | 1.59 | 2.35 / 2.35 | 1.66 | 2.49 .. 2.94 | 2.76 .. 3.12 |
| &nbsp;&nbsp;before | 1.98 / 1.86 | 1.14 | 2.11 / 2.04 | 1.44 | - .. - | - .. - |
| TT_Turn90 | 2.20 / 2.20 | 1.59 | 2.32 / 2.32 | 1.62 | 1.62 .. 2.06 | 2.32 .. 2.66 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.15 | 2.10 / 2.02 | 1.40 | - .. - | - .. - |
| TT_Turn90_A | 2.20 / 2.20 | 1.59 | 2.32 / 2.31 | 1.32 | 1.32 .. 1.60 | 2.32 .. 2.41 |
| TT_Turn90_C | 2.20 / 2.20 | 1.59 | 2.33 / 2.32 | 1.62 | 1.62 .. 2.64 | 2.33 .. 2.76 |
| TT_Turn90_Wide | 2.21 / 2.21 | 1.59 | 2.33 / 2.33 | 1.62 | 2.54 .. 2.97 | 2.69 .. 3.08 |
| &nbsp;&nbsp;before | 1.97 / 1.86 | 1.15 | 2.10 / 2.03 | 1.41 | - .. - | - .. - |
| TT_Trans_C_P | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.21 .. 1.21 | 0.97 .. 0.97 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.06 | - .. - | - .. - |
| TT_Trans_S_C | 1.64 / 1.64 | 1.40 | 1.65 / 1.65 | 1.41 | 1.41 .. 1.41 | 1.65 .. 1.65 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.14 | 1.65 / 1.64 | 1.27 | - .. - | - .. - |
| TT_Trans_S_P | 0.96 / 0.96 | 1.20 | - / - | - | - .. - | - .. - |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | - / - | - | - .. - | - .. - |
| TT_P_Dogleg_L | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.26 .. 1.46 | 0.98 .. 1.01 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.05 | - .. - | - .. - |
| TT_P_Dogleg_R | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.26 .. 1.47 | 0.99 .. 1.01 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.05 | - .. - | - .. - |
| TT_P_End | 0.96 / 0.96 | 1.20 | - / - | - | - .. - | - .. - |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | - / - | - | - .. - | - .. - |
| TT_P_Entry_Horizontal | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.34 .. 1.39 | 1.03 .. 1.05 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.06 | - .. - | - .. - |
| TT_P_Junction | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.20 | 1.20 .. 1.32 | 0.97 .. 1.03 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.05 | - .. - | - .. - |
| TT_P_Slope | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.20 | 1.31 .. 1.49 | 1.00 .. 1.01 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.05 | - .. - | - .. - |
| TT_P_Straight_2 | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.21 .. 1.25 | 0.97 .. 0.99 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.06 | - .. - | - .. - |
| TT_P_Straight_4 | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.30 .. 1.45 | 1.00 .. 1.01 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.06 | - .. - | - .. - |
| TT_P_Turn90 | 0.96 / 0.96 | 1.20 | 0.97 / 0.96 | 1.21 | 1.21 .. 1.38 | 0.97 .. 1.00 |
| &nbsp;&nbsp;before | 0.94 / 0.93 | 1.01 | 0.97 / 0.96 | 1.06 | - .. - | - .. - |
| TT_C_Dogleg_L | 1.64 / 1.64 | 1.39 | 1.64 / 1.64 | 1.41 | 1.50 .. 1.76 | 1.68 .. 1.73 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.22 | 1.64 / 1.63 | 1.26 | - .. - | - .. - |
| TT_C_Dogleg_R | 1.64 / 1.64 | 1.39 | 1.64 / 1.64 | 1.41 | 1.49 .. 1.76 | 1.69 .. 1.72 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.22 | 1.64 / 1.63 | 1.26 | - .. - | - .. - |
| TT_C_End | 1.64 / 1.64 | 1.40 | - / - | - | - .. - | - .. - |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.21 | - / - | - | - .. - | - .. - |
| TT_C_Entry_Horizontal | 1.64 / 1.64 | 1.40 | 1.65 / 1.65 | 1.41 | 1.59 .. 1.68 | 1.75 .. 1.77 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.21 | 1.65 / 1.64 | 1.27 | - .. - | - .. - |
| TT_C_Junction | 1.64 / 1.64 | 1.40 | 1.64 / 1.64 | 1.40 | 1.40 .. 1.56 | 1.64 .. 1.75 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.21 | 1.64 / 1.63 | 1.26 | - .. - | - .. - |
| TT_C_Slope | 1.64 / 1.64 | 1.40 | 1.64 / 1.64 | 1.40 | 1.72 .. 1.81 | 1.68 .. 1.70 |
| &nbsp;&nbsp;before | 1.61 / 1.60 | 1.21 | 1.64 / 1.63 | 1.26 | - .. - | - .. - |
| TT_C_Straight_2 | 1.64 / 1.64 | 1.40 | 1.65 / 1.65 | 1.42 | 1.42 .. 1.54 | 1.65 .. 1.68 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.21 | 1.65 / 1.64 | 1.27 | - .. - | - .. - |
| TT_C_Straight_4 | 1.64 / 1.64 | 1.40 | 1.65 / 1.65 | 1.42 | 1.55 .. 1.62 | 1.69 .. 1.71 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.21 | 1.65 / 1.64 | 1.27 | - .. - | - .. - |
| TT_C_Turn90 | 1.64 / 1.64 | 1.39 | 1.64 / 1.64 | 1.41 | 1.41 .. 1.58 | 1.64 .. 1.70 |
| &nbsp;&nbsp;before | 1.62 / 1.61 | 1.22 | 1.64 / 1.63 | 1.27 | - .. - | - .. - |

### Closedness, materials, light

pieces: 55; open / non-manifold / negative volume: none
pieces with a wood material: none
LOD0 != collider: none
single-piece light test: 40860 rays from the void along the routes, escapes not through an opening: none
max vertical socket error: 0.0000 deg

### Joint tests

231 joint tests (every opening against a copy of itself, every variant combination of a shape, and the plain straight 2 of its size)
min height 0.965, band 0.951, width 1.200 (across +-1 m of the plane); max floor step 0.000; worst ring mismatch 0.00123; sleeve reach [(0.25, 0.25)]; leaks 0 of 92400 rays
walk joints: 171, min height 2.200, band 2.198, width 1.592
largest ring mismatches: [('TT_Room', 'TT_Straight_2', 0.00123), ('TT_Trans_S_C', 'TT_Straight_2', 0.00123), ('TT_Trans_S_P', 'TT_Straight_2', 0.00123)]
tests with a leak: none

### Sockets against the old pieces (position and direction, tolerance 1 mm)

differences: [('TT_C_Junction', 1, [0.0, -3.1, -0.0], [0.0, -2.6, -0.0]), ('TT_C_Junction', 2, [2.6, 0.9, -0.0], [2.6, 0.6, -0.0]), ('TT_C_Junction', 3, [-2.6, -0.8, -0.0], [-2.6, -0.7, -0.0]), ('TT_Junction', 1, [0.0, -3.3, 0.0], [0.0, -2.8, 0.0]), ('TT_Junction', 2, [2.8, 1.0, 0.0], [2.8, 0.6, 0.0]), ('TT_Junction', 3, [-2.8, -0.9, 0.0], [-2.8, -0.7, 0.0]), ('TT_P_Junction', 1, [0.0, -2.8, 0.0], [0.0, -2.4, 0.0]), ('TT_P_Junction', 2, [2.4, 0.75, 0.0], [2.4, 0.5, 0.0]), ('TT_P_Junction', 3, [-2.4, -0.7, 0.0], [-2.4, -0.6, 0.0])]


### Entry_Incline (own check: the stairs defeat the vertical ray)

Route up the stairs; headroom measured square to the 45 degree slope from the line through the step noses (the 25 cm treads stand up to 0.25 m above it), and vertically over the highest tread; width wall to wall above the nose line.

| | Bottom joint: height / width | Stairs: headroom square to the slope (centre / band +-0.3) | Stairs: vertical headroom over the highest tread | Stairs: width min .. max | Head width 1.7 m |
|---|---|---|---|---|---|
| before | 1.98 / 1.14 | 1.86 / 1.80 | 2.93 | 1.45 .. 1.78 | 1.29 |
| after | 2.21 / 1.59 | 1.93 / 1.93 | >= 3.1 (shaft 3.41 high; its roof is above the ground cut along the whole stairs) | 1.67 .. 2.15 | 1.62 |

The square headroom is lower on the first steps because the shaft grows from the ring height over its first 1.2 m (as before); in play the capsule is vertical, so the vertical value counts. Treads are earth now (no timber), the shaft is 1.25 x the ring wide (2.0 m) and 1.55 x high (3.4 m).


## 4. Pieces (55 FBX; names)

- Walk standard (existing names, overwritten): TT_Straight_1, TT_Straight_2, TT_Straight_4, TT_Straight_Narrow, TT_Straight_Wide, TT_Curve_5, TT_Curve_10, TT_Curve_15, TT_Turn90, TT_Turn90_Wide, TT_Dogleg_L, TT_Dogleg_R, TT_Slope, TT_Junction, TT_Room, TT_End, TT_Entry_Horizontal, TT_Entry_Incline (18).
- Walk variants (NEW): `_A` and `_C` of TT_Straight_4, TT_Curve_5, TT_Curve_10, TT_Curve_15, TT_Turn90, TT_Dogleg_L, TT_Dogleg_R, TT_Slope (16).
- Crouch TT_C_* and prone TT_P_* (overwritten, 9 each: Straight_4, Straight_2, Turn90, Dogleg_L, Dogleg_R, Slope, Junction, End, Entry_Horizontal) (18); transitions TT_Trans_S_C, TT_Trans_C_P, TT_Trans_S_P (overwritten) (3).
- Catalog / generator: the new names end in `_A` / `_C` (e.g. `TT_Straight_4_A`, `TT_Dogleg_L_C`); none contains Straight_1 / Straight_2 / Narrow / Wide / `TT_C_` / `TT_P_` / `TT_Trans_` at the start, so the classifier's keyword rules give them the same kind as the standard piece. `Contains("Curve_")` matches the curve variants. `KindWeight` may want `_A` / `_C` weights (main session).

## 5. Import list for the user

1. Start Workbench (project Shashpul), let it scan. The `.xob.meta` files are already patched / written (GUIDs of existing pieces kept, 16 new written from the name).
2. Resource Browser, `Assets/Tunnels/TT`: select **all `TT_*.fbx` of the kit** (not the `TT_Cave_*` / `TT_Room_Drip_*` / `TT_Brk_*`): the **39 existing** ones
   (18 walk standard, 9 + 9 crouch/prone, 3 transitions: the FBX content changed, the `.xob` / `.txo` next to them are stale until this) and the **16 new** ones
   (`TT_Straight_4_A`, `_C`, `TT_Curve_5_A`, `_C`, `TT_Curve_10_A`, `_C`, `TT_Curve_15_A`, `_C`, `TT_Turn90_A`, `_C`, `TT_Dogleg_L_A`, `_C`, `TT_Dogleg_R_A`, `_C`, `TT_Slope_A`, `_C`):
   right-click, Register Resource / Reimport, wait for "Build ok". Check that a `.xob` appeared for each of the 16 new ones.
3. If Workbench ignores the pre-written meta of a new piece (no `.xob`), delete that one `.xob.meta`, register the FBX normally, then run `python Docs/blender/tunnelkit_finish_cp.py`-style patching
   or re-run `python Docs/blender/CL_install.py` (it patches an existing meta: removes the wood assignment, 2 dirt surfaces; it also re-copies the FBX from `Docs/blender/redesign_staging/full`, so only run it if you want to go back to those files).
4. New prefabs (16, already written, copies of the standard sibling with new IDs, dark probe children and `m_bExposureControl 0` kept):
   `Prefabs/Tunnels/TT/TT_Straight_4_A.et`, `_C`, `TT_Curve_5_A/_C`, `TT_Curve_10_A/_C`, `TT_Curve_15_A/_C`, `TT_Turn90_A/_C`, `TT_Dogleg_L_A/_C`, `TT_Dogleg_R_A/_C`, `TT_Slope_A/_C` (+ `.et.meta`). Open one to check that MeshObject resolves.
5. Game > Reload Game Scripts if the classifier / KindWeight was changed, World Editor: generator plugin, **Rebuild TT catalog**, then Verify catalog (every standard piece keeps its sockets; the three junctions have the new socket positions).
6. **Re-snap placed junctions** (TT_Junction, TT_C_Junction, TT_P_Junction): their sockets moved. Placed pieces of all other names keep their sockets.
7. Walk-through before trusting the sizes: a standard straight, an `_A` neck (1.32 wide, no noise), a `_C` bulge, a turn, the staggered junction, the incline stairs (riser 0.25), a transition S to C to P, with player, weapon drawn, crouch and prone.

## 6. Open points / not verified

- In the tables the "Body" columns of Junction and Room are the **doorway** zone (0.5 .. 1.15 m behind a door): the stubs keep the ring, 2.20 x 1.60 by design (the chamber itself is 2.8 / 3.0 m high). Everywhere else the walk body is at least 2.32 high and 1.32 wide (the `_A` necks) / 1.6 (standard).

- Nothing in the engine: import, collider, the capsule fit at 1.6 x 2.2 (the old 1.14 x 1.98 joint blocked), 1.32 neck, slope and stair walkability, light-tightness in the game (computed: sleeves overlap 0.25 m, no ray escapes), appearance of the earth texture on the rounded surfaces, performance of the larger triangle counts (the kit is about 522,902 triangles in total, 4000 - 33000 per piece).
- The existing prefabs of the overwritten pieces keep their dark probe positions (set for the old geometry); the standing walk pieces are 0.1 m wider each side and 0.1 - 1.0 m higher, the junction's probe is at the chamber centre (still inside). Check the probes in the junction and in the wide variants.
- Entry_Incline: pivot and sockets unchanged; the steps are earth now. Headroom: see the incline paragraph above. Its shaft is 2.0 m wide and 3.4 m high (as before, scaled from the new ring).
- Straight_1 and Straight_2 have no variants (the length leaves no room for the ring hold plus the ramp); the 1 m piece is entirely joint zone (its ceiling rises only 12 cm in the middle).
- `_A` has NO noise; `TT_Straight_Narrow` too. The `_C` and standard pieces keep the noise (walk 0.12) on top of the nominal sizes; maximum measured 2.98 m wide and 3.15 m high (limits 3.0 / 3.2).
- Junction doors: the openings no longer overlap in y (gap 0.3 m), but a sight line at a slight angle from deep in one side tunnel to the other is still possible over the 3.2 m of chamber.

## 7. Files

- `Docs/blender/tunnelkit_build_clear.py`, `CL_install.py`, `CL_measure.py`, `CL_report.py`, `CL_preview.py`.
- `Docs/blender/redesign_staging/full/*.fbx` (the 55 built files, identical to `Assets/Tunnels/TT`), `Docs/blender/previews/CL_*.png`, `CL_before_all.json`, `CL_after_full.json`, `CL_before_nonoise.json`.
- Previews (Workbench engine, studio lighting; they do not show the texture): `CL_plan_chain_A_std_C_A.png`, `CL_sections_A_std_C_crouch_prone.png`, `CL_inside_joint_*.png`, `CL_inside_neck_A.png`, `CL_inside_wide_C_into_neck_A.png`,
  `CL_plan_junction_staggered.png`, `CL_plan_junction_crouch_prone.png`, `CL_plan_room.png`, `CL_plan_turn90_C.png`, `CL_plan_turn90_Wide.png`, `CL_plan_dogleg_C.png`, `CL_section_entry_incline.png`, `CL_section_transitions.png`, `CL_inside_entry_horizontal_mouth.png`, `CL_inside_*_straight.png`, `CL_fillet_closeup.png`.

## 8. Walk entries: rounded mouths and graded dark boxes (25 Nov 2026)

All four entries.

- Horizontal entries, all three sizes (`tunnelkit_build_clear.py`, `build_entry_horizontal`, `rock_bumps`): rounded rim (LIP_R), mouth leaning
  back (RAKE_TOP), a bumpy rock mound round the opening about 3 x the piece's height across (MOUND_R, MOUND_UNEVEN). It ends before the joint
  so it can't block the next piece. Incline (`incline_collar`): a rugged rock
  collar about 15 m across round the hole (COLLAR_R, COLLAR_RISE), flat where the stairs come out (+z), shallow behind the hole so it
  clears the tunnel underneath. (`Docs/blender/CL_entry_probes.py` boxes unchanged.) Pivots and sockets unchanged, bounds
  much wider (walk x +-7.5, z -6 .. 8): rebuild the TT catalog. Collider = visual mesh (25 - 36k triangles).
- Dark boxes: `Docs/blender/CL_entry_probes.py` writes three per entry (-5, -10, -16 EV), inside the shell and behind the open part of the
  mouth. `tunnelkit_finish.py` rewrites prefabs without probes: re-run this script after it.
- Not verified in game: the look of the steps between the boxes, and whether the neighbouring piece's 8 m probe (reaches 2 to 3 m back into an
  entry) shows.

## 9. Occluders, trial (26 Nov 2026)

`tunnelkit_build_clear.py` (`fit_occluders`) buries up to 6 box occluders (`OCC_`, no material, like the cliffs') in the earth of the
pieces in `OCCLUDER_PIECES`: Straight_2, Straight_4, Turn90, Turn90_Wide. A box is accepted only if no face touches it with 5 cm
margin and its middle is in solid earth. Visible mesh and openings unchanged. They cover only part of the walls (curved walls take
short boxes). Open: whether the engine's culling in play changes, and that nothing is wrongly hidden. Roll out only after that.

## 10. Earth without sky light (26 Nov 2026, test)

White 'holes' underground were walls lit by the sky where a dark probe did not apply. `TT_Earth.emat` now has DiffuseIBL /
SpecularIBL / Ambient 0 (dug pieces; probes no longer needed for these walls). The four entries use `TT_Earth_Entrance.emat` (the
old material). Cave materials not changed yet. `tunnelkit_finish.py` still writes the old TT_Earth: add the three lines back after
running it. Soldiers and weapons still rely on the probes.
