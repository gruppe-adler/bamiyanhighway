"""The dark probe boxes of the entries (walk horizontal and incline, crouch and prone horizontal): replaces the probe children
of their prefabs. Plain Python (python Docs/blender/CL_entry_probes.py, from anywhere). Safe to run again; tune the table and re-run.

Three boxes per entry, getting darker the further in, so there is no single edge between daylight and dark. None reaches out of
the shell or into the open part of the mouth. Boxes are in the prefab's space (Enfusion x across, y up, z along), metres:
(brightness in EV, x from..to, y from..to, z from..to). The last one of each is the tunnel's own darkness (-16)."""
import os, re, hashlib

ADDON = r"C:\Users\nomisum\Documents\my games\ArmaReforgerWorkbench\addons\Shashpul"
PREFABS = os.path.join(ADDON, "Prefabs", "Tunnels", "TT")

ENTRIES = {
    # mouth at z 0 (its roof starts about z 0.8), joint at z 5
    "TT_Entry_Horizontal": [
        (-5, (-1.15, 1.15), (-0.2, 2.8), (1.6, 2.6)),
        (-10, (-1.15, 1.15), (-0.2, 2.8), (2.6, 3.6)),
        (-16, (-1.15, 1.15), (-0.2, 2.8), (3.6, 5.35)),
    ],
    # crouch and prone: joint at z 5; the boxes are as low and narrow as their tunnels
    "TT_C_Entry_Horizontal": [
        (-5, (-1.0, 1.0), (-0.2, 1.95), (1.6, 2.6)),
        (-10, (-1.0, 1.0), (-0.2, 1.95), (2.6, 3.6)),
        (-16, (-1.0, 1.0), (-0.2, 1.95), (3.6, 5.35)),
    ],
    "TT_P_Entry_Horizontal": [
        (-5, (-0.85, 0.85), (-0.2, 1.25), (1.6, 2.6)),
        (-10, (-0.85, 0.85), (-0.2, 1.25), (2.6, 3.6)),
        (-16, (-0.85, 0.85), (-0.2, 1.25), (3.6, 5.35)),
    ],
    # ground at y 0, the stairs come down towards -z to the joint at y -4, z -3.37: flat slabs, darker with depth
    "TT_Entry_Incline": [
        (-5, (-1.15, 1.15), (-2.2, -1.3), (-3.5, 0.3)),
        (-10, (-1.15, 1.15), (-3.1, -2.2), (-3.5, -0.6)),
        (-16, (-1.15, 1.15), (-4.2, -3.1), (-3.65, -1.4)),
    ],
}


def guid(key):
    return hashlib.md5(("SP_TT_ENTRYPROBE_" + key).encode()).hexdigest()[:16].upper()


def probe(name, i, ev, x, y, z, last):
    centre = [(a + b) / 2 for a, b in (x, y, z)]
    size = [b - a for a, b in (x, y, z)]
    key = "%s.%d" % (name, i)
    lines = [
        '  GameEnvironmentProbeEntity : "{565470F7BA530E0D}Prefabs/Structures/Core/ProbeHouse_Base.et" {',
        '   ID "%s"' % guid(key),
        '   coords %g %g %g' % tuple(round(v, 3) for v in centre),
        '   LVReflectionBrightness %d' % ev,
        '   ReflectionColor 1 1 1 1',
        '   LVDiffuseBrightness %d' % ev,
        '   DiffuseColor 1 1 1 1',
    ]
    if last:      # the exposure settings of the tunnel's probes, only where it is fully dark
        lines += ['   VisiblePercentBlack 90', '   VisiblePercentWhite 55']
    lines += [
        '   {',
        '    ProbeVolume : "{CD5BB05FBEEBAE01}Prefabs/Structures/Core/ProbeVolume_Base.et" {',
        '     ID "%s"' % guid(key + ".volume"),
        '     Box BoundingVolume "{%s}" {' % guid(key + ".box"),
        '      Size %g %g %g' % tuple(round(v, 3) for v in size),
        '     }',
        '    }',
        '   }',
        '  }',
    ]
    return "\n".join(lines)


def main():
    for name, boxes in ENTRIES.items():
        path = os.path.join(PREFABS, name + ".et")
        text = open(path, encoding="utf-8").read()
        # the prefab is: root { components {...} [ { children } ] }
        m = re.search(r"^ components \{\n.*?^ \}\n", text, flags=re.M | re.S)
        children = "\n".join(probe(name, i, *b, last=i == len(boxes) - 1) for i, b in enumerate(boxes))
        text = text[:m.end()] + " {\n" + children + "\n }\n}\n"
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            f.write(text)
        print("%s: %d probe boxes" % (name, len(boxes)))


main()
