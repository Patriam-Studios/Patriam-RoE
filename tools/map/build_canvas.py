"""The whole world canvas: 16384 by 6656 province pixels, 5.19 blocks each.

No texture may exceed 16384 pixels in either direction, so the whole 84992
block width of the Patriam world fits only at 5.1875 blocks a province pixel.
That is coarser than the 4.09 the mod ran at, and it is the density Alexander
chose so that the whole world sits on one canvas.

Sources, until the reboot lets the step 2 export run:

* the heightmap the mod shipped for the inner world, itself a 4 blocks a pixel
  sample, resampled to the new grid (it is what the 943 baronies were cut
  against, so their coastline survives the move),
* the whole world overview at 8 blocks a pixel for everything east of block
  48448, where the world is unfinished anyway,
* nothing for biomes and trees yet; those wait on the export.

The eastern filler, the flat default ground WorldPainter gives every new tile,
is not land and becomes sea. It is found by flood fill from the far corner
over its own narrow band of heights, so the two real landmasses out east,
which the sea surrounds, are left alone.

The 943 baronies keep their numbers, so every title, holding and line of
history stays valid. Their pixels are carried across by nearest sampling and
then reconciled with the new coastline: a barony pixel the new heightmap puts
under water is dropped, and new land within two pixels of a barony joins it.
The wastes and the seas are gridded afresh over the whole canvas.

Outputs: D:/Patriam-CK3-map/full/canvas_blocks.png (the raw heightmap in the
export's fixed point form, for refine_heightmap.py), full_pid.npy and
map_ranges.json beside it, and every file in map_data except the packed
heightmap, which pack_heightmap.py writes from the refined heightmap.

usage: python build_canvas.py [--write]
"""
import io
import json
import os
import sys
import time
from collections import deque

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
MD = os.path.join(MOD, "map_data")
SRC = "D:/Patriam-CK3-map"
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
OUT = os.path.join(SRC, "full")
WRITE = "--write" in sys.argv

BLOCKS_W, BLOCKS_H = 84992, 34560
PW, PH = 16384, 6656
HW, HH = PW * 2, PH * 2
BPP_X, BPP_Y = BLOCKS_W / PW, BLOCKS_H / PH          # blocks per province pixel
INNER_BLOCKS = 48448                                  # the old canvas ended here
OLD_PW, OLD_PH = 11840, 8448
OLD_UNITS_PER_BLOCK = 160.0
OLD_SEA_UNITS_PER_BLOCK = hs.CK3_SEA / (hs.SEA_BLOCK - hs.MIN_BLOCK)
SEA_CELL, LAND_CELL, D = 130, 170, 4                  # as the first canvas used
LIFT_REGIONS = ("mekanis",)      # raised clear of the water rather than flattened
CARVE = 0.5                      # how far the resampling leans towards the deepest of a neighbourhood

t0 = time.time()


def say(*a):
    print("%6.0fs" % (time.time() - t0), *a, flush=True)


# ---------------------------------------------------------------- heightmap
def old_units_to_blocks(u):
    r = u.astype(np.float32) - np.float32(hs.CK3_SEA)
    out = np.float32(hs.SEA_BLOCK) + r / np.float32(OLD_SEA_UNITS_PER_BLOCK)
    land = r >= 0
    out[land] = np.float32(hs.SEA_BLOCK) + r[land] / np.float32(OLD_UNITS_PER_BLOCK)
    return out


def resize_f(a, size):
    return np.array(Image.fromarray(a.astype(np.float32)).resize(size, Image.BILINEAR), dtype=np.float32)


