"""The grounds the base game has nothing like: the terracotta of Mekanis and
the lava and ash of Vurkia.

Mekanis is a mesa of red terracotta cut by canyons, as the Grand Canyon is.
Crusader Kings III ships no red rock at all: its desert mountain is grey brown
and its rocky desert is tan, so on either of them the mesa reads as ordinary
dry ground. This turns two of the base game's own terrain textures red, keeping
their grain and their normal and properties maps, and declares them as two more
materials in a copy of materials.settings.

The hue is taken from Minecraft's terracotta, which is what the mesa is built
of in the source world: a red orange around eighteen degrees for the ground and
a deeper, darker red for the rock.

usage: python make_materials.py [--write]
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

# Vurkia is not a matter of hue. Lava is a dark crust with fire in its cracks, so
# the light and dark of the source texture is read as a ramp instead: black
# crust, a red glow in the seams, and yellow where the crust has broken open.
# Ash is the same ramp run into grey, dark enough to read as burnt ground.
RAMP = {
    "patriam_lava": ("mountain_03_desert_diffuse.dds", [
        (0.00, (16, 8, 7)), (0.22, (48, 14, 8)), (0.42, (150, 36, 8)),
        (0.60, (232, 96, 14)), (0.80, (252, 174, 46)), (1.00, (255, 236, 150))]),
    "patriam_ash": ("mountain_03_desert_diffuse.dds", [
        (0.00, (14, 13, 15)), (0.40, (34, 32, 36)), (0.70, (58, 55, 58)),
        (1.00, (96, 92, 94))]),
}

# the normal and properties maps carry no colour, so the base game's own are used
BORROW = {
    "patriam_terracotta": "desert_rocky",
    "patriam_terracotta_rock": "mountain_03_desert",
    "patriam_lava": "mountain_03_desert",
    "patriam_ash": "mountain_03_desert",
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


def write_dds(im, src_path, out_path):
    """Write the texture with the same header and the same chain of mip levels
    as the texture it came from.

    Crusader Kings III loads every terrain diffuse into one texture array, and an
    array will not hold a texture whose resolution, format or number of mip
    levels differs from the first. A file with a single level, which is all that
    Pillow writes on its own, makes the whole array fail to build, and the entire
    world then draws purple. That is exactly what happened on 19 September 2026."""
    header = open(src_path, "rb").read(128)
    mips = int.from_bytes(header[28:32], "little") or 1
    data = bytearray()
    w, h = im.size
    for level in range(mips):
        lw, lh = max(1, w >> level), max(1, h >> level)
        m = im.resize((lw, lh), Image.LANCZOS)
        if lw < 4 or lh < 4:
            m = m.resize((4, 4), Image.LANCZOS)      # a block is four by four whatever the level holds
        buf = io.BytesIO()
        m.save(buf, format="DDS", pixel_format="DXT5")
        data += buf.getvalue()[128:]
    out = bytes(header) + bytes(data)
    want = os.path.getsize(src_path)
    assert len(out) == want, "wrote %d bytes where the base game's texture is %d" % (len(out), want)
    open(out_path, "wb").write(out)
    return mips


def ramp_map(path, stops):
    """Read the texture's light and dark as a ramp of colour, which is how a
    crust of lava is made out of a crust of dried mud."""
    a = np.array(Image.open(path).convert("RGB")).astype(np.float32) / 255.0
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])
    lum = np.clip((lum - lum.min()) / max(1e-6, lum.max() - lum.min()), 0.0, 1.0)
    xs = [p for p, _ in stops]
    out = np.stack([np.interp(lum, xs, [c[i] for _, c in stops]) for i in range(3)], axis=2)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def settings_with_new_materials():
    src = os.path.join(SRC, "materials.settings")
    s = io.open(src, encoding="utf-8-sig").read()
    assert "patriam_terracotta" not in s, "the base game already has it"
    block = ""
    for name in list(RECOLOUR) + list(RAMP):
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
    made = [(n, recolour(os.path.join(SRC, v[0]), *v[1:]), v[0]) for n, v in RECOLOUR.items()]
    made += [(n, ramp_map(os.path.join(SRC, v[0]), v[1]), v[0]) for n, v in RAMP.items()]
    for name, im, src in made:
        print("%-26s from %-32s mean rgb %s" % (name, src, np.array(im).reshape(-1, 3).mean(0).round()))
        if WRITE:
            mips = write_dds(im, os.path.join(SRC, src), os.path.join(OUT, name + "_diffuse.dds"))
            print("   wrote %s_diffuse.dds with %d mip levels" % (name, mips))
            im.resize((256, 256)).save(os.path.join(HERE, "build", "preview_" + name + ".png"))
    s = settings_with_new_materials()
    if WRITE:
        io.open(os.path.join(OUT, "materials.settings"), "w", encoding="utf-8-sig", newline="\n").write(s)
        print("wrote materials.settings with %d materials" % len(re.findall(r'\bid\s+=\s+"', s)))
    else:
        print("dry run; materials.settings would hold %d materials" % len(re.findall(r'\bid\s+=\s+"', s)))


if __name__ == "__main__":
    main()
