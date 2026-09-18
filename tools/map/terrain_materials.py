"""Which Crusader Kings III ground material each WorldPainter biome becomes.

Biomes are matched by name rather than id, so a biome the world has not used
yet still lands somewhere sensible, and custom biomes such as Ebony Forest are
handled by the same rules as Minecraft's own.

Material indices are positions in the game's gfx/map/terrain/materials.settings,
which is also what detail_index.tga stores. They are looked up by material id
at runtime so a game update that reorders the list cannot silently repaint the
map.
"""
import json
import os
import re

# The mod's own copy when it exists, since it declares the terracotta of Mekanis
# after every one of the base game's materials, and the index of a material is
# its place in this list.
_MOD_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                             "gfx", "map", "terrain", "materials.settings")
MATERIALS_SETTINGS = _MOD_SETTINGS if os.path.exists(_MOD_SETTINGS) else os.path.join(
    r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game",
    "gfx", "map", "terrain", "materials.settings")

# Checked top to bottom; the first rule whose pattern matches the biome name wins.
# Primary is the ground itself. Overlay is laid thinly on top for texture.
RULES = [
    # Vurkia is painted as basalt deltas: the blasted ground of fallen Argonia.
    (r"basalt|nether|soul_sand|crimson|warped", "mountain_02_b", "desert_cracked"),
    (r"deep.*ocean|ocean|frozen_ocean", "beach_02", None),
    (r"frozen_river|river", "floodplains_01", "wetlands_02_mud"),
    (r"stony_shore|stone_beach|windswept_cliffs", "beach_02_pebbles", "hills_01_rocks"),
    (r"tropical beach|beach|snowy_beach", "beach_02_mediterranean", None),
    (r"mangrove|swamp", "wetlands_02", "mud_wet_01"),
    (r"ice_spikes|snowy_plains|ice_plains|snowy_tundra|frozen_peaks|snowy_slopes", "snow", "mountain_02_snow"),
    (r"alps|jagged_peaks|stony_peaks|mountain", "mountain_02", "mountain_02_snow"),
    (r"alpine|grove|meadow", "northern_plains_01", "hills_01_rocks_small"),
    (r"badlands|mesa", "mountain_02_desert_c", "desert_rocky"),
    (r"dunes|desert", "desert_wavy_01", "desert_01"),
    (r"savanna", "drylands_01_grassy", "drylands_01"),
    (r"rainforest|bamboo|jungle", "forest_jungle_01", "forestfloor"),
    (r"boreal|taiga|pine", "forest_pine_01", "forestfloor"),
    (r"ebony|dark_forest|pale_garden", "forestfloor", "forest_leaf_01"),
    (r"birch|flower_forest|cherry|forest", "forest_leaf_01", "forestfloor"),
    (r"crag|windswept_gravelly|windswept_hills|windswept_forest|hills", "hills_01", "hills_01_rocks"),
    (r"sunflower|plains", "plains_01", "plains_01_noisy"),
]
FALLBACK = ("plains_01", "plains_01_noisy")

# The painted surface, which WorldPainter calls the terrain, outranks the biome:
# it is the ground itself. Matched by the terrain's name, first rule wins. A
# rule of None means the surface says nothing particular (grass is grass in a
# meadow and in a jungle alike), so the biome decides there.
SURFACE_RULES = [
    (r"^(bare )?grass|^dirt|permadirt|^custom \d+: custom", None),
    (r"sea floor", None),                                   # under the water, and the biome knows the shore better
    (r"beach|white sand", ("beach_02_mediterranean", "beach_02")),
    (r"red sand|red desert|mesa|terracotta|hardened clay|stained clay", ("patriam_terracotta", "patriam_terracotta_rock")),
    (r"desert mountain|canyon|sul(f|ph)ur", ("mountain_02_desert_c", "desert_rocky")),
    (r"riverside|riverbed", ("hills_01_rocks_small", "mud_wet_01")),
    (r"sandstone", ("desert_rocky", "desert_01")),
    (r"desert|sand|dune", ("desert_wavy_01", "desert_01")),
    (r"basalt|blackstone|obsidian|netherrack|nether|lava|magma|soul|ash", ("mountain_02_b", "desert_cracked")),
    (r"deep snow|snow|ice", ("snow", "mountain_02_snow")),
    (r"gravel|cobble", ("hills_01_rocks", "hills_01_rocks_small")),
    (r"stone|rock|mountain|granite|diorite|andesite|tuff|deepslate|calcite|bedrock", ("mountain_02", "mountain_02_b")),
    (r"forest", ("forestfloor", "forest_leaf_01")),
    (r"podzol|mycelium", ("forestfloor", "forest_pine_01")),
    (r"moss", ("forest_leaf_01", "forestfloor")),
    (r"mud|clay|swamp", ("wetlands_02", "wetlands_02_mud")),
    (r"farm|field|crop|wheat", ("farmland_01", "plains_01")),
]

