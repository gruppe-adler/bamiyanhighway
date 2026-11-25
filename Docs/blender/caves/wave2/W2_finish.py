"""W2_finish: the wave-2 version of cave_finish.py (a copy with additions; cave_finish.py itself is untouched).
Plain Python from the addon root:   python Docs/blender/caves/wave2/W2_finish.py [--prefab-only] <Name> [<Name> ...]     (or: all)
--prefab-only: only the prefab files (GUID from the xob.meta when it exists, else the path), no material / meta edits.

Two phases per asset, the script works out which one applies:
 1. BEFORE the import in Workbench (no <Name>.xob.meta yet): writes the prefab Prefabs/Tunnels/TT/<Name>.et (+ .et.meta, GUIDs from the
    name, so they never change) pointing at the model by PATH ("Assets/Tunnels/Cave/<Name>.xob", no GUID yet: the engine resolves a
    path-only reference, and Workbench rewrites it with the GUID on the first save), with the room's dark house probe.
 2. AFTER the import (the xob.meta and the MASK edds.meta exist): the MatPBRMulti material Data/<Name>.emat, the model's material
    assignments (cave rock -> the asset's material; for the TT_Brk_* transitions also the TT dug kit's own TT_Earth/TT_Wood materials
    for the dug tube and its timber), the collider surface, and the final prefab with the model's GUID.  Safe to run again.
The layers and tilings are cave_finish.py's (Cave_Chalk / Flowstone / Dripstone / Sediment, mask R/G/B).
"""
import os, re, sys, json, hashlib

ADDON = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
CAVE = os.path.join(ADDON, 'Assets', 'Tunnels', 'Cave')
TEX = os.path.join(CAVE, 'Textures')
DATA = os.path.join(CAVE, 'Data')
PREFABS = os.path.join(ADDON, 'Prefabs', 'Tunnels', 'TT')
TT_DATA = os.path.join(ADDON, 'Assets', 'Tunnels', 'TT', 'Data')
DIRT = "{C3691F2D8FE0234F}Common/Materials/Game/dirt.gamemat"
CONFIGS = ("PC", "XBOX_ONE", "XBOX_SERIES", "PS4", "PS5", "HEADLESS", "Xbox")


def guid(key):
    return hashlib.md5(("SP_CAVE_" + key).encode()).hexdigest()[:16].upper()      # the same function as cave_finish.py


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


def material(NAME):
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


def dug_emat(name):
    """the TT dug kit's own material (Assets/Tunnels/TT/Data/<name>.emat), by the GUID Workbench gave it"""
    p = os.path.join(TT_DATA, name + '.emat.meta')
    return resource(p) if os.path.exists(p) else None


def children(NAME):
    out = []
    info_p = os.path.join(CAVE, NAME + '_info.json')
    if os.path.exists(info_p):
        info = json.load(open(info_p))
        lo, hi = info['inner_min'], info['inner_max']
        cx, cy, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2, (lo[1] + hi[1]) / 2
        sx, sy, sz = hi[0] - lo[0] + 0.6, hi[2] - lo[2] + 0.6, hi[1] - lo[1] + 0.6
        out.append('\n'.join([
            '  GameEnvironmentProbeEntity : "{565470F7BA530E0D}Prefabs/Structures/Core/ProbeHouse_Base.et" {',
            '   ID "%s"' % guid(NAME + '.probe'),
            '   coords %.3f %.3f %.3f' % (cx, cy, cz),
            '   LVReflectionBrightness -16', '   ReflectionColor 1 1 1 1', '   LVDiffuseBrightness -16', '   DiffuseColor 1 1 1 1',
            '   VisiblePercentBlack 90', '   VisiblePercentWhite 55',
            '   {',
            '    ProbeVolume : "{CD5BB05FBEEBAE01}Prefabs/Structures/Core/ProbeVolume_Base.et" {',
            '     ID "%s"' % guid(NAME + '.probevol'),
            '     Box BoundingVolume "{%s}" {' % guid(NAME + '.probebox'),
            '      Size %.2f %.2f %.2f' % (sx, sy, sz),
            '     }', '    }', '   }', '  }']))
    return out


def fix_model(NAME, cave_emat):
    meta_path = os.path.join(CAVE, NAME + '.xob.meta')
    t = open(meta_path, encoding="utf-8").read()
    if 'MaterialAssigns' not in t:
        print('%s: the model is not imported yet (no MaterialAssigns in its meta)' % NAME)
        return None
    dug_earth, dug_wood = dug_emat('TT_Earth'), dug_emat('TT_Wood')
    brk = '_Brk_' in NAME
    if not brk:
        t = re.sub(r'    MaterialAssignClass "\{[0-9A-F]{16}\}" \{\s*SourceMaterial "TT_Wood"\s*AssignedMaterial "[^"]*"\s*\}\n', '', t)
    assign = {'TT_Earth': cave_emat, 'TT_CalciteGlow': cave_emat, 'TT_Ground': cave_emat}
    if brk:
        assign['TT_EarthDug'] = dug_earth
        assign['TT_Wood'] = dug_wood
    for src, dst in assign.items():
        if dst is None:
            print('  no emat found for', src)
            continue
        if 'SourceMaterial "%s"' % src in t:
            t = re.sub(r'(SourceMaterial "%s"\s*AssignedMaterial ")[^"]*(")' % src, r'\g<1>%s\g<2>' % dst, t)
    if 'ExportSceneHierarchy' not in t:
        t = t.replace('  FBXResourceClass PC {\n', '  FBXResourceClass PC {\n   ExportSceneHierarchy 1\n', 1)
    t = re.sub(r'"\{[0-9A-F]{16}\}[^"]*TT_[A-Za-z]+\.gamemat"', '"%s"' % DIRT, t)
    write(meta_path, t)
    return re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', t).group(1)


def prefab(NAME, xob, kids):
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


def finish(NAME):
    kids = children(NAME)
    if PREFAB_ONLY:
        # prefab only: the model is referenced by GUID when its xob.meta exists, otherwise by path; no material or meta file is touched
        mp = os.path.join(CAVE, NAME + '.xob.meta')
        xob = 'Assets/Tunnels/Cave/%s.xob' % NAME
        if os.path.exists(mp):
            m = re.search(r'Name "(\{[0-9A-F]{16}\}[^"]+\.xob)"', open(mp, encoding='utf-8').read())
            xob = m.group(1) if m else xob
        print(NAME, 'prefab (prefab-only mode):', prefab(NAME, xob, kids))
        return
    ready = os.path.exists(os.path.join(CAVE, NAME + '.xob.meta')) and os.path.exists(os.path.join(CAVE, NAME + '_MASK.edds.meta'))
    if not ready:
        print(NAME, 'prefab stub (model not imported yet):', prefab(NAME, 'Assets/Tunnels/Cave/%s.xob' % NAME, kids))
        return
    emat = material(NAME)
    xob = fix_model(NAME, emat)
    if xob:
        print(NAME, 'material', emat, 'prefab', prefab(NAME, xob, kids))


PREFAB_ONLY = '--prefab-only' in sys.argv
names = [a for a in sys.argv[1:] if not a.startswith('--')]
if names == ['all'] or not names:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import W2_assets as _A
    _A.build('crack')
    names = sorted(_A.build(k)[0].name for k in _A.ASSETS if os.path.exists(os.path.join(CAVE, _A.build(k)[0].name + '.fbx')))
for nm in names:
    finish(nm)
