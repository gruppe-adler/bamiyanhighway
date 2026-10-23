"""python -I preview.py <npy_dir> <out_dir> [tag] [names]"""
import numpy as np, sys, os, json
from PIL import Image, ImageDraw
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from build import l2s, s2l, EFF, LUMW, RECIPES
d,od=sys.argv[1],sys.argv[2]; tag=sys.argv[3] if len(sys.argv)>3 else ''
names=sys.argv[4:] or list(RECIPES)
pal=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'palette_analysis.json')))
def sw(lin): return tuple(int(x) for x in (l2s(np.array(lin,np.float32))*255+.5))
for nm in names:
    bcr=np.load(f'{d}/{nm}_bcr.npy'); R=bcr.shape[0]
    img=Image.fromarray(bcr[...,:3])
    # 3x3 tile (each 480)
    t=img.resize((480,480),Image.LANCZOS); big=Image.new('RGB',(1440,1440))
    for i in range(3):
        for j in range(3): big.paste(t,(i*480,j*480))
    big.save(f'{od}/{nm}{tag}_tile3x3.png')
    # sheet
    W=1400; sh=Image.new('RGB',(W,1000),(40,40,40)); dr=ImageDraw.Draw(sh)
    sh.paste(img.resize((640,640),Image.LANCZOS),(10,10))
    c=img.crop((R//2-256*R//1024,R//2-256*R//1024,R//2+256*R//1024,R//2+256*R//1024)).resize((640,640),Image.NEAREST if R<=1024 else Image.LANCZOS)
    sh.paste(c,(660,10)); dr.text((660,652),f'1:1-ish crop (centre {512*R//1024}px of {R})',fill=(255,255,255))
    lin=s2l(bcr[...,:3].astype(np.float32)/255).reshape(-1,3).mean(0,dtype=np.float64)
    eff=np.mean([v['eff_linear'] for v in pal['cliffs'].values()],0); ao=np.mean([v['ao_mean_covered'] for v in pal['cliffs'].values()])
    items=[('cliff eff (raw)',eff),('cliff eff x AO',eff*ao),('THIS tex mean',lin)]+[(f'layer {k}',pal['layers'][k]['linear_mean']) for k in ('Rock','Sand','Scree','Pale')]
    x=10
    for lab,col in items:
        dr.rectangle([x,700,x+185,860],fill=sw(col)); dr.text((x+4,864),lab,fill=(255,255,255)); dr.text((x+4,878),'#%02x%02x%02x lum %.3f'%(*sw(col),np.array(col)@LUMW),fill=(255,255,255)); x+=195
    # tex vs cliff-eff side-by-side swatch strip
    sh.save(f'{od}/{nm}{tag}_sheet.png')
    # roughness / normal view
    nmo=np.load(f'{d}/{nm}_nmo.npy'); nv=Image.fromarray(nmo[...,:2].copy().__array__().astype(np.uint8)) if False else None
    n3=np.dstack([nmo[...,0],nmo[...,1],np.full(nmo.shape[:2],255,np.uint8)]); 
    Image.fromarray(n3).resize((640,640),Image.LANCZOS).save(f'{od}/{nm}{tag}_normal.png')
    # numeric wrap test
    a=bcr[...,:3].astype(np.float32)
    nbr=np.abs(a[:,1:]-a[:,:-1]).mean(); wrapx=np.abs(a[:,0]-a[:,-1]).mean(); wrapy=np.abs(a[0]-a[-1]).mean(); nby=np.abs(a[1:]-a[:-1]).mean()
    lum=(lin@LUMW)
    print(nm,'wrapX %.3f vs nbrX %.3f | wrapY %.3f vs nbrY %.3f'%(wrapx,nbr,wrapy,nby),'mean lin',lin.round(4),'lum %.4f'%lum,'lum std(srgb8) %.1f'%(a@LUMW).std(),'rough %.3f'%(bcr[...,3].mean()/255))
