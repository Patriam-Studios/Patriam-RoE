"""map_data/nodes.dat, the terrain quadtree, for a map of any size.

The game draws its terrain through a quadtree of this file and clips every
pixel outside the nodes it holds. The map editor writes it on Save As, and a
map built by hand never had one, so the game fell back to a tree sized for its
own Earth and drew everything beyond 9216 by 4608 black.

Decoded from vanilla's file and checked against vanilla's heightmap:

* A complete quadtree of eleven levels over a fixed square of 16384 world
  units, one node per record, level by level, the four children of a parent
  in the order (x, y), (x+, y), (x, y+), (x+, y+). That is (4^11 - 1) / 3
  records, 1398101 of them, 32 bytes each, 44739232 bytes.
* Leaves are 16 units, 32 heightmap pixels, a quarter of a packed tile.
* Record: float x, float y, float size, all as a fraction of the square,
  measured from the bottom left of the map; uint16 min height, uint16 max
  height, both half the sixteen bit value; float geometric error of this
  level of detail; two uint16 that vanilla fills with per node statistics and
  that the game tolerates at zero; float next level geometric error; uint32
  flag, 1 when the node lies wholly outside the map.
* Nodes outside the map carry min 65535, max 0, both errors 0.

Geometric error is the greatest distance, in half units, between the true
heightmap and this node's level of detail, where a node of level L samples
every 2^(10 - L) leaf steps. The next level error is the greatest error among
the children.

usage: python build_nodes.py <heightmap.png> <map_data dir>
"""
import os
import struct
import sys
import time

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SQUARE = 16384.0
LEVELS = 11
LEAF_UNITS = 16
PX_PER_UNIT = 2          # heightmap pixels per world unit
LEAF_PX = LEAF_UNITS * PX_PER_UNIT
LEAVES = 1024            # per side of the square


def level_start(level):
    return (4 ** level - 1) // 3


def child_order_index(level):
    """Record offsets within a level, laid out so that a parent's four children
    are consecutive in the order (x, y), (x+, y), (x, y+), (x+, y+).

    Returns an array idx[iy, ix] giving the record index for node (ix, iy)."""
    n = 2 ** level
    if level == 0:
        return np.zeros((1, 1), dtype=np.int64)
    parent = child_order_index(level - 1)
    idx = np.empty((n, n), dtype=np.int64)
    base = level_start(level)
    pstart = level_start(level - 1)
    order = (parent - pstart) * 4 + base
    idx[0::2, 0::2] = order
    idx[0::2, 1::2] = order + 1
    idx[1::2, 0::2] = order + 2
    idx[1::2, 1::2] = order + 3
    return idx


