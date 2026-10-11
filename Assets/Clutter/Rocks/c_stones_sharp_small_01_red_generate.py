"""Clutter patch of small sharp stones (LOD0-LOD3) with an own baked texture set.

High poly = LOD0 subdivided (rounded edge band) + slight noise, shaded with a tileable rock
scan (box projected, red tint, height -> bump). Colour, roughness, normal and AO are baked onto
every LOD in one shared atlas; LOD0 gets most of the space, texture size is chosen from a
target texel density.

Run: blender --background --factory-startup --python make_stones4.py -- <out_dir> <rock_textures_dir> <preview_prefix>
"""
import bpy, bmesh, math, random, sys, os, glob
import numpy as np
from mathutils import Vector, Matrix

out_dir, rock_dir, preview = sys.argv[sys.argv.index("--") + 1:]
data_dir = os.path.join(out_dir, "Data")
NAME = "c_stones_sharp_small_01_red"
STONES = 20
PATCH_RADIUS = 1.4
GAP = 0.04
LOD_POINTS = [22, 15, 10, 6]          # ~2x the triangles of the previous version
LOD_KEEP = [1.0, 1.0, 0.6, 0.3]
LOD_UV_SCALE = [1.0, 0.5, 0.35, 0.25]  # texture space per LOD relative to LOD0 (linear)
TARGET_PX_PER_M = 900                  # LOD0 texel density goal (~1 px per mm)
ROCK_TILE_M = 0.6                      # one repeat of the rock scan covers this many metres
TINT = (0.888, 0.533, 0.402, 1)        # Color of c_stones_sharp_01_red.emat
EXPLODE = 3.0                          # stones are spread this far apart while baking

random.seed(4711)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
vl = bpy.context.view_layer


def find(pattern):
    return glob.glob(os.path.join(rock_dir, pattern))[0]


# ---------------- stones ----------------
def stone_points(size):
    sx, sy, sz = size * random.uniform(0.8, 1.3), size * random.uniform(0.6, 1.0), size * random.uniform(0.35, 0.6)
    pts = []
    for _ in range(LOD_POINTS[0]):
        d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
        r = random.uniform(0.75, 1.0)
        pts.append(Vector((d.x * sx * r, d.y * sy * r, d.z * sz * r)))
    order = [max(pts, key=lambda p: p.length)]
    rest = [p for p in pts if p is not order[0]]
    while rest:
        nxt = max(rest, key=lambda p: min((p - q).length for q in order))
        order.append(nxt); rest.remove(nxt)
    return order


stones, attempts = [], 0
while len(stones) < STONES and attempts < 20000:
    attempts += 1
    size = random.uniform(0.06, 0.18) * (1.6 if random.random() < 0.2 else 1.0)
    rot = Matrix.Rotation(random.uniform(0, math.tau), 3, 'Z') @ Matrix.Rotation(random.uniform(-0.35, 0.35), 3, 'X')
    pts = [rot @ p for p in stone_points(size)]
    foot = max(Vector((p.x, p.y)).length for p in pts)
    ang, rad = random.uniform(0, math.tau), (PATCH_RADIUS - foot) * math.sqrt(random.random())
    loc = Vector((math.cos(ang) * rad, math.sin(ang) * rad, size * 0.2))
    if all((loc.xy - o[1].xy).length >= foot + o[2] + GAP for o in stones):
        stones.append((size, loc, foot, pts))
assert len(stones) == STONES
stones.sort(key=lambda s: -s[0])


def select_only(objs, active):
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


low_mat = bpy.data.materials.new(NAME)   # slot name -> c_stones_sharp_small_01_red.emat
lods = []
for lod, (npts, keep) in enumerate(zip(LOD_POINTS, LOD_KEEP)):
    count = max(1, round(STONES * keep))
    parts = []
    for i, (size, loc, foot, pts) in enumerate(stones[:count]):
        bm = bmesh.new()
        verts = [bm.verts.new(p + loc + Vector((i * EXPLODE, 0, 0))) for p in pts[:npts]]
        res = bmesh.ops.convex_hull(bm, input=verts)
        stray = {v for v in res["geom_interior"] + res["geom_unused"] if isinstance(v, bmesh.types.BMVert)}
        if stray:
            bmesh.ops.delete(bm, geom=list(stray), context='VERTS')
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(f"tmp_{lod}_{i}")
        bm.to_mesh(me); bm.free()
        me.attributes.new("sid", 'INT', 'POINT').data.foreach_set("value", [i] * len(me.vertices))
        me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            poly.use_smooth = False
        me.materials.append(low_mat)
        part = bpy.data.objects.new(me.name, me)
        sc.collection.objects.link(part)
        parts.append(part)
    select_only(parts, parts[0])
    bpy.ops.object.join()
    ob = vl.objects.active
    ob.name = ob.data.name = f"{NAME}_LOD{lod}"
    lods.append(ob)
    print(f"LOD{lod}: stones={count} verts={len(ob.data.vertices)} tris={len(ob.data.polygons)}")

