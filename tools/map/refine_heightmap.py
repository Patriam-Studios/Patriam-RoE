"""Turn a raw height export into the heightmap the game renders.

Two things are wrong with a raw export. WorldPainter holds whole block heights
over most of the world, so a gentle slope comes out as a staircase of flat
terraces with a one block riser between them, and the game draws every riser
as a hard edge: a black wall on a hillside, a straight seam across a plain.
And a block is a metre, so the relief is far shallower than the game's own
maps, which exaggerate their mountains many times over.

This pass therefore works in blocks, blurs the terraces into slopes, and then
applies the height curve in height_scale.py, which doubles the relief of the
lowlands and hills and compresses only the summits.

The coastline is preserved exactly. Any pixel that was land stays a whisker
above the sea and any that was sea stays a whisker below it, so provinces.png,
which was cut from the same coastline, still agrees with what is drawn.

Inputs, one of:
  --from-units <png>    an existing heightmap.png written with the old flat
                        160 units a block, as the mod shipped until now
  --from-export <png>   a fresh export where value = (height - minHeight) * 64,
                        so a block has 64 steps and nothing is rounded away
  --from-blocks <png>   a raw export where value = height - minHeight (whole blocks)

usage: python refine_heightmap.py --from-units old.png --sigma 1.5 out.png
"""
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs

Image.MAX_IMAGE_PIXELS = None
OLD_SEA = 3932.0
OLD_UNITS_PER_BLOCK = 160.0
OLD_SEA_UNITS_PER_BLOCK = OLD_SEA / (hs.SEA_BLOCK - hs.MIN_BLOCK)


def read_blocks(mode, path):
    a = np.array(Image.open(path)).astype(np.float32)
    if mode == "--from-units":
        r = a - OLD_SEA
        blocks = np.where(r >= 0, hs.SEA_BLOCK + r / OLD_UNITS_PER_BLOCK,
                          hs.SEA_BLOCK + r / OLD_SEA_UNITS_PER_BLOCK)
    elif mode == "--from-export":
        blocks = a / 64.0 + hs.MIN_BLOCK
    elif mode == "--from-blocks":
        blocks = a + hs.MIN_BLOCK
    else:
        raise SystemExit("unknown input mode " + mode)
    return blocks.astype(np.float32)


def gaussian(a, sigma):
    """Separable Gaussian blur, done a row block at a time to keep memory down."""
    from scipy.ndimage import gaussian_filter1d
    out = np.empty_like(a)
    step = 1024
    pad = int(4 * sigma) + 1
    H = a.shape[0]
    # columns first, in bands of rows with an overlap so the band edge is exact
    for y0 in range(0, H, step):
        y1 = min(H, y0 + step)
        s0, s1 = max(0, y0 - pad), min(H, y1 + pad)
        band = gaussian_filter1d(a[s0:s1], sigma, axis=0, mode="nearest")
        out[y0:y1] = band[y0 - s0:y1 - s0]
    for y0 in range(0, H, step):
        y1 = min(H, y0 + step)
        out[y0:y1] = gaussian_filter1d(out[y0:y1], sigma, axis=1, mode="nearest")
    return out


def main(argv):
    mode, src = argv[0], argv[1]
    sigma = 1.5
    if "--sigma" in argv:
        sigma = float(argv[argv.index("--sigma") + 1])
    out_path = argv[-1]
    t0 = time.time()

    blocks = read_blocks(mode, src)
    H, W = blocks.shape
    land = blocks > hs.SEA_BLOCK
    print("%d x %d, land %.1f%%, blocks %.1f..%.1f  (%.0fs)" % (W, H, land.mean() * 100, blocks.min(), blocks.max(), time.time() - t0))

    smooth = gaussian(blocks, sigma)
    del blocks
    print("blurred with sigma %.2f  (%.0fs)" % (sigma, time.time() - t0))

    # The coastline is the province map's coastline; keep every pixel on its own side.
    eps = np.float32(0.05)
    np.maximum(smooth, np.float32(hs.SEA_BLOCK) + eps, out=smooth, where=land)
    np.minimum(smooth, np.float32(hs.SEA_BLOCK) - eps, out=smooth, where=~land)
    del land

    units = hs.blocks_to_units(smooth)
    del smooth
    units = np.round(units).astype(np.uint16)
    land_u = units > hs.CK3_SEA
    print("units %d..%d, land %.1f%%, land mean %.0f, p90 %.0f  (%.0fs)" % (
        units.min(), units.max(), land_u.mean() * 100, units[land_u].mean(), np.percentile(units[land_u], 90), time.time() - t0))
    Image.fromarray(units).save(out_path, optimize=False)
    print("wrote", out_path, "(%.0fs)" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1:])
