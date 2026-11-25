# Script leak audit: Shashpul scripts (2026-11-24)

Scope: everything under `Scripts/` of this addon (our code only). Method: full read of every file, a search of every
`new` / `Spawn*` / `Create*` / `Open*` / `Load` / `CallLater` / `ScriptInvoker` / `delete` / `static`, the local API docs for
the calls that matter, and all 11 Workbench log folders in `Documents/My Games/ArmaReforgerWorkbench/logs`. Nothing was
edited, no script reload was done, the Workbench was not driven. The code snippets below were NOT compiled.

Note on line numbers: `SP_TunnelSnapTool.c` is being rewritten while this audit runs (2099 lines at 19:09, 2261 lines at
19:19: the list became "assets with sides" and a key strip of text chips). Findings are anchored on function names; the
line numbers are those of the 19:09 copy unless marked "(19:19)". The lifecycle code (ghost, rows, `OnActivate`,
`OnDeActivate`, `OnBeforeUnloadWorld`, `CloseMenu`) is unchanged between the two copies.

## 1. Executive summary

* No leak of a script object is CONFIRMED in any of our classes. Over 11 sessions and 8 "Reload Game Scripts" runs the engine
  never reported `Leaked 'SP_...'`; the only leaked instance is the vanilla `PacejkaPlotTool` (4 times, once before our tool existed).
* The code review found no reference cycle, no unremoved invoker, no leaked file handle and no unbounded cache in any of
  the files. The hover tool's per-mouse-move allocations are bounded (they are freed by the next `Clear()`), see 4.2.
* The logs DO prove something more important: **three of three script reloads with `SP_TunnelSnapTool` as the active tool
  crashed the Workbench inside `SP_TunnelSnapTool.OnActivate`** (15:49:18, 19:10:03, 19:20:52), at the line
  `m_Hud = DebugTextScreenSpace.Create(m_API.GetWorld(), ...)`. This is F1 below. It is not a leak, but it sits on the
  exact reload path the leak question is about, and it must be fixed before the tool is used again.
* Findings: 12 in total. 1 HIGH (confirmed crash), 2 MEDIUM (likely), 8 LOW (3 likely, 5 theoretical), 1 INFO (performance).
* Game runtime and dedicated server: `SP_TunnelExposureComponent` does nothing on a dedicated server
  (`System.IsConsoleApp()` returns before any state is created) and on a client undoes everything it sets on the normal path
  (last piece deleted: callqueue entry removed, HDR brightness `-1`, post-process slot cleared, lights and probes deleted). The
  weak spot is the unusual path where the game or world is already gone when the last piece is deleted (F3).
  `SP_RockDebrisGeneratorEntity` is entirely `#ifdef WORKBENCH`, so it has no runtime state in game.

## 2. Findings table

Status: CONFIRMED = evidence in logs, LIKELY = follows from the code, THEORETICAL = needs an unusual sequence.

