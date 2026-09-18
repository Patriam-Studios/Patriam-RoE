"""Rivers where the WorldPainter world paints the river biome.

The game draws rivers from map_data/rivers.png, not from the heightmap. It is
an indexed image where white is land, pink is sea, and a river is a line one
pixel wide: green where it rises, blue along its course with the shade giving
its width, and red on the last pixel of a tributary where it joins a larger
river. Vanilla ships 631 sources over 286136 pixels of river.

So the river biome of the export is reduced to lines: every pixel of it is
thinned to a single thread, the threads are made into a tree rooted where the
water reaches the sea, short tributaries are dropped, and what is left is
painted with a width taken from how broad the painted river was.

The heightmap must not cut these channels below sea level, or the game floods
them and they read as inlets of the sea rather than as rivers. build_canvas.py
keeps river ground above the water plane for that reason.

usage: python build_rivers.py <export prefix> <map_data dir> [--write]
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
VANILLA_RIVERS = ("C:/Program Files (x86)/Steam/steamapps/common/Crusader Kings III"
                  "/game/map_data/rivers.png")
LAND, SEA = 255, 254
SOURCE, MERGE, SPLIT = 0, 1, 2
WIDTHS = [3, 4, 5, 6, 8, 9, 11]          # narrowest to widest, as vanilla numbers them
MIN_COMPONENT = 200                       # province pixels of painted river worth keeping
MIN_BRANCH = 30                           # a tributary shorter than this is not drawn
BLOCKS_PER_PX = 5.1875


def river_mask(prefix, W, H):
    """Every pixel the world paints as river, at province map resolution."""
    table = tm.load_biome_table(prefix + "_biomes.txt")
    want = [i for i, (share, name) in table.items() if "river" in name.lower()]
    print("river biomes:", ", ".join("%s %.2f%%" % (table[i][1], table[i][0]) for i in want))
    bio = np.array(Image.open(prefix + "_biome.png").resize((W, H), Image.NEAREST)).astype(np.int32) - 1
    m = np.isin(bio, want)
    print("painted river: %d pixels, %.2f%% of the map" % (m.sum(), m.mean() * 100))
    return m


def thin(m):
    """Zhang and Suen, until nothing more can be taken away."""
    img = m.astype(np.uint8)
    for it in range(60):
        removed = 0
        for step in (0, 1):
            p = np.pad(img, 1)
            n = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:],
                 p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]      # P2 clockwise to P9
            b = sum(x.astype(np.uint8) for x in n)
            a = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                c = (n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0)
            else:
                c = (n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0)
            kill = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            removed += int(kill.sum())
            img[kill] = 0
            del p, n, b, a, c, kill
        print("  thinning pass %d removed %d" % (it + 1, removed))
        if removed == 0:
            break
    return img.astype(bool)


def four_connect(sk, src):
    """A thinned line steps diagonally; the game's rivers step north, south,
    east and west. Fill the corner of every diagonal step, preferring one the
    painted river covered."""
    added = 0
    ys, xs = np.nonzero(sk)
    have = set(zip(ys.tolist(), xs.tolist()))
    for y, x in list(have):
        for dy, dx in ((1, 1), (1, -1)):
            ny, nx = y + dy, x + dx
            if (ny, nx) in have and (y, nx) not in have and (ny, x) not in have:
                pick = (y, nx) if src[y, nx] else (ny, x)
                have.add(pick)
                added += 1
    out = np.zeros_like(sk)
    ay = np.fromiter((p[0] for p in have), np.int32, len(have))
    ax = np.fromiter((p[1] for p in have), np.int32, len(have))
    out[ay, ax] = True
    print("  filled %d diagonal corners" % added)
    return out


def build(prefix, map_data, write):
    prov = Image.open(os.path.join(map_data, "provinces.png"))
    W, H = prov.size
    del prov
    hm = np.array(Image.open(os.path.join(map_data, "heightmap.png")))[::2, ::2]
    land = hm > hs.CK3_SEA
    del hm

    m = river_mask(prefix, W, H) & land
    lab, n = ndimage.label(m, np.ones((3, 3), bool))
    sizes = np.bincount(lab.ravel())
    small = np.nonzero(sizes < MIN_COMPONENT)[0]
    m &= ~np.isin(lab, small)
    print("kept %d of %d painted river threads, %d pixels" % (n - len(small) + 1, n, m.sum()))
    del lab, sizes

    width_px = ndimage.distance_transform_edt(m).astype(np.float32) * 2.0
    sk = thin(m)
    print("thinned to %d pixels" % sk.sum())
    sk = four_connect(sk, m)
    del m

    # the graph: every thread rooted where it meets the sea
    ys, xs = np.nonzero(sk)
    idx = {int(y) * W + int(x): i for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist()))}
    N = len(ys)
    print("graph of %d pixels" % N)
    nbr = [[] for _ in range(N)]
    for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            j = idx.get((y + dy) * W + (x + dx))
            if j is not None:
                nbr[i].append(j)

    sea_near = ndimage.binary_dilation(~land, np.ones((3, 3), bool))
    at_sea = sea_near[ys, xs]
    wide = width_px[ys, xs]
    del sea_near
    comp = np.full(N, -1, np.int32)
    landlocked = []
    parent = np.full(N, -1, np.int32)
    order = []
    ncomp = 0
    for start in range(N):
        if comp[start] >= 0:
            continue
        # every pixel of this thread, so that the root can be chosen properly
        seen = [start]
        comp[start] = ncomp
        q = deque([start])
        while q:
            i = q.popleft()
            for j in nbr[i]:
                if comp[j] < 0:
                    comp[j] = ncomp
                    seen.append(j)
                    q.append(j)
        roots = [i for i in seen if at_sea[i]]
        if not roots:
            # water that reaches neither the sea nor a lake has nowhere to go and
            # would stop dead on the ground, so it is not drawn at all
            landlocked.extend(seen)
            continue
        root = max(roots, key=lambda i: wide[i])        # the mouth is the broadest of them
        for i in seen:
            parent[i] = -1
        depth = {root: 0}
        q = deque([root])
        parent[root] = root
        while q:
            i = q.popleft()
            order.append(i)
            for j in nbr[i]:
                if parent[j] < 0:
                    parent[j] = i
                    q.append(j)
        ncomp += 1
    print("%d river threads, %d pixels dropped for reaching no water" % (ncomp, len(landlocked)))
    keep_comp = np.ones(N, bool)
    keep_comp[landlocked] = False

    # how far the water above each pixel reaches, so that short tributaries can go
    length = np.ones(N, np.int32)          # longest run of pixels above this one
    size = np.ones(N, np.int32)            # how many pixels drain through it
    for i in reversed(order):
        p = parent[i]
        if p != i:
            length[p] = max(length[p], length[i] + 1)
            size[p] += size[i]

    keep = np.zeros(N, bool)
    for i in order:                        # from the mouth upwards, so a parent is settled first
        if parent[i] == i:
            keep[i] = keep_comp[i]
        if not keep[i]:
            continue
        kids = [c for c in nbr[i] if parent[c] == i]
        if not kids:
            continue
        main = max(kids, key=lambda c: size[c])
        for c in kids:
            keep[c] = c == main or length[c] >= MIN_BRANCH
    kept = int(keep.sum())
    print("kept %d of %d pixels after dropping tributaries under %d px" % (kept, N, MIN_BRANCH))

    out = np.where(land, LAND, SEA).astype(np.uint8)
    wpx = width_px[ys, xs]
    del width_px
    # width from how broad the painted river is, in blocks
    blocks = wpx * BLOCKS_PER_PX
    # vanilla draws four fifths of its rivers with the two narrowest lines, so the
    # widest are kept for water that is genuinely broad
    band = np.digitize(blocks, [14, 26, 42, 64, 95, 140])
    for i in order:
        if not keep[i]:
            continue
        out[ys[i], xs[i]] = WIDTHS[band[i]]
    src_n = mrg_n = 0
    for i in order:
        if not keep[i]:
            continue
        kids = [c for c in nbr[i] if parent[c] == i and keep[c]]
        if not kids:                                    # nothing above it, so it rises here
            out[ys[i], xs[i]] = SOURCE
            src_n += 1
        elif len(kids) > 1:
            main = max(kids, key=lambda c: size[c])
            for c in kids:
                if c is not main:
                    out[ys[c], xs[c]] = MERGE          # the tributary ends on the larger river
                    mrg_n += 1
    print("%d sources, %d junctions, %d river pixels" % (src_n, mrg_n, kept))

    pal = Image.open(VANILLA_RIVERS).getpalette()
    im = Image.fromarray(out, mode="P")
    im.putpalette(pal)
    if write:
        im.save(os.path.join(map_data, "rivers.png"), optimize=True)
        print("wrote rivers.png at %d x %d" % (W, H))
    else:
        print("dry run, nothing written")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], "--write" in sys.argv)
