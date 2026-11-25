# Cave kit: a family of 32 underground assets and the generator rules to use them

Status: concept only, 24 Nov 2026. Nothing here is built. Numbers marked (guess) are my estimates; numbers with a file or measurement named are facts.
Read with: `CaveKit_Handoff.md` (cave generator state), `TunnelKit_CrawlPlan.md` (crouch/prone plan), `TunnelKit_Plan.md` (kit and generator).

## 0. Summary

- 32 assets in 9 groups: 4 big halls (a modular 100 m cathedral plus a lake hall), 5 medium rooms, 2 small chambers, 3 wide crawl chambers, 3 vertical/ledge rooms, 6 passages and squeezes, 3 junctions (one with a loop), 3 dead-end grottos, 3 dug-to-cave transitions. Sizes run from 6 m to about 110 m.
- Every asset has standing (S) sockets in phase A. Crawl stretches sit inside the asset, between funnels ("necks"), so the generator never has to match crawl sizes and the network always returns to standing size. C/P sockets are a later option.
- Every asset passes a measurable traversal test (section 3) run on its collider.
- The generator gets a theme per piece (DUG, CAVE, MIX), a stay/switch table, a passage kind, weighted room choice and a variety-aware score (section 4). Crossing between themes happens only through MIX pieces.
- First wave: 10 assets (section 5). Rough total 225 h, first usable result (stages 0 to 3) about 100 h.

## 1. What the existing code fixes (hard constraints)

| Fact | Source | Consequence |
|---|---|---|
| A socket's direction is one of four axis directions, picked by nearest bounding-box face (`OutwardOf`) | `SP_TunnelCatalog.c` lines 506-543 | Openings in a piece stay axis-aligned and the stub must reach the bbox. Oblique openings need the "fromBone" path that today is skipped for the TT kit (lines 696-705). |
| Sockets get the piece's size (`socket.m_iSize = piece.m_iSize`); TT sockets are role PATH | `AddSockets` | Per-socket size and theme must come from the memory-point names (section 4a). |
| `HandleDoor` and `PickSize` only run for role DOOR sockets, which exist only in the EoH kit | `AddSockets`, `Handle` | For TT, size mix is decided when a piece is picked, not at a door. |
| `m_aCap[3]`, `m_aDoorway[3]`, `m_aMask[3]` are indexed by size; `Mask`, `EndHere`, `JointMask` guard `size > 2` | `SP_TunnelGrower.c` lines 346-348, 767, 2076, 2493 | A new wide size W (index 4) needs these enlarged. |
| `TryRoom` and `TryRoomDirect` pick a room uniformly at random; `RoomChoices` only filters (once per network, no junction at dead ends, found by `Contains("Junction")`) | lines 2130, 2170, 2436 | Needs a weighted pick and a real "may repeat" flag. |
| `IsLarge()` = room whose bbox area exceeds 250 m2; `m_iMaxRooms` 6, room spacing 40 m, 50% room chance | `SP_TunnelCatalog.c` line 79, `SP_TunnelGrower.c` lines 7-16, 966 | Caves want closer rooms (12 m) and a higher room count. |
| `Fits` tests turned bounding boxes plus earth cover from `m_aTops` | `Fits`, `MeasureTops` | An L-shaped or diagonal hall wastes box space; tall pieces (over 8 m) are only placed where the earth is deep enough. |
| The generator never closes loops today. Connect mode has a route search to a pinned entrance (`PlanApproach`, `TryDock`) | `SP_TunnelGrower.c` lines 1454-1776 | Loops can reuse that search (section 4e). I read its signatures, not its internals. |
| Rooms can attach at any yaw already (`Attach` computes yaw freely) | `Attach` | "Entrances at any yaw" is a corridor-piece matter: 5/10/22.5 degree curves and short straights, plus the oblique-socket change above. |

## 2. The catalog

### 2.0 Builder parameters

Existing names used below (v4/v5 and `VARIANTS`): `seed rx ry h depth p wobble slope asym alcoves pockets drops ceil_var up_cap side_cap lopside vault bank swell ico voxel openings pools pool_r pool_depth lip talus relief ribs wall_amp stalactites stalagmites columns pairs straws len_st col_clear col_span len_scale cracks crack_len crack_density crack_depth ledge_amp ledge_step knob_amp knob_r mound_amp mound_r gours gour_R gour_steps gour_h gour_lip hero curtains boulders candles`. Lines below list only keys that differ from variant A's defaults.

New parameters (all in `build_void_low`, `floor_field2`, `plan_specs`, `traverse_check`):

| New key | Meaning |
|---|---|
| `ceil_slope` | Headroom change per metre along +Y, applied to the ceiling only, relative to the floor (`slope` shears both). 0 gives a parallel ceiling; -0.07 closes down 7 cm per metre. |
| `cross_slope` | Floor shear along X (m/m). `cross_ceil=0` leaves the ceiling flat. |
| `zones` | Low-ceiling ("crawl-zone mask"): `(x, y, rx, ry, ceil_h)` ellipses pushing the ceiling to `ceil_h` with a 1.5 m smoothstep. Values of 0.95 give prone, 1.45 crouch or kneel pockets, 1.8 a rest pocket. |
| `routes` | Polylines `(x, y, mode)` between openings with mode W/C/P. They replace the star-shaped `_paths` (`path_dist`), so formations, pools and floor features keep clear of them and `traverse_check` knows what to test. |
| `h_min` | Hard headroom floor on routes (2.0, 1.5 or 0.9). The shell builder lifts ceiling or lowers floor in 5 cm steps until true. |
| `levels` | Floor plateaux `(cx, cy, rx, ry, dz, blend)`; ramps come from the routes. |
| `openings` | Tuples gain `(side, along, size='S', dz=None, neck=2.4)`: size S/C/P/W, floor height override, funnel length. |
| `lean`, `spine`, `pinches` | Wall lean (x += lean*z); a centre-line shift list `(y, x)` for meanders; sideways squeezes `(y, min_width, length)`. |
| `islands` | Rock masses from floor to ceiling `(x, y, rx, ry)`: rings and loops. |
| `boulder_field` | `dict(count, r, region, cone, gap)` for breakdown, with a minimum gap between blocks. |
| `channel` | `dict(width, depth)`: a dry water-cut channel along a route. |
| `dens`, `mud` | Formation density multiplier (scales `stalactites hero pairs` and the v5 fill); share of floor in the Cave_Mud look. |
| `col_gap` | Minimum clear gap between columns on routes. |
| `seg` | `dict(master, i, n, cuts)` for modular halls (section 3.5). |
| `dug_stub` | `dict(len, side, through)` appends a kit-profile dug corridor (timber frames) to an opening, for transitions. |
| `vox`, `budget` | v5 merge voxel (`CAVE_VOXEL`) and triangle budget (`CAVE_BUDGET`) per asset. |