| # | File : function (line) | Class | Severity | Status | Evidence | Fix |
|---|---|---|---|---|---|---|
| F1 | `SP_TunnelSnapTool.c` : `OnActivate` (193; 203 at 19:19) | SP_TunnelSnapTool | HIGH (crash) | CONFIRMED | 3 crashes, see 4.4 | 6.1 |
| F2 | `SP_TunnelSnapTool.c` : whole class has no destructor; `DrawMenu` / `ShowGhost` use `m_API.GetWorld()` unchecked | SP_TunnelSnapTool | MEDIUM | LIKELY | tool was active at 3 reloads; ghost is a world-owned local entity, so it outlives the tool instance if the list is open | 6.2 |
| F3 | `SP_TunnelExposureComponent.c` : `OnDelete` (172), `Let` (580), `Grade` (557) | SP_TunnelExposureComponent | MEDIUM (game) | LIKELY | `Grade` returns on `!world` before it resets `s_iGradeStep/s_iGradeCamera`; `OnDelete` skips the whole reset when `GetGame()` is null; statics survive into the next session of the same process | 6.3 |
| F4 | `SP_TunnelSnapTool.c` : `OnBeforeUnloadWorld` (211), no `OnAfterLoadWorld` | SP_TunnelSnapTool | LOW | LIKELY | `m_Hud` (bound to the old world), `m_Shapes`, `m_aFrontier`, `m_aCatalogs` survive a world change | 6.4 |
| F5 | `SP_TunnelSnapTool.c` : `RebuildKit` (469) | SP_TunnelSnapTool | LOW | LIKELY | rebuild replaces `m_aCatalogs` while an open list still holds `m_MenuCat` / entries (weak pointers go null) | 6.5 |
| F6 | `SP_RockDebrisGeneratorEntity.c` : `MemoryCleanup` (693) | SP_RockDebrisGeneratorEntity | LOW | LIKELY | `m_Grid`, `m_aGridEntries` (every cloned cluster object, rejected ones included), `m_aOutlines`, `m_aShapePoints` stay allocated per generator after each regeneration. Editor only, bounded, same as vanilla forest generator | 6.6 |
| F7 | `SP_TunnelExposureComponent.c` : `OnPostInit` (66) | SP_TunnelExposureComponent | LOW | THEORETICAL | `s_aPieces.Insert(this)` without `Contains`; a second `OnPostInit` on one component would make `RemoveItem` leave a ghost entry, `IsEmpty()` never true, teardown (CallLater remove, `Let`) never runs | 6.7 |
| F8 | `SP_TunnelExposureComponent.c` : `UpdateTorch` (225) | SP_TunnelExposureComponent | LOW | THEORETICAL | creates spill+beam only when `!s_Spill`; if `CreateLight(POINT)` ever returns null but SPOT succeeds, a new beam entity is created every frame and the old one is overwritten (leaked entity), and `DropTorchLights` is only entered when `s_Spill` is set | 6.8 |
| F9 | `SP_TunnelExposureComponent.c` : `s_ManProbeRes` (45), `RegisterDiag` (104) | SP_TunnelExposureComponent | LOW | THEORETICAL | static `ref Resource` for the probe prefab never released; diag menu entries registered once and never removed. One resource, constant size | 6.3 |
| F10 | `SP_TunnelSnapTool.c` : `GatherSockets` (600), `PlaceSelected` (1467), `OnBeforeUnloadWorld` | SP_TunnelSnapTool | LOW | THEORETICAL | `m_aWorld` holds `IEntitySource` and indices for up to 1.5 s after an undo/delete (`REFRESH_INTERVAL_MS`); `m_aWorld[m_iMenuWorld]` can be stale or out of range when the list is open and the entity count changes | 6.9 |
| F11 | `SP_TunnelSnapTool.c` : `UpdateHover` (723), `RebuildFrontier` (1058), `ShowGhost` (1441) | SP_TunnelSnapTool | INFO (performance) | LIKELY | allocates one `SP_HoverSocket` per opening every 30 ms; `IsFree` is O(N^2) per rebuild; every arrow-key repeat spawns and deletes a whole piece prefab | 6.10 |
| F12 | `SP_TunnelCatalog.c` : `BuildPiece` (646), `SP_TunnelMeasurePlugin.c` : `MeasureOne` (106), `SP_TunnelGenPlugin.c` : `YawProbe` (1239) | catalog / plugins | LOW | THEORETICAL | entity is created in the world, measured, deleted; a script exception in between leaves a probe entity at 2048 700 2048 (and 2 undo entries per piece, about 200 per catalog rebuild). `m_File` in the measure plugin stays open until the next run if `Run` throws | 6.11 |

No findings (read in full): `SP_TunnelSnapPlugin.c`, `SP_TunnelConnect.c`, `SP_TunnelSpline.c`, `SP_TunnelGrower.c`,
`SP_TunnelGenPlugin.c` (apart from F12), `SP_TunnelGenRecordComponent.c`, `SP_TunnelSplinePointData.c`, `SelectionToPolylinePlugin.c`,
all `EnfusionMCP/EMCP_WB_*.c` (stateless `NetApiHandler`s: a request and a response object per call, both owned by the engine,
no statics, no callbacks, no files, no timers).

## 3. Object inventory and how each is released

### 3.1 SP_TunnelSnapTool.c (the hover tool)

