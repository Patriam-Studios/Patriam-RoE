"""Towns and fortresses composed from the buildings of Imperator: Rome.

The two games build a settlement differently. Imperator draws a city as a crowd
of building meshes clustered together, placed by its own city_data according to
how many people live there, so one Imperator mesh is ONE HOUSE. Crusader Kings
III draws a whole holding as a single entity, and its own building_..._city_01
mesh is an ENTIRE TOWN. Handing one Imperator house to a slot where the base
game expected a town is why Thenithria was a speck.

So a holding here is composed, which the base game itself does: an entity may
declare locators at any position and attach other entities to them, as
gfx/models/artifacts/props/bp1/bp1_lantern_01_a.asset does with its flame, and
as the base game's own gallery entity building_all does with every holding it
owns. Each level of each set is one entity carrying a centrepiece mesh with a
town of houses laid about it.

THE TOWN IS NOT A WHEEL. Rings would read as rings, so the outline of each town
is lumped by three slow waves, every house wanders off its ring and turns on the
spot, and the grand buildings are only more likely at the heart rather than
sorted into rings by rank. Eighteen or nineteen distinct meshes stand in a large
town. The randomness is seeded, so running this twice writes the same world.

WHAT THE NUMBERS MEAN. A locator position is in province pixels, and this map is
16384 by 6656 of them. The median barony measures about 26 pixels across, so the
capital at level four is built to fill one, and a village at level one already
covers better than half, which matters because every holding in the world starts
at level one: a lord must pay for the levels above it.

FORTRESSES. Imperator ships one fort mesh and no others. The first level is that
fort alone, laid as a plain mesh and not as an entity, so the commonest holding
in the world takes the simplest path the game has. The levels above it are the
same fort with a settlement growing at its gate, which is what tells them apart,
and the houses are of the culture's own set, so a Thenithrian fortress gathers a
Roman village and a Drunathaenic one a Greek village.

usage: python build_holding_models.py [--write]
"""
import io
import math
import os
import random
import sys

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SETS = os.path.join(MOD, "gfx", "models", "buildings", "imperator")
OUT = os.path.join(SETS, "zz_patriam_holdings.asset")
WRITE = "--write" in sys.argv

############################################################
# The layout. These are the numbers to turn.
############################################################

# How wide one Imperator house is, in province pixels, before it is scaled.
# Measured off the bounding boxes in the mesh files themselves: a house body
# runs from 0.6 to 2.8 pixels across and averages about 2.3. Every Hellenistic
# mesh also drags a 5.09 pixel ground decal, which is a blend patch and not the
# building, so it is ignored here and the decals of neighbours are meant to
# overlap.
HOUSE_WIDTH = 2.3

# The size of every attached house, applied on the locator rather than on the
# mesh, so that one number here resizes every building in every holding without
# a mesh being touched.
BUILDING_SCALE = 1.15

# The lane left between two houses. Narrow it for a crowded town, widen it for
# one that breathes. Spacing follows from the two numbers above it.
LANE = 0.15
SPACING = HOUSE_WIDTH * BUILDING_SCALE + LANE

# Where the innermost ring sits and how much further out each ring beyond it
# goes. Rings tighter than the houses are wide give a town that crowds rather
# than one that rings, which is the look wanted. The first ring stands well off
# the middle so that the centrepiece, which is a civic complex and not a house,
# keeps a square of open ground about it rather than having cottages built
# through its walls.
FIRST_RING = 3.8
RING_STEP = 1.55

# How far the town reaches at each holding level, as a radius in province
# pixels, so a town measures about twice this across. THIS IS THE FIRST NUMBER
# TO TURN if a town looks too small or too large for its barony, the median
# barony being about 26 pixels across.
TOWN_RADIUS = {1: 11.0, 2: 12.4, 3: 13.4, 4: 14.2}

# The fortress. Imperator's fort measures 9.0 province pixels across, so nothing
# may be built inside this radius of the middle, and the village at its gate
# reaches out to these.
FORT_CLEAR = 6.0
FORT_TOWN_RADIUS = {2: 10.6, 3: 12.6, 4: 14.4}