### 2.1 Big halls (4). Large (over 250 m2), joined by W8 seams

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Hall_CathedralHead` | Entry end of the 100 m cathedral, dripstone-rich. 26 x 20 x 9-12 m | Floor rises 1.5 m S to N, flowstone bank on the east wall; domed roof with 7 high pockets and 4 drops | 3: S standing at floor 0; N **W8** seam at +1.5 m; S standing on the west wall (-5 m, +0.3) | walk | Seam must match Mid exactly; probe coverage |
| `TT_Cave_Hall_CathedralMid` | Generic middle module, repeatable, stalactite forest and a breakdown boulder field. 30 x 20 x 7-9 m | Floor keeps the 5% rise; roof lower (7 m), 3 drops over the boulders | 4: S and N **W8** seams, E standing at +2.0 (raised ledge), W standing low | walk | Boulder collider cost |
| `TT_Cave_Hall_CathedralFoot` | End of the chain: flowstone cascade closing the hall. 24 x 18 x 10 m | Floor climbs 3.5 m up a cascade to a high gallery; roof follows the cascade | 3: S **W8** seam; E standing at +3.5 on the gallery; W standing low | walk, ramp up to 20 degrees | Terminal; sealed W8 cap if it is the last |
| `TT_Cave_Hall_Lake` | Basin hall with a dry 16 x 10 basin 2.2 m deep stepped by gour terraces (water is the user's). 30 x 22 x 8 m | Rim walk 3-5 m wide all round; terraces down into the basin; roof lifts over the basin | 4 at different heights: S 0, E +1.2, N +3.0 (ledge), W low | walk | Basin steps need the 30 degree test; dry basin may look odd without water |

```
Head : seed=81, rx=10, ry=13, h=9.5, p=3.0, slope=0.05, asym=0.85, alcoves=12, pockets=7, drops=4, ceil_var=0.35, vault=1.4, bank=0.9, swell=0.4,
       openings=[('S',0.0),('N',0.0,'W'),('W',-5.0,'S',0.3)], stalactites=60, stalagmites=18, columns=6, pairs=10, hero=8, curtains=3, gours=2, boulders=4,
       seg=dict(master=73,i=0,n=4), vox=0.07, budget=300000
Mid  : seed=82, rx=10, ry=15, h=7.5, p=3.2, slope=0.05, asym=0.9, drops=3, openings=[('S',0.0,'W'),('N',0.0,'W'),('E',6.0,'S',2.0),('W',-7.0)],
       stalactites=90, boulders=0, boulder_field=dict(count=30,r=(0.6,1.8),region=(0.1,0.6),gap=1.3), dens=1.3, seg=dict(master=73,i=1,n=4), vox=0.07
Foot : seed=83, rx=9, ry=12, h=10, slope=0.10, bank=1.6, ribs=0.22, gours=3, gour_steps=8, curtains=5, openings=[('S',0.0,'W'),('E',6.0,'S',3.5),('W',-4.0)], vox=0.07
Lake : seed=84, rx=15, ry=11, h=8, p=3.0, pools=1, pool_r=(4.5,7.0), pool_depth=(1.8,2.4), gours=3, gour_R=(2.5,3.5), gour_steps=7, vault=1.0, stalactites=40, dens=0.8,
       routes=[ring along the rim], openings=[('S',0.0),('E',3.0,'S',1.2),('N',-4.0,'S',3.0),('W',2.0)], vox=0.08
```

### 2.2 Medium rooms (5)

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Room_Cathedral` | Existing A: tall dome, fat columns, two rimstone pools. 9 x 8 x 5.4 m | Flat, pool lips; domed | 3 S: S, E, N | walk | Unchanged; budget lower than the 332k of the v5 test |
| `TT_Cave_Room_LowHall` | Existing B: ceiling just above head height, forest of short stalactites and straws. 11 x 9 x 3.9 m | Flat; low ceiling 2.6-3.9 m | 3 S: W, E, N | walk, a few ducking spots under clusters | Dense formations near routes |
| `TT_Cave_Room_Terraces` | Existing C: five gour terraces stepping across the floor. 10 x 8.4 x 4.4 m | Floor steps down about 0.8 m across the room | 3 S: S, N, W | walk | Terrace steps vs the 0.35 step rule |
| `TT_Cave_Room_Curtains` | Existing D: narrow tall chimney, flowstone ribbing. 7 x 6.4 x 7.6 m | Flat; roof chimney | 2 S: S, E | walk | Curtains still look crumpled (handoff) |
| `TT_Cave_Room_Pillars` | Forest of 16 columns under a low roof, a slalom route. 13 x 12 x 3.6 m | Floor rises 3% toward N; roof slopes with it | 3 S, staggered: S, E, N | walk | Column gaps become traps; `col_gap` and collision |

```
Pillars: seed=85, rx=6.5, ry=6.0, h=3.6, p=3.5, slope=0.03, columns=16, col_span=3.8, col_clear=1.2, col_gap=1.3, pairs=8, stalactites=8, hero=2, gours=0,
         openings=[('S',-1.5),('E',2.0),('N',1.0)], vox=0.05
```
A to D keep their `VARIANTS` entries and gain `routes=` so the test applies.

### 2.3 Small chambers (2)

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Chamber_Bubble` | Phreatic bubble: near-spherical, smooth walls, almost bare. 7 x 6 x 3.4 m | Floor bowl 0.3 m; ceiling a smooth dome | 2 S on adjacent walls (S +0.8, E -0.6) | walk | Looks like a plain sphere unless the knobs and cracks read well |
| `TT_Cave_Chamber_Cleft` | Wall cleft you move through sideways, leaning walls. 3 x 10 x 6 m | Rubble floor rising 12 degrees S to N; ceiling a slot | 3 S: S at 0, N at +1.2, one high side hole | walk, sideways | Width 1.3 m at pinch is close to the S limit |

```
Bubble: seed=86, rx=3.5, ry=3.0, h=3.4, p=2.0, wobble=0.05, ribs=0, knob_r=0.25, knob_amp=0.05, stalactites=0, hero=1, cracks=1, openings=[('S',0.8),('E',-0.6)], vox=0.035
Cleft : seed=87, rx=1.6, ry=5.0, h=6, p=4.0, lean=0.25, slope=0.12, ceil_slope=-0.10, pockets=4, pinches=[(-1.0,1.3,1.5)], stalactites=3, ribs=0.12,
        openings=[('S',0.0),('N',0.0,'S',1.2)], vox=0.035
