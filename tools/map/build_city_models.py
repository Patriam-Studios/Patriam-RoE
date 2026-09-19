"""Cities of many buildings, composed from the houses of Imperator: Rome.

The two games build a city differently. Imperator draws one as a crowd of
building meshes clustered together, placed by its own city_data according to how
many people live there, so one Imperator mesh is one house. Crusader Kings III
draws a whole holding as a single entity, and its own building_..._city_01 mesh
is an entire town. Handing one Imperator house to a slot where the base game
expected a town is why Thenithria was a speck: the map was drawing one house.

Scaling that house up to the size of a town would give one absurd building.
Instead a city here is composed, which the base game itself does: an entity may
declare locators at any position and attach other entities to them, as
gfx/models/artifacts/props/bp1/bp1_lantern_01_a.asset does, and as the holding
entity fp3_building_persian_temple_01_a_01_entity does. So each holding level
gets one entity carrying a centrepiece mesh, ringed by locators, each locator
holding one Imperator house.

The layout is a town rather than a grid: rings around the centre, each ring
further out and carrying more houses, every house nudged off its ring and turned
on the spot so that the result does not read as a wheel. The grand meshes sit in
the inner rings and the humble ones on the outskirts, which is the shape of a
real town. The randomness is seeded, so running this twice writes the same city.

WHAT THE NUMBERS MEAN. A locator position is in province pixels, and this map is
16384 by 6656 of them. The median barony measures about 26 pixels across, so a
holding has that much room. A village at level one covers about 6 pixels and the
capital at level four about 22, which nearly fills its barony and is what makes
Thenithria read as a great city.

usage: python build_city_models.py [--write]
"""
import io
import math
import os
import random
import sys

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SETS = os.path.join(MOD, "gfx", "models", "buildings", "imperator")
WRITE = "--write" in sys.argv

############################################################
# The layout. These are the numbers to turn.
############################################################

# How wide one Imperator house is, in province pixels. Measured off the bounding
# boxes in the mesh files themselves: a house body runs from 0.6 to 2.8 pixels
# across and averages about 2.3. Every hellenistic mesh also drags a 5.09 pixel
# ground decal, which is a blend patch and not the building, so it is ignored
# here and the decals of neighbouring houses are meant to overlap.
HOUSE_WIDTH = 2.3

# The lane left between two houses. Widen it for a town that breathes, narrow it
# for a crowded one. Spacing follows from the two.
LANE = 0.3
SPACING = HOUSE_WIDTH + LANE

# Where the innermost ring sits and how much further out each ring beyond it
# goes. The outermost ring of a level therefore sits at
# FIRST_RING + (rings - 1) * RING_STEP, and the town measures about twice that
# plus one house across.
FIRST_RING = 2.0
RING_STEP = 1.6

# How many rings each holding level carries. This is what turns a village into a
# capital, and it is the first thing to turn if a city looks too small or too
# large for its barony.
RINGS_PER_LEVEL = {1: 1, 2: 2, 3: 4, 4: 6}

# The size of every attached house, applied on the locator rather than on the
# mesh, so that one number here resizes every building in every city without any
# mesh being touched. Both games declare no scale at all on their buildings, so
# one is the measured starting value and not a guess, but it is the knob to turn
# if the houses come out too small or too large beside the base game's holdings.
BUILDING_SCALE = 1.0

# How far a house may wander off its ring, in province pixels, outwards and
# along the ring. Without this the rings read as rings.
JITTER_RADIAL = 0.35
JITTER_ALONG = 0.30

# How a house is turned. Imperator snaps its own houses to a number of steps and
# then adds a small variation, which keeps rectangular buildings roughly square
# to one another as a street would, so the same is done here.
ROTATION_STEPS = 8
ROTATION_JITTER = 8.0

# Seeded so that the same cities are written every time.
SEED = 6355

############################################################
# The meshes, grouped into tiers.
#
# The Greek tiers are the ones Imperator's own gfx/map/city_data/default.txt
# uses at each population tier. Its list at the third tier names six meshes and
# the game ships a seventh, hellenistic_03_07, which nothing in Imperator ever
# names; it is grouped with the six by its name, for the variety.
#
# Imperator's own data never names a single western mesh, so the Roman tiers
# come from the file names alone.
############################################################