| Object | Created | Released | Verdict |
|---|---|---|---|
| `m_aCatalogs` (`ref array<ref SP_TunnelCatalog>`), catalogs read from `$profile:*.txt` | `LoadCatalog` | `m_aCatalogs.Clear()` on kit change / rebuild, tool destruction | ok (kept across deactivation on purpose) |
| `m_Cache` (`map<string,int>`) | `PieceOfSource` | `LoadCatalog` clears it | bounded by the number of distinct prefab names in the world, no growth per hover |
| `m_aUnknown` | `PieceOfSource` | duplicates filtered with `Find`, cleared on catalog load | bounded |
| `m_aWorld` (`SP_HoverPiece`: weak `m_Src`, weak `m_Cat`) | `RefreshWorld` | `Clear()` at every refresh and in `OnBeforeUnloadWorld` | ok |
| `m_aAll` (`SP_HoverSocket`, weak `m_Def`) | `GatherSockets`, at most every 30 ms | `Clear()` at the start of every gather | bounded; sockets also referenced by `m_aFrontier` / `m_aCandidates` live one generation longer |
| `m_aCandidates`, `m_aFrontier` (strong refs to sockets) | `RebuildCandidates`, `RebuildFrontier` | `Clear()` at each rebuild; `m_aFrontier` is not cleared on deactivate | bounded (F4) |
| `m_Hud` (`ref DebugTextScreenSpace`) | `OnActivate` | `m_Hud = null` in `OnDeActivate` | ok; not on world unload (F4); crash in `OnActivate` (F1) |
| `m_Shapes` (`SCR_DebugShapeManager`, `set<ref Shape>`) | one per tool instance | `Clear()` at every `Redraw`, in `OnDeActivate` | bounded: at most 400 frontier spheres + candidates + 12 box lines per redraw; redraw only when the hovered opening changes |
| `m_aRows` (`DebugTextScreenSpace`, up to 17 in the 19:09 copy, about 15-25 chips in the 19:19 copy) | `DrawMenu` | `Clear()` at the start of every `DrawMenu`, in `CloseMenu` | bounded; redrawn on state change, never per frame |
| `m_aMenu` / `m_aGroups` (19:09) = `m_aAssets` (19:19), `SP_MenuEntry`, `SP_MenuGroup`, `SP_Asset` | `BuildMenu` | `Clear()` in `BuildMenu`, `CloseMenu` | no cycle: group -> entries is one-way, `SP_MenuEntry.m_Cat` is weak, `m_aView` is a weak alias |
| `m_aFoot` (`SP_HoverFoot`) | `BuildMenu` | `Clear()` in `BuildMenu`, `CloseMenu` | ok |
| `m_Ghost` (`IEntity`, local, `SpawnEntityPrefabLocal`) | `ShowGhost` | `DeleteGhost`: called first thing in `ShowGhost`, in `CloseMenu`, hence in `OnDeActivate`, `OnBeforeUnloadWorld`, `PlaceSelected`, Tab, Esc, click elsewhere, `OpenMenu`, `JumpNextEnd`. No destructor (F2) | every in-session path is covered |
| `TraceParam` (`FreeFraction`) | per call, at most once a second while the list is open | local, freed at scope exit | ok |
| `Resource.Load(prefab)` in `ShowGhost` | per ghost | local handle, engine caches the prefab while the entity lives | ok |
| `FileIO` | only through `SP_TunnelCatalog.Load/Save`, both close on every path | ok | ok |

Ghost lifecycle, path by path: menu closed by Esc, Tab, click elsewhere, N, O (empty result), placing a piece, tool deselected,
world unloaded: all go through `CloseMenu` and delete it. Selection change: `ShowGhost` deletes the previous one before it
spawns. Script reload with the list open: no code runs in the tool (F2). Script exception while a ghost exists: the next
`ShowGhost` still deletes it because `m_Ghost` is kept. The ghost prefab carries `SP_TunnelExposureComponent`, but its
`OnPostInit` returns before it registers anything when `game.InPlayMode()` is false, so the ghost cannot enter `s_aPieces`.

### 3.2 SP_TunnelExposureComponent.c (runs in game)

| State set | Set where | Undone where |
|---|---|---|
| `GetCallqueue().CallLater(Expose, 0, true)` | first registered piece (`OnPostInit`) | `OnDelete` of the last piece: `Remove(Expose)` |
| `SetCameraHDRBrightness(cam, x)` | `Expose` | `Let`: `-1` (auto) when the camera changes, when back in the open, when the diag "hold off" is on, on teardown |
| `SetCameraPostProcessEffect(cam, 15, ...)` | `Grade` | `Grade` with step 0 (`None`, empty string) from `Let`; on camera change `Let` runs first |
| `LightEntity` spill + beam (static) | `UpdateTorch` | `DropTorchLights`: torch off, left the tunnel (`s_fDark < 0.3` forces `s_bTorchOn = false`), teardown |
| black probe entity per soldier (`SpawnEntityPrefabLocal`, `AddChild`) | `OnManQuery`, every 0.5 s | `ManProbeTick` deletes it when the carrier is gone, not underground, or the probe is gone; `DropManProbes` on teardown; children also die with the carrier |
| `s_aPieces` (weak entries), `s_aProbeMen`, `s_aManProbes` (weak) | `OnPostInit`, `ManProbeTick` | `RemoveItem(this)`, `s_aPieces = null`, `Clear()` |
| `EntityFlags.FEATURE` on the owner | `OnPostInit` | dies with the entity |
| `DiagMenu` entries | `RegisterDiag`, once | never (F9) |

Dedicated server: `OnPostInit` returns at `System.IsConsoleApp()` before `s_aPieces`, the callqueue or the diag menu exist, and
`OnDelete` returns at `!s_aPieces`. Nothing accumulates. Per-frame work on a client is allocation free (no strings are built
unless the "Log exposure" diag is on; the only periodic array is `GetGadgetsByType` every 0.3 s while underground).

### 3.3 Other files

