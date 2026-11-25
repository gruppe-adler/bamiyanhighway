"""Turns the CL_measure JSON files into the markdown tables of Docs/TunnelKit_Clearance.md.
python Docs/blender/CL_report.py [before.json] [after.json]   (defaults: previews/CL_before_all.json, previews/CL_after_full.json)"""
import json, os, sys, re

here = os.path.dirname(os.path.abspath(__file__))
prev = os.path.join(here, "previews")
bf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(prev, "CL_before_all.json")
af = sys.argv[2] if len(sys.argv) > 2 else os.path.join(prev, "CL_after_full.json")
B = {p["name"]: p for p in json.load(open(bf))["pieces"]}
Ad = json.load(open(af))
A = {p["name"]: p for p in Ad["pieces"]}


def g(p, zone, k):
    if p is None:
        return None
    z = p["zones"].get(zone)
    return None if not z or z.get(k) is None else z[k]


def f(x):
    return "-" if x is None else ("%.2f" % x)


def pair(p, zone, k1, k2):
    return "%s / %s" % (f(g(p, zone, k1)), f(g(p, zone, k2)))


def main_zone(p):
    return "doorway" if "doorway" in p["zones"] else "body"


print("### Piece table (before -> after; height / band = floor to roof at the route centre / 0.3 m to either side; widths: minimum wall to wall at 0.35-1.4 m above the floor; mid = 1.5 m from both ends)\n")
print("| Piece | Joint height / band | Joint width | Body height / band | Body width | Mid width min .. max | Mid height min .. max |")
print("|---|---|---|---|---|---|---|")
order = sorted(A, key=lambda n: (n.startswith("TT_C_"), n.startswith("TT_P_"), n.startswith("TT_Trans"), n))
for n in order:
    a = A[n]
    base = re.sub(r"_(A|C)$", "", n) if not n.startswith(("TT_C_", "TT_P_", "TT_Trans")) else n
    b = B.get(n) or B.get(base)
    z = main_zone(a)
    zb = main_zone(b) if b else z
    mid = "mid" if "mid" in a["zones"] else z
    row = lambda p, zz: "%s | %s | %s | %s" % (pair(p, "joint", "h", "hb"), f(g(p, "joint", "w")), pair(p, zz, "h", "hb"), f(g(p, zz, "w")))
    print("| %s | %s | %s .. %s | %s .. %s |" % (n, row(a, z), f(g(a, mid, "w")), f(g(a, mid, "wmax")), f(g(a, mid, "h")), f(g(a, mid, "hmax"))))
    if b and (n == base):
        print("| &nbsp;&nbsp;before | %s | %s .. %s | %s .. %s |" % (row(b, zb), "-", "-", "-", "-"))

print("\n### Closedness, materials, light\n")
bad = [(n, p["closed"]) for n, p in A.items() if p["closed"]["open_edges"] or p["closed"]["multi_edges"] or p["closed"]["signed_volume"] <= 0]
print("pieces: %d; open / non-manifold / negative volume: %s" % (len(A), bad or "none"))
wood = [n for n, p in A.items() if any("Wood" in m for m in p["materials"])]
print("pieces with a wood material: %s" % (wood or "none"))
print("LOD0 != collider: %s" % ([n for n, p in A.items() if not p["lod_vs_utm"]["ok"]] or "none"))
rays = sum(p["light"]["rays"] for p in A.values())
leaks = [(n, p["light"]["leaks"]) for n, p in A.items() if p["light"]["leaks"]]
print("single-piece light test: %d rays from the void along the routes, escapes not through an opening: %s" % (rays, leaks or "none"))
print("max vertical socket error: %.4f deg" % max(s["up_error_deg"] for p in A.values() for s in p["sockets"]))

print("\n### Joint tests\n")
J = Ad["joints"]
print("%d joint tests (every opening against a copy of itself, every variant combination of a shape, and the plain straight 2 of its size)" % len(J))
print("min height %.3f, band %.3f, width %.3f (across +-1 m of the plane); max floor step %.3f; worst ring mismatch %.5f; sleeve reach %s; leaks %d of %d rays"
      % (min(j["h"] for j in J), min(j["hb"] for j in J), min(j["w"] for j in J), max(j["step"] for j in J if "Slope" not in j["a"] and "Incline" not in j["a"]),
         max(j["ring_mismatch"] for j in J), sorted(set((j["reach_a"], j["reach_b"]) for j in J)), sum(j["leaks_of_400"] for j in J), 400 * len(J)))
walk = [j for j in J if "_C_" not in j["a"] and "_P_" not in j["a"] and "Trans" not in j["a"]]
print("walk joints: %d, min height %.3f, band %.3f, width %.3f" % (len(walk), min(j["h"] for j in walk), min(j["hb"] for j in walk), min(j["w"] for j in walk)))
worst = sorted(J, key=lambda j: j["ring_mismatch"])[-3:]
print("largest ring mismatches:", [(j["a"], j["b"], j["ring_mismatch"]) for j in worst])
print("tests with a leak:", [(j["a"], j["sock_a"], j["b"], j["leaks_of_400"]) for j in J if j["leaks_of_400"]] or "none")

print("\n### Sockets against the old pieces (position and direction, tolerance 1 mm)\n")
diff = []
for n, a in A.items():
    base = re.sub(r"_(A|C)$", "", n) if not n.startswith(("TT_C_", "TT_P_", "TT_Trans")) else n
    b = B.get(n) or B.get(base)
    if not b:
        continue
    if len(a["sockets"]) != len(b["sockets"]):
        diff.append((n, "count"))
        continue
    for i, (sa, sb) in enumerate(zip(a["sockets"], b["sockets"])):
        d = max(abs(x - y) for x, y in zip(sa["pos"] + sa["out"], sb["pos"] + sb["out"]))
        if d > 1e-3:
            diff.append((n, i + 1, [round(x, 3) for x in sa["pos"]], [round(x, 3) for x in sb["pos"]]))
print("differences:", diff or "none")
