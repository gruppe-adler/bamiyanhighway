# TT_Cave_Hall_TwoLevel: small triangular patches (UV analysis, main session, 2026-11-24)

User report: several small triangular "missing texture" patches in the hall.

Measured on the exported `Assets/Tunnels/Cave/TT_Cave_Hall_TwoLevel.fbx` (scripts `Docs/blender/caves/newrooms/NR_uvcheck.py`, `NR_uvzero.py`;
run: `blender -b --factory-startup --python NR_uvcheck.py -- <fbx> <out.json> 1024`):

| UV set | what | LOD0 | LOD1 | LOD2 |
|---|---|---|---|---|
| UVMap (tiled, range -0.85..0.86) | overlap | expected (tiling) | | |
| UVMask (UV2, mask atlas 0..1) | triangles with ZERO UV area | **1741** | 800 | 255 |
| UVMask | triangles in overlapping texels | 454 (319 texels) | 199 | 121 |
| UVMask | triangles with negative UV winding | 0 | 118 | 106 |

Zero-area UVMask triangles of LOD0 (the likely cause of the visible patches):
- ALL 1741 are material index 2 (`TT_CalciteGlow`); none on `TT_Earth` / `TT_Ground`.
- 1698 are collinear (a degenerate line in the mask), 43 are a single point; 3D area median 0.0065 m^2 (about 8 cm), max 0.018 m^2, 180 above 0.01 m^2.
- Clustered in a few places (3 m cells, Blender x,y,z): (1.5, 4.5, 1.5) 277; (-1.5, 4.5, 4.5) 176; (1.5, 4.5, 10.5) 155; (1.5, 7.5, 1.5) 127; (1.5, 13.5, 1.5) 110 ...
  i.e. the formation groups (cone-shaped stalagmites / calcite), not the shell.
- 1393 further triangles have a mask texel density below 5% of the median (extreme stretching).
A zero-area UV triangle samples one point of the mask, so the mask channel (which selects the material layer) is wrong or empty there: a small
triangle of wrong / missing texture. That matches "multiple small triangular patches".

Probable cause: the formation cones (pole / apex triangles) get collapsed UV2 islands when the mask UVs are generated (UV2 unwrap or projection on the
merged mesh). Fix in the generator (not by hiding): give every formation triangle a non-degenerate UV2 (unwrap cones with a seam and a cap, or project
by the local normal), pad islands, remove the 454 overlaps, rerun `NR_uvcheck.py` (target: 0 zero-area, 0 overlap, 0 negative winding on UVMask in every LOD),
re-export, and apply the same check to `TT_Cave_Room_SwimThrough` and to the wave-2 assets (same generator).
