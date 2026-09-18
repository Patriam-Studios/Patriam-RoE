"""The terracotta ground of Mekanis, which the base game has nothing like.

Mekanis is a mesa of red terracotta cut by canyons, as the Grand Canyon is.
Crusader Kings III ships no red rock at all: its desert mountain is grey brown
and its rocky desert is tan, so on either of them the mesa reads as ordinary
dry ground. This turns two of the base game's own terrain textures red, keeping
their grain and their normal and properties maps, and declares them as two more
materials in a copy of materials.settings.

The hue is taken from Minecraft's terracotta, which is what the mesa is built
of in the source world: a red orange around eighteen degrees for the ground and
a deeper, darker red for the rock.

usage: python make_terracotta.py [--write]
"""
import io
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
SRC = os.path.join(GAME, "gfx", "map", "terrain")
OUT = os.path.join(MOD, "gfx", "map", "terrain")
WRITE = "--write" in sys.argv

# name: (source diffuse, hue in degrees, saturation, lightness)
RECOLOUR = {
    "patriam_terracotta": ("desert_rocky_diffuse.dds", 16.0, 1.85, 1.02),
    "patriam_terracotta_rock": ("mountain_03_desert_diffuse.dds", 13.0, 1.70, 1.18),
}
# the normal and properties maps carry no colour, so the base game's own are used
BORROW = {
    "patriam_terracotta": "desert_rocky",
    "patriam_terracotta_rock": "mountain_03_desert",
}


def recolour(path, hue_deg, sat, light):
    """Turn a texture red while keeping every bit of its grain."""
    rgb = np.array(Image.open(path).convert("RGB")).astype(np.float32) / 255.0
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    v = np.clip(v * light, 0.0, 1.0)
    s = np.clip(s * sat, 0.0, 1.0)
    h = np.full_like(v, hue_deg / 60.0)
    i = np.floor(h).astype(np.int32)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.stack([np.where(i == 0, v, q), np.where(i == 0, t, v), np.where(i == 0, p, p)], axis=2)
    return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8))


def settings_with_new_materials():
    src = os.path.join(SRC, "materials.settings")
    s = io.open(src, encoding="utf-8-sig").read()
    assert "patriam_terracotta" not in s, "the base game already has it"
    block = ""
    for name in RECOLOUR:
        borrowed = BORROW[name]
        block += ('\t{\n'
                  '\t\tname     = "%s"\n'
                  '\t\tdiffuse  = "%s_diffuse.dds"\n'
                  '\t\tnormal   = "%s_normal.dds"\n'
                  '\t\tmaterial = "%s_properties.dds"\n'
                  '\t\tmask     = "masks/%s_mask.png"\n'
                  '\t\tid       = "%s"\n'
                  '\t}\n' % (name, name, borrowed, borrowed, name, name))
    # the last closing brace of the masked block, so the new ids come after every
    # one of the base game's and no existing index moves
    cut = s.rindex("}", 0, s.index("# unmasked textures"))
    return s[:cut] + block + s[cut:]


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (src, hue, sat, light) in RECOLOUR.items():
        im = recolour(os.path.join(SRC, src), hue, sat, light)
        print("%-26s from %-32s mean rgb %s" % (name, src, np.array(im).reshape(-1, 3).mean(0).round()))
        if WRITE:
            im.save(os.path.join(OUT, name + "_diffuse.dds"), format="DDS", pixel_format="DXT5")
            im.resize((256, 256)).save(os.path.join(HERE, "build", "preview_" + name + ".png"))
    s = settings_with_new_materials()
    if WRITE:
        io.open(os.path.join(OUT, "materials.settings"), "w", encoding="utf-8-sig", newline="\n").write(s)
        print("wrote materials.settings with %d materials" % len(re.findall(r'\bid\s+=\s+"', s)))
    else:
        print("dry run; materials.settings would hold %d materials" % len(re.findall(r'\bid\s+=\s+"', s)))


if __name__ == "__main__":
    main()
