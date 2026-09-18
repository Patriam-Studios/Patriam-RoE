"""Build the terrain splat maps from the WorldPainter terrain export.

detail_index.tga and detail_intensity.tga are a four layer blend at province map
resolution. Each RGBA channel of the index picks a material by its position in
materials.settings, and the matching channel of the intensity gives its weight.
Vanilla fills every slot and its weights always add to 255, so these do too.

Three slots are used:

1. the ground the painted surface, the biome or the height calls for,
2. the ground of whatever lies nearby, weighted by how much of the
   neighbourhood it covers, which is what softens the joins. Straight on a
   border the two grounds each cover about half, so both sides of the line
   draw the same mixture and the seam disappears. A little noise is added so
   that the join wanders rather than running straight,
3. bare rock where the land is steep, snow where it is high, and otherwise a
   second texture for the ground itself so that broad plains are not flat.

usage: python build_terrain.py <export prefix> <heightmap.png> <map_data dir> <gfx terrain out dir>
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
CK3_SEA = 3932          # sixteen bit sea level in heightmap.png
SNOWLINE_BLOCKS = 150.0
SNOW_FULL_BLOCKS = 215.0
ROCK_SLOPE_START = 1.6   # blocks of rise per province pixel before rock shows
ROCK_SLOPE_FULL = 4.5
Q = 4                    # province pixels a blending pixel
BLEND_SIGMA = 1.6        # blending pixels, so about 33 blocks of softened join
MAX_BLEND = 0.46         # the ground of the pixel itself always keeps the most weight


def noise(shape, cell, rng, octaves=2):
    """A smooth random field in 0 to 1, used to break up anything regular."""
    H, W = shape
    out = np.zeros(shape, np.float32)
    amp = 0.0
    for o in range(octaves):
        c = cell // (2 ** o)
        small = rng.random((max(2, H // c + 2), max(2, W // c + 2))).astype(np.float32)
        up = np.array(Image.fromarray(small).resize((W, H), Image.BICUBIC), dtype=np.float32)
        out += up * (0.5 ** o)
        amp += 0.5 ** o
    return np.clip(out / amp, 0.0, 1.0)


def blend_partner(primary, used, H, W):
    """For every pixel, which other ground lies around it and how much of the
    neighbourhood it holds. Worked out on a quarter grid and stretched back."""
    hq, wq = H // Q, W // Q
    best = np.zeros((hq, wq), np.float32)
    best_id = np.zeros((hq, wq), np.uint8)
    second = np.zeros((hq, wq), np.float32)
    second_id = np.zeros((hq, wq), np.uint8)
    for mid in used:
        cov = (primary == mid).reshape(hq, Q, wq, Q).sum(axis=(1, 3), dtype=np.uint16).astype(np.float32) / (Q * Q)
        cov = ndimage.gaussian_filter(cov, BLEND_SIGMA, mode="nearest")
        take_second = (cov > second) & (cov <= best)
        second = np.where(take_second, cov, second)
        second_id = np.where(take_second, np.uint8(mid), second_id)
        take_best = cov > best
        second = np.where(take_best, best, second)
        second_id = np.where(take_best, best_id, second_id)
        best = np.where(take_best, cov, best)
        best_id = np.where(take_best, np.uint8(mid), best_id)
        del cov
    up = lambda a, mode: np.array(Image.fromarray(a).resize((W, H), mode), dtype=a.dtype)
    return (up(best_id, Image.NEAREST), up(best, Image.BILINEAR),
            up(second_id, Image.NEAREST), up(second, Image.BILINEAR))


def main(prefix, heightmap_path, map_data_dir, out_dir):
    idx = tm.material_index()
    prov = Image.open(os.path.join(map_data_dir, "provinces.png"))
    W, H = prov.size
    del prov
    print("province map %d x %d" % (W, H))
    rng = np.random.default_rng(6355)

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

    # slot three: rock, snow, or a second texture for the ground itself
    grain = noise((H, W), 96, rng)
    third = overlay.copy()
    w3 = np.where(overlay == 255, 0.0, 0.10 + 0.24 * grain).astype(np.float32)
    rock = rock_w > w3
    third[rock] = idx[tm.STEEP_ROCK]
    w3 = np.maximum(w3, rock_w)
    snow = snow_w > w3
    third[snow] = idx[tm.HIGH_SNOW]
    w3 = np.maximum(w3, snow_w)
    w3[~land] = 0.0
    del rock_w, snow_w, overlay, rock, snow

    # Very steep ground gives up its ground entirely to the rock.
    cliff = w3 > 0.85
    primary[cliff] = third[cliff]
    w3[cliff] = 0.0
    del cliff

    # slot two: the neighbouring ground, which is what makes the joins soft
    used = [int(u) for u in np.unique(primary)]
    print("blending across %d grounds" % len(used))
    best_id, best, second_id, second = blend_partner(primary, used, H, W)
    is_best = primary == best_id
    partner = np.where(is_best, second_id, best_id)
    w2 = np.where(is_best, second, best).astype(np.float32)
    del best_id, best, second_id, second, is_best
    # a wandering edge rather than a clean contour line
    w2 *= (0.72 + 0.56 * noise((H, W), 24, rng))
    np.clip(w2, 0.0, MAX_BLEND, out=w2)
    w2[~land] = 0.0
    w2[partner == primary] = 0.0
    del land, grain

    w1 = np.clip(1.0 - w2 - w3, 0.08, 1.0).astype(np.float32)
    total = w1 + w2 + w3
    i1 = np.round(w1 / total * 255.0).astype(np.uint8)
    i2 = np.minimum(np.round(w2 / total * 255.0), 255 - i1).astype(np.uint8)
    i3 = (255 - i1.astype(np.int32) - i2.astype(np.int32)).clip(0, 255).astype(np.uint8)
    assert (i1.astype(np.int32) + i2 + i3 == 255).all(), "weights must add to 255, as vanilla's do"
    del w1, w2, w3, total

    index = np.empty((H, W, 4), dtype=np.uint8)
    index[..., 0] = primary
    index[..., 1] = partner
    index[..., 2] = third
    index[..., 3] = 255
    intensity = np.zeros((H, W, 4), dtype=np.uint8)
    intensity[..., 0] = i1
    intensity[..., 1] = i2
    intensity[..., 2] = i3
    print("mean weights: ground %.2f, neighbour %.2f, rock or texture %.2f"
          % (i1.mean() / 255, i2.mean() / 255, i3.mean() / 255))
    del primary, partner, third, i1, i2, i3

    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(index, "RGBA").save(os.path.join(out_dir, "detail_index.tga"))  # uncompressed, as vanilla ships it
    Image.fromarray(intensity, "RGBA").save(os.path.join(out_dir, "detail_intensity.tga"))  # uncompressed, as vanilla ships it
    used = np.unique(index[..., :3])
    names = {v: k for k, v in idx.items()}
    print("wrote detail_index.tga and detail_intensity.tga at %d x %d" % (W, H))
    print("materials in use: " + ", ".join(names.get(int(u), "unused") for u in used if u != 255))


if __name__ == "__main__":
    main(*sys.argv[1:5])
