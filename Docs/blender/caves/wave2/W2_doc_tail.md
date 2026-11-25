## What the user must do (import list)

Workbench picks up new FBX files in `Assets/Tunnels/Cave/` by itself while it runs (the first asset appeared as `.xob`, `.txo`, `_MASK.edds` without a click),
so normally the import is already done when you open the project. If not: in the Resource Browser right-click `Assets/Tunnels/Cave` -> reimport / register the new
`TT_Cave_*` and `TT_Brk_*` FBX files and their `_MASK.tif` (the tif needs an `.edds.meta`: `wb_resources register` on it, or right-click -> Register).

Then, from the addon root, once per batch:

```
python Docs/blender/caves/wave2/W2_finish.py all          # or one or more names
```

* before the import it writes only the prefab (`Prefabs/Tunnels/TT/<Name>.et` + `.et.meta`) pointing at the model by PATH (no GUID exists yet);
* after the import it writes `Assets/Tunnels/Cave/Data/<Name>.emat` (MatPBRMulti, the same layers as the existing rooms), patches the model's material assignments
  (for `TT_Brk_*` the dug tube takes the TT dug kit's own `TT_Earth.emat` and its timber `TT_Wood.emat`), and rewrites the prefab with the model's GUID and the dark house probe.

Prefab GUIDs: the `.et` files written before the import reference `"Assets/Tunnels/Cave/<Name>.xob"` without a GUID; run `W2_finish.py` again after the import (or save the prefab once in
Workbench) and the GUID is filled in. The prefab entity IDs are derived from the name, so they never change.

Then rebuild the tunnel catalog (the new prefabs are rooms / passages for the generator; the theme logic for `TT_Cave_*` / `TT_Brk_*` is the one from the concept doc, not yet compiled).

Other agents re-import tunnels at the same time: the FBX files of this wave only have NEW names, nothing existing was overwritten.

## Export notes (UV2 / LODs)

* `W2_export.py` is a copy of the new-rooms agent's `NR_export.py` (cave_export + a UV2 repair), snapshot of 2026-11-24. The repair gives every zero-area or overlapping mask triangle its own
  8 px cell in a FREE block of the atlas (an affine copy: the mask is baked from per-vertex values, so the cell holds exactly the right data) and repeats until nothing overlaps
  (the NR version used a reserved band and left a few hundred overlaps; mine takes free blocks). Checked on the exported FBX with `W2_uvcheck.py` (= NR_uvcheck.py) at the mask resolution (2048):
  zero-area, overlapping and negative-winding triangles are listed per asset above.
* No LODs are exported for these assets (`CAVE_LOD_MIN` is raised): the seam-protected LODs of the NR script only reached 65 percent on these small meshes and a plain decimate re-creates
  zero-area / stretched mask triangles. The assets are 80-280k triangles; a LOD chain is a later step.

## State when this agent stopped

* A background batch (`W2_batch.sh crack saddle breakthrough`, started 2026-11-25) may still be running: it rebuilds Crack (wider pinch), Saddle (higher crouch band) and Breakthrough
  (the NEW dug-kit ring 1.6 x 2.2, no timber), and exports each one if every route passes and the cave is sealed. Results land in `wave2/results/`; then run
  `python Docs/blender/caves/wave2/W2_make_doc.py` and, for the exported ones, `python Docs/blender/caves/wave2/W2_finish.py --prefab-only <Name>` (or the full `W2_finish.py` after the import).
* Not exported because a check failed: Jct_Star, Hall_Lake, Ledge_Cascade (see the table); retry with `W2_queue.sh <key> bcrp` after changing the shape (`W2_assets2/3.py`), `W2_sdfcheck.py <key>` tests a design in seconds.
* TT_Brk_Hole and TT_Brk_Cutting were built with the NEW dug ring (24 profile points found at the dug openings). The cave openings of all pieces still use the old cave ring 1.4 x 2.1 (like the existing rooms).