# How much the outline of a town wanders from a circle, as a part of its radius.
# Three waves, each slower than the last, keep it from reading as any shape at
# all. At zero every town is a disc.
LUMP = (0.16, 0.11, 0.07)

# How far a house may wander off its ring, in province pixels, outwards and
# along the ring.
JITTER_RADIAL = 0.45
JITTER_ALONG = 0.40

# How a house is turned. Imperator snaps its own houses to a number of steps and
# then varies them a little, which keeps rectangular buildings roughly square to
# one another as a street would, so the same is done here.
ROTATION_STEPS = 8
ROTATION_JITTER = 9.0

# How strongly the grand tiers keep to the middle of a town. At zero every tier
# is equally likely anywhere, which reads as a suburb; at one the tiers sort
# themselves into rings, which reads as a target.
TIER_BIAS = 0.75

# Seeded, so that the same world is written every time.
SEED = 6355

# A holding is one entity, so every city of a level would otherwise be the same
# town laid down again and again across the world. Each level is therefore built
# three times over, and the game is given all three to choose between, which is
# what the base game does with its own two western cities. Add a fourth name
# here for more variety still, at the cost of a longer file.
VARIANTS = ("first", "second", "third")

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

# What stands at the heart of each city. The Roman centrepiece is the tallest
# piece of its set and carries every Roman level. The Greek centrepiece is a
# grander thing, so it takes only the larger Greek levels and the two small ones
# are given the finest ordinary house of the set instead.
SETS_LAYOUT = [
    {
        "key": "hellenistic",
        "name": "Greek",
        "tiers": GREEK_TIERS,
        "city": "patriam_hellenistic_city_%02d_%s_entity",
        "fort": "patriam_hellenistic_fort_%02d_%s_entity",
        "centres": {1: "hellenistic_01_03", 2: "hellenistic_02_02",
                    3: "hellenistic_center", 4: "hellenistic_center"},
    },
    {
        "key": "roman",
        "name": "Roman",
        "tiers": ROMAN_TIERS,
        "city": "patriam_roman_city_%02d_%s_entity",
        "fort": "patriam_roman_fort_%02d_%s_entity",
        "centres": {1: "western_center", 2: "western_center",
                    3: "western_center", 4: "western_center"},
    },
]

FORT_MESH = "patriam_hellenistic_fort_mesh"


def outline(angle, radius, waves):
    """The reach of the town at this angle: a circle with three slow waves laid
    over it, so that no two quarters of a town are the same size. The waves are
    divided out again so that the radius asked for is the furthest the town ever
    reaches rather than its middling reach, and a barony is never overrun."""
    a, b, c = LUMP
    return radius * (1.0
                     + a * math.sin(2.0 * angle + waves[0])
                     + b * math.sin(3.0 * angle + waves[1])
                     + c * math.sin(5.0 * angle + waves[2])) / (1.0 + a + b + c)


def pick_mesh(tiers, share, rng, previous):
    """One house. The grand tiers are likelier at the heart of the town and the
    humble ones on its outskirts, but every tier may stand anywhere, which is
    what keeps a town from reading as a target. `share` is how far out the house
    stands, nought at the middle and one at the edge."""
    wanted = 4.0 - 3.0 * share
    weights = [max(0.06, 1.0 - TIER_BIAS * abs(t - wanted)) for t in (1, 2, 3, 4)]
    for _ in range(8):
        tier = rng.choices((1, 2, 3, 4), weights)[0]
        choice = rng.choice(tiers[tier])
        if choice != previous:
            return choice
    return choice


