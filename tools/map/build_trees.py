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

Density follows the painted strength, thinned by two scales of noise so that
the trees gather into woods with clearings and thin ground between them rather
than lying as an even wash. A region may override both the species and the
density: Alexander named the trees of Norkinia, Aeloen, Watol, Northern
Kallonia and Bouropheia on 19 September 2026.

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
TARGET_TREES = 430000

PINE = ["tree_pine_01_b_mesh", "tree_pine_single_01_a_mesh"]
LEAF = ["tree_leaf_01_a_mesh", "tree_leaf_01_b_mesh", "tree_leaf_01_c_mesh"]
JUNGLE = ["tree_jungle_01_d_mesh", "tree_jungle_01_c_mesh", "tree_palm_01_a_mesh"]
# The temperate mix Alexander asked for: mostly ordinary leaf trees, a quarter
# cypress, and cherry scattered thinly through them. A mesh repeated in the list
# is drawn that much more often.
TEMPERATE = (LEAF * 2) + ["tree_cypress_01_a_mesh", "tree_cypress_01_a_mesh", "tree_sakura_02_mesh"]

# Which meshes a layer plants, first match wins. Several meshes share a layer's
# trees evenly, which is how the base game varies a forest.
RULES = [
    (r"rock", None),
    (r"spruce|pine|aungmar|northern kallonia|windswept", PINE),
    (r"cherry", ["tree_sakura_01_mesh", "tree_sakura_02_mesh", "tree_sakura_03_mesh"]),
    (r"mangrove", ["tree_jungle_01_d_mesh", "tree_jungle_01_c_mesh"]),
    (r"senkaria", ["tree_palm_01_a_mesh"]),
    (r"ketan|mekanis", ["tree_cypress_01_a_mesh"]),
    (r"savannah", ["tree_leaf_01_single_a_mesh"]),
    (r".*", LEAF),
]

# What a region insists on, whatever layer was painted there. Alexander named
# these on 19 September 2026. Density is a multiplier on the painted strength.
# Watol is rainforest, and the closest the base game has is its jungle, so its
# jungle trees and palms stand in until something better is modelled.
REGION_TREES = {
    "norkinia": (PINE, 0.85),
    "aeloen": (PINE, 0.85),
    "watol": (JUNGLE, 1.0),
    "northern_kallonia": (TEMPERATE, 0.25),      # sparse temperate over most of it
    "bouropheia": (PINE, 1.6),                  # except the far north west, which is thick pine
}
# Norkinia, Aeloen and Watol carry no tree layer at all in the WorldPainter
# world, so there is nothing there to thin: their trees are sown on their own
# ground instead, everywhere the land will hold a forest.
SOWN = 0.62                    # strength given to ground a layer never covered
SOW_MAX_BLOCKS = 165.0         # nothing grows above this, where the rock begins
SOW_MAX_SLOPE = 3.2            # nor on a cliff, in blocks of rise a province pixel
BOUROPHEIA = ("northern_kallonia", "nw")        # Bouropheia is the north west of Northern Kallonia
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

    # A forest is not an even wash of trees. Two scales of noise decide where it
    # thickens into a wood, where it thins to trees dotted about, and where it
    # gives out altogether, so that the eye reads clumps rather than a lawn.
    clump = np.zeros_like(dens)
    for cell, amp in ((160, 0.62), (44, 0.38)):
        small = rng.random((max(2, PH // cell + 2), max(2, PW // cell + 2))).astype(np.float32)
        clump += amp * np.array(Image.fromarray(small).resize((PW, PH), Image.BICUBIC), dtype=np.float32)
    clump = np.clip(clump, 0.0, 1.0)
    clump = np.clip((clump - 0.34) * 2.6, 0.0, 1.6)      # bare ground under the low third
    dens *= clump

    # Ground that will hold a forest: not water, not the bare rock of a summit,
    # not a cliff face. Used where a region has trees but no layer ever painted
    # one, which is the case for Norkinia, Aeloen and Watol.
    el = hs.elevation_blocks(np.array(Image.open(
        os.path.join(MOD, "map_data", "heightmap.png")))[::2, ::2].astype(np.float32))
    gy, gx = np.gradient(el)
    plantable = land & (el < SOW_MAX_BLOCKS) & (np.hypot(gx, gy) < SOW_MAX_SLOPE)
    del gy, gx, el

    # what each region insists on, which overrides the painted layer
    import regions as rg
    rmap, rnames = rg.region_map(prefix, (PW, PH))
    region_of = np.zeros((PH, PW), np.uint8)
    region_names = []
    for name in REGION_TREES:
        if name == "bouropheia":
            m = rg.sub_mask(rmap, rnames, BOUROPHEIA[0], BOUROPHEIA[1])
        else:
            m = rmap == rnames.index(name) + 1
        region_names.append(name)
        region_of[m] = len(region_names)
        # a named region carries its own forest, so the painted layer is only a
        # floor to build on and never what holds it back
        sow = m & plantable
        raised = int((dens[sow] < SOWN * clump[sow]).sum())
        dens[sow] = np.maximum(dens[sow], SOWN * clump[sow])
        dens[m] *= REGION_TREES[name][1]
        print("  %-20s %8d province pixels, %7d of them sown, %7d too steep or too high"
              % (name, int(m.sum()), raised, int((m & ~plantable).sum())))
        del sow
    del rmap, plantable, clump

    # expected trees a province pixel at full strength, set so the total lands near the target
    weight = np.zeros_like(dens)
    for li, name in enumerate(layers):
        if meshes_for(name):
            m = which == li + 1
            weight[m] = dens[m]
    weight[region_of > 0] = dens[region_of > 0]
    total_weight = float(weight.sum())
    per_px = TARGET_TREES / max(total_weight, 1.0)
    per_px = min(per_px, 1.5)          # never more than three trees to two pixels, however little forest there is
    print("forest weight %.0f province pixels, %.3f trees a pixel at full strength" % (total_weight, per_px))

    by_mesh = {}
    # one number a pixel: which layer painted it, or which region has taken it over
    plan = which.copy()
    jobs = [(name, meshes_for(name), "layer") for name in layers]
    for ri, name in enumerate(region_names):
        plan[region_of == ri + 1] = len(layers) + ri + 1
        jobs.append((name, REGION_TREES[name][0], "region"))
    del region_of
    for ji, (name, meshes, kind) in enumerate(jobs):
        if not meshes:
            print("  %-28s plants nothing" % name)
            continue
        ys, xs = np.nonzero((plan == ji + 1) & (weight > 0))
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
        print("  %-20s %-7s %7d trees as %s" % (name, kind, len(xs), ", ".join(meshes)))

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
