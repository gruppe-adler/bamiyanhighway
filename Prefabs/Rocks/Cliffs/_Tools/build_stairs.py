"""Procedural rubble-stone stair for MatPBRMulti (cliff layers): stepped earth core + rounded stones, buried base.
usage: blender -b --factory-startup -P build_stairs.py -- <out work_v3.blend> <out mask .npy> [steps] [width_m]
Units are metres, +Y is up the stairs, z=0 is the ground line at the foot (the body continues SINK m below it)."""
import bpy, bmesh, sys, os, json, time
import numpy as np
from mathutils import Vector, Euler, noise
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uvcharts

a = sys.argv[sys.argv.index("--") + 1:]
out_blend, out_npy = a[0], a[1]
N = int(a[2]) if len(a) > 2 else 12
W = float(a[3]) if len(a) > 3 else 3.0
RISE, RUN, SINK = 0.18, 0.38, 1.2
LOD0_TRIS, RES = 40000, 2048
rng = np.random.default_rng(7)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
scene = bpy.context.scene


def activate(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


# ---- earth core: stepped profile extruded along x, tops 7 cm below the stone tops
top = [(i + 1) * RISE - 0.09 for i in range(N)]
prof = [(0, -SINK), (0, top[0])]
for i in range(N):
    prof.append(((i + 1) * RUN, top[i]))
    if i + 1 < N:
        prof.append(((i + 1) * RUN, top[i + 1]))
prof.append((N * RUN, -SINK))
bm = bmesh.new()
f = bm.faces.new([bm.verts.new((-W / 2, y, z)) for y, z in prof])
r = bmesh.ops.extrude_face_region(bm, geom=[f])
bmesh.ops.translate(bm, verts=[v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)], vec=(W, 0, 0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
me = bpy.data.meshes.new("earth")
bm.to_mesh(me)
bm.free()
earth = bpy.data.objects.new("earth", me)
scene.collection.objects.link(earth)
parts, stones = [earth], []


def stone_mesh(c, h, yaw, tilt, seed):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    R = Euler((tilt[0], tilt[1], yaw)).to_matrix()
    for v in bm.verts:
        p = Vector(v.co)
        q = p.lerp(p / p.length * 1.15, 0.6) if p.length > 0 else p
        q = Vector((q.x * h[0], q.y * h[1], q.z * h[2]))
        q += q.normalized() * 0.018 * noise.fractal(q * 4 + Vector((seed, 0, 0)), 0.6, 2.0, 3)
        v.co = R @ q + Vector(c)
    me = bpy.data.meshes.new("stone")
    bm.to_mesh(me)
    bm.free()
    return me


for i in range(N):
    x = -W / 2 + float(rng.uniform(-0.25, 0.0))
    while x < W / 2 - 0.1:
        w = float(rng.uniform(0.8, 1.5))
        if W / 2 - (x + w) < 0.6:
            w = W / 2 - x + 0.1
        xl, xr = max(x, -W / 2 - 0.05), min(x + w, W / 2 + 0.05)
        gap = float(rng.uniform(0.05, 0.1))
        h = (max(xr - xl - gap, 0.35) / 2, (RUN + 0.15) / 2 * float(rng.uniform(0.9, 1.15)), float(rng.uniform(0.12, 0.2)))
        ztop = (i + 1) * RISE + float(rng.uniform(-0.03, 0.05))
        c = ((xl + xr) / 2, i * RUN + RUN / 2 + 0.03 + float(rng.uniform(-0.04, 0.04)), ztop - h[2])
        yaw = float(rng.uniform(-0.12, 0.12))
        tilt = (float(rng.uniform(-0.07, 0.07)), float(rng.uniform(-0.07, 0.07)))
        kind = 1 if rng.uniform() < 0.35 else 0       # 1 = dark stone (mask G), 0 = tan stone (mask B)
        stones.append((c, h, yaw, tilt, kind))
        ob = bpy.data.objects.new("stone", stone_mesh(c, h, yaw, tilt, len(stones)))
        scene.collection.objects.link(ob)
        parts.append(ob)
        x += w
print("S_STONES", len(stones))

# ---- weld into one closed solid (voxel remesh = boolean union), then surface noise
bpy.ops.object.select_all(action='DESELECT')
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = earth
bpy.ops.object.join()
high = bpy.context.active_object
high.name = "HIGH"
t = time.time()
high.data.remesh_voxel_size = 0.018
high.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
n = len(high.data.vertices)
co = np.empty(n * 3)
high.data.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
nm = np.empty(n * 3)
high.data.vertices.foreach_get("normal", nm)
nm = nm.reshape(-1, 3)
d = np.array([0.014 * noise.fractal(Vector(p * 5), 0.7, 2.0, 3) + 0.004 * noise.fractal(Vector(p * 23), 0.7, 2.0, 2) for p in co])
high.data.vertices.foreach_set("co", (co + nm * d[:, None]).ravel())
high.data.update()
high.data.shade_smooth()
print("S_HIGH", len(high.data.polygons), "faces", round(time.time() - t, 1), "s")

# ---- LOD0
lod0 = high.copy()
lod0.data = high.data.copy()
lod0.name = lod0.data.name = "LOD0"
scene.collection.objects.link(lod0)
activate(lod0)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.quads_convert_to_tris()
bpy.ops.object.mode_set(mode='OBJECT')
m = lod0.modifiers.new("dec", 'DECIMATE')
m.ratio = LOD0_TRIS / len(lod0.data.polygons)
m.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="dec")
lod0.data.shade_smooth()
for u in list(lod0.data.uv_layers):
    lod0.data.uv_layers.remove(u)
dm = lod0.dimensions
size_m = round(max(dm.x, dm.y), 4)
rep = uvcharts.build(lod0, 1.0)
rep["mask_px_per_m"] = round(RES / rep["m_per_uv_unit"], 1)
lod0["uv_report"] = json.dumps(rep)
lod0.data.uv_layers["UVMap"].active_render = True
print("S_LOD0", len(lod0.data.polygons), "tris,", rep["islands"], "islands, m/uv", rep["m_per_uv_unit"], "size_m", size_m)

# ---- bakes
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
pr = bpy.context.preferences.addons["cycles"].preferences
pr.compute_device_type = 'HIP'
pr.get_devices()
for dv in pr.devices:
    dv.use = True
scene.cycles.use_denoising = False
scene.cycles.samples = 8
lod0.data.uv_layers.active = lod0.data.uv_layers["UVMap"]


def new_img(name, alpha=True):
    im = bpy.data.images.new(name, RES, RES, alpha=alpha, float_buffer=True)
    im.colorspace_settings.name = 'Non-Color'
    return im


def read(im):
    px = np.empty(RES * RES * 4, np.float32)
    im.pixels.foreach_get(px)
    return px.reshape(RES, RES, 4)


def bake_geometry(src_out, name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    g = nt.nodes.new("ShaderNodeNewGeometry")
    em = nt.nodes.new("ShaderNodeEmission")
    o_ = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(g.outputs[src_out], em.inputs["Color"])
    nt.links.new(em.outputs[0], o_.inputs["Surface"])
    im = new_img(name)
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = im
    nt.nodes.active = tn
    lod0.data.materials.clear()
    lod0.data.materials.append(mat)
    activate(lod0)
    bpy.ops.object.bake(type='EMIT', margin=8, use_clear=True)
    return read(im)


pos = bake_geometry("Position", "pos")
nor = bake_geometry("Normal", "nor")
inside = pos[..., 3] > 0.5

# AO from LOD0 onto itself (as for the cliffs), 1 m occlusion distance
aom = bpy.data.materials.new("AO")
aom.use_nodes = True
nt = aom.node_tree
nt.nodes.clear()
ao_n = nt.nodes.new("ShaderNodeAmbientOcclusion")
ao_n.only_local = True
ao_n.samples = 16
ao_n.inputs["Distance"].default_value = 1.0
em = nt.nodes.new("ShaderNodeEmission")
o_ = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(ao_n.outputs["AO"], em.inputs["Color"])
nt.links.new(em.outputs[0], o_.inputs["Surface"])
im_ao = new_img("ao")
tn = nt.nodes.new("ShaderNodeTexImage")
tn.image = im_ao
nt.nodes.active = tn
lod0.data.materials.clear()
lod0.data.materials.append(aom)
activate(lod0)
scene.cycles.samples = 32
bpy.ops.object.bake(type='EMIT', margin=8, use_clear=True)
ao = read(im_ao)[..., 0]

# tangent normal from HIGH
bvh = BVHTree.FromObject(high, bpy.context.evaluated_depsgraph_get())
vv = np.empty(len(lod0.data.vertices) * 3)
lod0.data.vertices.foreach_get("co", vv)
vv = vv.reshape(-1, 3)
dev = np.array([bvh.find_nearest(Vector(v))[3] for v in vv[::5]])
ext = max(float(np.quantile(dev, 0.999)) * 1.5, 0.002)
mat = bpy.data.materials.new("N")
mat.use_nodes = True
lod0.data.materials.clear()
lod0.data.materials.append(mat)
high.data.materials.clear()
high.data.materials.append(bpy.data.materials.new("H"))
im_n = new_img("nrm", alpha=False)
im_n.generated_color = (0.5, 0.5, 1.0, 1.0)
tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
tn.image = im_n
mat.node_tree.nodes.active = tn
bpy.ops.object.select_all(action='DESELECT')
high.select_set(True)
lod0.select_set(True)
bpy.context.view_layer.objects.active = lod0
scene.cycles.samples = 8
bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', normal_r='POS_X', normal_g='NEG_Y', normal_b='POS_Z',
                    use_selected_to_active=True, cage_extrusion=ext, max_ray_distance=ext * 2, margin=8, use_clear=False)
nrm = read(im_n)
np.save(out_npy.replace("_mask_v3", "_nmo_v3"),
        np.dstack([nrm[..., 0], nrm[..., 1], np.zeros_like(ao), ao]).astype(np.float16))

# ---- mask from the known stone layout (B = stone, R = dust on upward faces, G = scree in the earth crevices)
idx = np.argwhere(inside)
P = pos[inside][:, :3].astype(np.float64)
Nz = nor[inside][:, 2]
f_min = np.full(len(P), 9.0)
kind_of = np.zeros(len(P))
for c, h, yaw, tilt, kind in stones:
    c = np.array(c)
    rr = max(h) * 1.5
    sel = np.where((np.abs(P[:, 0] - c[0]) < rr) & (np.abs(P[:, 1] - c[1]) < rr) & (np.abs(P[:, 2] - c[2]) < rr))[0]
    if not len(sel):
        continue
    Rm = np.array(Euler((tilt[0], tilt[1], yaw)).to_matrix())
    q = ((P[sel] - c) @ Rm) / np.array(h)          # row-vector form = inverse rotation
    fq = (np.abs(q) ** 4).sum(1) ** 0.25
    better = fq < f_min[sel]
    kind_of[sel[better]] = kind
    f_min[sel] = np.minimum(f_min[sel], fq)


def vn(P, s):   # cheap smooth noise from sines, 0..1
    return 0.5 + 0.5 * (np.sin(P[:, 0] * 7.1 * s + P[:, 1] * 3.3 * s) * np.sin(P[:, 1] * 6.7 * s - P[:, 2] * 4.1 * s) * 0.6
                        + np.sin(P[:, 2] * 9.3 * s + P[:, 0] * 2.2 * s) * 0.4)


def sm(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


edge = 1.07 + 0.05 * (vn(P, 4) - 0.5)
stone = sm(edge + 0.05, edge - 0.02, f_min)
aoi = ao[inside]
up = sm(0.45, 0.85, Nz)
R_ = np.clip(up * (0.25 + 0.7 * vn(P, 2.5)) * (1 - 0.6 * stone) + 0.2 * stone * up * (vn(P, 6) > 0.6), 0, 1)
G_ = np.clip(stone * kind_of, 0, 1)                 # dark stones
B_ = np.clip(stone * (1 - kind_of), 0, 1)           # tan stones
mask = np.zeros((RES, RES, 4), np.float32)
mask[idx[:, 0], idx[:, 1]] = np.c_[R_, G_, B_, np.ones(len(P))]
np.save(out_npy, mask.astype(np.float16))
print("S_KINDS", sum(k for *_, k in stones), "dark of", len(stones))
print("S_MASK mean RGB", [round(float(x.mean()), 3) for x in (R_, G_, B_)], "stone share", round(float((stone > 0.5).mean()), 3))
lod0.data.materials.clear()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=False)
print("S_DONE size_m", size_m, "dims", [round(x, 3) for x in lod0.dimensions], "min z", round(float(vv[:, 2].min()), 3))
