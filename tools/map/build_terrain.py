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
# Blocks of rise a province pixel before bare rock shows through. Set at 1.6 the
# rock covered nearly half the land, because the ground is far sharper than it
# was, and the world went dark and purple under it. Ordinary hills keep their
# ground now and only a true cliff gives it up.
ROCK_SLOPE_START = 3.8
ROCK_SLOPE_FULL = 9.5
Q = 4                    # province pixels a blending pixel
BLEND_SIGMA = 2.4        # blending pixels, so about 50 blocks of softened join
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


def reconcile(slots, weights, used, H, W):
    """Give every texel the four grounds its neighbourhood carries.

    The game point samples detail_index and gathers a neighbouring texel's
    weight only into a slot whose material matches. A ground a texel does not
    carry in any of its four slots is therefore dropped rather than blended,
    which draws a hard seam and, where enough is dropped, leaves the ground
    barely drawn at all. Vanilla answers this by filling every slot: its four
    are in use over 100, 99, 67 and 56 per cent of its map, while two slots were
    all this ever wrote.

    So each texel takes the four grounds that weigh most across its own three by
    three neighbourhood, and keeps its own weight for each of them, which is
    nothing for a ground only its neighbours carry. The weights it did carry are
    unchanged, so the ground it draws is the same; it is only ready to be blended
    with what stands beside it."""
    def own_weight(mid):
        own = np.zeros((H, W), np.float32)
        for k in range(len(slots)):
            own += np.where(slots[k] == mid, weights[k], 0).astype(np.float32)
        return own

    top_w = [np.full((H, W), -1.0, np.float32) for _ in range(4)]
    top_id = [np.full((H, W), 255, np.uint8) for _ in range(4)]
    for mid in used:
        near = ndimage.uniform_filter(own_weight(mid), 3, mode="nearest")
        for r in range(4):
            take = near > top_w[r]
            for q in range(3, r, -1):                  # everything below it moves down one
                top_w[q] = np.where(take, top_w[q - 1], top_w[q])
                top_id[q] = np.where(take, top_id[q - 1], top_id[q])
            top_w[r] = np.where(take, near, top_w[r])
            top_id[r] = np.where(take, np.uint8(mid), top_id[r])
            near = np.where(take, np.float32(-1.0), near)     # placed once and no lower
            del take
        del near
    del top_w

    # each slot then takes this texel's own weight for the ground that sits there
    out_w = [np.zeros((H, W), np.float32) for _ in range(4)]
    for mid in used:
        own = own_weight(mid)
        for r in range(4):
            out_w[r] = np.where(top_id[r] == mid, own, out_w[r])
        del own
    return top_id, out_w


def agree(index, used, passes=1):
    """Make neighbouring texels name the same grounds.

    The game point samples detail_index and gathers each neighbouring texel's
    weight only into a slot whose material matches, so where two texels side by
    side name different grounds the weight is dropped instead of blended. That
    is what draws a hard seam, and where enough of it is dropped the ground is
    not drawn at all. Taking the vote of each three by three neighbourhood
    settles the disagreements: a lone texel that names a ground none of its
    neighbours carry gives way to theirs.
    """
    out = index
    for _ in range(passes):
        best = None
        best_id = np.zeros(out.shape, np.uint8)
        for mid in used:
            c = ndimage.uniform_filter((out == mid).astype(np.float32), 3, mode="nearest")
            if best is None:
                best, best_id[:] = c, np.uint8(mid)
            else:
                take = c > best
                best = np.where(take, c, best)
                best_id = np.where(take, np.uint8(mid), best_id)
            del c
        out = best_id
        del best
    return out


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
    # A region that insists on its own ground never takes snow. Mekanis is a
    # tableland carried high enough to clear its ravines, and the snowline would
    # otherwise put a white cap on a desert mesa.
    forced = [idx[m] for pair in tm.REGION_GROUND.values() for m in pair if m]
    forced += [idx[m] for m in tm.VURKIA_LAVA if m]
    snow_w[np.isin(primary, forced)] = 0.0
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
    cliff = w3 > 0.92
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

    # Settle the grounds so that neighbouring texels name the same ones, then
    # measure what is left, since every disagreement is a seam the game draws.
    used_now = [int(u) for u in np.unique(primary)]
    primary = agree(primary, used_now)
    third_used = [int(u) for u in np.unique(third) if u != 255]
    if third_used:
        settled = agree(np.where(third == 255, np.uint8(third_used[0]), third), third_used)
        third = np.where(third == 255, np.uint8(255), settled)
        del settled
    disagree = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = primary[:-dy or None, :-dx or None]
        b = primary[dy:, dx:]
        d = np.zeros((H, W), bool)
        d[:-dy or None, :-dx or None] = a != b
        disagree |= d
        del a, b, d
    print("texels whose neighbour names another ground: %.2f%% (every one of them is a seam)"
          % (disagree.mean() * 100))
    del disagree

    slots = [primary, partner, np.where(i3 > 0, third, np.uint8(255))]
    ids, ws = reconcile(slots, [i1, i2, i3], sorted(set(used_now) | set(third_used)), H, W)
    del slots, primary, partner, third, i1, i2, i3

    index = np.empty((H, W, 4), dtype=np.uint8)
    intensity = np.zeros((H, W, 4), dtype=np.uint8)
    total = sum(ws)
    np.maximum(total, 1.0, out=total)
    acc = np.zeros((H, W), np.int32)
    for r in range(4):
        index[..., r] = ids[r]
        if r < 3:
            v = np.round(ws[r] / total * 255.0).astype(np.int32)
            np.clip(v, 0, 255 - acc, out=v)
        else:
            v = 255 - acc
        intensity[..., r] = v.astype(np.uint8)
        acc += v
        del v
    index[..., 3] = np.where(intensity[..., 3] > 0, ids[3], np.uint8(255))
    del ids, ws, total, acc
    for r in range(4):
        print("   slot %d carries a ground over %5.1f%% of the map" % (r, (index[..., r] != 255).mean() * 100))
    assert (intensity.astype(np.int32).sum(2) == 255).all(), "weights must add to 255, as vanilla's do"

    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(index, "RGBA").save(os.path.join(out_dir, "detail_index.tga"))  # uncompressed, as vanilla ships it
    Image.fromarray(intensity, "RGBA").save(os.path.join(out_dir, "detail_intensity.tga"))  # uncompressed, as vanilla ships it
    used = np.unique(index[..., :3])
    names = {v: k for k, v in idx.items()}
    print("wrote detail_index.tga and detail_intensity.tga at %d x %d" % (W, H))
    print("materials in use: " + ", ".join(names.get(int(u), "unused") for u in used if u != 255))


if __name__ == "__main__":
    main(*sys.argv[1:5])
