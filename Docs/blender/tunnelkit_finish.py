"""Tunnel test kit (TT_): after tunnelkit_build.py exported the FBXs and Workbench imported them (ExportFBXResource),
finish them: materials, collider surface, prefabs. Plain Python (python Docs/blender/tunnelkit_finish.py from the addon
root), or exec() it in Blender. Safe to run again.

- Data/TT_Earth.emat, Data/TT_Wood.emat: the EoH Tunnel Network's mud and timber (no sky light: IBL and ambient 0,
  double-sided, no fog). The emats keep the GUIDs Workbench gave them.
- Each .xob.meta: the collider's surface is dirt (Workbench made up TT_*.gamemat names).
- Prefabs/Tunnels/TT/<Name>.et (+ .et.meta): GenericEntity, MeshObject, RigidBody static with BuildingFireView, like the
  Graben pieces, and SP_TunnelExposureComponent (holds the camera's exposure inside; entrances by depth). GUIDs are made from the name, so running this again gives the same ones.
"""
import os, re, hashlib

# Tries the engine's "not culled the standard way" flag on every piece (SP_TunnelExposureComponent.m_bKeepRendered), to stop
# pieces vanishing past ~20 m underground. Draws nothing. Set False if it makes no difference or costs frame time.
KEEP_RENDERED = True

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
ASSETS = os.path.join(ADDON, "Assets", "Tunnels", "TT")
PREFABS = os.path.join(ADDON, "Prefabs", "Tunnels", "TT")
DIRT = "{C3691F2D8FE0234F}Common/Materials/Game/dirt.gamemat"
# The earth takes the terrain-object material with terrain heightmap shadows (the user, 22 Nov): the terrain's own
# shadow falls on it underground. Blends on vertex colour R (the FBX's 'Col' layer, R 0: the terrain's texture)
EARTH_EMAT = "{003244BB00581E06}Common/Materials/default_MatTerrainObj_TerrShadows.emat"

# The inside: dark mud, no sky light (IBL and ambient 0), the one thing that keeps the tunnel dark
EARTH = """MatPBRBasic {
 Color 0.46 0.35 0.24 1
 MetalnessScale 0
 Cull none
 DisableFog 1
 BCRMap "{0F4E177CBD0F9B82}Assets/_SharedData/Soil/ST_Soil_01_1m_BCR.edds"
 NMOMap "{3796ACEE6478C91C}Assets/_SharedData/Soil/ST_Soil_01_1m_NMO.edds"
 GlobalMapsUVTransform MatUVTransform "{6AED1700A1000001}" {
  TilingU 16
  TilingV 16
 }
}
"""

# The outside (what the sky sees: the shell, a mouth's face): a terrain-object material under TerrShadows, blending on
# vertex colour R only (R 0 in the model: the terrain's texture). A terrain-object material has no way to shut the
# sky's light out, so it can't be the inside
GROUND = """MatTerrainObject : "%s" {
 BCRMap "{0F4E177CBD0F9B82}Assets/_SharedData/Soil/ST_Soil_01_1m_BCR.edds"
 NMOMap "{3796ACEE6478C91C}Assets/_SharedData/Soil/ST_Soil_01_1m_NMO.edds"
 MetalnessScale 0
 MaterialBlendUseVertexColor R
 MaterialBlendUseTerrainDistance 0
 UseOnTerrainHeightmapShadows 1
}
""" % EARTH_EMAT

EMAT_META = """MetaFileClass {{
 Name "{{{guid}}}{path}"
 Configurations {{
  EMATResourceClass PC {{
  }}
  EMATResourceClass XBOX_ONE : PC {{
  }}
  EMATResourceClass XBOX_SERIES : PC {{
  }}
  EMATResourceClass PS4 : PC {{
  }}
  EMATResourceClass PS5 : PC {{
  }}
  EMATResourceClass HEADLESS : PC {{
  }}
  EMATResourceClass Xbox : PC {{
  }}
 }}
}}
"""

TUNNEL_MOD = os.path.join(os.path.dirname(ADDON), "EoHTunnelNetwork_6AC512E279B88EC4", "data", "Assets", "Materials", "EoH_Tunnel_Wood.emat")