# ---------------- atlas: unwrap together (keeps world scale ratios), shrink lower LODs, pack ----------------
select_only(lods, lods[0])
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(70), island_margin=0.0, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
for ob, s in zip(lods, LOD_UV_SCALE):
    for d in ob.data.uv_layers[0].data:
        d.uv = d.uv * s
select_only(lods, lods[0])
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.select_all(action='SELECT')   # pack only touches selected UVs
bpy.ops.uv.pack_islands(margin=0.002, rotate=True, rotate_method='ANY', shape_method='CONCAVE', margin_method='FRACTION')
bpy.ops.object.mode_set(mode='OBJECT')


def uv_and_3d_area(ob):
    me = ob.data
    uv = me.uv_layers[0].data
    a_uv = a_3d = 0.0
    for p in me.polygons:
        (a, b, c) = [uv[i].uv for i in p.loop_indices[:3]]
        a_uv += abs((b - a).cross(c - a)) / 2
        a_3d += p.area
    return a_uv, a_3d


a_uv, a_3d = uv_and_3d_area(lods[0])
print(f"UV fill: LOD0 {a_uv:.0%}, all LODs {sum(uv_and_3d_area(o)[0] for o in lods):.0%}")
px_per_m_at_1 = math.sqrt(a_uv / a_3d)   # texels per metre for a 1 px texture
TEX = next((t for t in (512, 1024, 2048) if t * px_per_m_at_1 >= TARGET_PX_PER_M), 4096)
print(f"texture {TEX}px -> LOD0 {TEX * px_per_m_at_1:.0f} px/m "
      f"(LOD1 {TEX * px_per_m_at_1 * LOD_UV_SCALE[1]:.0f}, LOD3 {TEX * px_per_m_at_1 * LOD_UV_SCALE[3]:.0f})")

# ---------------- high poly ----------------
high = lods[0].copy(); high.data = lods[0].data.copy(); high.name = "high"
sc.collection.objects.link(high)
for poly in high.data.polygons:
    poly.use_smooth = True       # subdivided flat faces + smooth normals = rounded edge band
sub = high.modifiers.new("sub", 'SUBSURF'); sub.subdivision_type = 'SIMPLE'; sub.levels = sub.render_levels = 3
tn = bpy.data.textures.new("n", 'CLOUDS'); tn.noise_scale = 0.012; tn.noise_depth = 3
dp = high.modifiers.new("d", 'DISPLACE'); dp.texture = tn; dp.texture_coords = 'GLOBAL'; dp.strength = 0.0025
select_only([high], high)
for m in list(high.modifiers):
    bpy.ops.object.modifier_apply(modifier=m.name)
print("high poly tris:", len(high.data.polygons))

hm = bpy.data.materials.new("high_mat"); hm.use_nodes = True
N, L = hm.node_tree.nodes, hm.node_tree.links
bsdf = N["Principled BSDF"]
tc = N.new("ShaderNodeTexCoord")
mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / ROCK_TILE_M,) * 3
L.new(tc.outputs["Object"], mp.inputs["Vector"])


def box_tex(path, colorspace):
    t = N.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path); t.image.colorspace_settings.name = colorspace
    t.projection = 'BOX'; t.projection_blend = 0.3; t.interpolation = 'Cubic'
    L.new(mp.outputs[0], t.inputs[0])
    return t


diff = box_tex(find("*diff*"), 'sRGB')
rough = box_tex(find("*rough*"), 'Non-Color')
disp = box_tex(find("*disp*"), 'Non-Color')
tint = N.new("ShaderNodeMix"); tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'; tint.inputs["Factor"].default_value = 1
tint.inputs[7].default_value = TINT
L.new(diff.outputs["Color"], tint.inputs[6])
L.new(tint.outputs[2], bsdf.inputs["Base Color"])
L.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.004
L.new(disp.outputs["Color"], bump.inputs["Height"])
L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
high.data.materials.clear(); high.data.materials.append(hm)

bpy.ops.mesh.primitive_plane_add(size=1, location=(STONES * EXPLODE / 2, 0, 0))   # contact AO only
vl.objects.active.scale = (STONES * EXPLODE + 6, 6, 1)
ground = vl.objects.active

