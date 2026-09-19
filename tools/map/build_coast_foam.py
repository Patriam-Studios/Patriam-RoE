"""Surf along the shores of Patriam.

The base game declares three foam emitters, large, middling and small, and
places not one of them: its own coast_foam.txt carries count zero on all three,
so the white water seen in its own game comes from the water itself and not from
these. Clearing that file therefore cost this map nothing, and what is written
here is something the base game never had.

Surf breaks where the sea has room to run at the land, so foam is laid only on
shores with open water in front of them, and never in a sheltered channel
between two islands. The size follows the same measure: the more open the water,
the larger the emitter. Each one is turned to face the shore.

Density is the thing to watch. Every instance is a particle emitter, and the
base game places about seven hundred of all kinds across its whole map, so this
keeps to a spacing that leaves a few thousand rather than the seventy thousand a
continuous line of surf would need.

usage: python build_coast_foam.py [--write]
"""
import io
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs

Image.MAX_IMAGE_PIXELS = None
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(MOD, "gfx", "map", "map_object_data", "coast_foam.txt")
WRITE = "--write" in sys.argv

OPENNESS = 51           # province pixels across, the window the sea is measured in
EXPOSED = 0.70          # how much of that window must be water for surf to break
SPACING = 18            # province pixels between emitters along the shore
SIZES = [("env_coast_foam_s", 0.74), ("env_coast_foam_m", 0.84), ("env_coast_foam_l", 1.0)]


def main():
    hm = np.array(Image.open(os.path.join(MOD, "map_data", "heightmap.png")))[::2, ::2]
    H, W = hm.shape
    land = hm > hs.CK3_SEA
    del hm
    coast = ndimage.binary_dilation(land, np.ones((3, 3), bool)) & ~land
    open_water = ndimage.uniform_filter((~land).astype(np.float32), OPENNESS, mode="nearest")

    # which way the shore lies: the land gradient points from the water to the land
    soft = ndimage.uniform_filter(land.astype(np.float32), 9, mode="nearest")
    gy, gx = np.gradient(soft)
    del soft, land

    take = coast & (open_water > EXPOSED)
    ys, xs = np.nonzero(take)
    print("shore facing open water: %d province pixels of %d" % (len(ys), coast.sum()))
    del coast, take

    # one emitter to a cell, so they are spread evenly rather than bunched
    keep = {}
    for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        keep.setdefault((y // SPACING, x // SPACING), i)
    picked = np.fromiter(keep.values(), np.int64, len(keep))
    ys, xs = ys[picked], xs[picked]
    print("one every %d pixels leaves %d emitters" % (SPACING, len(ys)))

    rng = np.random.default_rng(6355)
    facing = np.arctan2(gx[ys, xs], -gy[ys, xs])        # towards the land, in the map's frame
    exposure = open_water[ys, xs]
    del gx, gy, open_water

    rows = {name: [] for name, _ in SIZES}
    bands = np.digitize(exposure, [EXPOSED + 0.10, EXPOSED + 0.20])
    for i in range(len(ys)):
        name, scale = SIZES[int(bands[i])]
        a = facing[i] + rng.normal(0.0, 0.12)
        sc = scale * (0.85 + rng.random() * 0.35)
        rows[name].append("%.6f 0.000000 %.6f 0.000000 %.6f 0.000000 %.6f %.6f %.6f %.6f"
                          % (xs[i] + rng.random(), (H - ys[i]) - rng.random(),
                             np.sin(a / 2.0), np.cos(a / 2.0), sc, sc, sc))
    body = ""
    for name, _ in SIZES:
        r = rows[name]
        print("   %-22s %6d" % (name, len(r)))
        body += ('object={\n\tname="%s"\n\trender_pass=MapUnderWater\n'
                 '\tclamp_to_water_level=yes\n\tgenerated_content=no\n\tlayer="coast_foam_layer"\n'
                 '\tentity="%s"\n\tcount=%d\n\ttransform="%s\n"}\n'
                 % (name, name, len(r), "\n".join(r)))
    if WRITE:
        io.open(OUT, "w", encoding="utf-8-sig", newline="\n").write(body)
        print("wrote %s, %d emitters in all" % (os.path.basename(OUT), sum(len(r) for r in rows.values())))
    else:
        print("dry run, nothing written")


if __name__ == "__main__":
    main()
