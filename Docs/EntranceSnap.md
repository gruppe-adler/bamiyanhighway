# Entrance Snap (manual placement by openings)

Plugin: `Scripts/WorkbenchGame/EoHTunnelGen/SP_TunnelSnapPlugin.c` ("Entrance Snap", Ctrl+Shift+J, World Editor plugin menu).
Written 2026-11-24. **Never compiled or run yet**: reload scripts (World Editor menu `Game > Reload Game Scripts`) and report compile errors.

## Use
1. Select the piece that stays put, then ctrl-click the piece(s) to attach. The first selected stays; the others move.
2. Run the plugin. Each attached piece is turned (yaw only) and moved so one of its openings meets a free opening of a piece already placed
   (the first one, or one attached earlier in the same run): same position, same height, facing opposite directions.
3. Wrong opening? Run it again on the same two pieces without touching them: the next nearest pair is tried.
4. One undo step per run. The log (`SP_TunnelSnap:` lines) says which sockets were joined and the measured gap (should be under 1 cm) and facing error (under 1 degree).

Configure (plugin gear): kit (TT / EoH) and Reach (openings further apart than this are not paired, default 15 m).

## How it works
- Openings = the sockets in the generator's catalog (`$profile:SP_TunnelCatalog_TT.txt` / `SP_TunnelCatalog.txt`), which come from the bones of each model.
  Rebuild the catalog in the Tunnel Generator after adding pieces, or the plugin does not know them.
- Pairs: same size; path with path, doorframe with a doorway's room side (`SP_TunnelRole`). Ranked by the distance the two openings have now.
- Pose from `SP_TunnelGrower.Attach` (the same maths the generator uses), applied with `coords` and `angleY` like the generator's docking.
  The first run checks which way the editor turns for a yaw and redoes the rotation with the other sign if needed.

## The vanilla tool (`SCR_PrefabBoneSnappingTool`): source read, not a fit
User pasted the source on 2026-11-24. What it does:
- Works only in **Prefab Edit Mode**. Reads the edited prefab's bones (`Animation.GetBoneNames/GetBoneMatrix`, the same calls the catalog uses).
- You drag a prefab from the Resource Browser into the viewport; on the first mouse move it picks the bone nearest to the dropped entity **on screen**, then sets the new entity's `coords` to the bone position and `angles` to the bone's orientation, and moves it into the edited prefab as a child (`MoveEntitiesToPrefab`). Occupied bones are refused.
- So: the new piece's **origin** goes onto the bone and it takes the bone's orientation (no 180 degree turn, no use of the new piece's own bones, no size/role check, only the edited prefab's bones).
- Result for us: it builds composite prefabs. Pieces would only join correctly if each piece's origin sat on its own opening and faced it, which our pieces do not (origins are at the piece centre/start, openings are bones "1", "2"). Not usable for world placement without changing every model.

What it does give us (APIs now verified, all inside `#ifdef WORKBENCH` in a `WorldEditorTool`):
- `[WorkbenchToolAttribute(name, description, awesomeFontCode)]`, overrides `OnMouseMoveEvent(x,y)`, `OnMousePressEvent(x,y,WETMouseButtonFlag)`, `OnKeyPressEvent`, `OnActivate/OnDeActivate`.
- Cursor picking: `m_API.TraceWorldPos(x, y, TraceFlags.ENTS, traceStart, traceEnd, traceDir, out IEntity)`; `m_API.EntityToSource`, `SetEntitySelection`.
- Preview: `SCR_DebugShapeManager.AddSphere(pos, radius, colour, ShapeFlags.NOOUTLINE)`, `Shape.SetColor`, `DebugTextScreenSpace.Create(...)`; hover test `Math3D.PointLineSegmentDistanceSqr(point, traceStart, traceEnd)`.
- Entity angles are written as `"%1 %2 %3"` = (pitch, yaw, roll) from `Math3D.MatrixToAngles` (which returns yaw, pitch, roll).
This is enough to build the hover/preview tool (Phase 1 of the plan) with no guessing.

