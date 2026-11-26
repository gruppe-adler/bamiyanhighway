"""Turns the TT tunnel and cave prefabs into buildings flagged as underground structures (engine property of the Building class,
"Tunnel, cellar etc."), against pieces vanishing underground; and the placed pieces in the world layers with them (a layer names
the class of every placed entity).

Run with the world CLOSED in Workbench (it would overwrite the layers on save):
    python Docs/blender/tt_to_building.py            shows what would change
    python Docs/blender/tt_to_building.py --apply    does it
    python Docs/blender/tt_to_building.py --revert   back to GenericEntity
Safe to run again. Scripts that write TT prefabs from scratch (tunnelkit_finish.py, the cave finish scripts) write GenericEntity:
run this again after them."""
import glob, os, re, sys

ADDON = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFABS = os.path.join(ADDON, "Prefabs", "Tunnels", "TT")
LAYERS = os.path.join(ADDON, "worlds")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def prefab(text, revert):
    """The root entity's class and the property; only prefabs with the tunnel component (not the probes)"""
    if "SP_TunnelExposureComponent" not in text:
        return text
    nl = "\r\n" if "\r\n" in text else "\n"
    old, new = ("Building", "GenericEntity") if revert else ("GenericEntity", "Building")
    if not text.startswith(old + " {"):
        return text
    text = new + text[len(old):]
    if revert:
        return text.replace(" UndergroundStructure 1" + nl, "")
    # straight after the root's ID line
    return re.sub(r'^( ID "[0-9A-F]{16}"' + nl + ")", r"\1 UndergroundStructure 1" + nl, text, count=1, flags=re.M)


def layer(text, revert):
    old, new = ("Building", "GenericEntity") if revert else ("GenericEntity", "Building")
    # "GenericEntity [name] : "{GUID}Prefabs/Tunnels/TT/X.et" {", also as "$grp GenericEntity : ..." and inside another entity
    return re.subn(r'^((?:\$grp )?[ \t]*)%s\b(?=[^"\r\n]*: "\{[0-9A-F]{16}\}Prefabs/Tunnels/TT/(?!TT_\w*Probe)\w+\.et")' % old, r"\g<1>" + new, text, flags=re.M)


def main():
    revert = "--revert" in sys.argv
    apply = revert or "--apply" in sys.argv
    changed = 0
    for path in glob.glob(os.path.join(PREFABS, "*.et")):
        text = read(path)
        out = prefab(text, revert)
        if out != text:
            changed += 1
            if apply:
                write(path, out)
    print("prefabs %s: %d" % ("changed" if apply else "that would change", changed))
    for path in glob.glob(os.path.join(LAYERS, "*_Layers", "*.layer")):
        text = read(path)
        out, count = layer(text, revert)
        if count:
            print("   %s: %d placing lines (a group line stands for all its pieces)" % (os.path.relpath(path, ADDON), count))
            if apply:
                write(path, out)
    if not apply:
        print("nothing written; run with --apply (world closed)")


main()
