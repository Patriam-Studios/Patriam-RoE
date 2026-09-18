"""Build the terrain splat maps from the WorldPainter terrain export.

detail_index.tga and detail_intensity.tga are a four layer blend at province map
resolution. Each RGBA channel of the index picks a material by its position in
materials.settings, and the matching channel of the intensity gives its weight.
Vanilla leaves unused slots at index 255 and weight 0, and so does this.

Two slots are used. The first is the ground the biome calls for. The second is
whichever is strongest of a light overlay for texture, bare rock where the land
is steep, and snow where it is high, so that cliffs read as rock and summits as
snow whatever biome was painted there.

usage: python build_terrain.py <export prefix> <heightmap.png> <map_data dir> <gfx terrain out dir>
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
CK3_SEA = 3932          # sixteen bit sea level in heightmap.png
SNOWLINE_BLOCKS = 150.0
SNOW_FULL_BLOCKS = 215.0
ROCK_SLOPE_START = 1.6   # blocks of rise per province pixel before rock shows
ROCK_SLOPE_FULL = 4.5


def main(prefix, heightmap_path, map_data_dir, out_dir):
    idx = tm.material_index()
    prov = Image.open(os.path.join(map_data_dir, "provinces.png"))
    W, H = prov.size
    print("province map %d x %d" % (W, H))

    # The painted surface first, the biome where the surface is only grass, and
    # height and slope where neither spoke. terrain_materials.ground_maps is
    # shared with the colour map so the two can never disagree.
    primary, overlay, unresolved = tm.ground_maps(prefix, (W, H), idx)

    hm = np.array(Image.open(heightmap_path))[::2, ::2].astype(np.float32)
    assert hm.shape == (H, W), "heightmap does not halve to the province map"
    land = hm > CK3_SEA
    elev = hs.elevation_blocks(hm).astype(np.float32)
    del hm
    gy, gx = np.gradient(elev)
    slope = np.hypot(gx, gy).astype(np.float32)
    del gx, gy

    # Land nobody painted a biome on takes its ground from how high it stands.
    lowland = unresolved & land
    primary[lowland & (elev > 55)] = idx["hills_01"]
    overlay[lowland & (elev > 55)] = idx["hills_01_rocks_small"]
    primary[lowland & (elev > 115)] = idx["mountain_02"]
    overlay[lowland & (elev > 115)] = idx["mountain_02_b"]
    del unresolved, lowland

    primary[~land] = idx["beach_02"]
    overlay[~land] = 255

    rock_w = np.clip((slope - ROCK_SLOPE_START) / (ROCK_SLOPE_FULL - ROCK_SLOPE_START), 0, 1)
    snow_w = np.clip((elev - SNOWLINE_BLOCKS) / (SNOW_FULL_BLOCKS - SNOWLINE_BLOCKS), 0, 1)
    del slope

    # A light, uneven overlay so broad plains do not read as one flat texture.
    ys, xs = np.mgrid[0:H:4, 0:W:4]
    noise = (np.sin(xs * 0.021) * np.cos(ys * 0.017) + np.sin((xs + ys) * 0.009)) * 0.25 + 0.5
    noise = np.array(Image.fromarray((noise * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)) / 255.0
    over_w = np.where(overlay == 255, 0.0, 0.12 + 0.28 * noise)
    del noise, ys, xs

    second = overlay.copy()
    weight = over_w.astype(np.float32)
    rock = rock_w > weight
    second[rock] = idx[tm.STEEP_ROCK]
    weight = np.maximum(weight, rock_w)
    snow = snow_w > weight
    second[snow] = idx[tm.HIGH_SNOW]
    weight = np.maximum(weight, snow_w)
    weight[~land] = 0.0
    second[weight <= 0.0] = 255
    del rock_w, snow_w, over_w, overlay, elev

    # Very steep ground gives up its biome entirely.
    cliff = weight > 0.85
    primary[cliff] = second[cliff]
    second[cliff] = 255
    weight[cliff] = 0.0

    s = np.round(weight * 255).astype(np.uint8)
    index = np.empty((H, W, 4), dtype=np.uint8)
    index[..., 0] = primary
    index[..., 1] = second
    index[..., 2] = 255
    index[..., 3] = 255
    intensity = np.zeros((H, W, 4), dtype=np.uint8)
    intensity[..., 0] = 255 - s
    intensity[..., 1] = s
    del primary, second, weight, s

    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(index, "RGBA").save(os.path.join(out_dir, "detail_index.tga"))  # uncompressed, as vanilla ships it
    Image.fromarray(intensity, "RGBA").save(os.path.join(out_dir, "detail_intensity.tga"))  # uncompressed, as vanilla ships it
    used = np.unique(index[..., :2])
    names = {v: k for k, v in idx.items()}
    print("wrote detail_index.tga and detail_intensity.tga at %d x %d" % (W, H))
    print("materials in use: " + ", ".join(names.get(int(u), "unused") for u in used if u != 255))


if __name__ == "__main__":
    main(*sys.argv[1:5])