```

### 2.4 Wide crawl chambers (3). Entered from standing sockets through a neck

All three: S sockets with `neck=4.5`, so the ceiling descends from 2.1 m to the crawl height in at most 0.3 m per metre. Stalactites only where the ceiling is above 1.3 m and never over a route.

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Crawl_Slab` | Prone-only flat chamber wider than one person (the 7b test chamber). 9 x 6 x 0.95-1.7 m | Floor rises 4 degrees to N, ceiling closes down relative to it; one 1.5 m kneel pocket | 2 S: S wall -0.6, E wall +1.2, each with its neck | prone 6-8 m, kneel pocket | Looks like a lowered box if the shapes are too tame; capsule height unknown |
| `TT_Cave_Crawl_Saddle` | A low band cuts diagonally across a normal-height room; it is 0.95 m at the west end, 1.45 m at the east. 14 x 8 x 0.95-2.6 m | Roof dips into a saddle; floor slopes 3% | 2 S at the tall ends (S -3.0, N +2.5) | walk, then prone through the west or crouch through the east (two routes) | Players need to see both options; both must pass |
| `TT_Cave_Crawl_Rubble` | Breakdown crawl: jammed blocks under a sagging slab, two winding routes. 9 x 8 x 1.3-1.9 m | Floor tilts 5% cross-slope; roof slab sags toward one corner | 2 S: W 0.0, E -1.0 | crouch with two prone spots, an in-piece loop | Collider tris of blocks; gaps between 0.35 and 0.9 m must be filled |

```
Slab  : seed=91, rx=4.5, ry=3.2, h=1.7, p=3.2, wobble=0.05, slope=0.07, ceil_slope=-0.07, cross_slope=0.03, zones=[(-1.5,1.0,2.4,1.8,0.95),(2.3,-1.0,1.3,1.1,1.5)],
        stalactites=0, hero=0, columns=0, straws=6, boulders=2, bank=0.35, swell=0.15, relief=0.04, gours=0, mud=0.6, h_min=0.9,
        openings=[('S',-0.6,'S',0,4.5),('E',1.2,'S',0,4.5)], routes=[S->(-1.5,1.0,'P')->E], vox=0.03, budget=140000
Saddle: seed=92, rx=7, ry=4, h=2.6, p=4.0, slope=0.03, zones=[(0,0,7.0,2.2,0.95),(3.5,0,2.5,2.0,1.45)], ceil_var=0.2, asym=0.8, h_min=0.9, openings=[('S',-3.0,'S',0,4.5),('N',2.5,'S',0,4.5)], vox=0.04
Rubble: seed=93, rx=4.5, ry=4.0, h=1.8, p=3.0, slope=0.04, cross_slope=-0.05, ceil_slope=-0.03, boulders=0,
        boulder_field=dict(count=20,r=(0.35,0.9),region=(0.1,0.85),gap=1.3), zones=[(1.5,-1.0,1.6,1.4,0.95)], straws=3, hero=0, h_min=0.9, vox=0.035
```

### 2.5 Vertical and ledge rooms (3)

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Ledge_Rift` | Tall rift with a high gallery on the east wall. 40 x 7 x 12 m, walls leaning 12 degrees | Rubble talus floor rising 3.5%; gallery floor at +5.5 m, joined to the floor by a 25 degree rubble ramp mid-way | 3 S: S low 0, N low +2.4, E on the gallery +5.5 | walk, two routes (low, high) | Needs about 14 m of earth; a drop from the gallery edge |
| `TT_Cave_Ledge_Collapse` | Collapse chamber: floor is a cone of boulders rising 5.5 m under a breakdown dome, bare rock. 26 x 20 x 10 m | Cone toward the ceiling (3 m headroom at the crest); outer ring flat | 4 S: S low, N low, W low, E at the crest +4.5 | walk; switchbacks up the cone | Steep rubble; gaps between blocks |
| `TT_Cave_Ledge_Cascade` | Giant flowstone cascade pouring 4.5 m down one wall into gour steps. 14 x 12 x 6 m | Cross slope about 17 degrees on the cascade, gour terraces at the foot; roof follows | 3 S: upper gallery N at +4.5, S low, E at +1.2 on the gour steps | walk, steps and a ramp | Slippery-looking slope must stay under 30 degrees |

```
Rift    : seed=94, rx=3.5, ry=20, h=12, p=4.5, lean=0.22, wobble=0.10, slope=0.035, ribs=0.22, stalactites=18, columns=0, boulders=10, bank=0.6,
          levels=[(3.0,0,1.8,20,5.5,2.5)], openings=[('S',0.0),('N',0.0,'S',2.4),('E',-12.0,'S',5.5)], vox=0.07, budget=280000
Collapse: seed=95, rx=10, ry=13, h=10, p=2.6, pockets=8, drops=2, boulders=0, boulder_field=dict(count=70,r=(0.5,2.2),region=(0.0,0.55),cone=5.5,gap=1.0), dens=0.3,
          openings=[('S',0.0),('N',2.0),('W',-3.0),('E',1.0,'S',4.5)], h_min=2.0, vox=0.07
Cascade : seed=96, rx=6.5, ry=7, h=6, cross_slope=-0.30, bank=1.6, gours=3, gour_R=(1.8,2.6), gour_steps=8, gour_h=0.20, ribs=0.20, curtains=4,
          openings=[('N',-2.0,'S',4.5),('S',1.0),('E',0.5,'S',1.2)], vox=0.045
