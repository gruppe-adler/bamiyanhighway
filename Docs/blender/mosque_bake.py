"""Re-unwrap Mosque_LOD0 and re-bake Mosque_01_MASK (R stripes/ribs, G worn, B grime) + Mosque_01_NMO (A = baked AO).
Run headless:  blender --factory-startup -b mosque_v4.blend --python mosque_bake.py   (saves mosque_v4_baked.blend, writes the two tifs into the addon)
1 UV unit = 87.65 m is kept so the tilings in the emats stay valid.
"""
import bpy, bmesh, numpy as np, math, os, time
from mathutils import Vector, noise

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul\Prefabs\Structures\Mosque_01"
OUT_BLEND = r"D:\gronom\Auftraege\2016\GruppeAdler\Modding\bamiyan_highway\blender\mosque\mosque_v4_baked.blend"
RES = 4096; M_PER_UV = 87.65; AO_SAMPLES = 24
T0 = time.time()
def log(*a): print(f'[{time.time()-T0:6.1f}s]', *a, flush=True)

o = bpy.data.objects['Mosque_LOD0']; me = o.data
for ob in bpy.data.objects:
    if ob.name.startswith('Pane_') : ob.hide_render = True; ob.hide_viewport = True
o.hide_render = False; o.hide_viewport = False; o.hide_set(False)      # the saved file may have it hidden
bpy.context.view_layer.objects.active = o
for ob in bpy.context.selected_objects: ob.select_set(False)
o.select_set(True)

# ---------- 0. clean mesh (duplicate verts / degenerate faces / invalid n-gons) ----------
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mosque_ngon_fix.py'), encoding='utf-8').read())
fix_ngons(me)

# ---------- 0b. flatten the old raised 3D ribs (they floated above the dome); ribs are painted flush instead ----------
def flatten_ribs():
    nv = len(me.vertices); c0 = np.zeros(nv * 3, np.float32); me.vertices.foreach_get('co', c0); c0 = c0.reshape(-1, 3)
    nr = np.zeros(nv * 3, np.float32); me.vertices.foreach_get('normal', nr); nr = nr.reshape(-1, 3)
    rho = np.hypot(c0[:, 0], c0[:, 1]); az = np.degrees(np.arctan2(c0[:, 1], c0[:, 0])) % 360; z = c0[:, 2]
    base = z[(rho < 6.3) & (z > 8.3)].min(); cen = np.array([0, 0, base])
    m = ((nr * (c0 - cen)).sum(1) > 0) & (z > 9.0) & (z < 14.8) & (rho > 1.2) & (rho < 6.3); moved = 0
    for zl in np.unique(np.round(z[m], 1)):
        idx = np.nonzero(m & (np.abs(z - zl) < 0.05))[0]
        if len(idx) < 40: continue
        a, r = az[idx], rho[idx]
        med = np.array([np.median(r[np.abs(((a - ai + 180) % 360) - 180) < 15]) for ai in a])
        sel = (r - med) > 0.008
        k = idx[sel]; sc = (med[sel] / r[sel])
        c0[k, 0] *= sc; c0[k, 1] *= sc; moved += int(sel.sum())
    me.vertices.foreach_set('co', c0.reshape(-1)); me.update(); return moved
FLATTEN_RIBS = False     # user removed the raised paint faces from the dome (2026-10-25); flattening would now smooth the dome imperfections
if FLATTEN_RIBS: print('ribs flattened (vertices):', flatten_ribs())

# ---------- 1. new UV layout ----------
bpy.context.scene.tool_settings.use_uv_select_sync = True      # uv operators only act on the mesh selection in headless mode
for u in list(me.uv_layers):
    if u.name == 'BakeUV': me.uv_layers.remove(u)
uvl = me.uv_layers.new(name='BakeUV'); me.uv_layers.active = uvl
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(70), margin_method='FRACTION', island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
bm = bmesh.new(); bm.from_mesh(me); uv = bm.loops.layers.uv['BakeUV']
A_world = sum(f.calc_area() for f in bm.faces)
def uvarea(): return sum(abs(sum(f.loops[i][uv].uv.x * f.loops[(i + 1) % len(f.loops)][uv].uv.y - f.loops[(i + 1) % len(f.loops)][uv].uv.x * f.loops[i][uv].uv.y for i in range(len(f.loops)))) / 2 for f in bm.faces)
k = math.sqrt((A_world / M_PER_UV ** 2) / uvarea())
for f in bm.faces:
    for l in f.loops: l[uv].uv = (l[uv].uv.x * k, l[uv].uv.y * k)
