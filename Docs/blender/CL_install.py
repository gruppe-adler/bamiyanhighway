"""Installs the redesigned TT pieces (Docs/blender/redesign_staging/full/*.fbx, from tunnelkit_build_clear.py) into the addon:
  * copies each FBX to Assets/Tunnels/TT (overwrites the standing / crouch / prone / transition pieces IN PLACE; NEW names for the variants)
  * .xob.meta: an existing one is PATCHED (Workbench's GUIDs kept): the TT_Wood material assignment is removed, the collider surface list
    has one dirt entry per remaining material (2); a missing one is written (GUIDs made from the name)
  * Prefabs/Tunnels/TT/<variant>.et (+ .et.meta) for the NEW names only: a copy of the standard sibling's prefab (dark probe children,
    m_bExposureControl 0, m_bKeepRendered, m_bEntrance are all kept) with fresh IDs and the variant's .xob. EXISTING prefabs are never touched.
Plain Python (python Docs/blender/CL_install.py, from anywhere). Safe to run again. Needs the originals backed up first (the script
does not do that: copy Assets/Tunnels/TT/TT_*.fbx and *.xob.meta somewhere outside the addon before the first run)."""
import os, re, shutil, hashlib

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
STAGE = os.path.join(ADDON, "Docs", "blender", "redesign_staging", "full")
ASSETS = os.path.join(ADDON, "Assets", "Tunnels", "TT")
PREFABS = os.path.join(ADDON, "Prefabs", "Tunnels", "TT")
DIRT = "{C3691F2D8FE0234F}Common/Materials/Game/dirt.gamemat"


def guid(key):
    return hashlib.md5(("SP_TT_CL_" + key).encode()).hexdigest()[:16].upper()


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


def new_meta(name):
    return XOB_META.format(name=name, xob=guid(name + ".xob"), dirt=DIRT, g_earth=guid(name + ".m0"), g_ground=guid(name + ".m1"),
                           earth=resource("TT_Earth.emat"), ground=resource("TT_Ground.emat"),
                           **{"c%d" % i: guid(name + ".c%d" % i) for i in range(7)})


def patch_meta(t):
    """A meta that exists: no TT_Wood assignment, one dirt surface per remaining material (2)"""
    t = re.sub(r'\n    MaterialAssignClass "\{[0-9A-F]{16}\}" \{\n     SourceMaterial "TT_Wood"\n     AssignedMaterial "[^"]*"\n    \}', '', t)
    t = re.sub(r'(SurfaceProperties \{\n)((?:\s*"[^"]*"\n)*)', lambda m: m.group(1) + ('      "%s"\n' % DIRT) * 2, t)
    return t


def sibling(name):
    m = re.match(r"^(.*)_([AC])$", name)
    if m and not name.startswith("TT_Trans_") and not re.match(r"^TT_[CP]_", name):
        return m.group(1)
    return None


def main():
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(STAGE) if f.endswith(".fbx"))
    patched, created, prefabs = [], [], []
    for name in names:
        shutil.copy2(os.path.join(STAGE, name + ".fbx"), os.path.join(ASSETS, name + ".fbx"))
        mp = os.path.join(ASSETS, name + ".xob.meta")
        if os.path.exists(mp):
            text = patch_meta(open(mp, encoding="utf-8").read())
            patched.append(name)
        else:
            text = new_meta(name)
            created.append(name)
        write(mp, text)
    for name in names:
        sib = sibling(name)
        pp = os.path.join(PREFABS, name + ".et")
        if sib is None or os.path.exists(pp):
            continue
        src = open(os.path.join(PREFABS, sib + ".et"), encoding="utf-8").read()
        sib_meta = open(os.path.join(ASSETS, sib + ".xob.meta"), encoding="utf-8").read()
        sib_xob = re.search(r'Name "(\{[0-9A-F]{16}\})Assets/Tunnels/TT/%s\.xob"' % re.escape(sib), sib_meta).group(1)
        new_xob = "{%s}" % re.search(r'Name "\{([0-9A-F]{16})\}Assets/Tunnels/TT/%s\.xob"' % re.escape(name), open(os.path.join(ASSETS, name + ".xob.meta"), encoding="utf-8").read()).group(1)
        text = src.replace(sib_xob + "Assets/Tunnels/TT/%s.xob" % sib, new_xob + "Assets/Tunnels/TT/%s.xob" % name)
        counter = [0]

        def fresh(m):
            counter[0] += 1
            return '%s"%s"' % (m.group(1), guid("%s.id.%d" % (name, counter[0])))
        text = re.sub(r'(\bID )"[0-9A-F]{16}"', fresh, text)
        text = re.sub(r'((?:MeshObject|RigidBody|SP_TunnelExposureComponent) )"\{[0-9A-F]{16}\}"',
                      lambda m: '%s"{%s}"' % (m.group(1), guid("%s.comp.%s" % (name, m.group(1).strip()))), text)
        write(pp, text)
        write(pp + ".meta", PREFAB_META.format(guid=guid(name + ".et"), path="Prefabs/Tunnels/TT/%s.et" % name))
        prefabs.append(name)
    print("FBX copied: %d; metas patched: %d, written: %d; new prefabs: %d" % (len(names), len(patched), len(created), len(prefabs)))
    print("written metas (new names):", ", ".join(created))
    print("new prefabs:", ", ".join(prefabs))


main()