def lay_out(tiers, radius, rng, clear=0.0):
    """Every house of one settlement: where it stands, how it is turned and
    which mesh it is. Houses are laid ring by ring from the middle outwards, out
    to a lumped outline, and nothing is laid within `clear` of the middle, which
    is how a fortress keeps its ground."""
    waves = [rng.random() * 2.0 * math.pi for _ in range(3)]
    houses = []
    previous = None
    ring = max(FIRST_RING, clear + SPACING * 0.5)
    while ring <= radius:
        start = rng.random() * 2.0 * math.pi      # so no two rings line up
        count = max(3, int(round(2.0 * math.pi * ring / SPACING)))
        for i in range(count):
            angle = start + 2.0 * math.pi * i / count
            reach = outline(angle, radius, waves)
            if ring > reach:
                continue
            r = ring + rng.uniform(-JITTER_RADIAL, JITTER_RADIAL)
            if r < clear:
                continue
            along = rng.uniform(-JITTER_ALONG, JITTER_ALONG) / max(r, 0.1)
            x = r * math.cos(angle + along)
            z = r * math.sin(angle + along)
            mesh = pick_mesh(tiers, min(1.0, r / max(reach, 0.1)), rng, previous)
            previous = mesh
            step = 360.0 / ROTATION_STEPS
            yaw = (rng.randrange(ROTATION_STEPS) * step
                   + rng.uniform(-ROTATION_JITTER, ROTATION_JITTER)) % 360.0
            houses.append((x, z, yaw, mesh))
        ring += RING_STEP
    return houses


def entity(name, mesh, houses, note):
    """One composed holding, as the text of its asset block."""
    reach = max([math.hypot(x, z) for x, z, _, _ in houses] or [1.0])
    out = ["############################################################"]
    out.append("# %s" % note)
    out.append("############################################################")
    out.append("entity = {")
    out.append('\tname = "%s"' % name)
    out.append('\tpdxmesh = "%s"' % mesh)
    out.append("")
    for i, (x, z, yaw, _) in enumerate(houses):
        out.append('\tlocator = { name = "house_%03d" position = { %.3f 0.0 %.3f } '
                   "rotation = { 0.0 %.1f 0.0 } scale = %.3f }"
                   % (i, x, z, yaw, BUILDING_SCALE))
    out.append("")
    for i, (_, _, _, house) in enumerate(houses):
        out.append('\tattach = { "house_%03d" = "%s_entity" }' % (i, house))
    out.append("")
    # Without this the game culls the whole holding by the reach of its
    # centrepiece alone, which is one building, and the town around it with it.
    out.append("\tcull_radius = %d" % int(reach * 2.0 + 20.0))
    out.append("}")
    return "\n".join(out)


def build(rng):
    """Every composed holding of both sets, and a note of what was written."""
    blocks, report = [], []
    for spec in SETS_LAYOUT:
        for level in (1, 2, 3, 4):
            for variant in VARIANTS:
                houses = lay_out(spec["tiers"], TOWN_RADIUS[level], rng)
                across = 2.0 * max(math.hypot(x, z) for x, z, _, _ in houses) + HOUSE_WIDTH * BUILDING_SCALE
                kinds = len({h for _, _, _, h in houses})
                blocks.append(entity(
                    spec["city"] % (level, variant), spec["centres"][level] + "_mesh", houses,
                    "%s city, level %d, the %s town of three. %d houses of %d kinds\n"
                    "# about a centre of %s, measuring about %.1f province pixels across."
                    % (spec["name"], level, variant, len(houses), kinds,
                       spec["centres"][level], across)))
                report.append(("%s city" % spec["name"], level, variant, len(houses), kinds, across))
        for level in (2, 3, 4):
            for variant in VARIANTS:
                houses = lay_out(spec["tiers"], FORT_TOWN_RADIUS[level], rng, clear=FORT_CLEAR)
                across = 2.0 * max(math.hypot(x, z) for x, z, _, _ in houses) + HOUSE_WIDTH * BUILDING_SCALE
                kinds = len({h for _, _, _, h in houses})
                blocks.append(entity(
                    spec["fort"] % (level, variant), FORT_MESH, houses,
                    "%s fortress, level %d, the %s village of three. The fort of Imperator\n"
                    "# with %d houses of %d kinds at its gate, about %.1f province pixels across."
                    % (spec["name"], level, variant, len(houses), kinds, across)))
                report.append(("%s fortress" % spec["name"], level, variant, len(houses), kinds, across))
    head = [
        "############################################################",
        "# The holdings of Patriam, composed from the buildings of Imperator: Rome.",
        "#",
        "# GENERATED by tools/map/build_holding_models.py. Do not edit by hand:",
        "# turn the constants at the head of that tool and run it again.",
        "#",
        "# Crusader Kings III draws a holding as one entity, and Imperator draws a",
        "# city as many house meshes clustered together, so each holding below is one",
        "# entity carrying a centrepiece with a house attached at every locator laid",
        "# about it. Positions are in province pixels on a map 16384 of them wide,",
        "# where the median barony measures about 26 across.",
        "#",
        "# Houses stand %.2f apart at a scale of %.2f, rings step %.1f, the outline"
        % (SPACING, BUILDING_SCALE, RING_STEP),
        "# wanders by %d parts in a hundred, seed %d." % (int(sum(LUMP) * 100), SEED),
        "############################################################",
        "",
    ]
    return "\n".join(head) + "\n\n".join(blocks) + "\n", report