* `SP_RockDebrisGeneratorEntity.c`: all state is `#ifdef WORKBENCH` (line 121 to 2826). `m_Grid`, `m_aGridEntries`, the line/point/rectangle
  arrays are cleared at the start of every regeneration (`PopulateGrid`, `RegenerateForest`); `MemoryCleanup` clears the lines,
  points and rectangles but not the grid and the clones (F6). Statics: `s_aPreviousPoints2D` (reset at the end of a normal regeneration, left
  over after the early return when there are no shape points: a stale polygon for the next partial regeneration, not a leak),
  `s_DebugShapeManager` (one for all generators, cleared at the start of every regeneration), `s_Benchmark`. In a built
  world each placed generator still deserialises its `m_aLevels` / `m_aClusters` attribute data (vanilla does the same).
* `SP_TunnelGenPlugin.c` / `SP_TunnelGrower.c` / `SP_TunnelConnect.c` / `SP_TunnelSpline.c`: per run the plugin builds a
  `SP_TunnelGrower`, layouts, paths, pins and obstacles as locals; they are freed when `Generate` returns. The grower owns
  its current layout (`ref m_Layout`), the plugin keeps the best one only for the length of the call. No back references, so
  no cycle (path marks use integer indices). The plugin keeps one `m_Catalog` (small) and weak `array<IEntity>` scratch lists.
* `SP_TunnelSnapPlugin.c`: one `ref SP_TunnelCatalog`, weak `m_LastMover/m_LastAnchor`. Fine.

## 4. Log analysis