```

### 2.6 Passages and connectors (6). All S at both ends, kind PASSAGE

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Pass_Meander` | The standard cave connector: a 2-3.5 m wide standing passage with two bends. 18 x 3 x 2.6-3.4 m | Floor rises 1.1 m end to end; roof varies with ceiling pockets | 2 S, S and N, in line on the axis (the bends cancel) | walk | Long line of sight if the bends are too soft |
| `TT_Cave_Pass_SqueezeC` | Short crouch squeeze with standing ends. 8 x 2.6 m | Flat; roof drops to 1.5 m for 3 m | 2 S | walk, 3 m crouch | Needs to read as natural, not as a lowered corridor |
| `TT_Cave_Pass_SqueezeP` | Prone squeeze with a jog so there is no line of sight. 12 x 2.6 m | Floor of dry mud, roof 0.92 m for 3 m | 2 S | walk, 3 m prone | Smallest margins in the kit |
| `TT_Cave_Pass_GalleryCrawl` | Long wide crawl gallery with rest pockets. 26 x 3-5.5 x 0.95-1.8 m | Roof ripples: prone stretches (0.95), crouch stretches (1.4), three 1.8 m rest pockets at about 8 m spacing | 2 S, each with a 4 m neck | crawl about 18 m (guess: tiring) | Longest prone stretch is a tuning item |
| `TT_Cave_Pass_Flooded` | Low wide passage with a dry water-cut channel. 14 x 4 x 1.85-2.4 m | Channel 0.55 m deep between two 1.3 m ledges; flat roof | 2 S | crouch on a ledge or walk in the channel | Reads wrong without water |
| `TT_Cave_Pass_Crack` | Crack passage, tall and leaning, sideways squeeze in the middle. 16 x 1.5 x 6 m | Floor rises 6 degrees; walls lean 19 degrees | 2 S | walk, sideways | Width 1.25 m at the pinch |

```
Meander: seed=101, rx=1.9, ry=9.5, h=3.1, p=3.5, spine=[(-9,0),(-3,0),(0,2.4),(4,-1.8),(9,0)], slope=0.06, ceil_var=0.3, asym=0.8, stalactites=3, straws=10, hero=0, openings=[('S',0.0),('N',0.0)], vox=0.04
SqueezeC: seed=102, rx=1.3, ry=4.0, h=2.1, p=4.0, zones=[(0,0,1.3,2.2,1.5)], h_min=1.5, openings=[('S',0.0),('N',0.0)], vox=0.03
SqueezeP: seed=103, rx=1.3, ry=6.0, h=1.8, p=4.0, spine=[(-6,0),(-1.5,0),(0,0.9),(1.5,0),(6,0)], zones=[(0,0,1.6,3.0,0.92)], ceil_slope=-0.10, mud=0.8, h_min=0.9, vox=0.03
Gallery : seed=104, rx=2.5, ry=13, h=1.5, p=4.0, lopside=0.2, slope=0.03, cross_slope=0.04, h_min=0.9,
          zones=[(0,-8,2.2,2.2,0.95),(0,-1,2.4,2.2,1.4),(1,6,2.2,2.5,0.95),(-0.8,-4.5,1.8,1.5,1.8),(0.8,2.5,1.8,1.5,1.8),(0,9.5,1.8,1.5,1.8)],
          openings=[('S',0.0,'S',0,4.0),('N',0.0,'S',0,4.0)], vox=0.04
Flooded : seed=105, rx=2.0, ry=7, h=1.9, p=4.0, channel=dict(width=2.2,depth=0.55), ribs=0.05, straws=6, openings=[('S',0.0),('N',0.0)], vox=0.04
Crack   : seed=106, rx=0.75, ry=8, h=6, p=5.0, lean=0.35, wobble=0.10, ribs=0.12, spine=[(-8,0),(-2,0.6),(3,-0.5),(8,0)], slope=0.10, pockets=4, pinches=[(-1.0,1.25,1.2)], vox=0.04
```

### 2.7 Junction caves (3), 3 to 5 openings

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Jct_Tri` | Asymmetric three-way chamber over breakdown. 12 x 10 x 3.4 m | West half 1.2 m lower, stepped; one roof drop | 3 S: S +0.5, E -1.0, W at +1.2 | walk | None in particular |
| `TT_Cave_Jct_Island` | A rock island in the middle makes a ring: wide walk round one side, low crouch route round the other. 14 x 12 x 4 m | Floor flat; roof drops to 1.1 m beside the island on the low side | 4 S, one per wall | walk, crouch on the short way (a loop inside the piece) | Island must not block sight lines everywhere |
| `TT_Cave_Jct_Star` | Five-way hub on two levels. 16 x 16 x 5 m | Sunk 1 m basin in the middle with a ramp ring; one crawl approach (5 m neck) | 5: S, N, E (-3.0), E high (+2.4), W via crawl neck | walk, one crouch approach | Collider size; too many entrances to read |

```
Tri   : seed=111, rx=6, ry=5, h=3.4, p=3.0, levels=[(-3,0,3,5,-1.2,1.5)], drops=3, boulders=3, openings=[('S',0.5),('E',-1.0),('W',2.0,'S',1.2)], vox=0.045
Island: seed=112, rx=7, ry=6, h=4, p=3.2, islands=[(0.5,0,2.6,2.0)], zones=[(-2.8,0,1.2,3.0,1.1)], h_min=1.5, openings=[('S',0),('N',0),('E',0),('W',0)], vox=0.05
Star  : seed=113, rx=8, ry=8, h=5, p=2.8, levels=[(0,0,4,4,-1.0,2.0)], zones=[(-6.5,0,2.0,1.6,1.4)],
        openings=[('S',-1.5),('N',2.0),('E',-3.0),('E',4.0,'S',2.4),('W',0.0,'S',0,5.0)], vox=0.06
```

### 2.8 Dead-end grottos (3), one opening

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Cave_Grotto_Jewel` | Tiny, very dense: straws, candles, a mini gour. 6 x 5 x 2.8 m | Flat, bowl in the middle | 1 S | walk | Triangle cost per metre is the highest in the kit |
| `TT_Cave_Grotto_Sump` | Dry basin ending at a sealed low arch where water would be. 9 x 7 x 3.5 m | Basin 1 m deep with gour steps; roof drops to 0.3 m at the far edge (sealed, no gap) | 1 S | walk | Sealed arch must not read as a gap |
| `TT_Cave_Grotto_Crawl` | Secret nook at the end of a 6 m prone neck. 6 x 4 x 1.2 m | Flat; roof 1.15 m | 1 S, neck 5 m | prone | Dead end in prone: the only way out is back |

