"""After Workbench imported a cave room (cave_export.py's FBX + _MASK.tif): its MatPBRMulti material, the model's
material assignments and collider surface, and the prefab (into Prefabs/Tunnels/TT, so the tunnel generator's catalog
sees it as a room). Plain Python from the addon root:  python Docs/blender/caves/cave_finish.py TT_Room_Drip_A
Safe to run again.

Layers (all on UV set 1 = world-space box UVs, so they run on across every joint; the mask on UV set 2):
  1 base rock      Cave_Chalk       (calm grey-cream rock: hardly any hero features, so it can tile over walls and ceilings)
  2 mask R         Cave_Flowstone   (flowstone: floor sheets, smooth wall zones, round the roots)
  3 mask G         Cave_Dripstone   (the formations, and blocky wall zones), warm tint
  4 mask B         Cave_Sediment    (the floor ground outside the flowstone sheets)
  dirt             Cave_Mud (off for now: DirtOpacity 0)
  The four layers tile at different sizes (5.9 / 5 / 2.5 / 7 m) and the mask (cave_export.break_up_repetition) puts them in
  patches of 3-13 m, so nothing repeats over a long wall
Which mask channel drives which layer is an assumption (R->2, G->3, B->4): check it in Workbench.
"""
import os, re, sys, hashlib

ADDON = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
NAME = sys.argv[1] if len(sys.argv) > 1 else 'TT_Room_Drip_A'
CAVE = os.path.join(ADDON, 'Assets', 'Tunnels', 'Cave')
TEX = os.path.join(CAVE, 'Textures')
DATA = os.path.join(CAVE, 'Data')
PREFABS = os.path.join(ADDON, 'Prefabs', 'Tunnels', 'TT')
TT_DATA = os.path.join(ADDON, 'Assets', 'Tunnels', 'TT', 'Data')
DIRT = "{C3691F2D8FE0234F}Common/Materials/Game/dirt.gamemat"
CONFIGS = ("PC", "XBOX_ONE", "XBOX_SERIES", "PS4", "PS5", "HEADLESS", "Xbox")


def guid(key):
    return hashlib.md5(("SP_CAVE_" + key).encode()).hexdigest()[:16].upper()


def resource(meta_path):
    t = open(meta_path, encoding="utf-8").read()
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+)"', t).group(1)


def tex(name, kind):
    return resource(os.path.join(TEX, '%s_%s.edds.meta' % (name, kind)))


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def meta_text(guid_, path, cls):
    lines = ['MetaFileClass {', ' Name "{%s}%s"' % (guid_, path), ' Configurations {']
    for c in CONFIGS:
        lines.append('  %s %s {' % (cls, c if c == 'PC' else c + ' : PC'))
        lines.append('  }')
    lines += [' }', '}', '']
    return "\n".join(lines)


def uvt(key, tiling):
    return 'MatUVTransform "{%s}" {\n  TilingU %s\n  TilingV %s\n }' % (guid(key), tiling, tiling)


def material():
    mask = resource(os.path.join(CAVE, NAME + '_MASK.edds.meta'))
    n = NAME
    emat = f"""MatPBRMulti {{
 DisableFog 1
 UVSrcGlobalMaps "UV set 2"
 MaskMap "{mask}"
 DirtOpacity 0
 DirtBCRMap "{tex('Cave_Mud', 'BCR')}"
 Color_1 1 0.96 0.9 1
 BCR_1 "{tex('Cave_Chalk', 'BCR')}"
 NMO_1 "{tex('Cave_Chalk', 'NMO')}"
 UVTransform_1 {uvt(n + '.uv1', 6)}
 Roughness_1 1
 Metalness_1 0
 Enabled_2 1
 Color_2 0.93 0.88 0.78 1
 BCR_2 "{tex('Cave_Flowstone', 'BCR')}"
 NMO_2 "{tex('Cave_Flowstone', 'NMO')}"
 UVTransform_2 {uvt(n + '.uv2', 7)}
 Roughness_2 0.45
 Metalness_2 0
 Enabled_3 1
 Color_3 1 0.85 0.66 1
 BCR_3 "{tex('Cave_Dripstone', 'BCR')}"
 NMO_3 "{tex('Cave_Dripstone', 'NMO')}"
 UVTransform_3 {uvt(n + '.uv3', 14)}
 Roughness_3 0.32
 Metalness_3 0
 Enabled_4 1
 Color_4 0.95 0.9 0.84 1
 BCR_4 "{tex('Cave_Sediment', 'BCR')}"
 NMO_4 "{tex('Cave_Sediment', 'NMO')}"
 UVTransform_4 {uvt(n + '.uv4', 5)}
 Roughness_4 0.95
 Metalness_4 0
}}
"""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, NAME + '.emat')
    write(path, emat)
    meta = path + '.meta'
    if not os.path.exists(meta):
        write(meta, meta_text(guid(NAME + '.emat'), 'Assets/Tunnels/Cave/Data/%s.emat' % NAME, 'EMATResourceClass'))
    return resource(meta)