## Hover tool: "Entrance Snap (hover)" (`Scripts/WorkbenchGame/EoHTunnelGen/SP_TunnelSnapTool.c`)
Written 2026-11-24 from the verified vanilla tool APIs. **Never compiled or run.** It is a `WorldEditorTool`: pick it in the World Editor tool bar, not the plugin menu.
1. Move the cursor over pieces: the free openings under the ray light up yellow, the HUD line (top left) names the piece and opening.
2. Click an opening of the piece that should MOVE: it turns cyan, every free opening that fits it shows dim green.
3. Point at the opening it should join: green = fits, red = doesn't (HUD says why: size, or role). When it fits, a magenta ghost box shows where the moving piece will stand.
4. Click: the piece is turned and moved (`SP_TunnelGrower.Attach`), selected, one undo step, the log and HUD give gap in cm and facing error. Esc cancels a pick.
- An opening is "taken" when another piece's opening sits within 0.5 m of it, so unselected neighbours are known (the plugin could not know).
- Pieces are found among the top-level world entities that come from catalog prefabs; rescanned when the entity count changes (at most every 1.5 s). The log prints the scan time.
- Mouse button: the left button is assumed to be flag bit 1 (the enum values are not in the API docs). The log prints the raw flags for the first three presses; if clicking does nothing, send me those numbers.
- Settings: kit (TT / EoH / **Both**, default Both; pieces only join within their own kit, the tool says "different kit" otherwise), pick radius (2.5 m), marker radius, ghost box on/off.
- Buttons in the tool settings: **Rebuild TT catalog**, **Rebuild EoH catalog** (same measuring as the generator's Rebuild catalog, then rescans the world).
- A prefab from `Prefabs/Tunnels/TT` that the catalog doesn't know (added after it was built: on 2026-11-24 that was `TT_Cave_Jct_Island`; the probe prefabs are skipped on purpose) is reported in the log and on the HUD line with the hint to rebuild.
- Covered: every TT prefab with bones (straights, curves, turns, doglegs, slope, junction, rooms, `TT_Room_Drip_A-E`, cave rooms/passes, entries, end) and all 53 EoH pieces, all via the catalogs.

### Growing a maze by keyboard (no list; our TT kit only, the EoH pack is not supported in this tool)
Everything is on the key strip at the top left, one row per decision. Bright chip = the key does something now, grey = it can't here, blue = the current choice.
```
TYPE     Normal tunnel (8)   [Up/Down] other types        <- only the chosen type; while you press Up/Down the others appear:
TYPE     Normal tunnel (8)  Dripstone cave (3)  Rooms (2)  Entries (1)  Cave breakthroughs (0)  Ends and caps (1)
STEER    [Left/Right]  ... Curve_15 15L  Curve_10 10L  [Straight_4 ^]  Curve_10 10R  Turn90 90R ...      (normal tunnel: turn levels, left to right)
PIECE    [Left/Right]  ... Hall_A ^  [Pass_Meander <>]  Jct_Island *3 ...                               (any other type: its pieces)
OPTIONS  [1] walk (8)  [2] crouch (2)  [3] prone (0)  [Tab] side 1/2  [PgUp/PgDn] piece 2/8
KEYS     [Space] place  [X/Ctrl+X/Backspace] remove selected  [N/B] other open end (4)  [O] overlaps shown  [Esc] close
```
- **N** picks the nearest open end (**B** the previous; again: the next nearest) and (no camera movement any more: the automatic camera jump/follow was removed on request); or click an open end (red balls = open ends, yellow = under the cursor). A 50% ghost of the chosen piece appears. The piece placed last is offered first; at the first end, the longest straight.
- **Up / Down: TYPE** of piece (normal tunnel, dripstone cave, rooms, entries, cave breakthroughs, ends/caps). Only the chosen type is shown on the strip; its siblings appear while you navigate with Up/Down and fold away 1.5 s after the last press or on any other key. Types with nothing that fits are grey.
- **Left / Right** work on the row under the type. **In the normal tunnel type: steer** (unchanged): the next turn level that leans further that way, the gentlest first; again = sharper; the opposite arrow eases back; the row shows the turn levels left to right (one piece per level, nearest the current length). **In every other type** there is no turn to steer: Left/Right move to the previous / next piece of that type (wrapping).
- **PageUp / PageDown:** previous / next piece of the current type (the PIECE row, with a glyph `^ > < <> U *N` and how many of it already stand in the world).
- **Tab:** next *side* of the current piece. A piece is one placement with all its sides: a curve has a left and a right side, a room one per fitting opening, a straight (symmetric) one.
- **1 / 2 / 3:** walking / crouching / prone option (the passage after the piece; `TT_Trans_S_C` is the crouch option at a standing end). The numbers say how many pieces of the current type offer each.
- **Space** (or Enter) places the piece (one undo step, current layer). With "Chain" on, the next open end is chosen automatically.
- **Remove: X, Ctrl+X, Backspace or Delete** (whichever the editor lets through; Ctrl+X is the editor's own Cut and Delete its own delete, so the tool may not get those) deletes the selected pieces of the kit (the one you just placed is selected; undoable) and selects the open end that comes free again, so a wrong piece is replaced with one more key. Only pieces of the kit are deleted. The log prints the first 60 keys that reach the tool (`SP_TunnelSnapTool: key <code> (ctrl, alt, shift)`), so you can see which keys the editor keeps.
- **O** hides/shows overlapping pieces (default: shown with a WARNING on the HUD line; the box test gives false alarms). **M** switches to the older "move a placed piece" mode. **Esc** ends the placement.
- Keys the engine owns (W, V, and probably Q/E/R and the WASD fly keys) are not used. If another key here is also an editor shortcut, tell me which.
- Stance needs size classes in the catalog: `ClassifyTT` knows `TT_C_*` (crouch), `TT_P_*` (prone) and `TT_Trans_<A>_<B>` (kind `TRANSITION`, weight 0 in the generator). Press **Rebuild TT catalog** in the tool settings after importing pieces.

## Path between two openings (25 Nov 2026)
**Drag** from one free opening and let go over another (or **shift+click** both): a random chain of pieces is built between them and selected.
**Space** builds a different one (as long as no other tool key or click came in between), **X** removes the path, **Esc** cancels after a first
shift+click. A plain click still places one piece as before.

- Nothing that already stands is moved. What the chain misses the second opening by is spread over all its joints: at most 12 cm sideways /
  along, 6 cm step, 1.5 degrees per joint (setting "Path": the gap; the sleeves overlap 25 cm). Longer links have more joints to give.
- Search: `SP_TunnelPathFinder.c` (weighted A*, every run weighs the moves differently, `_A` / `_C` variants picked at random). Always dug pieces (transitions
  when the sizes differ). A cave opening (1.45 x 2.10 m; dug is 1.60 x 2.20) gets a `TT_Adapter_Cave` first, as part of the path (`IsCaveOpening`:
  every cave piece, the cave side of the breakthroughs). Keeps clear of what is placed; mildly prefers to stay under
  ground when both ends are.
- Python port on the 25 Nov catalog and layer: the user's pair (42 m, 0.3 m height) 4 of 4 each way, 2-7 cm per joint; random walk-size
  pairs 8-35 m 16 of 20, 25-50 m 12 of 12.
- New pieces that would raise the hit rate (same port, one attempt per pair; none built yet):
  crouch curve 15 deg / 4 m: crouch 55 -> 95 % (prone not measured, same gap in the kit);
  walk, short links 6-18 m (today 53 %): turn 45 deg 73 %, step slope 0.3 m / 2 m 70 %, curve 10 deg / 2 m 70 %, slope + turn 45 77 %.
  Side jogs and 0.5 / 1.5 m straights: no gain.

## Known limits / next steps
- Yaw only (the generator never tilts pieces; slopes are pieces with rising openings).
- No live preview or hover picking yet. The APIs are now known (see above), so a hover tool is the next step.
- Sockets already used by pieces that are not in the selection are not known; select the neighbour too if a free-looking opening is taken.
- Direction comes from the catalog (bounding-box side, or the angle in a `TT_Curve_N` name), not from the bone's own forward axis, which has never been verified in-engine.

### Entrance adapter and the menu look (2026-11-25)
- **Type "Adapters"** (the 7th type, `GroupOf` in the tool): `TT_Adapter_Cave`, a 3 m entrance piece between the NEW dug tunnel opening (1.6 x 2.2 m, opening "1") and the OLD cave opening (1.4 x 2.1 m, opening "2"). Both sockets are standing size, so it fits any open end; the list offers first the end that fits the opening you are at: the cave end onto a cave opening, else the dug-tunnel end (Tab switches). Labels say which end joins. Measured on the FBX: tunnel end 1.60 x 2.20, cave end 1.40-1.48 x 2.10, smooth morph. Built by `Docs/blender/tunnelkit_build_adapter.py`, installed by `Docs/blender/CL_install_adapter.py` (FBX, xob meta, prefab with one dark probe). After the import: Rebuild TT catalog.
- **Menu look:** smaller text (12 px), a bold look (each text drawn twice, 0.7 px apart: the engine's debug text has no bold), keycap style (key on a lighter cap, label next to it), one dark palette, amber row names (TYPE / STEER or PIECE / OPTIONS / KEYS), blue for the current choice, dim for what is not available. No more square brackets.
