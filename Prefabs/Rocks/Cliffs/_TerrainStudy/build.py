"""Terrain candidate builder. python -I build.py <R> <outdir> [names...]
Builds tileable BCR(RGBA: sRGB colour + roughness) / NMO(RGBA: normal RG, metal B, AO A) from the shared cliff layers.
Tile = 8 m: Rock x4 (2.0 m), Sand x3 (2.67 m, cliff 2.7), Scree x2 (4.0 m, cliff 3.3), Pale x2 (4.0 m, cliff 4.1)."""
import numpy as np, sys, os, json
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
HERE=os.path.dirname(os.path.abspath(__file__)); LAY=os.path.join(HERE,'..','_Layers')
LN={'Rock':'RockPorous','Sand':'Sand','Scree':'Scree','Pale':'SandstonePale'}
REP={'Rock':4,'Sand':3,'Scree':2,'Pale':2}
LUMW=np.array([.2126,.7152,.0722],np.float32)
def s2l(x): return np.where(x<=0.04045,x/12.92,((x+0.055)/1.055)**2.4).astype(np.float32)
def l2s(x): x=np.clip(x,0,1); return np.where(x<=0.0031308,12.92*x,1.055*x**(1/2.4)-0.055).astype(np.float32)

def resample(src,N,R):
    """periodic: tile src N times into RxR, area-prefiltered, bilinear with wrap"""
    S=src.shape[0]; d=S*N/R
    if d>1.0:
        sig=0.42*d
        f=np.fft.fftfreq(S).astype(np.float32); fr=np.fft.rfftfreq(S).astype(np.float32)
        g=np.exp(-2*np.pi**2*sig**2*(f[:,None]**2+fr[None,:]**2)).astype(np.float32)
        src=np.fft.irfft2(np.fft.rfft2(src)*g,s=(S,S)).astype(np.float32)
    u=((np.arange(R)*N/R)%1.0)*S
    i0=np.floor(u).astype(int)%S; i1=(i0+1)%S; fx=(u-np.floor(u)).astype(np.float32)
    a=src[i0]; b=src[i1]
    rows=lambda m:(1-fx)[None,:]*m[:,i0]+fx[None,:]*m[:,i1]
    ra=rows(a); rb=rows(b)
    return ((1-fx)[:,None]*ra+fx[:,None]*rb).astype(np.float32)

def load_layer(k,R):
    n=LN[k]; N=REP[k]
    b=np.array(Image.open(f'{LAY}/CliffLayer_{n}_BCR.tif')).astype(np.float32)/255
    m=np.array(Image.open(f'{LAY}/CliffLayer_{n}_NMO.tif')).astype(np.float32)/255
    h=np.array(Image.open(f'{LAY}/CliffLayer_{n}_DETAIL_MASK.tif')).astype(np.float32)/255
    L={}
    lin=s2l(b[...,:3])
    L['rgb']=np.stack([resample(lin[...,c],N,R) for c in range(3)],-1)
    L['rough']=resample(b[...,3],N,R)
    L['nx']=resample(m[...,0]*2-1,N,R); L['ny']=resample(m[...,1]*2-1,N,R)
    L['ao']=resample(m[...,3],N,R); L['h']=resample(h,N,R)
    # height: normalise to 0..1 by percentiles so layers compete evenly
    lo,hi=np.percentile(L['h'][::7,::7],[2,98]); L['h']=np.clip((L['h']-lo)/(hi-lo),0,1)
    return L

def pnoise(R,cyc,beta,seed):
    """periodic noise, uniform 0..1 (rank), features ~ R/cyc px. cyc = lowest cycles per tile."""
    rng=np.random.default_rng(seed)
    w=rng.standard_normal((R,R)).astype(np.float32)
    F=np.fft.rfft2(w)
    f=np.fft.fftfreq(R)*R; fr=np.fft.rfftfreq(R)*R
    rad=np.sqrt(f[:,None]**2+fr[None,:]**2).astype(np.float32)
    amp=np.where(rad>=cyc,(np.maximum(rad,1e-3)/cyc)**(-beta/2),0).astype(np.float32)
    amp[rad>R/4]=0   # keep it smooth, no pixel-scale noise
    x=np.fft.irfft2(F*amp,s=(R,R)).astype(np.float32)
    flat=x.ravel(); o=np.argsort(flat); r=np.empty(flat.size,np.float32); r[o]=np.linspace(0,1,flat.size,dtype=np.float32)
    return r.reshape(R,R)
def sstep(a,b,x): t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)