def guid(key):
    return hashlib.md5(("SP_TT_" + key).encode()).hexdigest()[:16].upper()


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def materials():
    write(os.path.join(ASSETS, "Data", "TT_Earth.emat"), EARTH)
    write(os.path.join(ASSETS, "Data", "TT_Ground.emat"), GROUND)
    meta = os.path.join(ASSETS, "Data", "TT_Ground.emat.meta")
    if not os.path.exists(meta):
        write(meta, EMAT_META.format(guid=guid("ground.emat"), path="Assets/Tunnels/TT/Data/TT_Ground.emat"))
    wood = open(TUNNEL_MOD, encoding="utf-8").read() if os.path.exists(TUNNEL_MOD) else EARTH
    # the tunnel mod's own container GUIDs would clash: give ours their own
    wood = re.sub(r'"\{[0-9A-F]{16}\}"', '"{%s}"' % guid("wood.uv"), wood)
    wood = re.sub(r'^ (DiffuseIBL|SpecularIBL|Ambient) .*\n', '', wood, flags=re.M)      # vanilla interiors take ambient light
    write(os.path.join(ASSETS, "Data", "TT_Wood.emat"), wood)


def resource(emat):
    meta = open(os.path.join(ASSETS, "Data", emat + ".meta"), encoding="utf-8").read()
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+)"', meta).group(1)


def fix_meta(meta_path):
    t = open(meta_path, encoding="utf-8").read()
    if 'ExportSceneHierarchy' not in t:      # the empties (openings) only come through as memory points with it
        t = t.replace('  FBXResourceClass PC {\n', '  FBXResourceClass PC {\n   ExportSceneHierarchy 1\n', 1)
    t = re.sub(r'"\{[0-9A-F]{16}\}TT_[A-Za-z]+\.gamemat"', '"%s"' % DIRT, t)
    t = re.sub(r'(SourceMaterial "TT_Earth"\s*AssignedMaterial ")[^"]*(")', r'\g<1>%s\g<2>' % resource("TT_Earth.emat"), t)
    # TT_Ground is new to models imported before it existed: its assignment and its collider surface added
    if 'SourceMaterial "TT_Ground"' not in t:
        entry = ('    MaterialAssignClass "{%s}" {\n     SourceMaterial "TT_Ground"\n     AssignedMaterial "%s"\n    }\n'
                 % (guid(os.path.basename(meta_path) + ".ground"), resource("TT_Ground.emat")))
        t = t.replace("   }\n   MeshParams {", entry + "   }\n   MeshParams {", 1)
    else:
        t = re.sub(r'(SourceMaterial "TT_Ground"\s*AssignedMaterial ")[^"]*(")', r'\g<1>%s\g<2>' % resource("TT_Ground.emat"), t)
    t = re.sub(r'(SurfaceProperties \{\n)((?:\s*"[^"]*"\n)*)', lambda m: m.group(1) + ('      "%s"\n' % DIRT) * 3, t)
    write(meta_path, t)
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', t).group(1)


PREFAB = """GenericEntity {{
 ID "{id}"
 components {{
  MeshObject "{{{mesh}}}" {{
   Object "{xob}"
  }}
  RigidBody "{{{body}}}" {{
   LayerPreset "BuildingFireView"
   SimState Collision
   ModelGeometry 1
  }}
  SP_TunnelExposureComponent "{{{expo}}}" {{
{entrance}  }}
 }}
}}
"""

PREFAB_META = """MetaFileClass {{
 Name "{{{guid}}}{path}"
 Configurations {{
  EntityTemplateResourceClass PC {{
  }}
  EntityTemplateResourceClass XBOX_ONE : PC {{
  }}
  EntityTemplateResourceClass XBOX_SERIES : PC {{
  }}
  EntityTemplateResourceClass PS4 : PC {{
  }}
  EntityTemplateResourceClass PS5 : PC {{
  }}
  EntityTemplateResourceClass HEADLESS : PC {{
  }}
  EntityTemplateResourceClass Xbox : PC {{
  }}
 }}
}}
"""


def prefabs():
    os.makedirs(PREFABS, exist_ok=True)
    made = []
    for name in sorted(os.listdir(ASSETS)):
        if not name.endswith(".xob.meta"):
            continue
        base = name[:-len(".xob.meta")]
        xob = fix_meta(os.path.join(ASSETS, name))
        path = "Prefabs/Tunnels/TT/%s.et" % base
        write(os.path.join(PREFABS, base + ".et"), PREFAB.format(id=guid(base + ".id"), mesh=guid(base + ".mesh"), body=guid(base + ".body"), xob=xob,
                                                                   expo=guid(base + ".expo"), entrance=("   m_bEntrance 1\n" if "Entry" in base else "") + ("   m_bKeepRendered 1\n" if KEEP_RENDERED else "")))
        meta = os.path.join(PREFABS, base + ".et.meta")
        if not os.path.exists(meta):
            write(meta, PREFAB_META.format(guid=guid(base + ".et"), path=path))
        made.append(base)
    return made


materials()
done = prefabs()
print("finished %d pieces: %s" % (len(done), ", ".join(done)))