def known_entities():
    """Every entity the ported sets declare, read off the asset files."""
    names = set()
    for folder in ("hellenistic_city", "roman_city", "hellenistic_fort"):
        here = os.path.join(SETS, folder)
        for f in sorted(os.listdir(here)):
            if not f.endswith(".asset") or f.startswith("zz_"):
                continue
            for line in io.open(os.path.join(here, f), encoding="utf-8-sig"):
                line = line.strip()
                if line.startswith("name = ") and line.endswith('_entity"'):
                    names.add(line.split('"')[1])
    return names


def known_meshes():
    """Every mesh the ported sets declare."""
    names = set()
    for folder in ("hellenistic_city", "roman_city", "hellenistic_fort"):
        here = os.path.join(SETS, folder)
        for f in sorted(os.listdir(here)):
            if not f.endswith(".asset") or f.startswith("zz_"):
                continue
            for line in io.open(os.path.join(here, f), encoding="utf-8-sig"):
                line = line.strip()
                if line.startswith("name = ") and line.endswith('_mesh"'):
                    names.add(line.split('"')[1])
    return names


def self_check():
    """The smallest thing that fails if any of the above breaks."""
    entities, meshes = known_entities(), known_meshes()
    assert entities and meshes, "the ported sets declare nothing"
    text, report = build(random.Random(SEED))
    assert text.count("{") == text.count("}"), "braces unbalanced"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("attach = {"):
            assert line.split('"')[3] in entities, "attached %s is not declared" % line
        if line.startswith("pdxmesh = "):
            assert line.split('"')[1] in meshes, "centre %s is not declared" % line
        if line.startswith("locator = {") or line.startswith("attach = {"):
            assert line.count("{") == line.count("}"), "braces: " + line
    counts = {}
    for kind, level, variant, houses, kinds, across in report:
        counts.setdefault(kind, {}).setdefault(level, []).append((houses, kinds, across))
    counts = {k: {l: min(v) for l, v in levels.items()} for k, levels in counts.items()}
    for kind, levels in counts.items():
        got = [levels[k][0] for k in sorted(levels)]
        assert got == sorted(got), "%s does not grow with its level: %s" % (kind, got)
        assert min(levels[k][1] for k in levels) >= 6, "too few kinds of building in " + kind
        assert levels[max(levels)][1] >= 12, "too few kinds of building in a grown " + kind
        assert min(got) >= 12, "%s is a hamlet at its smallest: %s" % (kind, got)
        assert max(levels[k][2] for k in levels) <= 31.0, "a holding wider than a barony"
    # written twice, the same thing twice over
    assert build(random.Random(SEED))[0] == text, "the tool is not deterministic"


def main():
    self_check()
    text, report = build(random.Random(SEED))
    for kind, level, variant, houses, kinds, across in report:
        print("%-16s level %d, %-6s town: %3d houses, %2d kinds, about %.1f province pixels across"
              % (kind, level, variant, houses, kinds, across))
    if WRITE:
        io.open(OUT, "w", encoding="utf-8-sig", newline="\n").write(text)
        print("wrote %s, %d holdings in all" % (os.path.relpath(OUT, MOD), len(report)))
    else:
        print("dry run, nothing written")


if __name__ == "__main__":
    main()
