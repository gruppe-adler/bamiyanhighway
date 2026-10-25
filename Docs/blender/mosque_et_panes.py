"""Regenerate the pane children of Prefabs/Structures/Mosque_01.et from a panes.json exported out of Blender.
usage: python mosque_et_panes.py panes.json   (entries: kind, bx, by, bz, rot_z_deg; engine coords = (bx, bz, by), yaw = -rot_z)"""
import json, random, sys
ET = "Prefabs/Structures/Mosque_01.et"
XOB = {"Pane_Body": "{5276EAB3D29C2206}Prefabs/Structures/Mosque_01/Panes/Pane_Body.xob",
       "Pane_Drum": "{F778C5E05345B1CD}Prefabs/Structures/Mosque_01/Panes/Pane_Drum.xob"}
rng = random.Random(20251025)
h = lambda: "".join(rng.choice("0123456789ABCDEF") for _ in range(16))
lines = open(ET, encoding="utf-8").read().split("\n")
head_end = next(i for i, l in enumerate(lines) if l.startswith("  GenericEntity {"))
out = lines[:head_end]
for kind, bx, by, bz, rz in json.load(open(sys.argv[1])):
    yaw = (-rz) % 360
    out += ["  GenericEntity {", f'   ID "{h()}"', "   components {", f'    MeshObject "{{{h()}}}" {{', f'     Object "{XOB[kind]}"', "    }",
            f'    RigidBody "{{{h()}}}" {{', '     LayerPreset "BuildingFireView"', "     SimState Collision", "     ModelGeometry 1", "    }", "   }",
            f"   coords {bx:.3f} {bz:.3f} {by:.3f}", f"   angles 0 {yaw:.2f} 0", "  }"]
out += [" }", "}"]
open(ET, "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("panes", len(json.load(open(sys.argv[1]))))
