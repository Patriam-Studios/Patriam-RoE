"""The named regions of the world, as masks over the export.

The world map of Patriam names its lands, and several things on the Crusader
Kings III map have to know which land they are standing on: which trees grow
there, and whether the ground is the red rock of Mekanis. Nothing in the
WorldPainter world records the names, so each region is found here by a seed
point read off the published world map and grown into the landmass that holds
it. Islands of an archipelago are taken by a box around the group instead.

Seeds are in blocks of the source world, x from the west edge and y from the
north edge, the same frame the export uses.

Mekanis is the exception: it shares its landmass with Olzhar and Senkaria, so
it is taken from the mesa and red desert its surface is painted with, closed
over the canyons cut through it, which are painted as grass at the bottom.

usage: python regions.py <export prefix>     writes and reports the masks
"""
import io
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
Q = 8                     # export pixels a mask pixel, so 16 blocks
B = 16.0                  # blocks a mask pixel

# name: (seed x, seed y) in blocks, or a box (x0, y0, x1, y1) for an archipelago
SEEDS = {
    "olzhar": (8588, 15725),      # the whole western landmass, split below into three
    "aungmar": (22257, 10282),
    "northern_kallonia": (28546, 13185),
    "norkinia": (34836, 11370),
    "aeloen": (32417, 16934),
    "watol": (36772, 18509),
    "southern_kallonia": (25643, 19112),
}
BOXES = {
    "ketan": (18000, 12500, 25000, 17500),
    "taienmar": (28500, 19500, 34000, 23500),
    "vurkia": (21312, 24000, 57440, 34560),
}
MESA_SURFACES = ("mesa", "red desert", "afana")     # what Mekanis is painted with
SAND_SURFACES = ("desert", "dune", "white sand")    # and Senkaria, which is sand rather than rock


def land_mask(prefix):
    h = np.array(Image.open(prefix + "_height.png"))[::Q, ::Q].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
    w = np.array(Image.open(prefix + "_water.png"))[::Q, ::Q].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
    return (h > hs.SEA_BLOCK) & ~(w > h)


def surface_mask(prefix, keys, close=9):
    """Everywhere painted with one of these surfaces, closed over the gaps cut
    through it: the canyons of the mesa read as grass at the bottom."""
    table = tm.load_biome_table(prefix + "_surfaces.txt")
    want = [i for i, (share, name) in table.items()
            if any(k in name.lower() for k in keys)]
    surf = np.array(Image.open(prefix + "_surface.png"))[::Q, ::Q].astype(np.int32) - 1
    m = np.isin(surf, want)
    m = ndimage.binary_closing(m, np.ones((close, close), bool))   # 144 blocks, wider than any canyon
    return ndimage.binary_fill_holes(m)


def largest(m):
    lab, n = ndimage.label(m)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == sizes.argmax()


def build(prefix):
    land = land_mask(prefix)
    H, W = land.shape
    lab, n = ndimage.label(land)
    names = sorted(SEEDS) + sorted(BOXES) + ["mekanis", "senkaria"]
    out = np.zeros((H, W), dtype=np.uint8)
    report = []
    for name, (bx, by) in SEEDS.items():
        x, y = int(bx / B), int(by / B)
        if not land[y, x]:                                    # a label can sit just off its coast
            ys, xs = np.nonzero(land[max(0, y - 40):y + 40, max(0, x - 40):x + 40])
            assert len(ys), "no land near the seed for %s" % name
            d = (ys - min(y, 40)) ** 2 + (xs - min(x, 40)) ** 2
            y, x = max(0, y - 40) + ys[d.argmin()], max(0, x - 40) + xs[d.argmin()]
        k = lab[y, x]
        out[lab == k] = names.index(name) + 1
        report.append((name, int((lab == k).sum())))
    for name, (x0, y0, x1, y1) in BOXES.items():
        box = np.zeros((H, W), dtype=bool)
        box[int(y0 / B):int(y1 / B), int(x0 / B):int(x1 / B)] = True
        m = box & land & (out == 0)
        out[m] = names.index(name) + 1
        report.append((name, int(m.sum())))
    # Olzhar, Mekanis and Senkaria share one landmass and are told apart by what
    # they are painted with: the red rock of the mesa, the sand of the desert,
    # and Olzhar's own grass for everything left.
    west = out == names.index("olzhar") + 1
    mek = largest(surface_mask(prefix, MESA_SURFACES, close=17)) & west   # 272 blocks, wider than any canyon
    out[mek] = names.index("mekanis") + 1
    sand = surface_mask(prefix, SAND_SURFACES) & west & ~mek
    out[sand] = names.index("senkaria") + 1
    report.append(("mekanis", int(mek.sum())))
    report.append(("senkaria", int(sand.sum())))
    report.append(("olzhar, what is left", int((out == names.index("olzhar") + 1).sum())))
    return out, names, report


def region_map(prefix, size=None):
    """The region index for every pixel, 0 where no region claims it, and the
    list of names in index order. Cached beside the export."""
    cache = prefix + "_regions.png"
    names_file = prefix + "_regions.txt"
    if os.path.exists(cache) and os.path.exists(names_file):
        out = np.array(Image.open(cache))
        names = [l.rstrip("\n") for l in io.open(names_file, encoding="utf-8")]
    else:
        out, names, report = build(prefix)
        Image.fromarray(out).save(cache)
        io.open(names_file, "w", encoding="utf-8", newline="\n").write("\n".join(names) + "\n")
        for name, px in report:
            print("  %-20s %8d pixels, %8.0f square blocks" % (name, px, px * B * B))
    if size is not None and (out.shape[1], out.shape[0]) != tuple(size):
        out = np.array(Image.fromarray(out).resize(tuple(size), Image.NEAREST))
    return out, names


def sub_mask(out, names, name, part=None):
    """One region, or a quarter of it: part is one of nw, ne, sw, se."""
    m = out == names.index(name) + 1
    if part is None:
        return m
    ys, xs = np.nonzero(m)
    midx, midy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
    keep = np.ones(len(ys), bool)
    if "w" in part:
        keep &= xs <= midx
    if "e" in part:
        keep &= xs > midx
    if "n" in part:
        keep &= ys <= midy
    if "s" in part:
        keep &= ys > midy
    q = np.zeros_like(m)
    q[ys[keep], xs[keep]] = True
    return q


if __name__ == "__main__":
    prefix = sys.argv[1]
    for f in (prefix + "_regions.png", prefix + "_regions.txt"):
        if os.path.exists(f):
            os.remove(f)
    out, names = region_map(prefix)
    print("regions:", ", ".join(names))
    for i, name in enumerate(names):
        m = out == i + 1
        if not m.any():
            print("  %-20s EMPTY" % name)
            continue
        ys, xs = np.nonzero(m)
        print("  %-20s blocks x %6d..%6d  y %6d..%6d" % (
            name, xs.min() * B, xs.max() * B, ys.min() * B, ys.max() * B))
