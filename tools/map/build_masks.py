"""Blank material masks at the size of this map.

The base game names a mask image for every ground material in
gfx/map/terrain/materials.settings, and it sizes its terrain to those images.
Ours ships none, so vanilla's own masks loaded, all 9216 by 4608, and the game
drew every province beyond that rectangle black and every sea beyond it flat.
The blend itself comes from detail_index.tga and detail_intensity.tga, so the
masks need hold nothing. They only have to be the right size.

usage: python build_masks.py <width> <height>
"""
import io
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game\gfx\map\terrain"


def main(w, h):
    settings = io.open(os.path.join(GAME, "materials.settings"), encoding="utf-8-sig").read()
    paths = sorted(set(re.findall(r'mask\s*=\s*"([^"]+)"', settings)))
    first = None
    for rel in paths:
        out = os.path.join(MOD, "gfx", "map", "terrain", rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if first is None:
            Image.fromarray(np.zeros((h, w), dtype=np.uint8)).save(out, optimize=True)
            first = out
        else:
            shutil.copyfile(first, out)
    print("%d blank masks at %d x %d, %d bytes each" % (len(paths), w, h, os.path.getsize(first)))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