# ---------------- bake ----------------
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 16
bk = sc.render.bake
bk.use_selected_to_active = True
bk.cage_extrusion = 0.08
bk.max_ray_distance = 0.2
bk.margin = 16
bk.margin_type = 'EXTEND'
bk.use_pass_direct = bk.use_pass_indirect = False
bk.use_pass_color = True

low_mat.use_nodes = True
img_node = low_mat.node_tree.nodes.new("ShaderNodeTexImage")
low_mat.node_tree.nodes.active = img_node


def bake_lod(lod_ob, kind, margin=16, **kw):
    img = bpy.data.images.new(f"{kind}_{lod_ob.name}", TEX, TEX, alpha=True, float_buffer=True)
    img.generated_color = (0, 0, 0, 0)
    img.colorspace_settings.name = 'Non-Color'
    img_node.image = img
    for o in lods:
        o.hide_render = o is not lod_ob
        o.visible_diffuse = o.visible_glossy = o.visible_shadow = o.visible_transmission = False
    select_only([high, lod_ob], lod_ob)
    bk.margin = margin
    bk.margin_type = 'EXTEND' if margin else 'ADJACENT_FACES'   # EXTEND with 0 px still floods the image
    bpy.ops.object.bake(type=kind, **kw)
    return np.array(img.pixels[:], np.float32).reshape(TEX, TEX, 4)


maps = {k: [] for k in ("albedo", "rough", "normal", "ao")}


def uv_mask(ob):
    """Pixels whose centre lies inside one of this LOD's UV triangles."""
    m = np.zeros((TEX, TEX), bool)
    uv = ob.data.uv_layers[0].data
    for p in ob.data.polygons:
        t = np.array([uv[i].uv[:] for i in p.loop_indices[:3]]) * TEX - 0.5
        x0, y0 = np.floor(t.min(0)).astype(int); x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, TEX - 1), min(y1, TEX - 1)
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax, ay), (bx, by), (cx, cy) = t
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= 0) & (l2 >= 0) & (1 - l1 - l2 >= 0)
        m[y0:y1 + 1, x0:x1 + 1] |= inside
    return m


masks = [uv_mask(ob) for ob in lods]
for ob in lods:
    maps["albedo"].append(bake_lod(ob, 'DIFFUSE'))
    maps["rough"].append(bake_lod(ob, 'ROUGHNESS'))
    maps["normal"].append(bake_lod(ob, 'NORMAL', normal_space='TANGENT'))
    maps["ao"].append(bake_lod(ob, 'AO'))
    print("baked", ob.name)


def composite(layers, bleed=16):
    # inside an island: that LOD's bake; around it: that LOD's own bake margin; rest: bleed
    out = np.zeros((TEX, TEX, 3), np.float32); cov = np.zeros((TEX, TEX), bool)
    grown = [m.copy() for m in masks]
    for g in grown:
        for _ in range(3):
            g |= np.roll(g, 1, 0) | np.roll(g, -1, 0) | np.roll(g, 1, 1) | np.roll(g, -1, 1)
    for sel in (masks, grown):
        for lay, m in zip(layers, sel):
            m = m & ~cov
            out[m] = lay[..., :3][m]; cov |= m
    for _ in range(bleed):
        grow = np.zeros_like(cov); acc = np.zeros_like(out); cnt = np.zeros((TEX, TEX), np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sc_ = np.roll(cov, (dy, dx), (0, 1)); so = np.roll(out, (dy, dx), (0, 1))
            add = sc_ & ~cov
            acc[add] += so[add]; cnt[add] += 1; grow |= add
        out[grow] = acc[grow] / cnt[grow][:, None]; cov |= grow
    return out


def push_pull(img, mask):
    """Fill everything outside the islands from the nearest covered area, so mips never see empty texels."""
    levels = [(img * mask[..., None], mask.astype(np.float32))]
    while levels[-1][1].shape[0] > 1:
        c, w = levels[-1]; h2 = c.shape[0] // 2
        levels.append((c.reshape(h2, 2, h2, 2, -1).sum((1, 3)), w.reshape(h2, 2, h2, 2).sum((1, 3))))
    filled = levels[-1][0] / np.maximum(levels[-1][1], 1e-6)[..., None]
    for c, w in reversed(levels[:-1]):
        up = filled.repeat(2, 0).repeat(2, 1)
        filled = np.where((w > 0)[..., None], c / np.maximum(w, 1e-6)[..., None], up)
    return filled


_composite = composite
union = np.logical_or.reduce(masks)
def composite(layers, bleed=8):
    out = _composite(layers, bleed)
    keep = union.copy()
    for _ in range(bleed):
        keep |= np.roll(keep, 1, 0) | np.roll(keep, -1, 0) | np.roll(keep, 1, 1) | np.roll(keep, -1, 1)
    out[~keep] = push_pull(out, keep)[~keep]
    return out


albedo = composite(maps["albedo"])
rough_c = composite(maps["rough"])[..., 0]
normal = composite(maps["normal"])
ao = composite(maps["ao"])[..., 0]
print(f"atlas coverage {sum(m.sum() for m in masks) / TEX / TEX:.0%}")


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def save(name, rgba):
    img = bpy.data.images.new(name, TEX, TEX, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.clip(rgba, 0, 1).astype(np.float32).ravel())
    img.filepath_raw = os.path.join(data_dir, name + ".png"); img.file_format = 'PNG'; img.save()
    print("SAVED", img.filepath_raw)


os.makedirs(data_dir, exist_ok=True)
base = to_srgb(albedo * (0.5 + 0.5 * ao)[..., None])
save(NAME + "_BCR", np.dstack([base, rough_c]))
save(NAME + "_NMO", np.dstack([normal[..., 0], 1.0 - normal[..., 1], np.zeros_like(ao), ao]))

# ---------------- export ----------------
bpy.data.objects.remove(high); bpy.data.objects.remove(ground)
img_node.image = None
for ob in lods:
    ob.hide_render = False
    sid = [0] * len(ob.data.vertices)
    ob.data.attributes["sid"].data.foreach_get("value", sid)
    for v, i in zip(ob.data.vertices, sid):
        v.co.x -= i * EXPLODE
    ob.data.attributes.remove(ob.data.attributes["sid"])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, NAME + ".blend"))