bm.to_mesh(me); bm.free(); me.update()
log('islands unwrapped, world area', round(A_world), 'scale', k)
def read_uv():
    a = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers['BakeUV'].data.foreach_get('uv', a); return a.reshape(-1, 2)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=False, margin_method='FRACTION', margin=0.0012, pin=False, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')
uvs = read_uv(); log('packed 1:1 bounds', uvs.min(0), uvs.max(0))
if uvs.max() > 1.0 or uvs.min() < 0.0:
    # does not fit at 87.65 m/uv: fit into 0..1 (texel density slightly higher -> layer tiling grows by TILING_FACTOR, see print)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True, margin_method='FRACTION', margin=0.0012, pin=False, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT'); uvs = read_uv()
    me.calc_loop_triangles(); lt_ = me.loop_triangles; ln = np.zeros(len(lt_) * 3, np.int32); lt_.foreach_get('loops', ln); t = uvs[ln.reshape(-1, 3)]
    uva = float(np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1])).sum() / 2)
    log('fallback packing: density', round(math.sqrt(A_world / uva), 1), 'm/uv  => multiply all emat tilings by', round(M_PER_UV / math.sqrt(A_world / uva), 3))

# ---------- 2. per-texel world position via rasterisation ----------
tri_idx = np.zeros(len(me.loop_triangles) * 3, np.int32); me.calc_loop_triangles()
lt = me.loop_triangles; n_t = len(lt)
loops = np.zeros(n_t * 3, np.int32); lt.foreach_get('loops', loops); loops = loops.reshape(-1, 3)
verts = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', verts)
co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
def rib_vertex_flags():
    """vertices of the raised 3D dome ribs: radial residual against a circular rolling median (ribs are narrow, the dome unevenness is not)"""
    nr = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('normal', nr); nr = nr.reshape(-1, 3)
    rho = np.hypot(co[:, 0], co[:, 1]); az = np.degrees(np.arctan2(co[:, 1], co[:, 0])) % 360; z = co[:, 2]
    base = z[(rho < 6.3) & (z > 8.3)].min(); cen = np.array([0, 0, base])
    m = ((nr * (co - cen)).sum(1) > 0) & (z > 9.0) & (z < 14.8) & (rho > 1.2) & (rho < 6.3)
    flag = np.zeros(len(co), np.float32)
    for zl in np.unique(np.round(z[m], 1)):
        idx = np.nonzero(m & (np.abs(z - zl) < 0.05))[0]
        if len(idx) < 40: continue
        a, r = az[idx], rho[idx]
        med = np.array([np.median(r[np.abs(((a - ai + 180) % 360) - 180) < 15]) for ai in a])
        flag[idx[(r - med) > 0.012]] = 1.0
    return flag
ribv = rib_vertex_flags() if FLATTEN_RIBS else np.zeros(len(co), np.float32)
if 'Rib' in me.attributes:      # raised dome rib strips (top verts flagged 1.0 in mosque_v4.blend): painted with the band colour through the mask (material = plaster)
    ribv = np.zeros(len(me.vertices), np.float32); me.attributes['Rib'].data.foreach_get('value', ribv)
log('rib vertices flagged', int(ribv.sum()))
P = co[verts[loops]]                         # (n_t,3,3)
RV = ribv[verts[loops]]                      # (n_t,3)
UV = uvs[loops] * RES                        # (n_t,3,2) in texels
polyidx = np.zeros(n_t, np.int32); lt.foreach_get('polygon_index', polyidx)
nrm = np.zeros(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('normal', nrm); nrm = nrm.reshape(-1, 3)[polyidx]
ribmap = np.zeros((RES, RES), np.float32); pos = np.full((RES, RES, 3), np.nan, np.float32); nz = np.zeros((RES, RES), np.float32); cover = np.zeros((RES, RES), bool)
for t in range(n_t):
    a, b, c = UV[t]
    x0, x1 = int(np.floor(min(a[0], b[0], c[0]))) - 1, int(np.ceil(max(a[0], b[0], c[0]))) + 1
    y0, y1 = int(np.floor(min(a[1], b[1], c[1]))) - 1, int(np.ceil(max(a[1], b[1], c[1]))) + 1
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, RES - 1), min(y1, RES - 1)
    if x1 < x0 or y1 < y0: continue
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    w0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
    w1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
    w2 = 1 - w0 - w1; m = (w0 >= -0.01) & (w1 >= -0.01) & (w2 >= -0.01)
    if not m.any(): continue
    ys, xs = np.nonzero(m)
    p = w0[m][:, None] * P[t, 0] + w1[m][:, None] * P[t, 1] + w2[m][:, None] * P[t, 2]
    pos[ys + y0, xs + x0] = p; nz[ys + y0, xs + x0] = nrm[t][2]; cover[ys + y0, xs + x0] = True
    ribmap[ys + y0, xs + x0] = w0[m] * RV[t, 0] + w1[m] * RV[t, 1] + w2[m] * RV[t, 2]