```
Jewel: seed=121, rx=3, ry=2.5, h=2.8, p=2.6, dens=3.0, straws=40, candles=10, pairs=12, gours=1, gour_R=(1.0,1.3), ribs=0.10, openings=[('S',0.0)], vox=0.03
Sump : seed=122, rx=4.5, ry=3.5, h=3.5, pools=1, pool_r=(2.4,3.0), pool_depth=(0.9,1.2), zones=[(0,-3.2,1.5,0.8,0.3)], gours=2, openings=[('S',0.0)], vox=0.035
Crawl: seed=123, rx=3, ry=2, h=1.3, p=3.0, zones=[(0,0,2.4,1.6,1.15)], straws=4, hero=0, h_min=0.9, openings=[('S',0.0,'S',0,5.0)], vox=0.03
```

### 2.9 Transitions between dug and cave (3), kind ROOM or PASSAGE, theme MIX

Each has one dug socket (`d`) and one or more cave sockets (`c`). The first 4 to 6 m on the dug side are the real kit profile with earth, timber frames and the kit's sleeves; the cave side uses rock frames.

| Name | Character, size | Floor / ceiling | Openings | Mode | Risk |
|---|---|---|---|---|---|
| `TT_Brk_Breakthrough` | A dug tunnel breaks into a cave: 6 m of timbered tunnel, then the wall is gone and a 8 x 6 m chamber follows. 16 x 6 x 2.6-3 m | Floor continues, then a 0.6 m rubble drop; ragged edge where earth meets rock | 2 S: dug at 0, cave at the far end | walk | Two meshes merged: the dug shell must close against the cave shell |
| `TT_Brk_Hole` | The squeeze version: a dug stub, a ragged hole climbed over rubble steps, a crouch squeeze, then cave passage. 12 x 5 m | Three rubble steps of 0.27 m, then crouch roof 1.45 m for 3 m | 2 S: dug, cave | walk, 3 m crouch | Step height vs the crouch step limit |
| `TT_Brk_Cutting` | A dug straight with a cave pocket opening off its east wall; the tunnel carries on. 10 x 8 x 3 m | Dug floor flat; cave floor 0.3 m lower | 3 S: dug S, dug N (in line), cave E | walk | Gives the generator a side door into the cave theme |

```
Breakthrough: seed=131, rx=3, ry=3, h=3.0, openings=[('N',0.0)], dug_stub=dict(len=6,side='S'), levels=[(0,2.5,2.5,2.5,-0.6,1.0)], vox=0.035
Hole        : seed=132, rx=1.8, ry=3.5, h=2.2, zones=[(0,3.0,1.2,2.0,1.45)], dug_stub=dict(len=4,side='S'), levels=[(0,-1.0,1.2,1.0,0.8,0.3)], openings=[('N',0.0)], vox=0.035
Cutting     : seed=133, rx=3, ry=3, h=3.0, openings=[('E',0.0)], dug_stub=dict(len=10,side='S',through=True), vox=0.035
```

## 3. Rules shared by all assets

### 3.1 The traversal guarantee (measurable)

The model is `_walk_final.py` (scratchpad `caves/`). It flood-fills a 0.5 m grid with headroom 2.0, floor slope 40 degrees and step 0.35. It has four gaps that the new check must close:
1. one movement mode only;
2. no corridor width (0.5 m cells cannot test 1.2 m);
3. it keeps only the highest floor per cell, so the floor under a ledge is lost (rifts, cascades, collapse cones);
4. it hard-codes `slope_plane = 0.05` and runs on the visual LOD0, not the collider.

New `cave_walkcheck.py`: cell 0.25 m, a stack of floor layers per cell (every upward face with at least 0.9 m headroom), erosion by half the route width, and the collider (UTM) as the surface.

| | Walk | Crouch | Prone |
|---|---|---|---|
| Headroom on a route (collider) | at least 2.0 (design 2.2) | at least 1.50 (EoH C opening 1.571) | at least 0.90 (EoH P opening 0.899; absolute floor 0.85) |
| Route width (free disc diameter) | at least 1.2 (EoH S 1.21) | at least 1.3 (EoH C 1.295) | at least 1.3 (EoH P 1.295) |
| Comfortable width (design target) | 1.6 | 1.8 | 1.8 |
| Floor slope on a route | 30 degrees (cells up to 40 as in the model) | 25 (guess) | 15 (CrawlPlan: about 20 may fail in the engine) |
| Step | 0.35 (model) | 0.25 (guess) | 0.15 (guess) |
| Roof descent into a lower mode | n/a | 0.35 m/m | 0.35 m/m |

Mode of a cell: W if headroom is 2.0 or more, C if 1.5 or more, P if 0.9 or more, otherwise blocked. Capsule heights are not known (CrawlPlan section 6): confirm in play mode before trusting the C and P numbers.

Pass criteria for every asset, per `routes`:
1. Every pair of openings is connected, using only cells of the route's declared mode or higher.
2. Route length is at most 2.2 times the straight distance.
3. The crawl metres (cells of mode C or P on the shortest route) are within 20% of the value in the catalog.
4. No false-hope gaps: a floor region with headroom between 0.35 and 0.9 m is not allowed. It becomes rock (floor raised) or at least 0.9 m.
5. A prone stretch has a rest pocket (free disc radius 0.9 at headroom 1.4 or more) at least every 8 m.
6. No wedge: no dead-end gap narrower than 1.2 m and longer than 1 m, off the route.

On failure the builder reseeds (up to 12 tries) and then relaxes `zones` by 5 cm per try. Checks run before export; the numbers go into the stats JSON with `opening_profile_points_found` (which must stay 11/11 per opening).

### 3.2 Opening profiles and joints

- Standing: the kit's exact `INNER` (11 points, 1.4 x 2.1 m, from `tunnelkit_build.py` lines 24-25). Shell 0.6, sleeve 0.25 reach, `SLEEVE_IN` 0.1, `SLEEVE_T` 0.3, frame 12 cm deep and 15 cm long. Both ends identical.
- Crawl: `INNER_C` (1.30 x 1.57) and `INNER_P` (1.30 x 0.90) from CrawlPlan section 3, same 11-point topology, thinner frames. Used only in later C/P sockets.
- Wide: `INNER_W8`, 8 m wide, 2.2 m walls, 4.5 m crown (same topology, guess), for hall seams only.
- Cave pieces keep the frame geometry but with a limestone material instead of wood. Dug pieces keep their timber. A dug-to-cave joint therefore shows timber on one side and rock on the other, which reads as intended.
- Neck: the cave must not narrow below the route width within `neck` metres of any opening (default 2.4 m). The existing fade (`FADE_START` 0.4, `FADE_END` 1.4) is too short for a wide room meeting a 1.4 m door.
- Catalog contract: sockets axis-aligned, stub reaching the bbox, memory points `1`, `2`, ... named with suffixes (section 4a).

