"""Trees where the WorldPainter world has them.

The base game places its forests through eighteen generator files of tree
positions, all of them on its own Earth. A map that does not replace them gets
Europe's forests laid across its terrain, which is what this mod showed until
now. This writes all eighteen: the ones we use from the tree layers of the
WorldPainter world, and the rest empty.

The export records, for every sampled block, the strongest tree layer there
(0 to 15) and which layer it was. A layer's name decides the species, by the
rules below, checked top to bottom. "Rocks" is a custom object layer and not a
forest, so it plants nothing.

Density follows the painted strength. The total is held near the base game's
own, a little over half a million trees, since every tree is an instance the
game draws.

usage: python build_trees.py <export prefix> [--write]
"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs

Image.MAX_IMAGE_PIXELS = None
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(MOD, "gfx", "map", "map_object_data", "generated")
WRITE = "--write" in sys.argv
TARGET_TREES = 650000

# Which meshes a layer plants, first match wins. Several meshes share a layer's
# trees evenly, which is how the base game varies a forest.
RULES = [
    (r"rock", None),
    (r"spruce|pine|aungmar|northern kallonia|windswept", ["tree_pine_01_b_mesh", "tree_pine_single_01_a_mesh"]),
    (r"cherry", ["tree_sakura_01_mesh", "tree_sakura_02_mesh", "tree_sakura_03_mesh"]),
    (r"mangrove", ["tree_jungle_01_d_mesh", "tree_jungle_01_c_mesh"]),
    (r"senkaria", ["tree_palm_01_a_mesh"]),
    (r"ketan|mekanis", ["tree_cypress_01_a_mesh"]),
    (r"savannah", ["tree_leaf_01_single_a_mesh"]),
    (r".*", ["tree_leaf_01_a_mesh", "tree_leaf_01_b_mesh", "tree_leaf_01_c_mesh"]),
]
# The file each mesh is written to, which is the vanilla file of that mesh.
FILE_OF = {
    "tree_leaf_01_a_mesh": "tree_leaf_high_generator_1.txt",
    "tree_leaf_01_b_mesh": "tree_leaf_high_generator_2.txt",
    "tree_leaf_01_c_mesh": "tree_leaf_high_generator_3.txt",
    "tree_leaf_01_single_a_mesh": "tree_leaf_01_single_generator_1.txt",
    "tree_pine_single_01_a_mesh": "tree_pine_01_a_generator_1.txt",
    "tree_pine_01_b_mesh": "tree_pine_01_b_generator_1.txt",
    "tree_cypress_01_a_mesh": "tree_cypress_01_generator_1.txt",
    "tree_palm_01_a_mesh": "tree_palm_generator_1.txt",
    "tree_jungle_01_c_mesh": "tree_jungle_01_c_generator_1.txt",
    "tree_jungle_01_d_mesh": "tree_jungle_01_d_generator_1.txt",
    "tree_sakura_01_mesh": "tree_sakura_01_generator.txt",
    "tree_sakura_02_mesh": "tree_sakura_02_generator.txt",
    "tree_sakura_03_mesh": "tree_sakura_03_generator.txt",
}
EMPTY = ["reeds_01_generator_1.txt", "steppe_bush_01_generator.txt", "tree_leaf_2_high_generator_1.txt",
         "tree_pine_impassable_01_a_generator_1.txt", "tree_sakura_forest_generator.txt"]


def meshes_for(name):
    for pattern, meshes in RULES:
        if re.search(pattern, name.lower()):
            return meshes
    return None


def main(prefix):
    layers = []
    for line in io.open(prefix + "_layers.txt", encoding="utf-8"):
        kind, idx, name = line.rstrip("\n").split("\t")
        if kind == "tree":
            layers.append(name)
    print("tree layers:", len(layers))

    prov = Image.open(os.path.join(MOD, "map_data", "provinces.png"))
    PW, PH = prov.size
    del prov
    dens = np.array(Image.open(prefix + "_trees.png").resize((PW, PH), Image.BILINEAR)).astype(np.float32) / 15.0
    which = np.array(Image.open(prefix + "_treelayer.png").resize((PW, PH), Image.NEAREST))
    hm = np.array(Image.open(os.path.join(MOD, "map_data", "heightmap.png")))[::2, ::2]
    land = hm > hs.CK3_SEA
    del hm
    dens[~land] = 0.0
    dens[which == 0] = 0.0

    rng = np.random.default_rng(6355)
    # expected trees a province pixel at full strength, set so the total lands near the target
    weight = np.zeros_like(dens)
    for li, name in enumerate(layers):
        if meshes_for(name):
            m = which == li + 1
            weight[m] = dens[m]
    total_weight = float(weight.sum())
    per_px = TARGET_TREES / max(total_weight, 1.0)
    per_px = min(per_px, 1.5)          # never more than three trees to two pixels, however little forest there is
    print("forest weight %.0f province pixels, %.3f trees a pixel at full strength" % (total_weight, per_px))

    by_mesh = {}
    for li, name in enumerate(layers):
        meshes = meshes_for(name)
        m = which == li + 1
        if not meshes:
            print("  %-28s plants nothing" % name)
            continue
        ys, xs = np.nonzero(m & (weight > 0))
        if len(ys) == 0:
            print("  %-28s no land under it" % name)
            continue
        lam = weight[ys, xs] * per_px
        n = rng.poisson(lam)
        keep = n > 0
        ys, xs, n = np.repeat(ys[keep], n[keep]), np.repeat(xs[keep], n[keep]), None
        x = xs + rng.random(len(xs))
        z = (PH - ys) - rng.random(len(ys))
        pick = rng.integers(0, len(meshes), size=len(xs))
        for mi, mesh in enumerate(meshes):
            sel = pick == mi
            by_mesh.setdefault(mesh, []).append(np.stack([x[sel], z[sel]], axis=1))
        print("  %-28s %7d trees as %s" % (name, len(xs), ", ".join(meshes)))

    if not WRITE:
        print("dry run; total %d trees" % sum(sum(len(a) for a in v) for v in by_mesh.values()))
        return
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for mesh, fname in FILE_OF.items():
        parts = by_mesh.get(mesh, [])
        pts = np.concatenate(parts) if parts else np.zeros((0, 2))
        lines = []
        if len(pts):
            yaw = rng.random(len(pts)) * 2.0 * np.pi
            qy, qw = np.sin(yaw / 2.0), np.cos(yaw / 2.0)
            sc = 0.7 + rng.random(len(pts)) * 0.7
            rows = ["%.6f 0.000000 %.6f 0.000000 %.6f 0.000000 %.6f %.6f %.6f %.6f" % (p[0], p[1], a, b, c, c, c)
                    for p, a, b, c in zip(pts, qy, qw, sc)]
            lines = ["object={",
                     "\tname=\"%s_0\"" % fname.replace(".txt", ""),
                     "\trender_pass=Map",
                     "\tclamp_to_water_level=no",
                     "\tgenerated_content=yes",
                     "\tlayer=\"tree_high_layer\"",
                     "\tpdxmesh=\"%s\"" % mesh,
                     "\tcount=%d" % len(pts),
                     "\ttransform=\"" + "\n".join(rows) + "\n\"}"]
        io.open(os.path.join(OUT, fname), "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
        total += len(pts)
        print("wrote %-44s %7d" % (fname, len(pts)))
    for fname in EMPTY:
        io.open(os.path.join(OUT, fname), "w", encoding="utf-8-sig", newline="\n").write("")
        print("wrote %-44s   empty" % fname)
    print("total trees", total)


if __name__ == "__main__":
    main(sys.argv[1])
