"""The packed heightmap format, decoded from vanilla and proven against it.

A heightmap of W by H is cut into tiles on a 64 pixel grid, (W / 64) by (H / 64)
of them. Every tile holds 65 by 65 samples, sharing one row and one column with
its neighbours. Tile (tx, ty) covers heightmap rows ty*64 - 1 through ty*64 + 63
and columns tx*64 through tx*64 + 64. The shared row is therefore at the top of
each tile and the shared column at its right, with the map edge replicated
where a tile runs off it.

indirection_heightmap.png holds one RGBA pixel per tile:
    red    column of the tile within its compression band
    green  row of the tile within its compression band
    blue   two to the power of the compression level
    alpha  the compression level, 0 to max_compress_level

A tile at level L keeps every (1 << L)th sample, so it is (64 >> L) + 1 pixels
square in the atlas. Bands are stacked by level, and level_offsets gives each
band's position MEASURED FROM THE BOTTOM of packed_heightmap.png. Within a band
a tile's rows run in ordinary top to bottom image order.

Getting either of those two details wrong makes the game read heights from the
wrong tile, which renders as straight walls across the land and a checkerboard
of triangles across the sea. Both mistakes were made once. A verifier that used
the same wrong model then passed every tile, which is why check_against_vanilla
exists and must pass before any output is judged.
"""
import numpy as np

STRIDE = 64
TILE = 65


def tile_rows(ty):
    return ty * STRIDE - 1


def padded(heightmap):
    """Replicate the edge one pixel beyond the top and the right."""
    return np.pad(heightmap, ((1, 0), (0, 1)), mode="edge")


def source_tile(pad, tx, ty, level=0):
    """The samples a tile at (tx, ty) must hold, from a padded heightmap."""
    y = tile_rows(ty) + 1          # plus one for the row added by padded()
    x = tx * STRIDE
    step = 1 << level
    return pad[y:y + TILE:step, x:x + TILE:step]


def atlas_tile(atlas, level_offsets, level, col, row):
    n = (STRIDE >> level) + 1
    ah = atlas.shape[0]
    bottom = ah - (level_offsets[level] + row * n)
    return atlas[bottom - n:bottom, col * n:col * n + n]


def check_against_vanilla(map_data_dir, level_offsets=(0, 1397, 3129, 3690, 3861), tolerance=60.0):
    """Rebuild every vanilla tile through the model and report the error.

    Vanilla compresses tiles lossily, so coarse levels differ from point samples
    by a few tens of units, growing with the level; uncompressed level 0 tiles
    stay within about 5. Reading the wrong tile instead costs thousands. The
    tolerance sits between the two, so it separates a correct model from a
    wrong one rather than demanding lossless tiles vanilla never had."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    hm = np.array(Image.open(map_data_dir + "/heightmap.png")).astype(np.int32)
    atlas = np.array(Image.open(map_data_dir + "/packed_heightmap.png")).astype(np.int32)
    ind = np.array(Image.open(map_data_dir + "/indirection_heightmap.png")).astype(np.int32)
    pad = padded(hm)
    worst, total, bad = 0.0, 0, 0
    for ty in range(ind.shape[0]):
        for tx in range(ind.shape[1]):
            col, row, _, level = (int(v) for v in ind[ty, tx])
            got = atlas_tile(atlas, level_offsets, level, col, row)
            want = source_tile(pad, tx, ty, level)
            err = float(np.abs(got - want).mean()) if got.shape == want.shape else 1e9
            worst = max(worst, err)
            bad += err > tolerance
            total += 1
    return total, bad, worst


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game\map_data"
    total, bad, worst = check_against_vanilla(d)
    print("vanilla: %d tiles, %d beyond tolerance, worst mean error %.2f" % (total, bad, worst))
    assert bad == 0, "the format model does not reproduce vanilla"
    print("format model reproduces vanilla")
