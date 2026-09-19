"""A lake of fire in every caldera of Vurkia.

Alexander asked whether the lava could be a map object rather than ground, and
it can: the base game draws each of its 232 lakes as one flat plane laid on the
map, placed by gfx/map/map_object_data/lakes.txt with a position, a turn and a
scale, and drawn through its water shader. The same plane with the lava texture
and an ordinary mesh shader gives a molten disc with a clean edge, and a caldera
is round, so a disc fits one far better than it fits a natural lake.

The ground underneath still has to be filled clear of the water plane, which
build_canvas.py does, or the game draws the sea inside the crater.

Height: the transform's second number is the world height, which the defines
scale to WORLD_EXTENTS_Y over the whole sixteen bit range, so the surface of a
filled caldera sits a shade over three.

usage: python build_lava_lakes.py <export prefix> [--write]
"""
import io
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs
import regions as rg

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
OUT = os.path.join(MOD, "gfx", "map", "map_object_data", "patriam_lava_lakes.txt")
SMOKE_OUT = os.path.join(MOD, "gfx", "map", "map_object_data", "patriam_volcanic_smoke.txt")
SMOKE_ENTITY = os.path.join(MOD, "gfx", "models", "mapitems", "lava_lakes", "patriam_volcanic_smoke.asset")
SMOKE_COUNT = 900             # plumes over the whole archipelago
ASSET_DIR = os.path.join(MOD, "gfx", "models", "mapitems", "lava_lakes")
WRITE = "--write" in sys.argv
BLOCKS_PER_PX = 5.1875
MIN_MASK_PX = 16              # smaller craters are left to the painted ground alone
WORLD_Y = 50.0                # WORLD_EXTENTS_Y in common/defines
SURFACE = hs.CK3_SEA + 0.5 * hs.LOW_UNITS_PER_BLOCK    # the filled floor, in heightmap units

ASSET = '''pdxmesh = {
\tname = "patriam_lava_lake_mesh"
\tfile = "lake.mesh"

\tmeshsettings = {
\t\tname = "pPlaneShape1"
\t\tindex = 0
\t\ttexture_diffuse = "patriam_lava_diffuse.dds"
\t\ttexture_normal = "nonormal.dds"
\t\ttexture_specular = "nospec.dds"
\t\tshader = "standard"
\t\tshader_file = "gfx/FX/pdxmesh.shader"
\t}
\tscale = 1.0
}

entity = {
\tname = "patriam_lava_lake_entity"
\tpdxmesh = "patriam_lava_lake_mesh"
}
'''


SMOKE_ASSET = '''entity = {
\tname = "patriam_volcanic_smoke"
\tlocator = { name = part1 }

\tdefault_state = "idle"
\tstate = { name = "idle" state_time = 5
\t\tevent = { time = 0 node = "part1" particle = "city/city_smoke_02" trigger_once = yes skip_forward = 2 }
\t}
\tcull_radius = 60
}
'''


def smoke(lava, islands, PW, PH, rng):
    """Plumes where a fissure would vent: along the rims of the calderas, over
    the fire that shows through the ash, and thinly over the rest of the ash."""
    rim = ndimage.binary_dilation(lava, iterations=2) & islands & ~lava
    weight = np.zeros(islands.shape, np.float32)
    weight[islands] = 0.25
    weight[rim] = 1.0
    weight[lava] = 0.6
    ys, xs = np.nonzero(weight > 0)
    if not len(ys):
        return []
    w = weight[ys, xs]
    pick = rng.choice(len(ys), size=min(SMOKE_COUNT, len(ys)), replace=False, p=w / w.sum())
    rows = []
    for i in pick:
        x = (xs[i] + rng.random()) * rg.B / BLOCKS_PER_PX
        y = (ys[i] + rng.random()) * rg.B / 5.192
        sc = 0.7 + rng.random() * 1.3
        rows.append("%.6f 0.000000 %.6f 0.000000 0.000000 0.000000 1.000000 %.6f %.6f %.6f"
                    % (x, PH - y, sc, sc, sc))
    return rows


def main(prefix):
    lava, calderas, filled = rg.vurkia_lava(prefix)
    prov = Image.open(os.path.join(MOD, "map_data", "provinces.png"))
    PW, PH = prov.size
    del prov
    lab, n = ndimage.label(calderas)
    sizes = np.bincount(lab.ravel())
    rows = []
    kept = 0
    for k in range(1, n + 1):
        if sizes[k] < MIN_MASK_PX:
            continue
        ys, xs = np.nonzero(lab == k)
        # the mask grid is sixteen blocks a pixel; the map is measured in province pixels
        cx = xs.mean() * rg.B / BLOCKS_PER_PX
        cy = ys.mean() * rg.B / 5.192          # blocks a province pixel down the map
        radius = np.sqrt(sizes[k] * rg.B * rg.B / np.pi) / BLOCKS_PER_PX
        y = SURFACE / 65535.0 * WORLD_Y + 0.05
        rows.append("%.6f %.6f %.6f 0.000000 0.000000 0.000000 1.000000 %.6f %.6f %.6f"
                    % (cx, y, PH - cy, radius, radius, radius))
        kept += 1
    print("%d calderas, %d of them wide enough for a lake of fire" % (n, kept))
    if rows:
        r = [float(x.split()[7]) for x in rows]
        print("   radius from %.1f to %.1f province pixels, %.0f to %.0f blocks"
              % (min(r), max(r), min(r) * BLOCKS_PER_PX, max(r) * BLOCKS_PER_PX))
    body = ('object={\n\tname="patriam_lava_lakes"\n\trender_pass=Map\n'
            '\tclamp_to_water_level=no\n\tgenerated_content=no\n\tlayer="lake_layer"\n'
            '\tpdxmesh="patriam_lava_lake_mesh"\n\tcount=%d\n\ttransform="%s\n"}\n'
            % (len(rows), "\n".join(rows)))
    if not WRITE:
        print("dry run, nothing written")
        return
    os.makedirs(ASSET_DIR, exist_ok=True)
    # The lake object is left out for now. The base game's lake mesh is a square
    # plane, so a caldera came out as an orange rectangle lying across the crater
    # rather than filling it, and under an ordinary mesh shader it does not move.
    # The painted ground carries the lava until a round mesh exists to lay on it.
    for stale in (OUT, os.path.join(ASSET_DIR, "lake.mesh"),
                  os.path.join(ASSET_DIR, "patriam_lava_lake.asset"),
                  os.path.join(ASSET_DIR, "patriam_lava_diffuse.dds")):
        if os.path.exists(stale):
            os.remove(stale)
    print("the %d widest craters are painted rather than laid with a mesh, which is square" % kept)

    islands, _, _ = rg.vurkia_parts(prefix)
    rows = smoke(lava, islands, PW, PH, np.random.default_rng(6355))
    io.open(SMOKE_ENTITY, "w", encoding="utf-8-sig", newline="\n").write(SMOKE_ASSET)
    io.open(SMOKE_OUT, "w", encoding="utf-8-sig", newline="\n").write(
        'object={\n\tname="patriam_volcanic_smoke"\n\trender_pass=Map\n'
        '\tclamp_to_water_level=no\n\tgenerated_content=no\n\tlayer="env_effect_layer"\n'
        '\tentity="patriam_volcanic_smoke"\n\tcount=%d\n\ttransform="%s\n"}\n'
        % (len(rows), "\n".join(rows)))
    print("wrote %d plumes of smoke over Vurkia" % len(rows))


if __name__ == "__main__":
    main(sys.argv[1])