def build(recipe,R,Ls,seed):
    """recipe: base, overlays [(layer,frac,cyc,beta,soft)], depth, nstrength, rough_off"""
    keys=['Rock','Sand','Scree','Pale']
    w={k:np.zeros((R,R),np.float32) for k in keys}; w[recipe['base']][:]=1
    for j,(k,frac,cyc,beta,soft) in enumerate(recipe['over']):
        n=pnoise(R,cyc,beta,seed*100+j)
        m=sstep(frac+soft,frac-soft,n)           # frac = coverage
        for kk in keys: w[kk]*=(1-m)
        w[k]+=m
    d=recipe.get('depth',0.25)
    sc={k:Ls[k]['h']*recipe.get('hmix',1.0)+w[k] for k in keys}
    top=np.maximum.reduce([sc[k] for k in keys])
    b={k:np.maximum(sc[k]-top+d,0)*(w[k]>0.002) for k in keys}
    tot=sum(b.values())+1e-6
    b={k:b[k]/tot for k in keys}
    mix=lambda f:sum(b[k]*Ls[k][f] for k in keys)
    rgb=sum(b[k][...,None]*Ls[k]['rgb'] for k in keys)
    out=dict(rgb=rgb,rough=mix('rough'),nx=mix('nx'),ny=mix('ny'),ao=mix('ao'),h=mix('h'),w=b)
    # colour grading to target mean (linear) and contrast control
    tl=np.array(recipe['target'],np.float32)
    c=recipe.get('contrast',1.0)
    if c!=1.0:
        lum=rgb@LUMW; mu=lum.mean()
        rgb=rgb*(((lum-mu)*c+mu)/np.maximum(lum,1e-4))[...,None]
    gain=tl/rgb.reshape(-1,3).mean(0); rgb=rgb*gain
    out['rgb']=np.clip(rgb,0,1); out['gain']=gain
    s=recipe.get('nstrength',1.0); out['nx']*=s; out['ny']*=s
    out['rough']=np.clip(out['rough']+recipe.get('rough_off',0),0,1)
    out['cover']={k:float(b[k].mean()) for k in keys}
    return out

def pack(o):
    bcr=np.dstack([l2s(o['rgb']),o['rough']]); nmo=np.dstack([o['nx']*.5+.5,o['ny']*.5+.5,np.zeros_like(o['rough']),o['ao']])
    q=lambda a:(np.clip(a,0,1)*255+.5).astype(np.uint8)
    return q(bcr),q(nmo)

# ---- targets ---------------------------------------------------------------
EFF=np.array([0.3118,0.12749,0.07117],np.float32)       # mean of 18 cliffs' mask-weighted layer means (linear), lum .1626
def tgt(lum,chroma=EFF):
    c=chroma/(chroma@LUMW); return c*lum
SANDC=np.array([0.3444,0.2046,0.1018],np.float32)
RECIPES={
 'FootDebris':dict(base='Scree',over=[('Rock',0.28,8,1.8,0.14),('Sand',0.14,6,1.8,0.12),('Pale',0.06,10,1.6,0.10)],
                   target=tgt(0.128),depth=0.55,hmix=0.45,contrast=1.0,nstrength=1.0),
 'DustyTransition':dict(base='Sand',over=[('Rock',0.14,8,1.8,0.14),('Scree',0.14,10,1.7,0.12),('Pale',0.12,6,1.8,0.14)],
                   target=tgt(0.185,0.65*EFF/(EFF@LUMW)+0.35*SANDC/(SANDC@LUMW)),depth=0.6,hmix=0.35,contrast=0.8,nstrength=0.75,rough_off=0.0),
 'CliffMatch':dict(base='Rock',over=[('Sand',0.24,6,1.8,0.14),('Scree',0.08,8,1.7,0.10),('Pale',0.10,6,1.8,0.14)],
                   target=tgt(0.1626),depth=0.55,hmix=0.45,contrast=1.0,nstrength=1.0),
}
if __name__=='__main__':
    R=int(sys.argv[1]); od=sys.argv[2]; names=sys.argv[3:] or list(RECIPES)
    os.makedirs(od,exist_ok=True)
    Ls={k:load_layer(k,R) for k in REP}
    for nm in names:
        o=build(RECIPES[nm],R,Ls,seed=abs(hash(nm))%97+1 if False else {'FootDebris':11,'DustyTransition':23,'CliffMatch':37}[nm])
        bcr,nmo=pack(o)
        np.save(os.path.join(od,f'{nm}_bcr.npy'),bcr); np.save(os.path.join(od,f'{nm}_nmo.npy'),nmo)
        json.dump(dict(cover=o['cover'],gain=o['gain'].tolist()),open(os.path.join(od,f'{nm}_info.json'),'w'))
        print(nm,o['cover'],o['gain'])
