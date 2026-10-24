"""Write the Workbench files for a cliff without terrain slot: Data/<Asset>.emat, Cliff_Base_<Name>.et.
usage: python make_wb_files.py <Cliffs dir> <AssetName>   (reads <Asset>/<Asset>_report.json)
MASK/NMO are referenced by path only: Workbench assigns their GUIDs when it imports the .tif files."""
import json, os, random, sys
root, name = sys.argv[1:3]
rep = json.load(open(os.path.join(root, name, f"{name}_report.json")))
rel = f"Prefabs/Rocks/Cliffs/{name}"
L = {"CliffLayer_RockPorous": ("456F9AC41EC2E1CA", "7DB72156C7B5B354"), "CliffLayer_Sand": ("400909965D675648", "78D1B204841004D6"),
     "CliffLayer_Scree": ("6278EAA54D460434", "5AA05137943156AA"), "CliffLayer_SandstonePale": ("0A95F13AD8712A95", "324D4AA80106780B")}
lines = ["MatPBRMulti {", ' SurfaceProperties "{D745FD8FC67DB26A}Common/Materials/Game/stone.gamemat"',
         f' MaskMap "{rel}/{name}_MASK.edds"', f' GlobalNMOMap "{rel}/{name}_NMO.edds"']
for e in rep["emat"]:
    n, l = e["slot"], e["layer"]
    if n > 1:
        lines.append(f" Enabled_{n} 1")
    lines += [f' BCR_{n} "{{{L[l][0]}}}Prefabs/Rocks/Cliffs/_Layers/{l}_BCR.edds"',
              f' NMO_{n} "{{{L[l][1]}}}Prefabs/Rocks/Cliffs/_Layers/{l}_NMO.edds"',
              f" UVTransform_{n} MatUVTransform {{", f"  TilingU {e['TilingU']}", f"  TilingV {e['TilingV']}"]
    if e["Rotation"]:
        lines.append(f"  Rotation {e['Rotation']}")
    lines.append(" }")
lines.append("}")
os.makedirs(os.path.join(root, name, "Data"), exist_ok=True)
open(os.path.join(root, name, "Data", f"{name}.emat"), "w", newline="\n").write("\n".join(lines))
h = lambda: "".join(random.choice("0123456789ABCDEF") for _ in range(16))
et = f'''GenericEntity {{
 ID "{h()}"
 components {{
  MeshObject "{{{h()}}}" {{
   Object "{rel}/{name}.xob"
  }}
  RigidBody "{{{h()}}}" {{
   LayerPreset "BuildingFireView"
   SimState Collision
   ModelGeometry 1
  }}
 }}
}}'''
open(os.path.join(root, f"Cliff_Base_{name[6:]}.et"), "w", newline="\n").write(et)
print("wrote", name)