### 3.3 Light, material, culling (decided 23 Nov)

- Vanilla interior approach: a house probe child at -16, sized to the room, one per piece; segments of a hall get one probe each. Passages get one. The cave probe is -16 like the dug kit's `TT_TunnelProbe*.et`, so brightness is continuous across a border.
- One `MatPBRMulti` material with the `MaskMap` (second UV set), layers as in the handoff plan; `Cave_Limestone`, `Cave_Dripstone` and `Cave_Mud` still need importing. Mask 2k for rooms, 1k for passages and grottos.
- No exposure script: `m_bExposureControl` off, `m_bKeepRendered` on (`EntityFlags.FEATURE`, the no-cull flag).
- Every piece must be completely below the terrain with closed openings, or daylight leaks in.
- Sight line risk (test, not assumed): the 20 m underground sight rule from `TunnelKit_Plan.md` conflicts with a 100 m hall; the no-cull flag should let the far end render. Check lighting and rendering at the far end of the cathedral chain.

### 3.4 Triangle, collider and build limits

Fit from the v5 test (room A, about 200-220 m2 of shell, voxel 0.025, 332k triangles): triangles are about **1.1 x shell area / voxel^2**. That is about 1750 per m2 at 0.025 and 450 per m2 at 0.05.

| Size class | Voxel | LOD0 cap | Collider cap |
|---|---|---|---|
| Grotto, small, crawl, squeeze | 0.03 - 0.035 | 70 - 150k | 6 - 8k |
| Medium room, passage, junction | 0.035 - 0.05 | 110 - 220k | 7 - 25k |
| Hall segment, rift, collapse | 0.07 - 0.08 | at most 300k | at most 40k |

- Collider: formations flagged `collide=0` are dropped; at least 25 triangles per m2 of walkable floor (guess); the walk check runs on it.
- Build limit: shell area / voxel^2 at most 2.5M cells. The 100 m hall was about 9.6M cells (12 GB, 8 minutes, 864k triangles with 3800 formations); linear extrapolation gives about 3 GB and 2 minutes at 2.5M (guess). At most 12 hero and 150 fill formations per segment (5 per metre instead of 38).
- LOD chain: `_LOD0`, `_LOD1` (about 25%: voxel doubled, no formations under 0.3 m, no straws), `_LOD2` (about 5%: shell hull). Distances 0-30, 30-70, over 70 m (guess; tune on the cathedral).
- Memory: 32 masks at 2k are about 90 MB; many pieces use 1k.

### 3.5 Splitting big halls (the cathedral)

1. Build one low-resolution master void for the whole 100 m (voxel 0.3 as in variant E), with a pinch forced at each cut: 8 m wide, 4.5 m high, 5 m long, exactly `INNER_W8`.
2. Each segment is its own Blender run on the slab between cuts, with its own origin at its first opening (kit convention). Formations are planned globally with the master seed, assigned by y, none within 6 m of a cut.
3. The first and last 3 m of a Mid are the W8 profile exactly, with the same section, so any Mid can follow a Head or another Mid. Interiors differ per Mid variant (more Mids later).
4. A chain is Head, 1 to 3 Mids, Foot. About 100 m with two Mids. `TT_Cave_Cap_W` seals an unfinished seam.
5. The seam joints use the normal sleeve logic; the collider seam is checked by walking the seam in the test.

## 4. The generator concept

### 4a. Themes (derived, plus a small table)

- Theme from the name: `TT_Cave_*` is CAVE, `TT_Brk_*` is MIX, every other `TT_*` and the EoH kit is DUG. Kind from the token after the theme (`Hall`, `Room`, `Chamber`, `Crawl`, `Ledge`, `Pass`, `Jct`, `Grotto`, `Cap`), not from `Contains(...)`: today's `ClassifyTT` would read `Bend` or `Slope` inside new names as a kind.
- Per socket: memory-point name `<n>[S|C|P|W][d|c]`, for example `1Sd`, `2Sc`, `3W`. No suffix: size S and the piece's theme. A MIX piece's sockets carry their own theme; a joint requires equal size and equal theme.
- A small sidecar table (written by the finish script, read by `SP_TunnelCatalog.Build`): `name crawl=18 repeat=1 dz=1.5 weight=1.0`. Defaults when absent. New fields on `SP_TunnelPieceDef`: `m_iTheme, m_fCrawlLen, m_bRepeat, m_fDz, m_fWeight`; on `SP_TunnelSocketDef`: `m_iTheme`. New kind `PASSAGE` (a corridor-pool piece). New size `W`. Save and load of the catalog file need a version field.

### 4b. Connection affinity (defaults, guesses to tune)

Probability that an opening in a theme is continued by a piece of a theme. A piece may only join an open socket of the same theme, so cave to dug directly is impossible by construction:

| Opening is in | CAVE piece | DUG piece | MIX piece |
|---|---|---|---|
| CAVE | 0.88 | 0 | 0.12 |
| DUG | 0 | 0.90 | 0.10 |
| MIX, cave side | 1.0 | 0 | 0 |
| MIX, dug side | 0 | 1.0 | 0 |

- Your example numbers (cave 0.8, dug 0.7) are lower than mine because a crossing also needs a free MIX piece to fit. The two stay-values are settings (`caveStay`, `dugStay`); transition share is `1 - stay`.
- The MIX probability is multiplied by a ramp: 0 until the branch has run `minRun` in the theme (dug 30 m, cave 45 m), then rising to 1 over 20 m, and by a share factor `clamp(1 + 2*(wanted - actual), 0.2, 3)` using `caveShare` against the actual cave length share. A network is capped at `maxCrossings` (default 3).
- Inside CAVE, kind weights (relative): passage 1.0 (crawl passages x `crawlShare` 0.15), small/medium room 0.6, junction 0.35, hall chain 0.2 (once per network), vertical 0.3. Cave rooms are meant to be closely linked: room spacing 12 m (dug stays 40), side-branch chance 0.75 (dug 0.5), room chance 0.8.
- At theme borders: after a MIX piece, a minimum of 12 m in the new theme (no second crossing, no end, no entrance). If no MIX fits, the branch simply stays in its theme; nothing is counted as an end. Ends are theme-specific: DUG ends with `TT_End`; CAVE tries a Grotto (1-opening room) at weight x3, then `TT_Cave_Cap_S` (a rubble plug). Entrances (`TT_Entry_*`) are DUG only; a sinkhole cave entrance is a later piece.