log('rasterised', int(cover.sum()), 'texels =', round(cover.mean() * 100, 1), '%')

# dilate position map a few texels so bilinear/mips never sample empty texels
for _ in range(6):
    new = ~cover
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.roll(np.roll(cover, dy, 0), dx, 1); shp = np.roll(np.roll(pos, dy, 0), dx, 1); shn = np.roll(np.roll(nz, dy, 0), dx, 1)
        take = new & sh
        pos[take] = shp[take]; nz[take] = shn[take]; cover |= take; new = ~cover
log('dilated')

# ---------- 3. procedural masks ----------
X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
valid = cover
R = np.hypot(X, Y); AZ = np.degrees(np.arctan2(Y, X))
def band(z, lo, hi, soft=0.02): return np.clip(np.minimum(z - lo, hi - z) / soft, 0, 1)
stripe = np.zeros((RES, RES), np.float32)
body = (R > 8.2) & (Z < 5.7)
for lo, hi in ((1.0, 1.35), (1.9, 2.5), (3.45, 3.9), (5.35, 5.65)): stripe = np.maximum(stripe, band(Z, lo, hi) * body)
drum = (R < 6.4) & (Z > 6.05) & (Z < 8.5)
for lo, hi in ((6.15, 6.45), (7.72, 7.97), (8.0, 8.46)): stripe = np.maximum(stripe, band(Z, lo, hi) * drum)
dome = (R < 6.3) & (Z > 8.5) & (R > 1.0)
RIB_AZ, RIB_HALF = 25.3, 4.0                       # measured rib axes on the original model: 25.3 + 45k deg
RIB_PAINT = False        # ribs are real raised geometry with MOS_PAINT since 2026-10-25 (painted-on ribs had jagged edges)
if RIB_PAINT: stripe = np.maximum(stripe, np.clip((RIB_HALF + 0.4 - np.abs(((AZ - RIB_AZ + 22.5) % 45.0) - 22.5)) / 0.8, 0, 1) * dome * (Z > 9.1) * (Z < 14.8))
# dome rib strips have their own material (MOS_RIB), no mask paint needed
stripe[~valid] = 0
log('stripe done')

def fbm(px, py, pz, scale, octaves=4, seed=0.0):
    out = np.zeros(px.shape, np.float32); amp = 1.0; tot = 0.0; fr = scale
    rng = np.random.default_rng(int(seed * 1000) + 3)
    ph = rng.uniform(0, 100, (octaves, 3))
    for o_ in range(octaves):
        # cheap separable value noise via sines (vectorised; deterministic)
        out += amp * (np.sin(px * fr + ph[o_, 0]) * np.sin(py * fr * 1.13 + ph[o_, 1]) * np.sin(pz * fr * 0.87 + ph[o_, 2]) + np.sin(px * fr * 0.71 + py * fr * 1.31 + pz * fr * 0.53 + ph[o_, 1]))
        tot += amp * 2; amp *= 0.5; fr *= 2.03
    return out / tot * 0.5 + 0.5
worn_n = fbm(X, Y, Z, 1.1, 5, 1)
height_w = 0.35 + 0.65 * np.exp(-np.clip(Z, 0, None) / 1.6)
G = np.clip((worn_n - 0.52) * 3.2, 0, 1) * height_w * (0.6 + 0.4 * (1 - np.abs(nz)))
streak_n = fbm(X * 3.0, Y * 3.0, Z * 0.25, 1.0, 3, 2)
B = np.clip((streak_n - 0.45) * 2.0, 0, 1) * 0.5 + np.exp(-np.clip(Z, 0, None) / 0.9) * 0.45
def blur(a, r=4, it=3):                      # smooth the low-frequency masks: with 2.3 cm texels a hard noise mask shows up as big pixels; detail comes from the tiled layer textures
    a = a.astype(np.float32)
    for _ in range(it):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r, r) if i == ax else (0, 0) for i in range(2)], mode='edge'), axis=ax, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r, a.shape[ax] + 2 * r), axis=ax); lo = np.take(np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax), np.arange(0, a.shape[ax]), axis=ax)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a
