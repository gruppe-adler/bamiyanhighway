"""After ExportFBXResource: portal emats must be MatLightPortal and registered (.emat.meta with the GUID from the xob.meta); drop blank-name assigns;
give the collider a valid surface material.  run from the addon root: python Docs/blender/mosque_fix_meta.py"""
import re, os, random
R = "Prefabs/Structures/Mosque_01"; m = open(R + "/Mosque_01.xob.meta", encoding="utf-8").read()
tm = open(R + "/Data/Mosque_01_Carpet.emat.meta", encoding="utf-8").read()
m2 = re.sub(r'    MaterialAssignClass "\{[0-9A-F]+\}" \{\n     SourceMaterial ""\n     AssignedMaterial "[^"]*"\n    \}\n', '', m)
for src, g in re.findall(r'SourceMaterial "(PRT_[^"]*)"\n\s+AssignedMaterial "\{([0-9A-F]+)\}', m2):
    open(f"{R}/Data/{src}.emat", "w", newline="\n").write("MatLightPortal {\n}")
    open(f"{R}/Data/{src}.emat.meta", "w", newline="\n").write(tm.replace("{5F51CC1EBC288A0D}Prefabs/Structures/Mosque_01/Data/Mosque_01_Carpet.emat", "{%s}%s/Data/%s.emat" % (g, R, src)))
    print("portal emat", src, g)

# collider: Workbench auto-generated references to non-existing Mosque_01_*.gamemat ("Failed to open" spam) -> stone surface + building fire view layer
NEW = '\\1     LayerPreset "BuildingFireView"\n     SurfaceProperties {\n      "{D745FD8FC67DB26A}Common/Materials/Game/stone.gamemat"\n     }\n'
m2 = re.sub(r'(GeometryParam UTM_Mosque_01 \{\n)     (?:LayerPreset "[^"]*"\n     )?SurfaceProperties \{.*?\n     \}\n', NEW, m2, flags=re.S)
if os.path.exists(R + "/Data/.emat"): os.remove(R + "/Data/.emat")
if m2 != m: open(R + "/Mosque_01.xob.meta", "w", encoding="utf-8", newline="\n").write(m2); print("meta cleaned")

# gold finial/dome top: vanilla golden faucet material (user request)
GOLD = "{0C97B4386EDE9A99}Assets/Props/Furniture/Faucet_01/data/Faucet_01_golden.emat"
m3 = open(R + "/Mosque_01.xob.meta", encoding="utf-8").read()
m4 = re.sub(r'(SourceMaterial "Mosque_01_Gold"\n\s+AssignedMaterial ")[^"]*"', lambda mo: mo.group(1) + GOLD + '"', m3)
if m4 != m3: open(R + "/Mosque_01.xob.meta", "w", encoding="utf-8", newline="\n").write(m4); print("gold -> vanilla golden emat")

# dome rib strips: own emat (flat brown band paint, no masks -> no baked-AO streaks, crisp geometry edges)
mm = re.search(r'SourceMaterial "Mosque_01_Rib"\n\s+AssignedMaterial "\{([0-9A-F]+)\}', open(R + "/Mosque_01.xob.meta", encoding="utf-8").read())
if mm:
    open(R + "/Data/Mosque_01_Rib.emat", "w", newline="\n").write("""MatPBRMulti {
 SurfaceProperties "{D745FD8FC67DB26A}Common/Materials/Game/stone.gamemat"
 BCR_1 "{01B09F8DCC870BA5}Prefabs/Structures/Mosque_01/_Layers/MosqueLayer_BandPaint_BCR.edds"
 NMO_1 "{3968241F15F0593B}Prefabs/Structures/Mosque_01/_Layers/MosqueLayer_BandPaint_NMO.edds"
 UVTransform_1 MatUVTransform "{6AB17DCAD1FCAEB1}" {
  TilingU 87.65
  TilingV 87.65
 }
}""")
    open(R + "/Data/Mosque_01_Rib.emat.meta", "w", newline="\n").write(tm.replace("{5F51CC1EBC288A0D}Prefabs/Structures/Mosque_01/Data/Mosque_01_Carpet.emat", "{%s}%s/Data/Mosque_01_Rib.emat" % (mm.group(1), R)))
    print("rib emat written", mm.group(1))