# A whole region can insist on its own ground whatever is painted under it.
# Mekanis is a mesa of red terracotta rock cut by deep canyons, and the floors of
# those canyons are painted as grass, which left green threads running through
# the red. The whole tableland reads as desert rock instead.
REGION_GROUND = {
    "mekanis": ("patriam_terracotta", "patriam_terracotta_rock"),
}

# Slope and height override the biome where the land itself is steep or high,
# so cliffs read as rock and summits as snow whatever was painted there.
STEEP_ROCK = "mountain_02_b"
HIGH_SNOW = "mountain_02_snow"


def material_index():
    with open(MATERIALS_SETTINGS, encoding="utf-8-sig") as f:
        ids = re.findall(r'\bid\s*=\s*"([^"]+)"', f.read())
    return {name: i for i, name in enumerate(ids)}


def material_for(biome_name):
    name = biome_name.lower().replace("custom: ", "")
    for pattern, primary, overlay in RULES:
        if re.search(pattern, name):
            return primary, overlay
    return FALLBACK


def surface_material_for(surface_name):
    """The ground a painted surface calls for, or None to leave it to the biome."""
    name = surface_name.lower()
    for pattern, ground in SURFACE_RULES:
        if re.search(pattern, name):
            return ground
    return None


def ground_maps(prefix, size, idx, report=True):
    """Primary and overlay material index for every province pixel.

    Returns (primary, overlay, unresolved): the two uint8 index maps, 255 where
    there is no overlay, and the mask of pixels no biome or surface spoke for,
    which the caller grounds from height instead."""
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    W, H = size
    primary = np.full((H, W), idx[FALLBACK[0]], dtype=np.uint8)
    overlay = np.full((H, W), idx[FALLBACK[1]], dtype=np.uint8)
    unresolved = np.ones((H, W), dtype=bool)
    if prefix and os.path.exists(prefix + "_biome.png"):
        table = load_biome_table(prefix + "_biomes.txt")
        biome = np.array(Image.open(prefix + "_biome.png").resize((W, H), Image.NEAREST)).astype(np.int32) - 1
        unresolved = biome == -1
        for bid, (share, name) in table.items():
            p, o = material_for(name)
            m = biome == bid
            primary[m] = idx[p]
            overlay[m] = idx[o] if o else 255
        if report:
            print("biomes mapped:")
            for bid, (share, name) in sorted(table.items(), key=lambda kv: -kv[1][0])[:20]:
                print("  %6.2f%%  %-32s -> %s" % (share, name, material_for(name)))
        del biome
    elif report:
        print("no biome export at %s" % prefix)
    if prefix and os.path.exists(prefix + "_surface.png"):
        stable = load_biome_table(prefix + "_surfaces.txt")     # same three column shape
        surf = np.array(Image.open(prefix + "_surface.png").resize((W, H), Image.NEAREST)).astype(np.int32) - 1
        spoke = 0
        if report:
            print("surfaces mapped:")
        for sid, (share, name) in sorted(stable.items(), key=lambda kv: -kv[1][0]):
            ground = surface_material_for(name)
            if report:
                print("  %6.2f%%  %-32s -> %s" % (share, name, ground if ground else "left to the biome"))
            if ground is None:
                continue
            m = surf == sid
            primary[m] = idx[ground[0]]
            overlay[m] = idx[ground[1]] if ground[1] else 255
            unresolved[m] = False
            spoke += int(m.sum())
        if report:
            print("the painted surface decided %.1f%% of the map" % (spoke * 100.0 / (W * H)))
        del surf
    if prefix and os.path.exists(prefix + "_surface.png"):
        import regions                                  # imported here, since regions reads the rules above
        rmap, rnames = regions.region_map(prefix, (W, H))
        for name, ground in REGION_GROUND.items():
            m = rmap == rnames.index(name) + 1
            primary[m] = idx[ground[0]]
            overlay[m] = idx[ground[1]] if ground[1] else 255
            unresolved[m] = False
            if report:
                print("  %-12s takes %s over %.2f%% of the map, canyon floors and all"
                      % (name, ground, m.mean() * 100))
        del rmap
    return primary, overlay, unresolved


def load_biome_table(path):
    """Read <prefix>_biomes.txt written by export_terrain.js."""
    table = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3:
                table[int(parts[0])] = (float(parts[1]), parts[2])
    return table


if __name__ == "__main__":
    idx = material_index()
    for _, primary, overlay in RULES:
        for m in (primary, overlay):
            assert m is None or m in idx, "material %s is not in materials.settings" % m
    for _, ground in SURFACE_RULES:
        for m in (ground or ()):
            assert m is None or m in idx, "surface material %s is not in materials.settings" % m
    for m in (STEEP_ROCK, HIGH_SNOW) + FALLBACK:
        assert m in idx, m
    print("all %d rule materials exist in the game's list of %d" % (len(RULES), len(idx)))
    for name in ("sunflower_plains", "custom: Ebony Forest", "deep_ocean", "windswept_hills",
                 "custom: Dunes Hills", "custom: Alps", "dark_forest_hills", "river", "unresolved"):
        print("  %-24s -> %s" % (name, material_for(name)))
