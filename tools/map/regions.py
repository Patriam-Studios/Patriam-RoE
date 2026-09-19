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

The farming heartland of Southern Kallonia is another: it is not a landmass at
all but a cluster of realms, so it is read out of the title tree rather than
off the world map, and grown and feathered at its edge because a field ends
where the soil does and not on a political line.

usage: python regions.py <export prefix>     writes and reports the masks
"""
import glob
import io
import os
import re
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
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
WORLD_BLOCKS_X = 84992.0  # the width of the source world, for the province map scale

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
}
VURKIA_BOX = (21312, 24000, 48384, 34560)      # the archipelago, inside the finished world
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


def vurkia_parts(prefix):
    """Vurkia's islands and the calderas sunk into them.

    The basalt of the fallen archipelago is painted over its sea floor as well as
    its islands, so the paint alone takes in the whole ocean there. What counts as
    Vurkia is basalt that stands above the water, and a caldera is then a hollow
    enclosed by one of those islands: the crater of a volcano, drowned in the
    source world and filled with fire here."""
    land = land_mask(prefix)
    basalt = surface_mask(prefix, ("basalt", "blackstone"), close=5) & land
    box = np.zeros(land.shape, bool)
    x0, y0, x1, y1 = VURKIA_BOX
    box[int(y0 / B):int(y1 / B), int(x0 / B):int(x1 / B)] = True
    basalt &= box
    lab, n = ndimage.label(basalt)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    islands = np.isin(lab, np.nonzero(sizes >= 6)[0])
    filled = ndimage.binary_fill_holes(islands)
    calderas = filled & ~islands
    return islands, calderas, filled


def vurkia_lava(prefix):
    """Where fire shows through Vurkia: the calderas, and the gullies the ground
    drains along, which carry the magma down off the volcanoes."""
    islands, calderas, filled = vurkia_parts(prefix)
    h = np.array(Image.open(prefix + "_height.png"))[::Q, ::Q].astype(np.float32) / 64.0 + np.float32(hs.MIN_BLOCK)
    hollow = ndimage.gaussian_filter(h, 6) - h          # how far below its surroundings a pixel lies
    del h
    # Only the deepest few channels, and only where they run out of a crater, so
    # the fire reads as flows leaving the volcanoes rather than as a rash over
    # the whole archipelago.
    cut = np.percentile(hollow[islands], 99.2) if islands.any() else 1e9
    near_crater = ndimage.binary_dilation(calderas, iterations=6)
    channels = islands & (hollow > cut) & near_crater
    return calderas | channels, calderas, filled


def build(prefix):
    land = land_mask(prefix)
    H, W = land.shape
    lab, n = ndimage.label(land)
    names = sorted(SEEDS) + sorted(BOXES) + ["mekanis", "senkaria", "vurkia"]
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
    islands, calderas, filled = vurkia_parts(prefix)
    out[filled] = names.index("vurkia") + 1
    report.append(("vurkia, islands", int(islands.sum())))
    report.append(("vurkia, calderas", int(calderas.sum())))
    for name, (x0, y0, x1, y1) in BOXES.items():
        box = np.zeros((H, W), dtype=bool)
        box[int(y0 / B):int(y1 / B), int(x0 / B):int(x1 / B)] = True
        m = box & land & (out == 0)
        out[m] = names.index(name) + 1
        report.append((name, int(m.sum())))
    # Olzhar, Mekanis and Senkaria share one landmass and are told apart by what
    # they are painted with: the red rock of the mesa, the sand of the desert,
    # and Olzhar's own grass for everything left.
    west = (out == names.index("olzhar") + 1) | (out == 0)
    # The mesa is taken from the paint alone and not from the landmass: its own
    # ravines cut below the water plane, which splits the tableland into several
    # pieces of land, and the middle of Mekanis was falling outside the region
    # and keeping vanilla's grey rock.
    mek = largest(surface_mask(prefix, MESA_SURFACES, close=17))   # 272 blocks, wider than any canyon
    out[mek] = names.index("mekanis") + 1
    sand = surface_mask(prefix, SAND_SURFACES) & (out == names.index("olzhar") + 1) & ~mek
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


# Bouropheia, the north western arm of Northern Kallonia, as Alexander drew it
# on 19 September 2026. Blocks of the source world, clockwise from the north tip.
BOUROPHEIA_OUTLINE = [
    (29100, 9400), (29900, 10250), (30000, 11250), (29450, 12250), (28950, 13250),
    (28500, 14300), (27850, 14300), (27300, 13200), (26900, 12000), (27100, 10900),
    (27900, 10000), (28500, 9500),
]


def polygon_mask(shape, points_in_blocks, blocks_per_px=None):
    """Rasterise a polygon given in blocks onto a grid of the given shape.

    The scale is worked out from the shape unless it is given, so the same
    outline can be drawn on the region grid or on the province map."""
    from PIL import ImageDraw
    bx, by = blocks_per_px if blocks_per_px else (84992.0 / shape[1], 34560.0 / shape[0])
    img = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(img).polygon([(x / bx, y / by) for x, y in points_in_blocks], fill=255)
    return np.array(img) > 0


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


# The farming heartland of Southern Kallonia: the plains of the fifteen house
# tier realms, one contiguous cluster in the middle of the region, which is the
# rich ground that will one day feed the empire of Thenithria. The baronies are
# read out of the mod's own files rather than listed here, so that the fields
# follow the title tree wherever it goes.
HEARTLAND_GROW = 25.0        # blocks the fields carry past the edge of their baronies
HEARTLAND_FEATHER = 75.0     # and the width they thin away over into ordinary grass
HEARTLAND_MOTTLE = 150.0     # blocks: how coarsely that thinning is broken up
QH = 4                       # province pixels a heartland working pixel


def heartland_baronies():
    """The plains baronies of the house tier realms, by province number.

    A house tier realm is one whose title history turns its holder to house
    government. Its baronies are the province numbers under its block in the de
    jure tree, and the plains among them are the ones the province terrain
    leaves at the default. Farmland counts as plains here, so that a second run
    reads back what the first one wrote instead of finding an empty heartland.
    """
    house, current = set(), None
    for line in io.open(os.path.join(MOD, "history", "titles", "00_patriam_titles.txt"),
                        encoding="utf-8-sig"):
        opened = re.match(r"^([ekdcb]_[a-z0-9_]+) = \{", line)
        if opened:
            current = opened.group(1)
        elif "change_government = house_government" in line and current:
            house.add(current)
    assert house, "no house tier realm in the title history"

    under = {}                         # title: the province numbers under it
    for path in sorted(glob.glob(os.path.join(MOD, "common", "landed_titles", "*.txt"))):
        stack = []
        for line in io.open(path, encoding="utf-8-sig"):
            barony = re.search(r"\bprovince = (\d+)", line)
            if barony:
                for title in stack:
                    under.setdefault(title, set()).add(int(barony.group(1)))
                continue
            opened = re.match(r"^(\t*)([ekdcb]_[a-z0-9_]+) = \{\s*$", line)
            if opened:
                del stack[len(opened.group(1)):]
                stack.append(opened.group(2))

    terrain = {}
    for line in io.open(os.path.join(MOD, "common", "province_terrain", "00_province_terrain.txt"),
                        encoding="utf-8-sig"):
        written = re.match(r"(\d+)\s*=\s*([a-z_]+)", line.strip())
        if written:
            terrain[int(written.group(1))] = written.group(2)

    held = set()
    for title in house:
        held |= under.get(title, set())
    ids = sorted(p for p in held if terrain.get(p, "plains") in ("plains", "farmlands"))
    assert ids, "the house tier realms hold %d baronies and none of them are plains" % len(held)
    return ids


def smooth_noise(shape, cell, rng):
    """A smooth random field in 0 to 1, for breaking up anything regular."""
    small = rng.random((max(2, shape[0] // cell + 2), max(2, shape[1] // cell + 2))).astype(np.float32)
    up = Image.fromarray(small).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.clip(np.array(up, dtype=np.float32), 0.0, 1.0)


def heartland_mask(prefix, size):
    """Where the worked fields of the heartland are drawn, over the province map.

    The baronies draw a hard political line, so the mask is carried a little
    past them and then thinned away over a band, mottled with smooth noise, and
    the fields interlock with the grass beyond instead of stopping dead on a
    border. Worked out on a quarter grid, as the terrain blend is."""
    W, H = size
    pid = np.load(prefix + "_pid.npy", mmap_mode="r")
    assert pid.shape == (H, W), "the province numbers are %s, not the province map" % (pid.shape,)
    assert H % QH == 0 and W % QH == 0, "the province map does not divide by %d" % QH
    hq, wq = H // QH, W // QH
    ids = heartland_baronies()
    core = np.zeros((hq, wq), bool)
    for y in range(0, H, 1024):                       # in bands, so the whole id map never lands on the heap
        band = np.isin(np.asarray(pid[y:y + 1024]), ids)
        rows = band.shape[0] // QH
        core[y // QH:y // QH + rows] = band[:rows * QH].reshape(rows, QH, wq, QH).any(axis=(1, 3))
        del band
    per_pixel = WORLD_BLOCKS_X / W * QH               # blocks a working pixel
    away = ndimage.distance_transform_edt(~core) * per_pixel      # blocks out from the fields
    alpha = np.clip((HEARTLAND_GROW + HEARTLAND_FEATHER - away) / HEARTLAND_FEATHER, 0.0, 1.0)
    del away
    rng = np.random.default_rng(7726)
    mottled = alpha > smooth_noise((hq, wq), max(2, int(round(HEARTLAND_MOTTLE / per_pixel))), rng)
    del alpha
    return np.array(Image.fromarray(mottled.astype(np.uint8)).resize((W, H), Image.NEAREST)).astype(bool)


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
    ids = heartland_baronies()
    print("heartland: %d plains baronies under the house tier realms, %d to %d"
          % (len(ids), ids[0], ids[-1]))