### 4c. Where it plugs into the code

| Function | Change |
|---|---|
| `SP_TunnelOpen`, `SP_TunnelBranch` | Add `m_iTheme`; branch gets `m_iTheme, m_fThemeRun, m_iCrossings, m_fCrawlRun`. `OpenSockets`, `PlaceCorridor`, `RoomDoors` copy the theme like they copy the size. |
| `KindWeight` | Add `PASSAGE`; multiply the result by `ThemeFactor(piece, open, branch)` (the table above) at its single call in `TryCorridor` (line 1907). |
| `TryCorridor` | Socket test becomes size AND theme; passage crawl rules (below); `BreaksSight(PASSAGE)` true. |
| `RoomChoices`, `TryRoom`, `TryRoomDirect` | Return weighted choices: theme factor x variety factor (an already placed asset x0.1, a repeatable one x0.5) x piece weight. `PickRoom(...)` replaces the uniform `RandInt` at lines 2130 and 2170; `m_bRepeat` replaces the `Contains("Junction")` hack. |
| `RoomDoors`, `SideGrows` | Cave pieces use the cave branch chance; carry-on door preference prefers same-theme doors. |
| `HandleDoor`, `PickSize` | No change for TT (not reached). `PickSize` is reused as `PickMode` when choosing between walk, crouch and prone passages. |
| `EndHere` | Theme-specific caps and the Grotto preference; `m_aCap[3]` becomes a table by theme and size (W included). |
| `Score` | Variety and theme terms (4f). |
| `SP_TunnelGenSettings` (`Write`, `Read`, plugin UI) | New settings below; every key in all three places. |

New settings (default): `caveShare` 0.5, `caveStay` 0.88, `dugStay` 0.90, `minRunDug` 30, `minRunCave` 45, `maxCrossings` 3, `caveBranch` 0.75, `caveRoomSpacing` 12, `passageWeight` 2.0, `crawlShare` 0.15, `maxCrawlRun` 25, `crawlGate` 0.10, `loops` 1, `loopReach` 35, `maxRooms` 6 to 10 (a hall chain counts once), `candidates` 8 to 16.

### 4d. Crawl-only areas

- Phase A needs no size logic: every passage and chamber is S-ended with the crawl inside (catalog value `crawl=` metres).
- Crawl rules: no two crawl pieces in a row; `m_fCrawlRun` (crawl metres since the last 30 m without crawl) at most `maxCrawlRun` 25 m; the main route may use only crawl of at most 6 m (squeezes); crawl share by `crawlShare`.
- Shortcuts and secrets: with `crawlGate` probability, the first piece of a side branch is a crawl passage, so the area behind is only reachable by crawling. The main way never depends on prone only.
- Later (phase B, C/P sockets): composite units `[reducer, 2-6 crawl pieces, reducer]` as in CrawlPlan, placed as one all-or-nothing attempt.

### 4e. Loops that remerge

1. In-piece loops (no generator work): Jct_Island, Crawl_Rubble, Ledge_Rift (low and high route), Hall_Lake (rim both ways), Crawl_Saddle (prone or crouch).
2. Graph loops: when a branch ends in `EndHere` and a free (unhandled) opening of another branch lies within `loopReach` 35 m horizontally and 3 m vertically, and at least 40 m of network away, try to close it with the connect-mode search, the free opening acting as a pin with zero tolerance. Prefer crawl passages (x4). The search needs fine pieces to hit an exact pose: 5/10/22.5 degree curves, 1 and 2 m straights, and passages with lateral offsets of 0.5 to 4 m. Success rate is unknown; I would expect it to be low until those pieces exist, so measure attempts and successes in the layout summary. Fallback on failure: the end is capped as today.

### 4f. What a network should look like, and how scoring rewards it

```
Entry (dug) -> dug run 30-60 m, one dug room -> Breakthrough/Cutting/Hole -> cave:
  Meander -> Room (Cathedral) -> Pass -> Jct_Island (loop) -> hall chain (Head,Mid,Foot)
     |            |                         \-> Grotto at end
     |            \-> Jct_Tri -> Crawl_Slab -> Room_LowHall
     \-> crawl gate: Squeeze_P -> Grotto_Crawl (secret)
  then optionally Cutting -> dug run -> second entrance
```

Best-of-N (`Score`, lower is better) gets these new terms (weights are guesses):
- +12 for each repeat of a non-repeatable asset; -2 per distinct cave asset up to 12;
- +40 x |actual cave share - `caveShare`|; +25 per crossing outside 1 to `maxCrossings`;
- +8 per theme run shorter than `minRun` (flip-flopping); +6 if the same asset appears twice within 3 hops;
- +15 if the cave part has no room of 14 m or more while `caveShare` is above 0.3; +10 if `crawlShare` is above 0 and there is no crawl link;
- +12 for each loop short of `loops`.
`candidates` should go up to 16 because each candidate costs nothing in the world.

## 5. Build order