WATER_EMAT = """MatPBRBasicGlass {
 DiffuseIBL 0 0 0 1
 SpecularIBL 0 0 0 1
 Ambient 0 0 0 1
 Color 0.015 0.022 0.022 1
 Diffuse 0.01 0.012 0.012 1
 Specular 0.6 0.6 0.6 1
 BlendMode AlphaBlend
 AlphaMul 0.82
 RoughnessScale 0.04
 MetalnessScale 0
 DielectricReflectance 0.3
 CastShadow 0
 DisableFog 1
}
"""


def water_material():
    """still cave water: dark, glossy, mostly opaque (a guess at MatPBRBasicGlass's settings; tune in Workbench)"""
    path = os.path.join(DATA, 'Cave_Water.emat')
    write(path, WATER_EMAT)
    if not os.path.exists(path + '.meta'):
        write(path + '.meta', meta_text(guid('water.emat'), 'Assets/Tunnels/Cave/Data/Cave_Water.emat', 'EMATResourceClass'))
    return resource(path + '.meta')


def fix_water(water_emat):
    meta_path = os.path.join(CAVE, NAME + '_Water.xob.meta')
    if not os.path.exists(meta_path):
        print('no water model imported yet (%s_Water.fbx)' % NAME)
        return None
    t = open(meta_path, encoding="utf-8").read()
    if 'SourceMaterial "TT_Water"' in t:
        t = re.sub(r'(SourceMaterial "TT_Water"\s*AssignedMaterial ")[^"]*(")', r'\g<1>%s\g<2>' % water_emat, t)
    elif 'MaterialAssigns' in t:
        entry = ('    MaterialAssignClass "{%s}" {\n     SourceMaterial "TT_Water"\n     AssignedMaterial "%s"\n    }\n'
                 % (guid(NAME + '.assign.water'), water_emat))
        t = t.replace("   }\n   MeshParams {", entry + "   }\n   MeshParams {", 1)
    else:
        print('the water model is not imported yet: import it, then run again')
        return None
    write(meta_path, t)
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', t).group(1)


def children(water_xob):
    """the room's own dark probe (vanilla cave probe, sized to the room) and its water"""
    import json
    out = []
    info_p = os.path.join(CAVE, NAME + '_info.json')
    if os.path.exists(info_p):
        info = json.load(open(info_p))
        lo, hi = info['inner_min'], info['inner_max']
        # Blender X right, Y forward, Z up  ->  Enfusion X right, Y up, Z forward
        cx, cy, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2, (lo[1] + hi[1]) / 2
        sx, sy, sz = hi[0] - lo[0] + 0.6, hi[2] - lo[2] + 0.6, hi[1] - lo[1] + 0.6
        out.append('\n'.join([
            '  GameEnvironmentProbeEntity : "{565470F7BA530E0D}Prefabs/Structures/Core/ProbeHouse_Base.et" {',
            '   ID "%s"' % guid(NAME + '.probe'),
            '   coords %.3f %.3f %.3f' % (cx, cy, cz),
            # vanilla interiors' way (the coal mine shaft): a house probe, dark by its brightness (-16, tuned by the user)
            '   LVReflectionBrightness -16', '   ReflectionColor 1 1 1 1', '   LVDiffuseBrightness -16', '   DiffuseColor 1 1 1 1',
            '   VisiblePercentBlack 90', '   VisiblePercentWhite 55',
            '   {',
            '    ProbeVolume : "{CD5BB05FBEEBAE01}Prefabs/Structures/Core/ProbeVolume_Base.et" {',
            '     ID "%s"' % guid(NAME + '.probevol'),
            '     Box BoundingVolume "{%s}" {' % guid(NAME + '.probebox'),
            '      Size %.2f %.2f %.2f' % (sx, sy, sz),
            '     }', '    }', '   }', '  }']))
    if os.path.exists(info_p) and 'water_level' in json.load(open(info_p)):
        # NR: the water level marker as a plain child entity at the water surface height (not an FBX bone: the tunnel catalog makes a socket of every bone)
        wl = json.load(open(info_p))['water_level']
        out.append('\n'.join([
            '  GenericEntity {',
            '   ID "%s"' % guid(NAME + '.waterlevel'),
            '   Name "WaterLevel"',
            '   coords 0 %.3f 0' % wl, '  }']))
    if water_xob:
        out.append('\n'.join([
            '  GenericEntity {',
            '   ID "%s"' % guid(NAME + '.water'),
            '   components {',
            '    MeshObject "{%s}" {' % guid(NAME + '.watermesh'),
            '     Object "%s"' % water_xob,
            '    }', '   }', '   coords 0 0 0', '  }']))
    return out


