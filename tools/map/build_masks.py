"""Material masks at the size of this map.

The base game names a mask image for every ground material in
gfx/map/terrain/materials.settings, and it sizes its terrain to those images.
Ours shipped none at first, so vanilla's own masks loaded, all 9216 by 4608, and
the game drew every province beyond that rectangle black and every sea beyond it
flat.

What the game draws in a session comes from detail_index.tga and
detail_intensity.tga, so blank masks of the right size were enough for play. The
map editor is another matter: it paints the ground from these masks, and with
every one of them empty it found no material anywhere and drew the whole world
solid pink. So the masks are now written from the splat maps, which is the same
ground by another road: a material's mask holds, at every pixel, the weight that
material carries there.

Run with the width and height alone for blank masks, or add the map_data and
terrain directories to fill them from the splat maps.

usage: python build_masks.py <width> <height> [<map_data dir> <gfx terrain dir>]
"""
import io
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_materials as tm

Image.MAX_IMAGE_PIXELS = None
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game\gfx\map\terrain"


def mask_paths():
    mine = os.path.join(MOD, "gfx", "map", "terrain", "materials.settings")
    src = mine if os.path.exists(mine) else os.path.join(GAME, "materials.settings")
    settings = io.open(src, encoding="utf-8-sig").read()
    return sorted(set(re.findall(r'mask\s*=\s*"([^"]+)"', settings)))


def blank(w, h, paths):
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


def from_splat(w, h, paths, terrain_dir):
    """Every material's own weight, read back out of the two splat maps."""
    index = np.array(Image.open(os.path.join(terrain_dir, "detail_index.tga")))
    inten = np.array(Image.open(os.path.join(terrain_dir, "detail_intensity.tga")))
    assert index.shape[:2] == (h, w), "the splat maps are %s, not %d by %d" % (index.shape[:2], w, h)
    idx = tm.material_index()
    by_name = {}
    for name, mid in idx.items():
        by_name.setdefault(mid, name)
    used = set(np.unique(index[..., :3]).tolist()) - {255}
    print("filling %d masks from the splat maps, %d of them carry ground" % (len(paths), len(used)))
    empty = None
    written = 0
    for rel in paths:
        name = os.path.basename(rel).replace("_mask.png", "")
        out = os.path.join(MOD, "gfx", "map", "terrain", rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        mid = idx.get(name)
        if mid is None or mid not in used:
            if empty is None:
                Image.fromarray(np.zeros((h, w), dtype=np.uint8)).save(out, optimize=True)
                empty = out
            else:
                shutil.copyfile(empty, out)
            continue
        acc = np.zeros((h, w), dtype=np.uint16)
        for slot in range(3):
            m = index[..., slot] == mid
            acc[m] += inten[..., slot][m]
        arr = np.minimum(acc, 255).astype(np.uint8)
        Image.fromarray(arr).save(out)          # optimising a hundred megapixel mask is not worth the minutes
        written += 1
        print("  %-34s %5.2f%% of the map, %7d KB" % (name, (arr > 0).mean() * 100,
                                                      os.path.getsize(out) // 1024))
        del acc, arr
    print("wrote %d masks with ground and %d empty" % (written, len(paths) - written))


def main(w, h, map_data=None, terrain_dir=None):
    paths = mask_paths()
    if terrain_dir and os.path.exists(os.path.join(terrain_dir, "detail_index.tga")):
        from_splat(w, h, paths, terrain_dir)
    else:
        blank(w, h, paths)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), *sys.argv[3:5])