First wave (10 assets, highest variety per effort): Room_Cathedral, Room_LowHall, Room_Terraces, Room_Curtains (all four exist; they only need v5 plus export), Crawl_Slab (the user's 7b test), Pass_SqueezeP (CrawlPlan phase A), Pass_Meander (the everyday connector), Brk_Breakthrough (tests the theme logic), Grotto_Jewel (cheap, tests cave dead ends), Jct_Island (loop and crouch).

| Stage | Content | Needs | Hours (guess) | Test in Workbench |
|---|---|---|---|---|
| 0 Foundations | `INNER_C/P/W8` profiles; rock frame material; `cave_walkcheck.py`; bone-suffix convention; cave export pipeline (mask UV2, MatPBRMulti, probe, prefab, `cave_finish.py`) | Blender kit work | 24 | Import one room, check lighting at noon with the opening closed; walk it |
| 1 Builder params | `ceil_slope cross_slope zones routes h_min levels openings neck spine lean islands boulder_field` and the check hooked into `assemble2` | `cave_dripstone_room.py`, v4 | 16 | Build Slab, check the stats JSON, walk the prone route |
| 2 Wave 1 assets | 10 assets above; B, C, D through v5 | Stage 0 and 1 | 36 | Place by hand, walk each, check every opening joins a TT_Straight |
| 3 Generator themes | Catalog theme, bone suffix, token classification, `PASSAGE` kind, weighted pick, caps, settings, `Score`, oblique-socket option | `SP_TunnelCatalog.c`, `SP_TunnelGrower.c`, plugin | 24 | Rebuild catalog, Verify catalog, generate 10 seeds from an entry: theme table in the summary, no direct dug-cave joint |
| 4 Wave 2 | Saddle, Rubble, Gallery_Crawl, SqueezeC, Crack, Flooded, Cleft, Bubble, Jct_Tri, Jct_Star, Grotto_Sump, Grotto_Crawl, Brk_Hole, Brk_Cutting | Stage 3 | 50 | Generate with `caveShare` 0.7: variety count, crawl metres per route |
| 5 Halls | W8 joint, segmentation, Head, Mid, Foot, Lake, size W in the generator | Stage 3 | 40 | Walk the chain end to end, look at the seam, far-end render |
| 6 Vertical | Rift, Collapse, Cascade; deep-cover handling | Stage 5 | 21 | Terrain depth check; walk the high and low routes |
| 7 Loops and gates | Loop closing, crawl gates, 5/10/22.5 degree curves | Stage 3 | 14 | Count loops and gates in 20 seeds |

Total about 225 h; stages 0 to 3 (the first usable network) about 100 h.

## 6. Open questions

1. Must AI or heavy kit pass? If yes, crawl is only ever a side branch; if no, short squeezes (6 m or less) may sit on the main route.
2. Are 8 m wide hall seams acceptable (a new joint profile), or must every joint be the 1.4 m door? Without W8 the largest single piece is about 30 m.
3. How long may a prone stretch be before it stops being fun: 8 m, 18 m, 25 m? I assumed 25 m of crawl per route, 18 m in the gallery.
4. Should a network be able to start in a cave (a sinkhole or cave-mouth entrance piece), or always from a dug entrance?
5. Does the engine's crouch and prone capsule pass 1.5 m and 0.9 m? EoH's 1.571 and 0.899 are my only evidence.

## Appendix: all assets

Size class: XS under 8 m, S 8-14, M 14-20, L 20-35, XL 35 m or more. Triangles are the LOD0 cap from the voxel formula (estimates); colliders as in 3.4.

| # | Name | Theme | Size | Mode | Openings | LOD0 tris | Collider |
|---|---|---|---|---|---|---|---|
| 1 | `TT_Cave_Hall_CathedralHead` | CAVE | L | walk | 3 (S, W8, S) | 300k | 40k |
| 2 | `TT_Cave_Hall_CathedralMid` | CAVE | L | walk | 4 (2 W8, 2 S) | 300k | 40k |
| 3 | `TT_Cave_Hall_CathedralFoot` | CAVE | L | walk | 3 (W8, 2 S) | 300k | 35k |
| 4 | `TT_Cave_Hall_Lake` | CAVE | L | walk | 4 | 285k | 40k |
| 5 | `TT_Cave_Room_Cathedral` | CAVE | S | walk | 3 | 200k | 9k |
| 6 | `TT_Cave_Room_LowHall` | CAVE | S | walk | 3 | 215k | 10k |
| 7 | `TT_Cave_Room_Terraces` | CAVE | S | walk | 3 | 205k | 9k |
| 8 | `TT_Cave_Room_Curtains` | CAVE | XS | walk | 2 | 160k | 7k |
| 9 | `TT_Cave_Room_Pillars` | CAVE | M | walk | 3 | 165k | 15k |
| 10 | `TT_Cave_Chamber_Bubble` | CAVE | XS | walk | 2 | 110k | 6k |
| 11 | `TT_Cave_Chamber_Cleft` | CAVE | S | walk, sideways | 3 | 130k | 6k |
| 12 | `TT_Cave_Crawl_Slab` | CAVE | S | prone | 2 | 140k | 6k |
| 13 | `TT_Cave_Crawl_Saddle` | CAVE | M | walk, crouch or prone | 2 | 165k | 10k |
| 14 | `TT_Cave_Crawl_Rubble` | CAVE | S | crouch, 2 prone spots | 2 | 135k | 6k |
| 15 | `TT_Cave_Ledge_Rift` | CAVE | XL | walk, 2 levels | 3 | 280k | 40k |
| 16 | `TT_Cave_Ledge_Collapse` | CAVE | L | walk | 4 | 300k | 40k |
| 17 | `TT_Cave_Ledge_Cascade` | CAVE | M | walk | 3 | 260k | 19k |
| 18 | `TT_Cave_Pass_Meander` | CAVE | M | walk | 2 | 135k | 8k |
| 19 | `TT_Cave_Pass_SqueezeC` | CAVE | S | walk, 3 m crouch | 2 | 85k | 6k |
| 20 | `TT_Cave_Pass_SqueezeP` | CAVE | S | walk, 3 m prone | 2 | 115k | 6k |
| 21 | `TT_Cave_Pass_GalleryCrawl` | CAVE | L | crawl 18 m | 2 | 175k | 10k |
| 22 | `TT_Cave_Pass_Flooded` | CAVE | M | crouch or walk | 2 | 105k | 6k |
| 23 | `TT_Cave_Pass_Crack` | CAVE | M | walk, sideways | 2 | 120k | 7k |
| 24 | `TT_Cave_Jct_Tri` | CAVE | S | walk | 3 | 160k | 12k |
| 25 | `TT_Cave_Jct_Island` | CAVE | M | walk, crouch | 4 | 180k | 16k |
| 26 | `TT_Cave_Jct_Star` | CAVE | M | walk, 1 crouch | 5 | 190k | 25k |
| 27 | `TT_Cave_Grotto_Jewel` | CAVE | XS | walk | 1 | 120k | 6k |
| 28 | `TT_Cave_Grotto_Sump` | CAVE | S | walk | 1 | 160k | 7k |
| 29 | `TT_Cave_Grotto_Crawl` | CAVE | XS | prone | 1 | 70k | 6k |
| 30 | `TT_Brk_Breakthrough` | MIX | M | walk | 2 (1d, 1c) | 110k | 9k |
| 31 | `TT_Brk_Hole` | MIX | S | walk, 3 m crouch | 2 (1d, 1c) | 100k | 6k |
| 32 | `TT_Brk_Cutting` | MIX | S | walk | 3 (2d, 1c) | 120k | 8k |
