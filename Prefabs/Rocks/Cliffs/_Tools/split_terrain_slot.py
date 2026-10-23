"""Adds the terrain slot to a cliff FBX.

Run (Blender 5.x, always with --factory-startup so user add-ons can't hang it):
    NMO=<ao.npy> blender --factory-startup -b -P split_terrain_slot.py -- <in.fbx> <out.fbx>

NMO is a numpy file holding the 8-bit alpha (ambient occlusion) channel of <Asset>_NMO.tif, e.g.
    np.save('ao.npy', np.array(Image.open('<Asset>_NMO.tif').convert('RGBA'))[..., 3])

What it does (LOD0 decides, coarser LODs follow it per vertex):
  1. finds open, flat top surfaces: smoothed up-facing >= NZ, above HF of the height, AO >= AO, islands >= MI m2
  2. blurs that area mostly sideways (BLUR passes, HP = how little vertical edges conduct) into a smooth field
  3. faces where the field is above LO go into a second material "<material>_terrain"; the rest keep slot 1
  4. writes a vertex colour: terrain faces = 1 - field (0 on the plateau, 1 at the soft edge); rock faces = 1 (white)
  5. exports the FBX with custom props kept (the collider's `usage`)
Defaults (the values used for all cliffs): AO 0.7, NZ 0.7, SM 12, MI 20, TRIM 0.15, VOTE 3, BLUR 40, HP 3, LO 0.06, SPAN 0.6,
FZSM 3. Optional FZMIN (off by default): cos of the steepest slope allowed, e.g. 0.82 = about 35 deg; it also fades the blend
out toward steeper ground (tested: plateau on Crimson Badlands Ridge 253 -> 209 m2). The installed FBXs were made without it, with
ClutterThresholdAngle 20 in the terrain emats doing that job instead.
Writes nothing if no top qualifies (exit code 3). Always keep a copy of the original FBX; the xob.meta also needs a second
MaterialAssignClass mapping "<material>_terrain" to Data/<Asset>_terrain.emat.
"""
import bpy,sys,numpy as np,bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree
src,dst=sys.argv[-2],sys.argv[-1]
import os
SMOOTH=int(os.environ.get('SM',12)); NZ=float(os.environ.get('NZ',0.7)); HFRAC=float(os.environ.get('HF',0.4)); MIN_ISLAND=float(os.environ.get('MI',20)); MIN_HOLE=1.5
def P(*a): print(*a,flush=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
lods=sorted([o for o in bpy.data.objects if '_LOD' in o.name],key=lambda o:o.name)
base=lods[0].data.materials[0]
tm=bpy.data.materials.get(base.name+'_terrain') or bpy.data.materials.new(base.name+'_terrain')
me=lods[0].data
nv=len(me.vertices);nf=len(me.polygons)
co=np.empty(nv*3);me.vertices.foreach_get('co',co);co=co.reshape(-1,3)
zmin,zmax=co[:,2].min(),co[:,2].max()
fv=np.empty(nf*3,dtype=np.int64);me.polygons.foreach_get('vertices',fv);fv=fv.reshape(-1,3)  # tris
fn=np.empty(nf*3);me.polygons.foreach_get('normal',fn);fn=fn.reshape(-1,3)
fa=np.empty(nf);me.polygons.foreach_get('area',fa)
fc=np.empty(nf*3);me.polygons.foreach_get('center',fc);fc=fc.reshape(-1,3)
# vertex up-ness, area weighted, then diffuse along edges
vz=np.zeros(nv);vw=np.zeros(nv)
for k in range(3):
    np.add.at(vz,fv[:,k],fn[:,2]*fa);np.add.at(vw,fv[:,k],fa)
vz/=np.maximum(vw,1e-12)
vz_light=vz.copy()
e=np.concatenate([fv[:,[0,1]],fv[:,[1,2]],fv[:,[2,0]]]);e=np.unique(np.sort(e,axis=1),axis=0)
deg=np.bincount(e.ravel(),minlength=nv).astype(float)
for _ in range(SMOOTH):
    s=np.zeros(nv);np.add.at(s,e[:,0],vz[e[:,1]]);np.add.at(s,e[:,1],vz[e[:,0]])
    vz=(vz+s)/(1+deg)
fz=vz[fv].mean(1)
# steepness gate: lightly smoothed (3 passes ~ 0.5 m) so small steep areas are not averaged away by the heavy smoothing above
_e=np.unique(np.sort(np.concatenate([fv[:,[0,1]],fv[:,[1,2]],fv[:,[2,0]]]),axis=1),axis=0)
_d=np.bincount(_e.ravel(),minlength=nv).astype(float)
for _ in range(int(os.environ.get('FZSM',3))):
    _s=np.zeros(nv);np.add.at(_s,_e[:,0],vz_light[_e[:,1]]);np.add.at(_s,_e[:,1],vz_light[_e[:,0]])
    vz_light=(vz_light+_s)/(1+_d)
FZMIN=float(os.environ.get('FZMIN',0))   # optional: cos of the steepest slope that may carry terrain (0.82 ~ 35 deg). Off by default; the installed FBXs were made without it
fzl=vz_light[fv].mean(1)
_st=np.clip((vz_light-(FZMIN-0.12))/0.12,0,1);steep_v=_st*_st*(3-2*_st)   # 1 on flat ground, 0 on steep ground, smooth between
AO_THR=float(os.environ.get('AO',0.7))
_ao=np.load(os.environ['NMO']).astype(np.float32)/255
_uv=np.empty(len(me.loops)*2,dtype=np.float32);me.uv_layers[0].data.foreach_get('uv',_uv);_uv=_uv.reshape(-1,2)
_lv=np.empty(len(me.loops),dtype=np.int64);me.loops.foreach_get('vertex_index',_lv)
_px=np.clip((_uv[:,0]%1.0)*_ao.shape[1],0,_ao.shape[1]-1).astype(int);_py=np.clip((1-(_uv[:,1]%1.0))*_ao.shape[0],0,_ao.shape[0]-1).astype(int)
_s=np.zeros(nv);_c=np.zeros(nv);np.add.at(_s,_lv,_ao[_py,_px]);np.add.at(_c,_lv,1);vao=_s/np.maximum(_c,1)
for _ in range(int(os.environ.get('AOSM',6))):
    q=np.zeros(nv);np.add.at(q,e[:,0],vao[e[:,1]]);np.add.at(q,e[:,1],vao[e[:,0]]);vao=(vao+q)/(1+deg)
fao=vao[fv].mean(1)
P('AO face mean',round(float(fao.mean()),3),'share<thr',round(float((fao<AO_THR).mean()),3))
sel=(fz>NZ)&(fzl>=FZMIN)&(fc[:,2]>zmin+HFRAC*(zmax-zmin))&(fao>AO_THR)
# face adjacency via shared edges
def comps(mask):
    ed={}
    nb=[[] for _ in range(nf)]
    for i,t in enumerate(fv):
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
            k=(a,b) if a<b else (b,a)
            j=ed.get(k)
            if j is None: ed[k]=i
            else: nb[i].append(j);nb[j].append(i)
    return nb
nb=comps(None)
def islands(mask,minarea):
    seen=np.zeros(nf,bool);out=mask.copy()
    for s0 in np.flatnonzero(mask):
        if seen[s0]:continue
        st=[s0];seen[s0]=True;mem=[]
        while st:
            f=st.pop();mem.append(f)
            for g in nb[f]:
                if mask[g] and not seen[g]:seen[g]=True;st.append(g)
        if fa[mem].sum()<minarea: out[mem]=False
    return out
sel=islands(sel,MIN_ISLAND)
sel=~islands(~sel,MIN_HOLE)   # fill small holes
P('LOD0 sel faces',int(sel.sum()),round(float(sel.mean()),3),'area m2',round(float(fa[sel].sum()),1),'of',round(float(fa.sum()),1))
if sel.sum()==0:
    P('NOSEL'); sys.exit(3)

R=float(os.environ.get('R',2.0))
# smooth plateau field: blur the plateau indicator over the surface, mostly sideways (vertical edges conduct little)
ind=np.zeros(nv);cn=np.zeros(nv)
for k in range(3): np.add.at(ind,fv[:,k],sel.astype(float));np.add.at(cn,fv[:,k],1)
ind/=np.maximum(cn,1)
ev=co[e[:,0]]-co[e[:,1]];el=np.maximum(np.linalg.norm(ev,axis=1),1e-9)
we=(np.hypot(ev[:,0],ev[:,1])/el)**float(os.environ.get('HP',3))
sw=np.zeros(nv);np.add.at(sw,e[:,0],we);np.add.at(sw,e[:,1],we)
for _ in range(int(os.environ.get('BLUR',40))):
    q=np.zeros(nv);np.add.at(q,e[:,0],we*ind[e[:,1]]);np.add.at(q,e[:,1],we*ind[e[:,0]]);ind=(ind+q)/(1+sw)
ind=ind*steep_v   # fade the blend out toward steep ground
t=np.clip((ind-float(os.environ.get('LO',0.06)))/float(os.environ.get('SPAN',0.6)),0,1);vw_=t*t*(3-2*t)
grown=(vw_[fv].max(1)>0.02)&(fao>AO_THR)
grown&=(vw_[fv].max(1)>=float(os.environ.get('TRIM',0.15)))|sel
def bnd(m):
    return int(sum(1 for i in range(nf) for j in nb[i] if j>i and m[i]!=m[j]))
def vote(m,it):
    m=m.copy()
    for _ in range(it):
        cnt=np.array([sum(m[j] for j in nb[i]) for i in range(nf)])
        n_=np.array([len(nb[i]) for i in range(nf)])
        m=(0.5*m+cnt/np.maximum(n_,1))>0.5
    return m
_b0=bnd(grown)
grown=vote(grown,int(os.environ.get('VOTE',3)))
P('boundary edges',_b0,'->',bnd(grown))
P('grown faces',int(grown.sum()),'area',round(float(fa[grown].sum()),1))
kdv=KDTree(nv);[kdv.insert(Vector(c),i) for i,c in enumerate(co)];kdv.balance()
kd=KDTree(nf);[kd.insert(Vector(c),i) for i,c in enumerate(fc)];kd.balance()
vgm=np.zeros(nv);_cn=np.zeros(nv)
for k in range(3): np.add.at(vgm,fv[:,k],grown.astype(float));np.add.at(_cn,fv[:,k],1)
vgm/=np.maximum(_cn,1)
for o in lods:
    m=o.data
    if tm.name not in [x.name for x in m.materials]: m.materials.append(tm)
    idx=len(m.materials)-1
    n=len(m.polygons)
    if o is lods[0]:
        s_=grown; wv=vw_
    else:
        c=np.empty(n*3);m.polygons.foreach_get('center',c);c=c.reshape(-1,3)
        s_=np.array([vgm[kdv.find(Vector(p))[1]]>=0.5 for p in c]) if False else None
        vs=np.array([vgm[kdv.find(v.co)[1]] for v in m.vertices])
        pv=np.empty(n*3,dtype=np.int64);pv=None
        fvl=np.array([[x for x in p.vertices] for p in m.polygons]);s_=vs[fvl].mean(1)>=0.5
        wv=np.array([vw_[kdv.find(v.co)[1]] for v in m.vertices])
    mi=np.zeros(n,dtype=np.int32);mi[s_]=idx
    m.polygons.foreach_set('material_index',mi)
    lv=np.empty(len(m.loops),dtype=np.int64);m.loops.foreach_get('vertex_index',lv)
    lf=np.empty(len(m.loops),dtype=np.int64)
    for p in m.polygons: lf[p.loop_start:p.loop_start+p.loop_total]=p.index
    cw=np.where(s_[lf],1.0-wv[lv],1.0)   # rock-slot faces stay white (neutral), terrain faces carry the blend weight
    col=np.repeat(cw[:,None],4,axis=1).astype(np.float32)
    while m.color_attributes: m.color_attributes.remove(m.color_attributes[0])
    ca=m.color_attributes.new('Col','FLOAT_COLOR','CORNER');ca.data.foreach_set('color',col.ravel())
    m.update()
    P(o.name,n,int(s_.sum()))
bpy.ops.export_scene.fbx(filepath=dst,use_selection=False,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False,path_mode='AUTO',use_custom_props=True,colors_type='LINEAR')
P('exported')