def fix_model(cave_emat):
    meta_path = os.path.join(CAVE, NAME + '.xob.meta')
    t = open(meta_path, encoding="utf-8").read()
    if 'MaterialAssigns' not in t:
        # NR: Workbench has only registered the FBX (a minimal meta, no import yet): pre-write the scene hierarchy flag (the memory points
        # only come through with it) and the three material assignments, so the first import is already right. Run this script again after
        # the import to set the collision surfaces (Workbench writes GeometryParams with blank TT_* surface materials).
        NL = chr(10)
        assigns = ''.join('    MaterialAssignClass "{%s}" {' % guid(NAME + '.assign.' + s) + NL + '     SourceMaterial "%s"' % s + NL
                          + '     AssignedMaterial "%s"' % cave_emat + NL + '    }' + NL for s in ('TT_Ground', 'TT_Earth', 'TT_CalciteGlow'))
        head = '  FBXResourceClass PC {' + NL
        t = t.replace(head, head + '   ExportSceneHierarchy 1' + NL + '   MaterialAssigns {' + NL + assigns + '   }' + NL, 1)
        write(meta_path, t)
        print('meta pre-patched (scene hierarchy + material assigns); import in Workbench, then run this script again for the collision surfaces')
        return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', t).group(1)
    # only the materials the model really has (Workbench lists them in the meta after the import); adding a source material the FBX
    # does not contain makes the next reimport complain ("Deleted materials"). The timber frames are gone, so drop TT_Wood.
    t = re.sub(r'    MaterialAssignClass "\{[0-9A-F]{16}\}" \{\s*SourceMaterial "TT_Wood"\s*AssignedMaterial "[^"]*"\s*\}\n', '', t)
    assign = {'TT_Earth': cave_emat, 'TT_CalciteGlow': cave_emat,
              'TT_Ground': cave_emat}       # rooms are underground: the terrain material on the outer shell only looked like blue water
    for src, dst in assign.items():
        if 'SourceMaterial "%s"' % src in t:
            t = re.sub(r'(SourceMaterial "%s"\s*AssignedMaterial ")[^"]*(")' % src, r'\g<1>%s\g<2>' % dst, t)
    if 'ExportSceneHierarchy' not in t:      # the empties (openings) only come through as memory points with it
        t = t.replace('  FBXResourceClass PC {\n', '  FBXResourceClass PC {\n   ExportSceneHierarchy 1\n', 1)
    t = re.sub(r'"\{[0-9A-F]{16}\}[^"]*TT_[A-Za-z]+\.gamemat"', '"%s"' % DIRT, t)
    write(meta_path, t)
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', t).group(1)


def prefab(xob, kids):
    kid_block = (' {\n' + '\n'.join(kids) + '\n }\n') if kids else ''
    et = f"""GenericEntity {{
 ID "{guid(NAME + '.id')}"
 components {{
  MeshObject "{{{guid(NAME + '.mesh')}}}" {{
   Object "{xob}"
  }}
  RigidBody "{{{guid(NAME + '.body')}}}" {{
   LayerPreset "BuildingFireView"
   SimState Collision
   ModelGeometry 1
  }}
  SP_TunnelExposureComponent "{{{guid(NAME + '.expo')}}}" {{
   m_bKeepRendered 1
   m_bExposureControl 0
  }}
 }}
{kid_block}}}
"""
    os.makedirs(PREFABS, exist_ok=True)
    path = os.path.join(PREFABS, NAME + '.et')
    write(path, et)
    meta = path + '.meta'
    if not os.path.exists(meta):
        write(meta, meta_text(guid(NAME + '.et'), 'Prefabs/Tunnels/TT/%s.et' % NAME, 'EntityTemplateResourceClass'))
    return path


emat = material()
print('material', emat)
wxob = None          # no water in the prefabs (the user adds their own); fix_water/water_material kept for later
xob = fix_model(emat)
if xob:
    kids = children(wxob)
    print('prefab', prefab(xob, kids), 'children', len(kids))