def block_reduce(a, k, fn):
    H, W = a.shape
    return fn(a.reshape(H // k, k, W // k, k), axis=(1, 3))


def main(heightmap_path, out_dir):
    t0 = time.time()
    hm = np.array(Image.open(heightmap_path))
    H, W = hm.shape
    assert H % LEAF_PX == 0 and W % LEAF_PX == 0, "heightmap must be a multiple of 32"
    # world y runs upward, the image downward
    hm = hm[::-1].astype(np.uint16)
    leaves_x, leaves_y = W // LEAF_PX, H // LEAF_PX
    assert leaves_x <= LEAVES and leaves_y <= LEAVES, "map larger than the quadtree square"
    print("%d x %d px, %d x %d leaves of %d px  (%.0fs)" % (W, H, leaves_x, leaves_y, LEAF_PX, time.time() - t0))

    total = level_start(LEVELS)
    recs = np.zeros(total, dtype=[("x", "<f4"), ("y", "<f4"), ("s", "<f4"), ("mn", "<u2"), ("mx", "<u2"),
                                  ("err", "<f4"), ("b0", "<u2"), ("b1", "<u2"), ("err2", "<f4"), ("flag", "<u4")])
    recs["mn"] = 65535
    recs["flag"] = 1

    # Per level statistics on the map's own grid, then scattered into the tree.
    # Each level is worked a row of nodes at a time, so the map is never held
    # in more than one whole copy: at the coarse levels a whole map copy of the
    # resampled mesh alone is two gigabytes.
    half = (hm.astype(np.float32) * 0.5)
    del hm
    child_err = None
    for level in range(LEVELS - 1, -1, -1):
        n = 2 ** level
        node_px = LEAF_PX * (2 ** (LEVELS - 1 - level))
        idx = child_order_index(level)
        # nodes that touch the map
        nx = -(-W // node_px)
        ny = -(-H // node_px)
        Wp = nx * node_px
        # Level of detail: a node of level L keeps every 2^(10 - L)th sample,
        # and the error stored is the greatest distance between that mesh and
        # the ground. Of the metrics tried against vanilla's own file this one
        # matched best, a correlation of 0.87 and a median ratio of 1.02, with
        # the coarsest few levels running larger than vanilla's, which only
        # makes the game keep finer detail a little further out.
        stride = 2 ** (LEVELS - 1 - level)
        mn = np.full((ny, nx), np.inf, dtype=np.float32)
        mx = np.full((ny, nx), -np.inf, dtype=np.float32)
        err = np.ones((ny, nx), dtype=np.float32)
        STRIP = 1024
        for r in range(ny):
            y0 = r * node_px
            y1 = min(H, y0 + node_px)
            # a row of coarse nodes is worked in strips, so no copy is ever
            # larger than a thousand rows of the map
            for s0 in range(y0, y1, STRIP):
                s1 = min(y1, s0 + STRIP)
                strip = half[s0:s1]
                if Wp > W:
                    strip = np.pad(strip, ((0, 0), (0, Wp - W)), mode="edge")
                cols = strip.reshape(strip.shape[0], nx, node_px)
                mn[r] = np.minimum(mn[r], cols.min(axis=(0, 2)))
                mx[r] = np.maximum(mx[r], cols.max(axis=(0, 2)))
                if stride > 1:
                    coarse = strip[::stride, ::stride]
                    up = np.array(Image.fromarray(np.ascontiguousarray(coarse)).resize((Wp, strip.shape[0]), Image.BILINEAR), dtype=np.float32)
                    np.subtract(up, strip, out=up)
                    np.abs(up, out=up)
                    err[r] = np.maximum(err[r], up.reshape(up.shape[0], nx, node_px).max(axis=(0, 2)))
                    del coarse, up
                del cols, strip
        # next level error: the greatest among the four children
        if child_err is None:
            err2 = np.zeros((ny, nx), dtype=np.float32)
        else:
            cy, cx = child_err.shape
            ce = np.zeros((ny * 2, nx * 2), dtype=np.float32)
            ce[:cy, :cx] = child_err
            err2 = block_reduce(ce, 2, np.max)
        child_err = err
        sel = idx[:ny, :nx]
        recs["mn"][sel] = mn.astype(np.uint16)
        recs["mx"][sel] = mx.astype(np.uint16)
        recs["err"][sel] = err
        recs["err2"][sel] = err2
        recs["flag"][sel] = 0
        # The two remaining fields sit at three and a half and four times the
        # error in vanilla's file across every level, and are zero at the
        # leaves. Left at zero on inner nodes the game drew flat diamonds over
        # the sea, so they are filled to the same proportion here.
        if level < LEVELS - 1:
            recs["b0"][sel] = np.clip(np.round(err * 3.5), 1, 65535).astype(np.uint16)
            recs["b1"][sel] = np.clip(np.round(err * 4.0), 1, 65535).astype(np.uint16)
        print("level %2d: %4d x %4d nodes touch the map, node %5d px, err max %.1f  (%.0fs)" % (
            level, nx, ny, node_px, float(err.max()), time.time() - t0))
        # geometry for every node of the level
        ys, xs = np.mgrid[0:n, 0:n]
        recs["x"][idx] = xs / float(n)
        recs["y"][idx] = ys / float(n)
        recs["s"][idx] = 1.0 / n

    out = os.path.join(out_dir, "nodes.dat")
    with open(out, "wb") as f:
        f.write(recs.tobytes())
    print("wrote %s, %d records, %d bytes  (%.0fs)" % (out, total, total * 32, time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
