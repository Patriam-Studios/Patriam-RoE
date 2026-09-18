"""Pack heightmap.png into packed_heightmap.png and indirection_heightmap.png.

The format is documented, and proven against every vanilla tile, in
heightmap_format.py. This module only decides where tiles go and then checks the
result with that proven decoder, never with a model of its own.

Structure deliberately follows vanilla rather than anything minimal: five
compression levels are declared, tiles with any relief are stored whole at
level 0, and perfectly flat tiles are stored at level 4, as vanilla stores its
open sea. A flat tile is identical at every resolution, so no height is lost.

Hard limits, each of which has already broken a load:
    Tile addresses are single bytes, so a band holds at most 256 by 256 tiles.
    Direct3D 11 will not create a texture over 16384 pixels in either dimension;
    an atlas 16640 wide came back null and crashed the game.

usage: python pack_heightmap.py <heightmap.png> <map_data dir>
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heightmap_format as hf

Image.MAX_IMAGE_PIXELS = None
D3D11_MAX = 16384
LEVELS = 5
FLAT_LEVEL = 4


def main(src_path, out_dir):
    hm = np.array(Image.open(src_path))
    H, W = hm.shape
    assert W % hf.STRIDE == 0 and H % hf.STRIDE == 0, "heightmap must be a multiple of 64"
    TX, TY = W // hf.STRIDE, H // hf.STRIDE
    pad = hf.padded(hm)
    del hm

    detail, flat = {}, {}
    slot_of = np.empty((TY, TX), dtype=np.int64)
    level_of = np.empty((TY, TX), dtype=np.uint8)
    order_detail, order_flat = [], []
    for ty in range(TY):
        for tx in range(TX):
            t = hf.source_tile(pad, tx, ty, 0)
            if t.min() == t.max():
                v = int(t[0, 0])
                i = flat.get(v)
                if i is None:
                    i = len(order_flat); flat[v] = i; order_flat.append(v)
                slot_of[ty, tx] = i; level_of[ty, tx] = FLAT_LEVEL
            else:
                key = t.tobytes()
                i = detail.get(key)
                if i is None:
                    i = len(order_detail); detail[key] = i; order_detail.append((tx, ty))
                slot_of[ty, tx] = i; level_of[ty, tx] = 0
    n0, n4 = len(order_detail), len(order_flat)

    n_detail = hf.TILE
    n_flat = (hf.STRIDE >> FLAT_LEVEL) + 1
    cols0 = max(1, min(D3D11_MAX // n_detail, 256, math.ceil(math.sqrt(n0))))
    rows0 = math.ceil(n0 / cols0) if n0 else 0
    cols4 = max(1, min(256, n4))
    rows4 = math.ceil(n4 / cols4) if n4 else 0
    assert rows0 <= 256 and rows4 <= 256, "a band needs more than 256 rows of tiles"

    band0 = rows0 * n_detail
    offsets = [0, band0, band0, band0, band0]
    ah = band0 + rows4 * n_flat
    aw = max(cols0 * n_detail, cols4 * n_flat)
    assert aw <= D3D11_MAX and ah <= D3D11_MAX, "atlas %d x %d exceeds the texture limit" % (aw, ah)
    print("%d tiles: %d with relief at level 0, %d flat values at level %d" % (TX * TY, n0, n4, FLAT_LEVEL))
    print("atlas %d x %d, level 0 band %d x %d tiles, level %d band %d x %d tiles"
          % (aw, ah, cols0, rows0, FLAT_LEVEL, cols4, rows4))

    dtype = pad.dtype
    atlas = np.zeros((ah, aw), dtype=dtype)

    def place(level, col, row, samples):
        n = (hf.STRIDE >> level) + 1
        bottom = ah - (offsets[level] + row * n)
        atlas[bottom - n:bottom, col * n:col * n + n] = samples

    for i, (tx, ty) in enumerate(order_detail):
        place(0, i % cols0, i // cols0, hf.source_tile(pad, tx, ty, 0))
    for i, v in enumerate(order_flat):
        place(FLAT_LEVEL, i % cols4, i // cols4, np.full((n_flat, n_flat), v, dtype=dtype))

    ind = np.zeros((TY, TX, 4), dtype=np.uint8)
    detail_mask = level_of == 0
    ind[..., 0] = np.where(detail_mask, slot_of % cols0, slot_of % cols4)
    ind[..., 1] = np.where(detail_mask, slot_of // cols0, slot_of // cols4)
    ind[..., 2] = np.where(detail_mask, 1, 1 << FLAT_LEVEL)
    ind[..., 3] = level_of

    # Judge the output with the decoder proven against vanilla, on every tile.
    worst = 0
    for ty in range(TY):
        for tx in range(TX):
            col, row, _, level = (int(v) for v in ind[ty, tx])
            got = hf.atlas_tile(atlas, offsets, level, col, row).astype(np.int64)
            want = hf.source_tile(pad, tx, ty, level).astype(np.int64)
            assert got.shape == want.shape, "tile (%d, %d) has the wrong size" % (tx, ty)
            worst = max(worst, int(np.abs(got - want).max()))
    assert worst == 0, "a tile does not round trip, worst sample error %d" % worst
    print("every one of %d tiles round trips exactly through the vanilla proven decoder" % (TX * TY))

    zero = flat.get(0)
    empty = (zero % cols4, zero // cols4) if zero is not None else (0, 0)
    Image.fromarray(atlas).save(os.path.join(out_dir, "packed_heightmap.png"), optimize=True)
    Image.fromarray(ind, mode="RGBA").save(os.path.join(out_dir, "indirection_heightmap.png"), optimize=True)
    with open(os.path.join(out_dir, "heightmap.heightmap"), "w", encoding="utf-8-sig", newline="\n") as f:
        f.write('heightmap_file="map_data/packed_heightmap.png"\n'
                'indirection_file="map_data/indirection_heightmap.png"\n'
                "original_heightmap_size={ %d %d }\n" % (W, H) +
                "tile_size=65\n"
                "should_wrap_x=no\n"
                "level_offsets={ " + " ".join("{ 0 %d }" % o for o in offsets) + " }\n"
                "max_compress_level=%d\n" % (LEVELS - 1) +
                "empty_tile_offset={ %d %d }\n" % empty)
    print("wrote packed_heightmap.png, indirection_heightmap.png, heightmap.heightmap")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
