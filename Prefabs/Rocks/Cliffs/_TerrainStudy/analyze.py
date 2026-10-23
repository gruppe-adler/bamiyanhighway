import numpy as np, json, glob, os
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
C='..'
def s2l(x): return np.where(x<=0.04045,x/12.92,((x+0.055)/1.055)**2.4)
def l2s(x): x=np.clip(x,0,1); return np.where(x<=0.0031308,12.92*x,1.055*x**(1/2.4)-0.055)
def hexc(l): 
    s=(l2s(np.array(l))*255+.5).astype(int); return '#%02x%02x%02x'%tuple(s)
L={'Rock':'RockPorous','Sand':'Sand','Scree':'Scree','Pale':'SandstonePale'}
out={'layers':{},'cliffs':{}}
lin={}
for k,n in L.items():
    b=np.array(Image.open(f'{C}/_Layers/CliffLayer_{n}_BCR.tif'))[::4,::4].astype(np.float32)/255
    m=np.array(Image.open(f'{C}/_Layers/CliffLayer_{n}_NMO.tif'))[::4,::4].astype(np.float32)/255
    rgb=b[...,:3]; l=s2l(rgb); lum=l@[.2126,.7152,.0722]
    lin[k]=l.reshape(-1,3).mean(0)
    out['layers'][k]=dict(srgb_mean=(rgb.reshape(-1,3).mean(0)*255).round(1).tolist(),
      linear_mean=l.reshape(-1,3).mean(0).round(4).tolist(), hex_of_linear_mean=hexc(l.reshape(-1,3).mean(0)),
      lum_lin_mean=round(float(lum.mean()),4), lum_lin_std=round(float(lum.std()),4), lum_cv=round(float(lum.std()/lum.mean()),3),
      srgb_lum_std=round(float((rgb@[.2126,.7152,.0722]).std()*255),1),
      rough_mean=round(float(b[...,3].mean()),3), rough_std=round(float(b[...,3].std()),3),
      nmo_metal=round(float(m[...,2].mean()),3), nmo_ao_mean=round(float(m[...,3].mean()),3),
      normal_xy_std=[round(float(m[...,0].std()*2),3),round(float(m[...,1].std()*2),3)])
for f in sorted(glob.glob(f'{C}/Cliff_*/')):
    name=os.path.basename(os.path.normpath(f))
    mk=np.array(Image.open(f'{f}{name}_MASK.tif'))[::4,::4].astype(np.float32)/255
    nm=np.array(Image.open(f'{f}{name}_NMO.tif'))[::4,::4]
    cov=(nm[...,3]>0)|(np.abs(nm[...,0].astype(int)-128)>1)
    ao=nm[...,3].astype(np.float32)/255
    r,g,b=[mk[...,i][cov] for i in range(3)]
    c=np.broadcast_to(lin['Rock'],(r.size,3)).copy()
    for w,k in ((r,'Sand'),(g,'Scree'),(b,'Pale')):
        c=c*(1-w[:,None])+lin[k]*w[:,None]
    eff=c.mean(0); aom=float(ao[cov].mean())
    rep=json.load(open(f'{f}{name}_report.json')).get('mask_mean_rgb')
    out['cliffs'][name]=dict(cov=round(float(cov.mean()),3),mask_mean_covered=[round(float(x.mean()),3) for x in (r,g,b)],report_mask_mean=rep,
      eff_linear=eff.round(4).tolist(),eff_hex=hexc(eff),eff_lum=round(float(eff@[.2126,.7152,.0722]),4),
      ao_mean_covered=round(aom,3),eff_x_ao_hex=hexc(eff*aom),eff_x_ao_lum=round(float(eff@[.2126,.7152,.0722]*aom),4))
json.dump(out,open('palette_analysis.json','w'),indent=1)
for k,v in out['layers'].items(): print(k,v)
for k,v in out['cliffs'].items(): print(k,v['cov'],v['mask_mean_covered'],v['eff_hex'],v['eff_lum'],v['ao_mean_covered'],v['eff_x_ao_hex'],v['eff_x_ao_lum'])
