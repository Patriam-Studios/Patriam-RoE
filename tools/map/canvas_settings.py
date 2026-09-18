"""Everything that has to know the size of the canvas, written in one go.

* NJominiMap world extents and the tablecloth rectangle in the defines,
* the map table props, moved from vanilla's Earth to the centre of this map
  and scaled with its width,
* the ground texture tiling in settings.terrain, so a texel stays the same
  size on the ground as it is in the base game.

usage: python canvas_settings.py <province width> <province height>
"""
import io
import os
import re
import sys

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
VANILLA_W, VANILLA_H = 9216.0, 4608.0
VANILLA_TABLE = (4500.0, 2560.0)     # where vanilla parks its tabletop
VANILLA_TILE_FACTOR = 337.5


def main(w, h):
    # defines
    p = os.path.join(MOD, "common", "defines", "00_patriam_defines.txt")
    s = io.open(p, encoding="utf-8-sig").read()
    s = re.sub(r"WORLD_EXTENTS_X = \d+", "WORLD_EXTENTS_X = %d" % (w - 1), s)
    s = re.sub(r"WORLD_EXTENTS_Z = \d+", "WORLD_EXTENTS_Z = %d" % (h - 1), s)
    s = re.sub(r"SURROUND_MAP_INNER_RECT = \{[^}]*\}", "SURROUND_MAP_INNER_RECT = { 0.0 0.0 %d.0 %d.0 }" % (w, h), s)
    io.open(p, "w", encoding="utf-8-sig", newline="\n").write(s)
    print("defines: extents %d x %d" % (w - 1, h - 1))

    # map table props
    k = w / VANILLA_W
    cx, cz = w / 2.0, h / 2.0
    src = os.path.join(GAME, "gfx", "map", "map_object_data")
    out = os.path.join(MOD, "gfx", "map", "map_object_data")
    for name in ("map_table_ce1.txt", "map_table_ep3.txt", "map_table_tgp.txt", "map_table_western.txt"):
        t = io.open(os.path.join(src, name), encoding="utf-8-sig").read()

        def fix(m):
            v = [float(x) for x in m.group(1).split()]
            v[0] = cx + (v[0] - VANILLA_TABLE[0]) * k
            v[2] = cz + (v[2] - VANILLA_TABLE[1]) * k
            v[7] *= k; v[8] *= k; v[9] *= k
            return 'transform="' + " ".join("%.6f" % x for x in v) + "\n\""
        t2, n = re.subn(r'transform="([^"]+)\n"', fix, t)
        io.open(os.path.join(out, name), "w", encoding="utf-8-sig", newline="\n").write(t2)
        print("%-24s %d props centred on (%.0f, %.0f), scale %.3f" % (name, n, cx, cz, k))

    # ground texture tiling
    p = os.path.join(MOD, "gfx", "map", "terrain", "settings.terrain")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        "detail_blend_range = 0.25\n"
        "# Vanilla tiles its ground textures %.1f times across a map %d wide. This\n"
        "# map is %d wide, so the count rises in proportion and a texel stays the\n"
        "# same size on the ground as it is in the base game.\n"
        "detail_tile_factor = %.1f\n"
        "detail_tile_offset_x = 0\n"
        "detail_tile_offset_y = 0\n"
        "normal_height_scale = 0.8\n"
        "skirt_height_factor = 0.1\n"
        "normal_step_size = 1.6\n" % (VANILLA_TILE_FACTOR, VANILLA_W, w, VANILLA_TILE_FACTOR * k))
    print("settings.terrain: tile factor %.1f" % (VANILLA_TILE_FACTOR * k))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
