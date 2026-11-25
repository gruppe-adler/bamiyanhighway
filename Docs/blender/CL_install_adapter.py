"""Installs TT_Adapter_Cave (from redesign_staging/adapter, built by tunnelkit_build_adapter.py) into the addon: FBX -> Assets/Tunnels/TT,
a new .xob.meta (earth + ground, same pattern as the other TT pieces) and Prefabs/Tunnels/TT/TT_Adapter_Cave.et (+ .meta): a copy of the
TT_Straight_2 prefab (one dark corridor probe in the middle, exposure control 0) with fresh IDs.   python Docs/blender/CL_install_adapter.py"""
import os, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'CL_install.py'), encoding='utf-8').read().rsplit('\nmain()', 1)[0]
g = {'__name__': 'cl_install_lib'}
exec(compile(src, 'CL_install.py', 'exec'), g)
ADDON, ASSETS, PREFABS = g['ADDON'], g['ASSETS'], g['PREFABS']
name, sib = 'TT_Adapter_Cave', 'TT_Straight_2'
stage = os.path.join(ADDON, 'Docs', 'blender', 'redesign_staging', 'adapter', name + '.fbx')
shutil.copy2(stage, os.path.join(ASSETS, name + '.fbx'))
mp = os.path.join(ASSETS, name + '.xob.meta')
if not os.path.exists(mp):
    g['write'](mp, g['new_meta'](name))
text = open(os.path.join(PREFABS, sib + '.et'), encoding='utf-8').read()
sib_meta = open(os.path.join(ASSETS, sib + '.xob.meta'), encoding='utf-8').read()
sib_xob = re.search(r'Name "(\{[0-9A-F]{16}\})Assets/Tunnels/TT/%s\.xob"' % sib, sib_meta).group(1)
new_xob = re.search(r'Name "(\{[0-9A-F]{16}\})Assets/Tunnels/TT/%s\.xob"' % name, open(mp, encoding='utf-8').read()).group(1)
text = text.replace(sib_xob + 'Assets/Tunnels/TT/%s.xob' % sib, new_xob + 'Assets/Tunnels/TT/%s.xob' % name)
n = [0]
def fresh(m):
    n[0] += 1
    return '%s"%s"' % (m.group(1), g['guid']('%s.id.%d' % (name, n[0])))
text = re.sub(r'(\bID )"[0-9A-F]{16}"', fresh, text)
text = re.sub(r'((?:MeshObject|RigidBody|SP_TunnelExposureComponent) )"\{[0-9A-F]{16}\}"', lambda m: '%s"{%s}"' % (m.group(1), g['guid']('%s.comp.%s' % (name, m.group(1).strip()))), text)
pp = os.path.join(PREFABS, name + '.et')
g['write'](pp, text)
g['write'](pp + '.meta', g['PREFAB_META'].format(guid=g['guid'](name + '.et'), path='Prefabs/Tunnels/TT/%s.et' % name))
print('installed', name, 'xob guid', new_xob, 'prefab', pp)
