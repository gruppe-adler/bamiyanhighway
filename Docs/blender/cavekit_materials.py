"""Cave kit materials: one dark (no sky light) MatPBRBasic per imported Poly Haven rock set in Assets/Tunnels/Cave/Textures.
Plain Python from the addon root: python Docs/blender/cavekit_materials.py. Safe to run again (keeps the GUIDs of existing metas)."""
import os, re, hashlib

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
TEX = os.path.join(ADDON, "Assets", "Tunnels", "Cave", "Textures")
DATA = os.path.join(ADDON, "Assets", "Tunnels", "Cave", "Data")
# name -> (colour tint, texture tiling per 16 UV units; the kit's UVs are metres / 2.2 / 16)
SETS = {"Cave_Flowstone": (1.0, 0.96, 0.9), "Cave_Wall": (0.85, 0.78, 0.7), "Cave_WallDark": (1.0, 1.0, 1.0),
        "Cave_Floor": (0.9, 0.85, 0.8), "Cave_Riverbed": (0.9, 0.9, 0.9)}

EMAT = """MatPBRBasic {{
 DiffuseIBL 0 0 0 1
 SpecularIBL 0 0 0 1
 Ambient 0 0 0 1
 Color {r} {g} {b} 1
 MetalnessScale 0
 Cull none
 DisableFog 1
 BCRMap "{bcr}"
 NMOMap "{nmo}"
 GlobalMapsUVTransform MatUVTransform "{{{uv}}}" {{
  TilingU 16
  TilingV 16
 }}
}}
"""
META = """MetaFileClass {{
 Name "{{{guid}}}{path}"
 Configurations {{
{configs} }}
}}
"""
CONFIGS = "".join("  EMATResourceClass %s {\n  }\n" % c if c == "PC" else "  EMATResourceClass %s : PC {\n  }\n" % c
                  for c in ("PC", "XBOX_ONE", "XBOX_SERIES", "PS4", "PS5", "HEADLESS", "Xbox"))


def guid(key):
    return hashlib.md5(("SP_CAVE_" + key).encode()).hexdigest()[:16].upper()


def resource(path):
    t = open(path, encoding="utf-8").read()
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+)"', t).group(1)


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


os.makedirs(DATA, exist_ok=True)
for name, (r, g, b) in SETS.items():
    bcr = resource(os.path.join(TEX, name + "_BCR.edds.meta"))
    nmo = resource(os.path.join(TEX, name + "_NMO.edds.meta"))
    write(os.path.join(DATA, name + ".emat"), EMAT.format(r=r, g=g, b=b, bcr=bcr, nmo=nmo, uv=guid(name + ".uv")))
    meta = os.path.join(DATA, name + ".emat.meta")
    if not os.path.exists(meta):
        write(meta, META.format(guid=guid(name + ".emat"), path="Assets/Tunnels/Cave/Data/%s.emat" % name, configs=CONFIGS))
    print("made", name)