GREEK_TIERS = {
    1: ["hellenistic_01_01", "hellenistic_01_02", "hellenistic_01_03"],
    2: ["hellenistic_02_01", "hellenistic_02_02", "hellenistic_02_03",
        "hellenistic_02_04", "hellenistic_02_05"],
    3: ["hellenistic_03_01", "hellenistic_03_02", "hellenistic_03_03",
        "hellenistic_03_04", "hellenistic_03_05", "hellenistic_03_06",
        "hellenistic_03_07"],
    4: ["hellenistic_04_01", "hellenistic_04_02", "hellenistic_04_03",
        "hellenistic_04_04", "hellenistic_04_05", "hellenistic_04_06",
        "hellenistic_04_07", "hellenistic_04_08"],
}

ROMAN_TIERS = {
    1: ["western_01_01", "western_01_02", "western_01_03",
        "western_01_04", "western_01_05"],
    2: ["western_02_01", "western_02_02", "western_02_03", "western_02_04",
        "western_02_05", "western_02_06", "western_02_07"],
    3: ["western_03_01", "western_03_02", "western_03_03",
        "western_03_04", "western_03_05"],
    4: ["western_04_01", "western_04_02", "western_04_03",
        "western_04_04", "western_04_05", "western_04_06"],
}

# What stands at the heart of each level. The Roman centrepiece is the tallest
# piece of its set and carries every Roman level. The Greek centrepiece is a
# grander thing, so it takes only the larger Greek levels and the two small ones
# are given the finest ordinary house they have instead.
SET_LAYOUT = [
    {
        "key": "hellenistic",
        "name": "Greek",
        "folder": "hellenistic_city",
        "file": "patriam_hellenistic_city_levels.asset",
        "entity": "patriam_hellenistic_city_%02d_entity",
        "tiers": GREEK_TIERS,
        "centres": {1: "hellenistic_01_03", 2: "hellenistic_02_02",
                    3: "hellenistic_center", 4: "hellenistic_center"},
    },
    {
        "key": "roman",
        "name": "Roman",
        "folder": "roman_city",
        "file": "patriam_roman_city_levels.asset",
        "entity": "patriam_roman_city_%02d_entity",
        "tiers": ROMAN_TIERS,
        "centres": {1: "western_center", 2: "western_center",
                    3: "western_center", 4: "western_center"},
    },
]


def ring_radii(level):
    """The radius of each ring at this holding level, innermost first."""
    return [FIRST_RING + i * RING_STEP for i in range(RINGS_PER_LEVEL[level])]


def ring_count(radius):
    """How many houses fit around a ring of this radius, at three at the least."""
    return max(3, int(round(2.0 * math.pi * radius / SPACING)))


def ring_tier(level, index):
    """Which tier of mesh a ring takes. The grand tiers sit at the heart of the
    town and the humble ones on its outskirts, so the tier falls by one with
    every ring outwards and rests on the first."""
    return max(1, level - index)


def lay_out(level, tiers, rng):
    """Every house of one city: its position, its turn and which mesh it is."""
    houses = []
    for index, radius in enumerate(ring_radii(level)):
        pool = tiers[ring_tier(level, index)]
        count = ring_count(radius)
        start = rng.random() * 2.0 * math.pi     # so no two rings line up
        previous = None
        for i in range(count):
            angle = start + 2.0 * math.pi * i / count
            r = radius + rng.uniform(-JITTER_RADIAL, JITTER_RADIAL)
            along = rng.uniform(-JITTER_ALONG, JITTER_ALONG) / max(r, 0.1)
            x = r * math.cos(angle + along)
            z = r * math.sin(angle + along)

            # no two neighbours the same house, where the tier has the variety
            choice = rng.choice(pool)
            while choice == previous and len(pool) > 1:
                choice = rng.choice(pool)
            previous = choice

            step = 360.0 / ROTATION_STEPS
            yaw = rng.randrange(ROTATION_STEPS) * step
            yaw += rng.uniform(-ROTATION_JITTER, ROTATION_JITTER)
            houses.append((x, z, yaw % 360.0, choice))
    return houses


def compose(spec, level, rng):
    """One composite entity, as the text of its asset block."""
    houses = lay_out(level, spec["tiers"], rng)
    radii = ring_radii(level)
    across = 2.0 * (radii[-1] + HOUSE_WIDTH / 2.0)

    out = []
    out.append("############################################################")
    out.append("# %s holding, level %d. %d houses in %d ring%s about a centre of"
               % (spec["name"], level, len(houses), len(radii),
                  "" if len(radii) == 1 else "s"))
    out.append("# %s, measuring about %.1f province pixels across."
               % (spec["centres"][level], across))
    out.append("############################################################")
    out.append("entity = {")
    out.append('\tname = "%s"' % (spec["entity"] % level))
    out.append('\tpdxmesh = "%s_mesh"' % spec["centres"][level])
    out.append("")
    for i, (x, z, yaw, mesh) in enumerate(houses):
        out.append('\tlocator = { name = "house_%02d" position = { %.3f 0.0 %.3f } '
                   "rotation = { 0.0 %.1f 0.0 } scale = %s }"
                   % (i, x, z, yaw, format(BUILDING_SCALE, ".3f")))
    out.append("")
    for i, (x, z, yaw, mesh) in enumerate(houses):
        out.append('\tattach = { "house_%02d" = "%s_entity" }' % (i, mesh))
    out.append("}")
    return "\n".join(out), houses


