# StoneWall sand variants

## Created (StoneWall_02 only)
Prefabs/Structures/Walls/Stone/StoneWall_02/ (each with .et.meta, new GUID):
StoneWall_02_4m_v2_sand, _4m_v3_sand, _base_sand, _d_sand, _end_sand, _pole_sand, _start_sand.
(_4m_v1_sand already existed.) All inherit the vanilla prefab by GUID and override only MeshObject "{56DE7C8DCD0F4E0A}" -> MaterialAssignClass SourceMaterial "StoneWall_02" -> the existing StoneWall_02_sand.emat. No new emat was needed.

## NOT created: StoneWall_01 and StoneWall_03 (all 15 + 9 prefabs)
The material names and vanilla emat GUIDs/paths of these families could not be discovered. Vanilla files are in paks, game_read/asset_search/wb_resources getInfo return nothing, and wb_entity_inspect / MeshObject.Materials show no material info (prefabs have no overrides). Only the xob paths were found:
- StoneWall_01_4m_A: {5CDD10ECCA91BF5F}Assets/Structures/Walls/Stone/StoneWall_01_4m_A.xob
- StoneWall_03_4m: {9C643EA0EE9FBA8D}Assets/Structures/Walls/Stone/StoneWall_03/StoneWall_03_4m.xob
GUIDs were not guessed. To finish: in Workbench open one prefab of each family (Resource Browser, right-click StoneWall_01_4m_A.et -> open), select MeshObject, read the Materials/slot name and the emat (right-click -> copy resource name gives {GUID}path). Send me those and I will generate StoneWall_01_sand.emat / StoneWall_03_sand.emat (same recipe as StoneWall_02_sand.emat) and all prefabs.

## Caveats
- The component ID "{56DE7C8DCD0F4E0A}" and SourceMaterial "StoneWall_02" were copied from the v1 reference; I could not read the other vanilla 02 prefabs. A test spawn of _pole_sand loaded with 1 material assignment. If any other variant still looks grey, open it in the Prefab Editor and check MeshObject/Materials (a wrong slot name or component ID simply has no effect).
- Addon already has Prefabs/Structures/Walls/Stone/StoneWall_02/StoneWall_02_4m_v3.et (same GUID as vanilla, an override). _4m_v3_sand inherits that GUID, so it resolves to your addon version.

## Using with WEGenerator
Prefabs/WEGenerators/Walls/Stone/WG_StoneWall_01.et only references wall prefabs by GUID (FirstObject, LastObject, m_aWallGroups/m_sWallAsset). For a sand wall, duplicate it and replace those references with the _sand prefabs (StoneWall_02 only for now; the 01 generator needs the 01 sand variants first). No files were created for generators.

## In Workbench
1. Let Workbench pick up the new files (focus the window; or Resource Browser -> right-click folder -> Reimport / wb reload). The .meta files already exist with unique GUIDs.
2. Drag each *_sand.et into the world and compare with the vanilla one. Delete test entities; do not save the test world.

## Update: StoneWall_01 created
User supplied the materials: slot `StoneWall_01` = `{06FF1C00E5B352F0}Assets/Structures/Walls/Stone/Data/StoneWall_01.emat`, slot `StoneWall_01_MLOD` = `{EE3201F1138AD67A}...StoneWall_01_MLOD.emat`.
Created `Assets/Structures/Walls/Stone/Data/StoneWall_01_sand.emat` and `StoneWall_01_MLOD_sand.emat` (both `MatPBRMulti :` inheriting the vanilla emat with the same recipe as StoneWall_02_sand; assumes the vanilla MLOD emat is also MatPBRMulti - if Workbench complains, change the class) and 14 prefabs `StoneWall_01_*_sand.et` (4m_A, 4m_A_V2, 4m_B, 4m_B_V2, 4m_D, 4m_D_V2, 8m, 8m_End, 8m_End_V2, 8m_V2, end, end_V2, start, start_V2; `_base` skipped, it carries no mesh). MeshObject component id `{56DE7C8DCD0F4E0A}` verified from the addon copy of StoneWall_01_4m_A.et. Still missing: StoneWall_03 (needs the same two lines from the user).

## Update: StoneWall_03 created
Slots: `StoneWall_03` = `{DB00C2550E460229}Assets/Structures/Walls/Stone/StoneWall_03/Data/StoneWall_03.emat`, `StoneWall_03_MLOD` = `{828601F9AA154921}...StoneWall_03_MLOD.emat`. Created `Assets/Structures/Walls/Stone/StoneWall_03/Data/StoneWall_03_sand.emat` + `_MLOD_sand.emat` and 8 prefabs in `Prefabs/Structures/Walls/Stone/StoneWall_03/`: `_2m, _4m, _4m_D, _8m_A, _8m_B, _End, _Pole, _Start` (`_Base` skipped). Unverified: the MeshObject component id `{56DE7C8DCD0F4E0A}` is copied from the 01/02 families; the 03 base prefab was not readable. If a 03 sand wall stays grey, open it in the Prefab Editor and read the MeshObject component id.

## Generators
`Prefabs/WEGenerators/Walls/Stone/WG_StoneWall_01_sand.et`, `WG_StoneWall_02_sand.et`, `WG_StoneWall_03_sand.et` (+ metas). 01 is a copy of the vanilla generator with the sand prefabs (same paddings -0.5 / -0.125 / -0.175 / -0.373, 4m A/B plus D at weight 0.05). 02 and 03 were built by analogy (start, end, 4m variants, D at weight 0.05) with all paddings 0 because the vanilla generators are not readable: compare Pre/PostPadding and FirstObjectPostPadding/LastObjectPrePadding with `WG_StoneWall_02` in the property grid and adjust if the posts overlap or leave gaps. 03 uses only the 4 m group (no 2 m/8 m groups).

## Fix: MLOD emats are MatPBRBasic
The distant-LOD (MLOD) materials are baked single-texture materials, so the MatPBRMulti layer fields (Color_1, Enabled_n) had no effect. `StoneWall_0{1,2,3}_MLOD_sand.emat` are now `MatPBRBasic : "<vanilla MLOD emat>" { Color 1 0.86 0.799 1 }` (same pattern as Assets/Clutter/Rocks/Data/c_stones_sharp_01_red.emat). If the vanilla MLOD turns out to be another class, check its properties in the Workbench material editor.
