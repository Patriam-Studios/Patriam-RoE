"""Colour map and paper map for the Patriam world.

Vanilla's colormap.dds tints the terrain and flatmap.dds is the painted paper
map, both painted for a 9216 by 4608 Earth. Stretched over this world they put
Europe on the paper map and vanilla's colours on Patriamic ground.

Formats follow vanilla exactly, checked from its own headers: the colour map is
DXT5 and both paper maps are DXT1, at the full world resolution. Vanilla's
colour map carries mip levels and this does not, which only affects distant
sampling.

Until the WorldPainter biome export can run, colour comes from elevation. The
biome pass replaces that with painted biomes, so Senkaria reads as desert.

usage: python build_textures.py <heightmap.png> <gfx/map/terrain dir> [export prefix]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
CK3_SEA = 3932

# Elevation in blocks above the sea, and the ground colour at that height.
COLOUR_STOPS = [
    (0.0, (88, 116, 58)),
    (18.0, (104, 124, 66)),
    (55.0, (128, 122, 82)),
    (110.0, (122, 110, 94)),
    (160.0, (138, 134, 130)),
    (215.0, (226, 228, 232)),
]
SEA_TINT = (70, 96, 104)

# The colour a biome's ground gives the land, keyed by the primary material the
# biome maps to in terrain_materials.py. Where a biome was painted this replaces
# the green of the elevation ramp, so a desert reads as sand from any height
# and a pine forest as the dark of its needles; the ramp still takes over on
# high ground, where rock and snow belong to the height and not the biome.
MATERIAL_TINT = {
    "plains_01": (104, 124, 66),
    "northern_plains_01": (110, 124, 88),
    "forest_leaf_01": (72, 102, 54),
    "forest_pine_01": (58, 88, 60),
    "forest_jungle_01": (54, 98, 46),
    "forestfloor": (62, 84, 48),
    "hills_01": (120, 120, 82),
    "mountain_02": (124, 114, 100),
    "mountain_02_desert_c": (172, 122, 86),
    "snow": (228, 232, 236),
    "mountain_02_b": (76, 68, 64),          # the ash and dark rock of Vurkia
    "desert_wavy_01": (198, 172, 114),
    "drylands_01_grassy": (152, 142, 86),
    "wetlands_02": (82, 102, 72),
    "floodplains_01": (98, 122, 74),
    "beach_02": (190, 178, 140),
    "beach_02_mediterranean": (204, 190, 148),
    "beach_02_pebbles": (150, 146, 134),
    "desert_rocky": (176, 150, 108),
    "hills_01_rocks": (128, 124, 108),
    "hills_01_rocks_small": (128, 124, 108),
    "farmland_01": (132, 138, 70),
}
HIGH_GROUND_START, HIGH_GROUND_FULL = 95.0, 160.0   # blocks above the sea

PAPER_LAND = np.array([224, 206, 166], dtype=np.float32)
PAPER_SEA = np.array([188, 196, 186], dtype=np.float32)
PAPER_INK = np.array([96, 72, 48], dtype=np.float32)


def ramp(elev):
    out = np.zeros(elev.shape + (3,), dtype=np.float32)
    xs = [s[0] for s in COLOUR_STOPS]
    for c in range(3):
        out[..., c] = np.interp(elev, xs, [s[1][c] for s in COLOUR_STOPS])
    return out


def main(heightmap_path, terrain_dir, prefix=None):
    hm = np.array(Image.open(heightmap_path))[::2, ::2].astype(np.float32)
    H, W = hm.shape
    assert W % 4 == 0 and H % 4 == 0, "DXT needs dimensions divisible by four"
    land = hm > CK3_SEA
    elev = hs.elevation_blocks(hm).astype(np.float32)
    del hm
    print("world %d x %d, land %.1f%%" % (W, H, land.mean() * 100))

    # Colour map: a smooth ramp by height, softened so bands never read as lines.
    col = ramp(elev)
    if prefix and os.path.exists(prefix + "_biome.png"):
        idx = tm.material_index()
        names = {v: k for k, v in idx.items()}
        primary, _, _ = tm.ground_maps(prefix, (W, H), idx, report=False)
        tinted = 0
        high = np.clip((elev - HIGH_GROUND_START) / (HIGH_GROUND_FULL - HIGH_GROUND_START), 0, 1)[..., None]
        for mid in np.unique(primary):
            tint = MATERIAL_TINT.get(names.get(int(mid), ""))
            if tint is None:
                continue
            m = (primary == mid) & land
            if not m.any():
                continue
            # gentle shading by height inside the ground so broad plains are not one flat colour
            shade = (0.92 + 0.10 * np.clip(elev[m] / 80.0, 0, 1))[:, None]
            col[m] = (np.array(tint, dtype=np.float32)[None, :] * shade) * (1.0 - high[m]) + col[m] * high[m]
            tinted += int(m.sum())
        del primary, high
        print("ground tint applied to %.1f%% of the land" % (tinted * 100.0 / max(1, int(land.sum()))))
    col[~land] = SEA_TINT
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    del col
    rgba = img.convert("RGBA")
    os.makedirs(terrain_dir, exist_ok=True)
    rgba.save(os.path.join(terrain_dir, "colormap.dds"), format="DDS", pixel_format="DXT5")
    print("wrote colormap.dds, DXT5")
    del img, rgba

    # Paper map: parchment land, cooler parchment sea, soft relief, inked coast.
    gy, gx = np.gradient(elev)
    shade = np.clip(1.0 - (gx * 0.55 - gy * 0.55) * 0.08, 0.82, 1.08)
    del gx, gy
    lift = np.clip(elev / 240.0, 0, 1)[..., None]
    paper = PAPER_LAND[None, None, :] * (1.0 - 0.16 * lift)
    paper = paper * shade[..., None]
    paper[~land] = PAPER_SEA
    del shade, lift

    coast = Image.fromarray((land * 255).astype(np.uint8))
    edge = np.array(coast.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))) > 0
    paper[edge] = paper[edge] * 0.35 + PAPER_INK * 0.65
    del edge, coast

    out = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8)).convert("RGBA")
    del paper
    flat_dir = os.path.join(terrain_dir, "flat_maps")
    os.makedirs(flat_dir, exist_ok=True)
    for name in ("flatmap.dds", "flatmap_tgp.dds"):
        out.save(os.path.join(flat_dir, name), format="DDS", pixel_format="DXT1")
        print("wrote flat_maps/%s, DXT1" % name)
    out.convert("RGB").resize((W // 16, H // 16), Image.BILINEAR).save(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "preview_flatmap.png"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