def build(spec, rng):
    """The four levels of one set, as the text of one asset file."""
    head = [
        "############################################################",
        "# %s cities, composed from the houses of Imperator: Rome." % spec["name"],
        "#",
        "# GENERATED by tools/map/build_city_models.py. Do not edit by hand:",
        "# turn the constants at the head of that tool and run it again.",
        "#",
        "# Crusader Kings III draws a holding as one entity, and Imperator draws a",
        "# city as many house meshes clustered together, so each level below is one",
        "# entity carrying a centrepiece mesh with a house attached at every locator",
        "# around it. Positions are in province pixels on a map 16384 of them wide,",
        "# where the median barony measures about 26 across.",
        "#",
        "# Spacing between houses %.1f, innermost ring %.1f, ring step %.1f,"
        % (SPACING, FIRST_RING, RING_STEP),
        "# scale of every attached house %.3f, seed %d." % (BUILDING_SCALE, SEED),
        "############################################################",
        "",
    ]
    blocks, counts = [], {}
    for level in (1, 2, 3, 4):
        text, houses = compose(spec, level, rng)
        blocks.append(text)
        counts[level] = len(houses)
    return "\n".join(head) + "\n\n".join(blocks) + "\n", counts


def known_entities():
    """Every entity the two ported city sets declare, read off the asset files."""
    names = set()
    for spec in SET_LAYOUT:
        folder = os.path.join(SETS, spec["folder"])
        for f in sorted(os.listdir(folder)):
            if not f.endswith(".asset") or f.startswith("patriam_"):
                continue
            for line in io.open(os.path.join(folder, f), encoding="utf-8-sig"):
                line = line.strip()
                if line.startswith("name = ") and line.endswith('_entity"'):
                    names.add(line.split('"')[1])
    return names


def self_check():
    """The smallest thing that fails if any of the above breaks."""
    declared = known_entities()
    assert declared, "no entities found in the ported sets"
    rng = random.Random(SEED)
    for spec in SET_LAYOUT:
        text, counts = build(spec, rng)
        assert text.count("{") == text.count("}"), "braces unbalanced in " + spec["key"]
        for level in (1, 2, 3, 4):
            assert spec["centres"][level] in spec["tiers"].get(level, []) \
                or spec["centres"][level].endswith("_center") \
                or any(spec["centres"][level] in t for t in spec["tiers"].values()), \
                "centrepiece %s is not a mesh of this set" % spec["centres"][level]
        for line in text.splitlines():
            if line.strip().startswith("attach = {"):
                name = line.split('"')[3]
                assert name in declared, "attached entity %s is not declared" % name
            if line.strip().startswith("locator = {"):
                assert line.count("{") == line.count("}"), "locator braces: " + line
        # every level larger than the one below it, and within reach of its barony
        assert counts[1] < counts[2] < counts[3] < counts[4], counts
        assert counts[1] >= 4 and counts[4] >= 48, counts
    # a ring must hold enough houses to close, or the town reads as spokes
    for level in (1, 2, 3, 4):
        for radius in ring_radii(level):
            assert ring_count(radius) * SPACING >= 2.0 * math.pi * radius - SPACING


def main():
    self_check()
    rng = random.Random(SEED)
    for spec in SET_LAYOUT:
        text, counts = build(spec, rng)
        path = os.path.join(SETS, spec["folder"], spec["file"])
        print("%s cities" % spec["name"])
        for level in (1, 2, 3, 4):
            radii = ring_radii(level)
            print("   level %d: %3d houses, %d ring%s out to %.1f, about %.1f pixels across"
                  % (level, counts[level], len(radii), " " if len(radii) == 1 else "s",
                     radii[-1], 2.0 * (radii[-1] + HOUSE_WIDTH / 2.0)))
        if WRITE:
            io.open(path, "w", encoding="utf-8-sig", newline="\n").write(text)
            print("   wrote %s" % os.path.relpath(path, MOD))
        else:
            print("   dry run, nothing written")


if __name__ == "__main__":
    main()