Logs: `C:\Users\nomisum\Documents\My Games\ArmaReforgerWorkbench\logs\`, 11 folders from 2026-11-23 23:20 to 2026-11-24 19:20.

### 4.1 What the logs show

| Check | Result |
|---|---|
| `Leaked '<Class>' script instance` | 3 logs (23:54, 15:49:16, 19:10:02) and a 4th at 19:20:50: always exactly `PacejkaPlotTool (1x)`. Never an `SP_*` class |
| `==== Resource leaks ====` list | 6 logs (clean shutdowns). Only UI resources (`UI/Textures/Cursor/arrow_*_uiuc.edds`, imagesets, `RobotoCondensed`, scrollbar...). Nothing under `Assets/Tunnels`, `Prefabs/Tunnels`, `TT_GhostPreview`, `TT_ManProbe`, `TT_Grade_*`. The cursor texture counts (2 to 5) vary between sessions that never used our tool (23:20, 08:57) as well |
| `Resources are leaking! Check log!` (GameApp.cpp:1284) | 8 assertions (23:54; 14:48, 14:52, 15:00, 15:34, 15:49; 19:10; 19:20): every one raised by a menu/shortcut action (`QAction::activate`) = Reload Game Scripts with a world loaded. The only resource left in those cases is the vanilla terrain thermal profile (`system/thermal/thermalProfileTerrainDefault.conf`) |
| `has mismatched memory size upon removal` | 10 lines in the 08:57 session (vanilla cliff and crash barrier meshes, stored size 0), before our tool existed |
| Warnings/errors mentioning `SP_` | none except our own deliberate warnings (`the editor turns the other way: redoing the rotation...`, `no sockets on TT_TunnelProbe...`, `SearchResources is obsolete`). No `NULL pointer`, no VM exception from our classes |
| Module static memory | `WorkbenchGame` 3135K (14:33) to 3254K (19:10): grows only with the code size (CRC changes), identical between 15:34 and 15:49 |
| `SP_TunnelExposure` | no line in any log. Play mode was started twice (12:21, 15:54:46, "Workbench Reload Game" then `Entered offline game state`); with `Log exposure` off the component prints nothing, so these runs prove only that no script error appeared (`SCRIPT (E)` lines: only `SCR_MenuLayoutEditorComponent`, `SCR_BaseResupplySupportStationComponent`, `PacejkaPlotTool`) |

### 4.2 Before / after the first use of the tool (14:41:26 in `logs_2026-11-24_14-33-13`)

* Before: reloads at 14:34 and 14:39 (no world loaded yet), no `Leaked`, no assertion.
* After: SP_TunnelSnapTool ran in 5 sessions (14:33, 15:49, 16:08, 19:09, 19:10), about 107 pieces placed through the list
  (13 + 10 + 13 + 3 + 68), each placement followed by an `... entities scanned ... ms` line (97.6k entities, 82 pieces and 150 openings at the end of the
  last session). After the first, cold scan of a session (80-120 ms) the scan takes 15-36 ms and does not grow with use: 15-26 ms at 14-24 pieces, 15-18 ms at 82 pieces.
  Reloads at 14:48, 14:52, 15:00, 15:34, 15:49, 19:10, 19:20 all ended without an `SP_*` leak.
* In the three reloads that crashed the tool was the ACTIVE tool (the engine re-activated it: the crash is inside its `OnActivate`).
  So the old `SP_TunnelSnapTool` instance, with its HUD, shapes, rows and possibly a ghost, was destroyed without a leak report.

### 4.3 What the logs prove

* The script instance of every SP_ class is released at reload, including the tool instance that was active (no `Leaked 'SP_...'`).
* No SP_ resource (material, prefab, mesh) is still referenced when the Workbench shuts down cleanly (6 logs, 2 of them after
  the hover tool had been used: 15:49 and 16:08).
* No script error from any SP_ class while the tool or the generator ran.

### 4.4 What they cannot prove

* Heap growth during a session. The engine only reports leaked script instances and resources at teardown; nothing in the
  logs samples process memory. The Workbench was never closed by the user with the tool freshly used for hours, and the sessions
  that ended in a crash never reach the leak report. A 107-placement run is a small sample.
* Anything on the engine side that is not a script instance or a resource: entities spawned locally (the ghost), `DebugText`
  and `Shape` registrations, undo history. They die with their world or with the script object, which is not logged.
* Whether the ghost entity is orphaned by a reload with the list open: the crash happens before the user could look.
* The game runtime behaviour of `SP_TunnelExposureComponent` over a long mission, and any dedicated server behaviour: no log of either.
* The two `FREEZE_*.mdmp` files (07:26, 08:47) and the 00:19 crash (23-39-20) predate the tool and have no script frame.

Crash evidence (F1), all in `crash.log`, preceded in `console.log` by `Reloading game scripts` -> `Leaked 'PacejkaPlotTool'` ->
`Game destroyed` -> recompile -> `Loading World Editor script tools` -> `ENGINE (F): Crashed`:

| Time | Reason | Script frame |
|---|---|---|
| 15:49:18 (14-33-13) | Access violation, illegal write at 0x24 | `SP_TunnelSnapTool.c:189 OnActivate` (older copy) |
| 19:10:03 (19-09-23) | Access violation, illegal read at 0xffffffffffffffff | `SP_TunnelSnapTool.c:193 OnActivate` = the `DebugTextScreenSpace.Create(m_API.GetWorld(), ...)` line |
| 19:20:52 (19-10-12) | Access violation, illegal write at 0x24 | `SP_TunnelSnapTool.c:203 OnActivate` = the same statement in the 19:19 copy |

A write at 0x24 is what writing through a null `BaseWorld` pointer looks like and a read at 0xff..ff what a freed one looks like
(inference, the stack has no more detail); all three are at the first line of `OnActivate` that touches the world. After a reload the
editor activates the previously active tool before its world exists again.

## 5. Ranking by lifetime

1. Game runtime / dedicated server: F3, F7, F8, F9 (all in `SP_TunnelExposureComponent`; none is hit on the normal path; none exists on a dedicated server).
2. Workbench session (hours): F1, F2, F4, F5, F10, F11, F12 (tool and plugins), F6 (generator).
3. Nothing in `Game` reaches a dedicated server except the exposure component (inert there) and the rock generator
   (attribute data only).

## 6. Fixes (before / after, not compiled)

### 6.1 F1: no world access in `OnActivate` (do this first)

Before:
```c
protected override void OnActivate()
{
    m_PickSrc = null;
    m_iPickSocket = -1;
    m_iHover = -1;
    m_sHoverKey = "";
    m_Hud = DebugTextScreenSpace.Create(m_API.GetWorld(), "", DebugTextFlags.FACE_CAMERA, 20, 60, 16, 0xFFFFFFFF, 0xAA000000);
    if (LoadCatalog())
        RefreshWorld();

    ShowHint();
}
protected void SetHud(string text)
{
    if (m_Hud)
        m_Hud.SetText(text);
}
```
After: activation only resets state; the HUD, the catalog scan and the strip are made on the first mouse move, when the
world certainly exists. `UpdateHover` already rescans when `m_iEntityCount` differs (set to -1 here).
```c
protected override void OnActivate()
{
    m_PickSrc = null;
    m_iPickSocket = -1;
    m_iHover = -1;
    m_sHoverKey = "";
    m_iEntityCount = -1;
    m_iLastRefresh = 0;
    m_Hud = null;      // made by EnsureHud() on first use
}

protected bool EnsureHud()
{
    if (m_Hud)
        return true;

    if (!m_API)
        return false;

    BaseWorld world = m_API.GetWorld();
    if (!world)
        return false;

    m_Hud = DebugTextScreenSpace.Create(world, "", DebugTextFlags.FACE_CAMERA, 20, 60, 16, 0xFFFFFFFF, 0xAA000000);
    return true;
}

protected void SetHud(string text)
{
    if (EnsureHud())
        m_Hud.SetText(text);
}