def blocks_from_old_sources():
    """The canvas heightmap before the step 2 export existed: the old inner
    heightmap resampled, and the 8 block overview for everything east of it."""
    say("loading the inner heightmap")
    old = np.array(Image.open(os.path.join(SRC, "heightmap_old160.png")))
    west_w = int(round(INNER_BLOCKS / (BLOCKS_W / HW)))   # heightmap pixels of the inner world
    west = np.empty((HH, west_w), dtype=np.float32)
    band = 1024
    for y0 in range(0, old.shape[0], band * 2):
        # resample in bands of source rows to keep the float copy small
        src = old_units_to_blocks(old[y0:y0 + band * 2])
        ty0 = int(round(y0 * HH / old.shape[0])); ty1 = int(round(min(old.shape[0], y0 + band * 2) * HH / old.shape[0]))
        west[ty0:ty1] = resize_f(src, (west_w, ty1 - ty0))
    del old
    say("inner world resampled to %d x %d" % (west_w, HH))

    say("loading the whole world overview")
    ov = np.array(Image.open(os.path.join(SRC, "patriam_step8.png"))).astype(np.float32) + hs.MIN_BLOCK   # blocks
    # the filler: flood fill from the far corner over its narrow band of heights
    filler_band = (ov >= 65.0) & (ov <= 72.0)
    filler_band[:, :INNER_BLOCKS // 8] = False          # never west of the inner world
    lab, n = ndimage.label(filler_band)
    corner = lab[-1, -1]
    filler = lab == corner if corner else np.zeros_like(filler_band)
    # The filler's own noise leaves single pixels a block outside the band, which
    # would stand as thousands of one pixel islands; they are holes in the mask.
    filler = ndimage.binary_fill_holes(filler)
    # And any speck of land out east that is not one of the two real landmasses
    # goes the same way, so an unfinished coast does not shed islets.
    east_land = ov > hs.SEA_BLOCK
    east_land[:, :INNER_BLOCKS // 8] = False
    lab2, n2 = ndimage.label(east_land & ~filler)
    sizes = np.bincount(lab2.ravel())
    specks = np.isin(lab2, np.nonzero(sizes < 400)[0]) & (lab2 > 0)
    filler |= specks
    del lab2, east_land, specks
    fy, fx = np.nonzero(filler)
    say("filler: %d overview pixels, %.1f%% of the world, x %d..%d y %d..%d of %d x %d, sunk to the sea floor" % (
        filler.sum(), filler.mean() * 100, fx.min(), fx.max(), fy.min(), fy.max(), ov.shape[1], ov.shape[0]))
    del fy, fx
    ov[filler] = 52.0                                     # the eastern sea floor
    del lab, filler_band
    east_src = ov[:, INNER_BLOCKS // 8:]
    # The overview carries the sea floor as a block of noise, which an upscale
    # turns into relief on every sea tile and more relief tiles than the packed
    # heightmap can address. The floor of an unfinished sea is one flat depth.
    east_src = np.where(east_src < hs.SEA_BLOCK - 0.5, np.float32(52.0), east_src)
    east = resize_f(east_src, (HW - west_w, HH))
    del ov, east_src
    blocks = np.concatenate([west, east], axis=1)
    del west, east
    return blocks


def lift_region(prefix):
    """The regions whose ground is raised rather than flattened where it lies
    under the water plane, at sixteen blocks a pixel.

    Mekanis is cut by ravines that reach down to y 1 in the source, far below the
    plane at 62. Flattening them, as every other basin is flattened, is what left
    the mesa reading as a plain with hills on it. Instead the whole tableland is
    carried up until its deepest floor clears the water, which is what a mesa is:
    high ground with canyons cut into it."""
    import regions as rg
    out, names = rg.region_map(prefix)
    m = np.zeros(out.shape, bool)
    for name in LIFT_REGIONS:
        m |= out == names.index(name) + 1
    say("regions lifted clear of the water rather than flattened: %s, %.2f%% of the world"
        % (", ".join(LIFT_REGIONS), m.mean() * 100))
    return m


def apply_lift(blocks, prefix):
    """Raise each lifted region until its deepest dry ground clears the water,
    smoothly, and never near its own coast, so the coastline does not move."""
    import regions as rg
    out, names = rg.region_map(prefix)
    m = np.zeros(out.shape, bool)
    for name in LIFT_REGIONS:
        m |= out == names.index(name) + 1
    q = 8                                                   # eighths of the canvas
    mc = np.array(Image.fromarray(m.astype(np.uint8)).resize((HW // q, HH // q), Image.NEAREST)).astype(bool)
    # the LOWEST canvas pixel of each little square, not every eighth one: a
    # ravine four blocks wide falls between samples and the lift came out at
    # three blocks instead of sixty
    small = blocks.reshape(HH // q, q, HW // q, q).min(axis=(1, 3))
    deficit = np.where(mc & (small < hs.SEA_BLOCK + 1.0), np.float32(hs.SEA_BLOCK + 1.0) - small, 0.0).astype(np.float32)
    if deficit.max() <= 0:
        return blocks
    spread = ndimage.maximum_filter(deficit, size=25)        # about five hundred blocks
    spread = ndimage.gaussian_filter(spread, 10)
    # the real ocean, not the region's own ravines, which are under the plane
    # only until the lift raises them
    sea = (blocks[::q, ::q] <= hs.SEA_BLOCK) & ~mc
    dist = ndimage.distance_transform_edt(~sea).astype(np.float32)
    taper = np.clip((dist - 4.0) / 12.0, 0.0, 1.0) * ndimage.gaussian_filter(mc.astype(np.float32), 8)
    off = spread * taper
    say("lift: up to %.1f blocks, mean %.1f over the lifted regions"
        % (off.max(), off[mc].mean() if mc.any() else 0.0))
    full = np.array(Image.fromarray(off).resize((HW, HH), Image.BILINEAR), dtype=np.float32)
    del off, spread, taper, dist, sea, deficit
    blocks += full
    del full
    # anything still under the plane in those regions is flattened as before
    mfull = np.array(Image.fromarray(m.astype(np.uint8)).resize((HW, HH), Image.NEAREST)).astype(bool)
    stubborn = mfull & (blocks <= hs.SEA_BLOCK)
    blocks[stubborn] = np.float32(hs.SEA_BLOCK + 0.3)
    say("still under the plane after the lift and flattened: %d pixels" % int(stubborn.sum()))
    return blocks


def river_band(prefix, EW, EH):
    """Every block the world paints as river, at the export's own size. These
    are drawn as rivers by build_rivers.py rather than cut into the ground."""
    table = tm.load_biome_table(prefix + "_biomes.txt")
    want = [i for i, (share, name) in table.items() if "river" in name.lower()]
    bio = np.array(Image.open(prefix + "_biome.png")).astype(np.int32) - 1
    assert bio.shape == (EH, EW), "biome raster is not the size of the height raster"
    m = np.isin(bio, want)
    del bio
    # Only the finished world has rivers. East of it the shallow water over the
    # unfinished ground is called river as well, and a whole sea of it would
    # have come up as land.
    m[:, INNER_BLOCKS // 2:] = False
    say("river biome in the finished world: %.2f%% of the export, kept as land for build_rivers.py"
        % (m.mean() * 100))
    return m


def blocks_from_export(prefix):
    """The canvas heightmap from the whole world export, two blocks a pixel with
    sixty four steps to the block, so nothing arrives rounded into terraces.

    Water: WorldPainter keeps a water level for every block. Where it stands
    above the ground and above the sea it is either a lake or a river.

    A lake is lowered until the same depth of water covers it at the one water
    plane the game has. A river is left where it is, only lifted clear of the
    water plane if its bed lay below it, because the game draws rivers from
    map_data/rivers.png as meshes laid on the ground: cutting the channel down
    to sea level, as this did at first, turns every river into an inlet of the
    sea. build_rivers.py draws them from the same river biome.

    Ground below the sea with no water over it is a dry basin, the floor of a
    canyon in the mesa of Mekanis among others, and is lifted just clear of the
    sea so that it stays land."""
    say("loading the export")
    h = np.array(Image.open(prefix + "_height.png"))
    wl = np.array(Image.open(prefix + "_water.png"))
    EH, EW = h.shape
    assert (EW, EH) == (BLOCKS_W // 2, BLOCKS_H // 2), "export is not the whole world at step 2"

    # masks at a quarter of the export, 8 blocks a pixel, like the overview was
    q = 4
    hq = h[::q, ::q].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
    wq = wl[::q, ::q].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
    # the filler begins on a tile edge, half a tile west of where the inner world ends
    east0 = (INNER_BLOCKS // 128) * 128 // 8
    # from the sea's own level up: the filler's rim slopes down to the water and a
    # band starting above it left that rim standing as a ridge along its edge
    filler_band = (hq > hs.SEA_BLOCK) & (hq <= 72.0)
    filler_band[:, :east0] = False
    lab, n = ndimage.label(filler_band)
    corner = lab[-1, -1]
    sink = lab == corner if corner else np.zeros_like(filler_band)
    sink = ndimage.binary_fill_holes(sink)
    east_land = (hq > hs.SEA_BLOCK) & ~(wq > hq)
    east_land[:, :east0] = False
    lab2, n2 = ndimage.label(east_land & ~sink)
    sizes = np.bincount(lab2.ravel())
    sink |= np.isin(lab2, np.nonzero(sizes < 400)[0]) & (lab2 > 0)
    # a mask sampled every fourth pixel misses the specks between its samples,
    # which stood as a dotted line along the filler's edge; widen it over them
    sink = ndimage.binary_dilation(sink, iterations=2)
    say("filler and its islets: %.1f%% of the world" % (sink.mean() * 100))
    del lab, lab2, filler_band, east_land

    # the unfinished island off the north east of the inner world, excluded
    # from the first canvas and excluded still: the province map has sea there
    bx0, bx1, by0, by1 = 39000 // 8, 47800 // 8, 0, 9800 // 8     # a margin round it for its fringe of islets
    land_q = (hq > hs.SEA_BLOCK) & ~(wq > hq)
    lab3, n3 = ndimage.label(land_q)
    box_area = (bx1 - bx0) * (by1 - by0)
    sunk_px = 0
    isle = np.zeros_like(sink)
    for k in np.unique(lab3[by0:by1, bx0:bx1]):
        if k == 0:
            continue
        ys_, xs_ = np.nonzero(lab3 == k)
        if bx0 <= xs_.mean() <= bx1 and by0 <= ys_.mean() <= by1 and len(ys_) < 0.6 * box_area:
            isle[ys_, xs_] = True
            sunk_px += len(ys_)
    # and its coast, for the same specks, which otherwise trace its outline in the sea
    isle = ndimage.binary_dilation(isle, iterations=6)
    say("land at 8 blocks taken by widening the island's mask: %d" % int((isle & land_q & ~sink).sum() - sunk_px))
    sink |= isle
    del isle
    say("excluded north east island: %d pixels at 8 blocks sunk" % sunk_px)
    del lab3, land_q, hq, wq

    # the canvas, a band at a time; bands overlap so the resampling filter
    # never sees an edge that is not the edge of the world
    river_px = river_band(prefix, EW, EH)
    lift_q = lift_region(prefix)
    blocks = np.empty((HH, HW), dtype=np.float32)
    SB, TB, SO, TO = EH // 8, HH // 8, 135, 104     # source and target band and overlap rows, exact ratios
    stats = {"lake": 0, "basin": 0, "river": 0}
    for b in range(8):
        s0, s1 = b * SB, (b + 1) * SB
        a0, a1 = max(0, s0 - SO), min(EH, s1 + SO)
        gb = h[a0:a1].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
        wb = wl[a0:a1].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
        wet = wb > gb
        riv = river_px[a0:a1]
        # a river keeps its bed and only comes up if the bed lay under the water
        # plane, since the game lays the river mesh on the ground
        # Only a genuine river bed comes up. WorldPainter calls a great deal of
        # the shallow water out east river as well, and lifting a sea floor a
        # dozen blocks down would have laid a film of land across the ocean.
        lifted = riv & (gb <= hs.SEA_BLOCK) & (gb > np.float32(hs.SEA_BLOCK - 8.0))
        gb[lifted] = np.float32(hs.SEA_BLOCK + 0.35)
        lake = wet & (wb > hs.SEA_BLOCK) & ~riv
        gb[lake] = np.maximum(np.float32(hs.SEA_BLOCK) - (wb[lake] - gb[lake]), np.float32(hs.MIN_BLOCK))
        # Ground at the very bottom with no water over it is not a basin: it is a
        # part of the world with no tile at all, which the export writes as the
        # floor of the height range. Lifting that made specks of land in the void.
        offq = a0 % 8
        mk = np.repeat(np.repeat(lift_q[a0 // 8:-(-a1 // 8)], 8, axis=0), 8, axis=1)[offq:offq + a1 - a0, :EW]
        basin = ~wet & ~riv & ~mk & (gb <= hs.SEA_BLOCK) & (gb > np.float32(hs.MIN_BLOCK + 0.5))
        # the deeper the floor the lower it sits, so that a canyon in the mesa
        # does not come out as one flat pan
        gb[basin] = np.float32(hs.SEA_BLOCK + 0.3) + 0.7 * (1.0 - np.clip(
            (np.float32(hs.SEA_BLOCK) - gb[basin]) / 20.0, 0.0, 1.0))
        stats["lake"] += int(lake[s0 - a0:s1 - a0].sum()); stats["basin"] += int(basin[s0 - a0:s1 - a0].sum())
        stats["river"] += int(lifted[s0 - a0:s1 - a0].sum())
        del riv, lifted, mk
        off = a0 % q                                   # the mask row a band starts part way through
        m = np.repeat(np.repeat(sink[a0 // q:-(-a1 // q)], q, axis=0), q, axis=1)[off:off + a1 - a0, :EW]
        gb[m] = 52.0
        del wb, wet, lake, basin, m
        th = int(round((a1 - a0) * HH / EH))
        # A gorge only a few blocks wide is averaged away by the resampling, and
        # the mesa of Mekanis is cut through with them. Carrying the lowest of
        # each little neighbourhood alongside the average, and leaning towards it
        # where the two disagree, cuts those channels back in.
        up = resize_f(gb, (HW, th))
        deep = resize_f(ndimage.minimum_filter(gb, size=3), (HW, th))
        gap = np.clip(up - deep - 2.0, 0.0, None)
        del deep
        carved = up - np.float32(CARVE) * gap
        keep_dry = up > hs.SEA_BLOCK
        up = np.where(keep_dry, np.maximum(carved, np.float32(hs.SEA_BLOCK + 0.15)), carved)
        del carved, gap, keep_dry
        t_off = int(round((s0 - a0) * HH / EH))
        blocks[b * TB:(b + 1) * TB] = up[t_off:t_off + TB]
        del gb, up
        say("band %d of 8" % (b + 1))
    del h, wl
    blocks = apply_lift(blocks, prefix)
    say("lakes lowered to the sea plane: %.2f%% of the export; dry basins lifted: %.2f%%; "
        "river beds raised clear of the water: %.2f%%" % (
            stats["lake"] * 100.0 / (EW * EH), stats["basin"] * 100.0 / (EW * EH),
            stats["river"] * 100.0 / (EW * EH)))

    # The deep sea. Real bathymetry is kept near the coast, where it shows
    # through the water, and blended to one flat floor beyond it, because a
    # sea floor of one block noise makes every sea tile a relief tile and the
    # packed heightmap can address only so many.
    landp_ = blocks[::2, ::2] > hs.SEA_BLOCK
    dist = ndimage.distance_transform_edt(~landp_).astype(np.float32)      # province pixels from land
    wgt = np.clip((dist - 12.0) / 12.0, 0.0, 1.0)
    del dist, landp_
    wfull = np.array(Image.fromarray(wgt).resize((HW, HH), Image.BILINEAR), dtype=np.float32)
    del wgt
    sea = blocks <= hs.SEA_BLOCK
    floor = np.float32(hs.MIN_BLOCK)
    for y0 in range(0, HH, 1024):
        sl = slice(y0, y0 + 1024)
        bb, ww, ss = blocks[sl], wfull[sl], sea[sl]
        bb[ss] = bb[ss] * (1.0 - ww[ss]) + floor * ww[ss]
    del wfull, sea
    return blocks


if "--export" in sys.argv:
    blocks = blocks_from_export(sys.argv[sys.argv.index("--export") + 1])
else:
    blocks = blocks_from_old_sources()
say("canvas heightmap %d x %d, blocks %.1f..%.1f" % (blocks.shape[1], blocks.shape[0], blocks.min(), blocks.max()))

land_hm = blocks > hs.SEA_BLOCK
landp = land_hm[::2, ::2]
say("land %.1f%% of the canvas" % (landp.mean() * 100))

# ------------------------------------------------------------ province map
say("carrying the baronies across")
sk = np.load(os.path.join(SRC, "sk_pid.npy"))
bx0, by0, bx1, by1 = [int(v) for v in np.load(os.path.join(SRC, "sk_box.npy"))]
scale_x = (INNER_BLOCKS / OLD_PW) / BPP_X            # old pixel -> new pixel
scale_y = (BLOCKS_H / OLD_PH) / BPP_Y
nx0, nx1 = int(np.floor(bx0 * scale_x)), int(np.ceil(bx1 * scale_x))
ny0, ny1 = int(np.floor(by0 * scale_y)), int(np.ceil(by1 * scale_y))
ys, xs = np.mgrid[ny0:ny1, nx0:nx1]
oy = np.clip(np.round(ys / scale_y).astype(np.int64) - by0, 0, sk.shape[0] - 1)
ox = np.clip(np.round(xs / scale_x).astype(np.int64) - bx0, 0, sk.shape[1] - 1)
sub = sk[oy, ox]                                       # -1 outside, else id - 1
full = np.zeros((PH, PW), dtype=np.int32)
full[ny0:ny1, nx0:nx1] = np.where(sub >= 0, sub + 1, 0)
del ys, xs, oy, ox, sub
# reconcile with the new coastline
drowned = (full > 0) & ~landp
full[drowned] = 0
near = ndimage.binary_dilation(full > 0, iterations=2) & landp & (full == 0)
if near.any():
    # nearest barony for each such pixel
    dist, (iy, ix) = ndimage.distance_transform_edt(full == 0, return_indices=True)
    full[near] = full[iy[near], ix[near]]
    del dist, iy, ix
sk_count = int((full > 0).sum())
present = np.unique(full[full > 0])
say("baronies: %d pixels, %d of 943 present, %d pixels drowned, %d pixels joined" % (sk_count, len(present), int(drowned.sum()), int(near.sum())))
assert len(present) == 943, "a barony vanished in the move"
del drowned, near
NEXT = 944

# ------------------------------------------------------ wastes and the seas
h2, w2 = PH // D, PW // D
land_s = landp[:h2 * D, :w2 * D].reshape(h2, D, w2, D).all(axis=(1, 3))
sk_s = (full[:h2 * D, :w2 * D].reshape(h2, D, w2, D) > 0).any(axis=(1, 3))
sea_s = ~landp[:h2 * D, :w2 * D].reshape(h2, D, w2, D).any(axis=(1, 3))


def partition(mask, target, first_id):
    H, W = mask.shape
    ncy = max(1, round(H / target)); ncx = max(1, round(W / target))
    ch = -(-H // ncy); cw = -(-W // ncx)
    lab = np.zeros(mask.shape, dtype=np.int32)
    nid = first_id
    for cy in range(0, H, ch):
        for cx in range(0, W, cw):
            cell = mask[cy:cy + ch, cx:cx + cw]
            if not cell.any():
                continue
            l, n = ndimage.label(cell)
            sizes = np.bincount(l.ravel())
            for k in range(1, n + 1):
                if sizes[k] < 4:
                    continue
                lab[cy:cy + ch, cx:cx + cw][l == k] = nid
                nid += 1
    return lab, nid


imp_s, NEXT2 = partition(land_s & ~sk_s, LAND_CELL, NEXT)
imp_first, imp_last = NEXT, NEXT2 - 1
sea_lab_s, NEXT3 = partition(sea_s, SEA_CELL, NEXT2)
sea_first, sea_last = NEXT2, NEXT3 - 1
say("wastes %d..%d (%d), seas %d..%d (%d)" % (imp_first, imp_last, imp_last - imp_first + 1, sea_first, sea_last, sea_last - sea_first + 1))


def up(a):
    return np.repeat(np.repeat(a, D, axis=0), D, axis=1)


grid = np.zeros((PH, PW), dtype=np.int32)
grid[:h2 * D, :w2 * D] = up(imp_s) + up(sea_lab_s)
full = np.where(full > 0, full, grid)
del grid, imp_s, sea_lab_s, land_s, sk_s, sea_s

for step in range(60):
    gaps = full == 0
    if not gaps.any():
        say("gaps closed after %d dilations" % step)
        break
    src = np.zeros_like(full)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.zeros_like(full)
        ys_ = slice(max(dy, 0), full.shape[0] + min(dy, 0)); xs_ = slice(max(dx, 0), full.shape[1] + min(dx, 0))
        yd = slice(max(-dy, 0), full.shape[0] + min(-dy, 0)); xd = slice(max(-dx, 0), full.shape[1] + min(-dx, 0))
        sh[ys_, xs_] = full[yd, xd]
        src = np.where((src == 0) & gaps & (sh != 0), sh, src)
    if not (src != 0).any():
        say("WARNING %d pixels could not be filled" % int(gaps.sum()))
        break
    full = np.where(src != 0, src, full)
N = int(full.max())
ranges = {"sk_last": 943, "imp_first": imp_first, "imp_last": imp_last, "sea_first": sea_first, "sea_last": sea_last, "total": N}
say("total provinces %d" % N)

if not WRITE:
    say("dry run, nothing written")
    sys.exit(0)

os.makedirs(OUT, exist_ok=True)
np.save(os.path.join(OUT, "full_pid.npy"), full)
json.dump(ranges, open(os.path.join(OUT, "map_ranges.json"), "w"), indent=1)

# the raw heightmap in the export's fixed point form, for refine_heightmap.py
raw = np.round((blocks + np.float32(-hs.MIN_BLOCK)) * 64.0).astype(np.uint16)
Image.fromarray(raw).save(os.path.join(OUT, "canvas_blocks.png"), optimize=False)
del raw
say("wrote canvas_blocks.png")

# ---------------------------------------------------------------- map_data
os.makedirs(MD, exist_ok=True)
vals = np.arange(0, 256, 16)
cube = np.array([(r, g, b) for r in vals for g in vals for b in vals])
cube = cube[cube.sum(axis=1) > 0]
rng = np.random.default_rng(6355); rng.shuffle(cube)
assert len(cube) >= N, "only %d colours for %d provinces" % (len(cube), N)
cols = cube[:N]
img = np.zeros((PH, PW, 3), dtype=np.uint8)
nz = full > 0
img[nz] = cols[full[nz] - 1]
Image.fromarray(img).save(os.path.join(MD, "provinces.png"), optimize=True)
del img
say("wrote provinces.png")


def name_for(i):
    if i <= 943:
        return "SK_%04d" % i
    if i <= imp_last:
        return "WASTE_%04d" % i
    return "SEA_%04d" % i


with open(os.path.join(MD, "definition.csv"), "w", newline="", encoding="utf-8") as f:
    f.write("0;0;0;0;x;x;\n")
    for i in range(1, N + 1):
        r, g, b = cols[i - 1]
        f.write("%d;%d;%d;%d;%s;x;\n" % (i, r, g, b, name_for(i)))
say("wrote definition.csv")

# rivers.png is drawn by build_rivers.py, which needs the finished heightmap,
# so all that is written here is a map with no rivers on it at all.
riv = np.where(landp, 255, 254).astype(np.uint8)
rim = Image.fromarray(riv, mode="P")
rim.putpalette(Image.open(os.path.join(GAME, "map_data", "rivers.png")).getpalette())
rim.save(os.path.join(MD, "rivers.png"), optimize=True)
del riv, rim
say("wrote rivers.png, without rivers; build_rivers.py draws them")

# province terrain: the baronies keep the types they had, the wastes are mountains
old_terrain = io.open(os.path.join(MOD, "common", "province_terrain", "00_province_terrain.txt"), encoding="utf-8-sig").read().splitlines()
keep = [l for l in old_terrain if "=" in l and l.split("=")[0].strip().isdigit() and int(l.split("=")[0]) <= 943]
lines = ["default_land=plains", "default_sea=sea", "default_coastal_sea=coastal_sea"] + keep
lines += ["%d=mountains" % i for i in range(imp_first, imp_last + 1)]
io.open(os.path.join(MOD, "common", "province_terrain", "00_province_terrain.txt"), "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
say("wrote province terrain, %d barony lines kept" % len(keep))

props = ["# Province properties for Patriam: Rise of Empires.",
         "# Vanilla's file of the same name sets winter severity for 12717 provinces",
         "# numbered up to 13269. This world has fewer, and applying winter to a",
         "# province that does not exist dereferenced null when a session started.",
         "# A file with the same name always overrides vanilla's, so this is a",
         "# guaranteed replacement rather than one that depends on replace_path.", ""]
for i in range(1, N + 1):
    props.append("%d ={\n\twinter_severity_bias = 0.0\n}" % i)
io.open(os.path.join(MOD, "common", "province_terrain", "01_province_properties.txt"), "w", encoding="utf-8-sig", newline="\n").write("\n".join(props) + "\n")
say("wrote province properties")

open(os.path.join(MD, "default.map"), "w", encoding="utf-8", newline="\n").write("""definitions = "definition.csv"
provinces = "provinces.png"
rivers = "rivers.png"
topology = "heightmap.heightmap"
adjacencies = "adjacencies.csv"
island_region = "island_region.txt"
seasons = "seasons.txt"

#############
# SEA ZONES
#############
sea_zones = RANGE { %d %d }

#####################
# IMPASSABLE TERRAIN
#####################
# Every landmass that is not Southern Kallonia yet, and the Great Mountain Ring.
# These become real provinces as each region is provinced in turn.
impassable_mountains = RANGE { %d %d }
""" % (sea_first, sea_last, imp_first, imp_last))
open(os.path.join(MD, "adjacencies.csv"), "w", newline="", encoding="utf-8").write(
    "From;To;Type;Through;start_x;start_y;stop_x;stop_y;Comment\n-1;-1;;-1;-1;-1;-1;-1;\n")
open(os.path.join(MD, "island_region.txt"), "w", encoding="utf-8", newline="\n").write(
    "# Island regions, meaning no land path to the mainland.\n# The game uses these to shorten path finding.\n"
    "# Filled in once the counties of the offshore islands are named.\n")
open(os.path.join(MD, "seasons.txt"), "w", encoding="utf-8", newline="\n").write(
    "winter = {\n\tstart_date=00.12.01\n\tend_date=00.02.31\n}\n\nspring = {\n\tstart_date=00.03.01\n\tend_date=00.05.31\n}\n\n"
    "summer = {\n\tstart_date=00.06.01\n\tend_date=00.08.31\n}\n\nautumn = {\n\tstart_date=00.09.01\n\tend_date=00.11.30\n}\n")
say("wrote default.map, adjacencies, island_region, seasons")
say("done; next: refine_heightmap.py --from-export %s/canvas_blocks.png, then pack, nodes, masks, textures, terrain, locators" % OUT)
