"""Crouch / prone / transition pieces of the tunnel test kit: writes the .xob.meta of each new FBX (material remap to the
tunnel kit's emats, collider -> dirt gamemat, ExportSceneHierarchy so the empties become memory points) and the prefabs.
Plain Python:  python Docs/blender/tunnelkit_finish_cp.py   (from the addon root). Safe to run again; it only touches the
pieces listed in NAMES (never the standing kit). Doc: Docs/TunnelKit_CrouchProne.md.

If a .xob.meta already exists (the user imported the FBX in Workbench first) it is PATCHED, keeping Workbench's GUIDs;
otherwise it is written from the format of the standing kit's metas, with GUIDs made from the name, and the prefab points
at that GUID.
"""
import os, re, hashlib

NAMES = (["TT_%s_%s" % (f, p) for f in "CP" for p in ("Straight_4", "Straight_2", "Turn90", "Dogleg_L", "Dogleg_R", "Slope", "Junction", "End", "Entry_Horizontal")]
         + ["TT_Trans_S_C", "TT_Trans_C_P", "TT_Trans_S_P"])

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
ASSETS = os.path.join(ADDON, "Assets", "Tunnels", "TT")
PREFABS = os.path.join(ADDON, "Prefabs", "Tunnels", "TT")
DIRT = "{C3691F2D8FE0234F}Common/Materials/Game/dirt.gamemat"
KEEP_RENDERED = True


def guid(key):
    return hashlib.md5(("SP_TT_CP_" + key).encode()).hexdigest()[:16].upper()


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def resource(emat):
    meta = open(os.path.join(ASSETS, "Data", emat + ".meta"), encoding="utf-8").read()
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+)"', meta).group(1)


XOB_META = """MetaFileClass {{
 Name "{{{xob}}}Assets/Tunnels/TT/{name}.xob"
 Configurations {{
  FBXResourceClass PC {{
   ExportSceneHierarchy 1
   MaterialAssigns {{
    MaterialAssignClass "{{{g_earth}}}" {{
     SourceMaterial "TT_Earth"
     AssignedMaterial "{earth}"
    }}
    MaterialAssignClass "{{{g_wood}}}" {{
     SourceMaterial "TT_Wood"
     AssignedMaterial "{wood}"
    }}
    MaterialAssignClass "{{{g_ground}}}" {{
     SourceMaterial "TT_Ground"
     AssignedMaterial "{ground}"
    }}
   }}
   MeshParams {{
    MeshParam {name} {{
    }}
   }}
   GeometryParams {{
    GeometryParam UTM_{name} {{
     SurfaceProperties {{
      "{dirt}"
      "{dirt}"
      "{dirt}"
     }}
     Mass 0
     Margin 0
    }}
   }}
   Common TXOCommonClass "{{{c0}}}" : "{{0877E7C4BB2B2C9A}}Configs/System/ResourceTypes/PC/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass XBOX_ONE : PC {{
   Common TXOCommonClass "{{{c1}}}" : "{{9D5B6207F7628CE2}}Configs/System/ResourceTypes/XBOX_ONE/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass XBOX_SERIES : PC {{
   Common TXOCommonClass "{{{c2}}}" : "{{DD9F02115C764647}}Configs/System/ResourceTypes/XBOX_SERIES/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass PS4 : PC {{
   Common TXOCommonClass "{{{c3}}}" : "{{53EC476BC921D99A}}Configs/System/ResourceTypes/PS4/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass PS5 : PC {{
   Common TXOCommonClass "{{{c4}}}" : "{{F62AA8E7B8EA9D26}}Configs/System/ResourceTypes/PS5/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass HEADLESS : PC {{
   Common TXOCommonClass "{{{c5}}}" : "{{3A5B3356978039E8}}Configs/System/ResourceTypes/HEADLESS/MeshObjectCommon.conf" {{
   }}
  }}
  FBXResourceClass Xbox : PC {{
   Common TXOCommonClass "{{{c6}}}" {{
   }}
  }}
 }}
}}"""


def new_meta(name):
    return XOB_META.format(name=name, xob=guid(name + ".xob"), dirt=DIRT,
                           g_earth=guid(name + ".m0"), g_wood=guid(name + ".m1"), g_ground=guid(name + ".m2"),
                           earth=resource("TT_Earth.emat"), wood=resource("TT_Wood.emat"), ground=resource("TT_Ground.emat"),
                           **{"c%d" % i: guid(name + ".c%d" % i) for i in range(7)})


def patch_meta(t, name):
    """A meta Workbench wrote: scene hierarchy on, materials remapped, collider surfaces dirt (as tunnelkit_finish.py)"""
    if 'ExportSceneHierarchy' not in t:
        t = t.replace('  FBXResourceClass PC {\n', '  FBXResourceClass PC {\n   ExportSceneHierarchy 1\n', 1)
    t = re.sub(r'"\{[0-9A-F]{16}\}TT_[A-Za-z_]+\.gamemat"', '"%s"' % DIRT, t)
    for src, emat in (("TT_Earth", "TT_Earth.emat"), ("TT_Wood", "TT_Wood.emat"), ("TT_Ground", "TT_Ground.emat")):
        t = re.sub(r'(SourceMaterial "%s"\s*AssignedMaterial ")[^"]*(")' % src, r'\g<1>%s\g<2>' % resource(emat), t)
    t = re.sub(r'(SurfaceProperties \{\n)((?:\s*"[^"]*"\n)*)', lambda m: m.group(1) + ('      "%s"\n' % DIRT) * 3, t)
    return t


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
{extra}  }}
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


def main():
    os.makedirs(PREFABS, exist_ok=True)
    done, missing = [], []
    for name in NAMES:
        if not os.path.exists(os.path.join(ASSETS, name + ".fbx")):
            missing.append(name)
            continue
        meta_path = os.path.join(ASSETS, name + ".xob.meta")
        if os.path.exists(meta_path):
            text = patch_meta(open(meta_path, encoding="utf-8").read(), name)
        else:
            text = new_meta(name)
        write(meta_path, text)
        xob = re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', text).group(1)
        extra = ("   m_bEntrance 1\n" if "Entry" in name else "") + ("   m_bKeepRendered 1\n" if KEEP_RENDERED else "")
        write(os.path.join(PREFABS, name + ".et"), PREFAB.format(id=guid(name + ".id"), mesh=guid(name + ".mesh"), body=guid(name + ".body"),
                                                                  xob=xob, expo=guid(name + ".expo"), extra=extra))
        pm = os.path.join(PREFABS, name + ".et.meta")
        if not os.path.exists(pm):
            write(pm, PREFAB_META.format(guid=guid(name + ".et"), path="Prefabs/Tunnels/TT/%s.et" % name))
        done.append(name)
    print("finished %d pieces: %s" % (len(done), ", ".join(done)))
    if missing:
        print("no FBX yet for: %s" % ", ".join(missing))


main()