G = blur(G); B = blur(B)
G[~valid] = 0; B[~valid] = 0
log('G/B done')

# ---------- 4. AO bake (Cycles) ----------
scn = bpy.context.scene; scn.render.engine = 'CYCLES'; scn.cycles.samples = AO_SAMPLES; scn.cycles.device = 'CPU'
scn.cycles.use_denoising = False
if scn.world is None: scn.world = bpy.data.worlds.new('w')
scn.world.light_settings.distance = 3.5
img = bpy.data.images.new('AO_bake', RES, RES, alpha=False, float_buffer=False); img.colorspace_settings.name = 'Non-Color'
mat = bpy.data.materials.new('bake_tmp'); mat.use_nodes = True
nt = mat.node_tree; tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img; nt.nodes.active = tn
saved = [m for m in me.materials]
for i in range(len(me.materials)): me.materials[i] = mat
me.uv_layers.active = me.uv_layers['BakeUV']
scn.render.bake.margin = 6; scn.render.bake.use_clear = True
bpy.ops.object.bake(type='AO')
for i, m in enumerate(saved): me.materials[i] = m
log('AO baked')
ao = np.array(img.pixels[:], np.float32).reshape(RES, RES, 4)[..., 0]
ao = 0.32 + 0.68 * np.clip(ao ** 1.1, 0, 1)      # never fully black: pure 0 AO showed as black glitches under roofs / in window reveals
bpy.data.materials.remove(mat)

# ---------- 4b. less uniform wear/grime: masks driven by AO cavity (convex edges = wear, concave/crevices = grime), top-facing dust, drips, macro patchiness ----------
ao_s = blur(ao, 6, 2)
cav = np.clip((ao_s - ao) * 5.0, 0, 1)                        # darker than surroundings -> crevice
conv = np.clip((ao - ao_s) * 6.0, 0, 1) * (ao > 0.85)           # brighter than surroundings -> exposed edge/corner
macro = fbm(X, Y, Z, 0.33, 3, 7); macro2 = fbm(X * 1.7, Y * 1.7, Z * 0.6, 0.9, 3, 11)
top = np.clip((nz - 0.6) / 0.4, 0, 1)                           # up-facing: dust, rain stains, bird droppings
drip = np.clip((fbm(X * 9.0 + Y * 9.0, X * 0, Z * 0.12, 1.0, 2, 5) - 0.5) * 3.0, 0, 1) * (np.abs(nz) < 0.35) * np.clip((Z - 1.5) / 3.0, 0, 1)   # vertical streaks on walls (stronger higher up)
G2 = np.clip(G * (0.25 + 1.1 * macro) + conv * 0.8 * (0.4 + macro2) + top * 0.18 * macro2, 0, 1)
B2 = np.clip(B * (0.4 + 0.9 * macro2) + cav * 0.6 + top * 0.3 * (0.5 + macro) + drip * 0.35, 0, 1)
G = blur(G2, 2, 1); B = blur(B2, 2, 1); G[~valid] = 0; B[~valid] = 0
log('AO-driven wear/grime done')

# ---------- 5. write textures (flip: blender image row 0 = bottom, same as UV v) ----------
def save_rgba(name, arr):
    """arr: float RGBA 0..1, row 0 = bottom (same as UV v=0)"""
    im = bpy.data.images.new(name, RES, RES, alpha=True, float_buffer=False); im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).reshape(-1)); im.update()
    im.filepath_raw = os.path.join(ADDON, name + '.tif'); im.file_format = 'TIFF'; im.save()
    bpy.data.images.remove(im)
mask = np.zeros((RES, RES, 4), np.float32); mask[..., 0] = stripe; mask[..., 1] = G * (0.9); mask[..., 2] = np.clip(B, 0, 0.6); mask[..., 3] = 1.0
nmo = np.zeros((RES, RES, 4), np.float32); nmo[..., 0] = 0.502; nmo[..., 1] = 0.502; nmo[..., 2] = 0.0; nmo[..., 3] = np.where(valid, ao, 1.0)
save_rgba('Mosque_01_MASK', mask); save_rgba('Mosque_01_NMO', nmo)
log('textures written')

# ---------- 6. finalise UV names ----------
for u in list(me.uv_layers):
    if u.name != 'BakeUV': me.uv_layers.remove(u)
me.uv_layers['BakeUV'].name = 'UVMap'
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
log('saved', OUT_BLEND)
