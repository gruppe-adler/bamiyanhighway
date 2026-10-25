"""Robust n-gon handling. Blender's ear clipping (and Enfusion's) can triangulate big concave wall polygons with window arches wrongly:
a triangle then covers the arch opening ("half black windows"). fix_ngons(mesh) finds polygons whose triangulated area != polygon area, splits them
into convex pieces (connect_verts_concave) and finally triangulates everything. Call on every mesh before baking / exporting."""
import bmesh
from mathutils import geometry


def _tri_area(f):
    pts = [l.vert.co.copy() for l in f.loops]
    tris = geometry.tessellate_polygon([pts])
    a = 0.0
    for t in tris:
        a += ((pts[t[1]] - pts[t[0]]).cross(pts[t[2]] - pts[t[0]])).length / 2
    return a


def fix_ngons(me, verbose=True):
    """1) polygons whose tessellated area differs from the polygon area are self-overlapping/invalid (boolean output around window arches): delete them and
    triangle-fill their boundary again (holes = arches stay open); 2) triangulate everything."""
    bm = bmesh.new(); bm.from_mesh(me)
    n0 = (len(bm.verts), len(bm.faces))
    # the bevel/weld steps left ~2000 duplicate verts + zero-area triangles; they made the big wall polygons around the window arches self-overlap
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-7], context='FACES_ONLY')
    for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
    if verbose: print('clean mesh: verts/faces', n0, '->', (len(bm.verts), len(bm.faces)))
    big = [f for f in bm.faces if len(f.verts) > 4]
    bad = [f for f in big if abs(_tri_area(f) - f.calc_area()) > 1e-2 * max(f.calc_area(), 1e-6)]
    info = [(f.normal.copy(), f.material_index, f.smooth) for f in bad]
    edges = list({e for f in bad for e in f.edges})
    bmesh.ops.delete(bm, geom=bad, context='FACES_ONLY')
    edges = [e for e in edges if e.is_valid and e.is_boundary]
    new = bmesh.ops.triangle_fill(bm, edges=edges, use_beauty=True, use_dissolve=False)['geom'] if edges else []
    nf = [g for g in new if isinstance(g, bmesh.types.BMFace)]
    for f in nf:
        ref = max(info, key=lambda i: i[0].dot(f.normal)) if info else None
        if ref:
            if f.normal.dot(ref[0]) < 0: f.normal_flip()
            f.material_index = ref[1]; f.smooth = ref[2]
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    n_tri = len(bm.faces)
    bm.to_mesh(me); bm.free(); me.update()
    if verbose: print('fix_ngons: big polygons', len(big), 'invalid (refilled)', len(bad), 'new faces', len(nf), '-> tris', n_tri)
    return len(bad)