select_only(lods, lods[0])
bpy.ops.export_scene.fbx(
    filepath=os.path.join(out_dir, NAME + ".fbx"), use_selection=True,
    apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE',
    add_leaf_bones=False, bake_anim=False,
)
print("EXPORTED")

# ---------------- preview ----------------
bcr = bpy.data.images.load(os.path.join(data_dir, NAME + "_BCR.png"))
nmo = bpy.data.images.load(os.path.join(data_dir, NAME + "_NMO.png")); nmo.colorspace_settings.name = 'Non-Color'
pm = bpy.data.materials.new("prev"); pm.use_nodes = True
N, L = pm.node_tree.nodes, pm.node_tree.links
b = N["Principled BSDF"]
t1 = N.new("ShaderNodeTexImage"); t1.image = bcr
L.new(t1.outputs["Color"], b.inputs["Base Color"]); L.new(t1.outputs["Alpha"], b.inputs["Roughness"])
t2 = N.new("ShaderNodeTexImage"); t2.image = nmo
sep = N.new("ShaderNodeSeparateColor"); L.new(t2.outputs["Color"], sep.inputs[0])
inv = N.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1
L.new(sep.outputs[1], inv.inputs[1])
comb = N.new("ShaderNodeCombineColor"); L.new(sep.outputs[0], comb.inputs[0]); L.new(inv.outputs[0], comb.inputs[1])
comb.inputs[2].default_value = 1
nm = N.new("ShaderNodeNormalMap"); L.new(comb.outputs[0], nm.inputs["Color"]); L.new(nm.outputs[0], b.inputs["Normal"])
for ob in lods:
    ob.data.materials[0] = pm
    ob.hide_render = not ob.name.endswith("LOD0")
    ob.visible_diffuse = ob.visible_glossy = ob.visible_shadow = True
bpy.ops.mesh.primitive_plane_add(size=6)
gm = bpy.data.materials.new("g"); gm.diffuse_color = (0.25, 0.3, 0.4, 1); vl.objects.active.data.materials.append(gm)
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sun.rotation_euler = (0.8, 0.2, 0.9); sun.data.energy = 3.5
sc.collection.objects.link(sun)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
shots = [(f"lod{i}", (0, -2.4, 1.6), (math.radians(55), 0, 0), 32, i) for i in range(len(lods))]
shots.append(("close", (stones[0][1].x, stones[0][1].y - 0.45, 0.3), (math.radians(62), 0, 0), 50, 0))
for tag, loc, rot, lens, show in shots:
    for i, ob in enumerate(lods):
        ob.hide_render = i != show
    cam.location, cam.rotation_euler, cam.data.lens = loc, rot, lens
    sc.render.filepath = f"{preview}_{tag}.png"
    bpy.ops.render.render(write_still=True)