// first lines of OnMouseMoveEvent:
//     if (!m_Hud && EnsureHud()) { LoadCatalog(); ShowHint(); }
// and in UpdateHover:
//     if (m_aCatalogs.IsEmpty() && !LoadCatalog()) return;
```
In `DrawMenu` (and every other `DebugTextScreenSpace.Create` caller) add `if (!world) return;` after `BaseWorld world = m_API.GetWorld();`.
Until this is in: switch to another tool (for example the Select tool) BEFORE `Game > Reload Game Scripts`, and do not leave the hover tool active when saving scripts that auto-reload.

### 6.2 F2: destructor so a tool destroyed with an open list does not leave the ghost behind

Before: no destructor.
After:
```c
void ~SP_TunnelSnapTool()
{
    DeleteGhost();     // weak pointer: already null when the world is gone, so this is safe at shutdown
    m_aRows.Clear();
}
```

### 6.3 F3 + F9: reset all static state when the last piece goes, even without a world

Before (`OnDelete`, `Grade`):
```c
override void OnDelete(IEntity owner)
{
    if (!s_aPieces) return;
    s_aPieces.RemoveItem(this);
    if (s_LastPiece == this) s_LastPiece = null;
    if (s_aPieces.IsEmpty())
    {
        s_aPieces = null;
        ArmaReforgerScripted game = GetGame();
        if (game)
        {
            game.GetCallqueue().Remove(Expose);
            Let(game.GetWorld());
            DropManProbes();
            DropTorchLights();
            s_bTorchOn = false;
        }
    }
}
protected static void Grade(BaseWorld world, int camera, int step)
{
    if (!world) return;          // state below is never reset when the world is null
    ...
```
After:
```c
protected static void ResetState()
{
    s_iHeldCamera = -1;
    s_fSentGain = -1;
    s_iOutSince = 0;
    s_iGradeStep = 0;
    s_iGradeCamera = -1;
    s_bTorchOn = false;
    s_fDark = 0;
    s_LastPiece = null;
    s_ManProbeRes = null;
}

override void OnDelete(IEntity owner)
{
    if (!s_aPieces) return;
    s_aPieces.RemoveItem(this);
    if (s_LastPiece == this) s_LastPiece = null;
    if (!s_aPieces.IsEmpty()) return;

    s_aPieces = null;
    ArmaReforgerScripted game = GetGame();
    if (game)
    {
        game.GetCallqueue().Remove(Expose);
        Let(game.GetWorld());
    }

    DropManProbes();
    DropTorchLights();
    ResetState();       // also when game or world is already gone
}
```

### 6.4 F4: world change

```c
protected override void OnBeforeUnloadWorld()
{
    CloseMenu();
    m_Shapes.Clear();
    m_Hud = null;                 // bound to the old world, made again by EnsureHud()
    m_aWorld.Clear();
    m_aAll.Clear();
    m_aCandidates.Clear();
    m_aFrontier.Clear();
    m_PickSrc = null;
    m_iEntityCount = -1;
}
```

### 6.5 F5: rebuild with the list open

```c
protected void RebuildKit(int kit)
{
    CloseMenu();      // m_MenuCat and the entries point into the catalog that is about to be replaced
    ClearPick();
    ...
```

### 6.6 F6: rock generator

```c
protected void MemoryCleanup()
{
    m_aLines.Clear();
    ...                        // existing lines
    m_Grid = null;             // first: the grid holds raw pointers into the entries
    m_aGridEntries.Clear();
    m_aOutlines.Clear();
    m_aShapePoints = null;
}
```
All four are rebuilt at the start of `RegenerateForest` (`m_Grid = new ...`, `m_aOutlines.Clear()` then refilled, `m_aShapePoints = GetAnchorPoints(...)`,
`m_aGridEntries.Clear()` in `PopulateGrid`), so nothing reads them in between. Verify with a generator that has thousands of rocks.

### 6.7 F7

```c
if (!s_aPieces.Contains(this))
    s_aPieces.Insert(this);
```

### 6.8 F8

Before: `if (s_bTorchOn && !s_Spill) { s_Spill = ...; s_Beam = ...; }`
After:
```c
if (s_bTorchOn && (!s_Spill || !s_Beam))
{
    DropTorchLights();         // never keep one without the other, never overwrite a live entity
    s_Spill = LightEntity.CreateLight(...);
    s_Beam = LightEntity.CreateLight(...);
    ...
}
else if (!s_bTorchOn && (s_Spill || s_Beam))
    DropTorchLights();
```

### 6.9 F10

* In `UpdateHover`: refresh at once when the entity count DROPPED (`count < m_iEntityCount`), the 1.5 s throttle only for growth.
* In `PlaceSelected` and `OpenMenu`: `if (m_iMenuWorld < 0 || m_iMenuWorld >= m_aWorld.Count()) { CloseMenu(); return; }`.

### 6.10 F11 (performance only)

* `UpdateHover`: call `GatherSockets()` only when a piece moved (compare the transforms of the pieces, or throttle to 250 ms) instead of every 30 ms.
* `RebuildFrontier` / `RebuildCandidates`: bucket the sockets by cell (`int cell = (int)(x / 1) * 4096 + (int)(z / 1)`) in a `map<int, array<int>>` for `IsFree`, or at least skip `m_iWorld` pairs already seen.
* `ShowGhost`: remember the `(piece, socket)` of the current ghost and return early when unchanged; keep the entity and only `SetWorldTransform` it when the pose changes.

### 6.11 F12

Wrap the create ... delete pairs so the delete also runs when the measuring part bails out early (the code already deletes on
every normal path; only a script exception skips it). Optional: do the catalog rebuild inside one `BeginEntityAction` / `EndEntityAction`
pair for all pieces instead of two per piece.

## 7. Runtime verification procedure

Principle: a leak shows as a counter that does not return to its baseline after a cycle is repeated, or as a `Leaked '` line / a
TT_ or SP_ resource in the leak list. Do 7.1 first (no reload needed, no assertion dialog).

### 7.1 Temporary instrumentation (remove afterwards)

Add to the top of `SP_TunnelSnapTool.c`, inside the existing classes:
```c
class SP_HoverSocket
{
    static int s_iLive;
    void SP_HoverSocket() { s_iLive++; }
    void ~SP_HoverSocket() { s_iLive--; }
    ...existing members...
}
class SP_MenuEntry { static int s_iLive; void SP_MenuEntry() { s_iLive++; } void ~SP_MenuEntry() { s_iLive--; } ... }
class SP_HoverFoot { static int s_iLive; void SP_HoverFoot() { s_iLive++; } void ~SP_HoverFoot() { s_iLive--; } ... }
class SP_HoverPiece { static int s_iLive; void SP_HoverPiece() { s_iLive++; } void ~SP_HoverPiece() { s_iLive--; } ... }
// 19:19 copy: the same for SP_Asset
```
In the tool class:
```c
protected static int s_iGhostMade;
protected static int s_iGhostFreed;

protected void LeakReport(string where)
{
    int shapes = m_Shapes.CountShapes();
    Print(string.Format("LEAKCHECK %1: sockets live %2 (all %3, frontier %4, cand %5) | entries live %6 (menu %7) | foots live %8 (%9) | pieces live %10 (%11) | rows %12 | shapes %13 | ghost made %14 freed %15 now %16 | cache %17 unknown %18",
        where, SP_HoverSocket.s_iLive, m_aAll.Count(), m_aFrontier.Count(), m_aCandidates.Count(),
        SP_MenuEntry.s_iLive, m_aAssets.Count(), SP_HoverFoot.s_iLive, m_aFoot.Count(),
        SP_HoverPiece.s_iLive, m_aWorld.Count(), m_aRows.Count(), shapes,
        s_iGhostMade, s_iGhostFreed, (m_Ghost != null), m_Cache.Count(), m_aUnknown.Count()));
}
```
Call it: at the end of `CloseMenu()` (`LeakReport("closemenu")`), in `OnDeActivate` (after clearing), in `OnBeforeUnloadWorld`, and
from a spare key (for example `KC_F9`) in `OnKeyPressEvent`. Count the ghost: `s_iGhostMade++` right after a successful spawn in `ShowGhost`,
`s_iGhostFreed++` inside `DeleteGhost` after `delete`. In the 19:09 copy replace `m_aAssets.Count()` with `m_aMenu.Count()`.

Expected values, any number of cycles: after `closemenu`: entries live 0, foots live 0, rows 0, ghost made == freed, `ghost now` 0;
sockets live <= all + frontier + cand (the frontier and candidate arrays keep one older generation); pieces live == `m_aWorld.Count()`;
`cache` and `unknown` constant after the first scan. A counter that climbs with the number of cycles is the leak; copy the line pairs from the log.

For the game side add to `SP_TunnelExposureComponent.OnDelete` (when the last piece goes) and to `OnPostInit`:
```c
Print(string.Format("SP_TunnelExposure LEAKCHECK teardown: held cam %1, grade step %2 cam %3, lights %4/%5, probes %6, pieces left %7",
    s_iHeldCamera, s_iGradeStep, s_iGradeCamera, s_Spill != null, s_Beam != null,
    s_aManProbes.Count(), s_aPieces.Count()));
// OnPostInit, after Insert: Print("SP_TunnelExposure registered " + s_aPieces.Count());
```
(guard `s_aManProbes` against null). Expected after teardown: held cam -1, grade step 0, cam -1, lights 0/0, probes 0.

### 7.2 Hover tool cycles (in the running Workbench)

Always write the sequence down and compare the `LEAKCHECK` lines after cycle 1, 10 and 50.

1. Open the world, choose the tool, press F9 once (baseline).
2. Open and close the list 50 times: click an open end, Esc; alternatively N, Esc. Press F9. Expected: baseline, `ghost made == freed`.
3. Open the list and change the selection 100 times (arrows, 5 key repeats, mouse over rows), close it, F9. Expected: baseline.
4. Place and undo 20 times (Space, Ctrl+Z). Expected: entity count back to the original after undo; check that the next hover rescans (`entities scanned` line) without a script error (F10).
5. Switch tools 20 times (hover tool, Select tool, hover tool). Expected: one `OnDeActivate` report with rows 0, shapes 0, ghost now 0 each time.
6. Press `Rebuild TT catalog` with the list open (F5). Expected after the fix: list closes, no `NULL pointer` / `Index out of range` line.
7. Load another world (File > Open) with the tool active (F4). Expected after the fix: HUD text visible again after the first mouse move, `shapes 0` right after the unload.
8. Process memory (outside the game): run in PowerShell, once before step 2 and once after step 5:
   `Get-Process ArmaReforgerWorkbenchSteamDiag | Select-Object @{n='PrivateMB';e={[int]($_.PrivateMemorySize64/1MB)}}, @{n='WorkingSetMB';e={[int]($_.WorkingSet64/1MB)}}`
   A growth of more than a few tens of MB that does not return after switching tools twice, with the counters flat, points to the engine side (shapes/texts/undo history), not to script objects.

### 7.3 Script reload checks (the user does these; each reload with a world loaded raises the blocking assertion, press Ignore)

1. Select a different tool first (Select tool). `Game > Reload Game Scripts`. In the newest `console.log`: no `Leaked 'SP_`; the only
   allowed `Leaked` is `PacejkaPlotTool`. Do this 5 times in a row: the `Leaked` count must stay 0 or 1 line (Pacejka), not grow.
2. Only after F1 is fixed: reload with the hover tool active and the list open with a ghost visible. Expected: no crash in
   `OnActivate`, no semi-transparent piece left in the world after the reload (F2), no `Leaked 'SP_TunnelSnapTool'`.
   Before the fix this step reproduces the crash (3 of 3 so far): do not do it.
3. Quit the Workbench normally (File > Exit) after a long session with the tool: look at the last 40 lines of `console.log` for
   `==== Resource leaks ====`. Only `UI/...` entries are acceptable; any `Assets/Tunnels`, `Prefabs/Tunnels`, `TT_GhostPreview`,
   `TT_ManProbe`, `TT_Grade_` entry is ours.

Grep commands (Git Bash, from the logs folder):
```
grep -n "Leaked '" */console.log
grep -n "LEAKCHECK" logs_<newest>/script.log
awk '/==== Resource leaks ====/{f=1;next} f' logs_<newest>/console.log | grep -vi "UI/\|ui/"
grep -n "Reason: Access violation" -A4 */crash.log
```

### 7.4 Game runtime (play in the editor, then a built client if possible)

1. Enable `Win+Alt > Tunnels > Log exposure`. Walk into a tunnel piece and out 20 times: the `SP_TunnelExposure: gain ..., held ...` line stops (`dark 0`) after leaving and the picture returns to the game's exposure (no stuck dark or bright picture).
2. Turn the flashlight on and off 20 times underground: in the entity tree of the running game (or the script `LEAKCHECK` line) there is at most one spill and one beam, none outside the tunnel.
3. Run the mission, quit to the main menu, start again 3 times in the same process: the teardown line shows held cam -1, grade 0, lights 0/0, probes 0 each time; on the 2nd and 3rd run the colour grade appears when entering the tunnel (a missing grade on the second run is the F3 symptom).
4. Dedicated server: run it for 30 minutes with a player walking in the tunnels; the server log must not contain any `SP_TunnelExposure` line (the component is inert by `System.IsConsoleApp()`); compare server memory at start and after 30 min with the same PowerShell command on `ArmaReforgerServer`.

## 8. Not determined

* Whether the engine calls `OnDeActivate` on the active tool before a reload (the crash trace suggests the tool is simply destroyed and recreated; no `Leaked` line either way).
* Whether a ghost survives such a reload (the crash prevented observation).
* Real heap behaviour over hours: needs 7.1 and 7.2 step 8.
* The memory cost of the rock generators' retained grids (F6): depends on how many generators and rocks the world has.
* Whether `GetGame()` / `game.GetWorld()` are null inside `OnDelete` at world teardown in a built game (F3 is real only if they can be).
