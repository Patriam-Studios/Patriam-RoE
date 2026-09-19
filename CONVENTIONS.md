# Patriam: Rise of Empires

Total conversion for Crusader Kings III, targeting 1.19.0.6.
Setting: the World of Patriam. Campaign opens in 6355 ADA, during the reign of
Hythaerion the Conqueror.

## Calendar

Year zero is the arrival of the Drunathaen in Taienmar.
BDA means Before Drunathaen Arrival. ADA means After Drunathaen Arrival.

## Writing style, mandatory

All text in this mod is written in Patriamic English. This covers localisation,
documentation, commit messages and script comments alike.

1. No dash punctuation of any kind. No em dashes, no en dashes, no hyphens.
   Rewrite compound words as separate words. Code syntax is exempt, so
   underscores in keys and file names are fine.
2. British and New Zealand spelling. Honour, armour, localisation, defence.
3. No contractions in narration. Write "would not", never "wouldn't".
4. No rule of three. Avoid the three item rhetorical list.

## Map scope and the heightmap pipeline

First release covers Inner Patriam only, meaning everything inside the Great
Mountain Ring from Olzhar in the west to Norkinia in the east, plus the Vurkia
Archipelago. Excluded and reserved for later updates: Almion, Wurtum, Atawan,
Va'Nyll, Oa, Na'Ull and the rest. Almion and Wurtum are the only two of those
that exist on the WorldPainter source at all, and neither is finished.

### Source world

`C:\Worldpainter\Maps\Sixth Edition of the Patriam Map.world`, 5.4 GB.
Full extent 664 by 270 tiles, which is 84992 by 34560 blocks. Height range
runs from -64 to 318.77 and the water level is 62, so in an exported heightmap
where minHeight is stored as zero, sea level is the value 126.

The stock `HeightMapExporter` cannot be used on this world. A one to one export
would be 84992 by 34560 pixels and Java refuses to allocate a raster that
large. The exporters in `D:\Patriam-CK3-map` sample every Nth block instead,
which is what any Crusader Kings III map needs anyway.

* `tools/map/export_sampled.js` writes a whole world overview at one or more steps.
* `tools/map/export_region.js` writes one block region at one step, plus a matching water
  level image so that land and sea can be separated exactly.

Run them with java directly and not through `wpscript.exe`, whose classpath is
missing the image jars. Around 34 GB of heap is enough. Check the Windows
commit headroom first, because exhausting it is what has broken this world
before.

### The crop

Inner Patriam and Vurkia occupy blocks x 0 to 48448 and the full height of
34560, which is the left 757 of the 1328 overview columns. That works out at an
aspect of 1.402, which matches the published world map on the Patriam Studios
site to within a thousandth, so the crop is confirmed correct.

One landmass inside that crop is excluded: an unfinished island off the north
east, spanning overview pixels x 633 to 723 and y 13 to 129. It is identified
by flood fill from a seed rather than by a bounding box, because a rectangle
around it would clip the Great Mountain Ring. It is sunk to the surrounding
ocean floor.

### Crusader Kings III dimensions

The canvas covers the **whole world**, as Alexander ruled on 18 September 2026.
No texture may exceed 16384 pixels in either direction, a hard limit that has
crashed the game once already, so the 84992 block width fits only at 5.1875
blocks a province pixel.

* `provinces.png` is 16384 by 6656, so `WORLD_EXTENTS_X` is 16383 and
  `WORLD_EXTENTS_Z` is 6655.
* `heightmap.png` is 32768 by 13312, two pixels a unit as vanilla has it,
  2.594 blocks a pixel.
* One province pixel is 5.1875 blocks across and 5.192 down, a difference of
  a tenth of a per cent that nothing can see.
* Southern Kallonia's baronies moved across by nearest sampling and kept their
  numbers, so every title, holding and line of history stayed valid. Their
  pixel area fell to about 62 per cent of what it was, a median of about 520
  pixels against vanilla's 1003 and its floor of 121.
* The eastern filler, the flat default ground WorldPainter gives every new
  tile, is sunk to the sea floor: it is 15.8 per cent of the world and not
  land. The two unfinished landmasses out east stay as impassable wastes.

### The whole world export

`tools/map/export_full.cmd` loads the WorldPainter world once (44 GB of heap,
so only after a reboot, since this machine leaks commit) and samples every
second block: the height at sixty four steps to the block, the water level,
the biome, the strongest tree layer and which layer it was, and the plant
layers. `tools/map/export_surface.js` is a second pass for the painted
terrain of every block, which WorldPainter keeps apart from the biome.

`build_canvas.py --export <prefix>` turns that into the canvas. Water is the
subtle part: the game has one water plane, so a lake held above the sea is
lowered until the same depth of water covers it at that plane. A river is not,
for the reason given under Rivers below. Ground below the sea with no water
over it is a dry basin and is lifted clear. Real bathymetry is kept within a dozen province pixels of the
coast and blended to one flat floor beyond, because a sea floor of one block
noise makes every sea tile a relief tile and the packed heightmap can address
only 64512 of them.

The ground comes from `terrain_materials.ground_maps`, shared by the material
maps and the colour map so the two cannot disagree: the painted surface
first, the biome where the surface is only grass or dirt, and height and
slope where neither spoke. Vurkia is painted as basalt deltas and takes dark
rock and ash.

`build_terrain.py` then blends the joins. Every pixel carries its own ground
in the first slot and the ground of whatever lies around it in the second,
weighted by how much of the neighbourhood that other ground holds, worked out
on a quarter grid and blurred. On a border the two cover about half each, so
both sides draw the same mixture and the seam disappears, and a little noise
makes the join wander instead of running straight. The third slot carries bare
rock on steep ground, snow on high ground, and otherwise a second texture for
the ground itself. Weights always add to 255, as vanilla's do. The colour map
is softened over about the same width, so that the colour seen from a distance
never draws a harder edge than the texture beneath it.

### Regions

`tools/map/regions.py` names the lands. Nothing in the WorldPainter world
records them, so each region is a seed point read off the published world map,
grown into the landmass that holds it, with a box for an archipelago. Olzhar,
Mekanis and Senkaria share one landmass and are told apart by what they are
painted with: mesa and red desert for Mekanis, sand for Senkaria, the rest for
Olzhar. The mesa mask is closed over the canyons cut through it, whose floors
are painted as grass, so that the whole tableland reads as red rock rather
than showing green threads. Mekanis is taken from the paint alone and not from
the landmass under it, because its own ravines cut below the water plane and
break the tableland into several pieces of land: matching the landmass left the
middle of the mesa outside the region and wearing vanilla's grey rock.

### Mekanis and its canyons

Mekanis is a mesa of red terracotta cut by ravines, and the source world cuts
them down to y 1, sixty blocks below the water plane. Every other basin on the
map is flattened just clear of the water, which is what left the mesa reading
as a plain with hills on it. Instead the whole tableland is carried upwards by
a smooth offset until its deepest floor clears the plane, tapered to nothing
near its own coast so the coastline does not move. That is what a mesa is: high
ground with canyons cut into it.

Narrow gorges are also lost to the resampling, which averages a four block
channel away. Alongside the average the canvas carries the lowest of each small
neighbourhood, and leans towards it where the two disagree by more than two
blocks, which cuts the channels back in without touching open ground.

The base game has no red rock at all: its desert mountain is grey brown and its
rocky desert is tan. `tools/map/make_terracotta.py` turns two of its textures
red, keeping their grain and borrowing their normal and properties maps, and
writes a copy of materials.settings declaring them after every one of the base
game's materials, so that no existing material index moves. Every tool reads
the mod's copy when it is there.

### Vurkia

Vurkia is the wreck of Argonia, an archipelago of volcanoes, and the source
world paints its basalt over the sea floor as well as the islands, so the paint
alone takes in the whole ocean there. What counts as Vurkia is basalt standing
above the water, and a caldera is then a hollow enclosed by one of those
islands, drowned in the source and filled with fire here.

Each caldera is filled to a flat floor just clear of the water plane, or the
game would draw the sea inside the crater. `tools/map/build_vurkia.py` then lays
a lake of lava over the wider ones as a map object, which is how the base game
draws its own lakes: one flat plane with a position, a turn and a scale. The
ground itself is ash, with lava showing in the calderas and along the gullies
the land drains down, and nine hundred plumes of smoke rise from the rims and
the fissures, using the base game's own city smoke.

### The farming heartland

The middle of Southern Kallonia is the rich ground that will one day feed the
empire of Thenithria, and it was reading as ordinary grass with puddles in it.
The fifteen realms whose title history turns their holder to house government
sit there in one contiguous cluster and hold 107 baronies between them, of
which the 64 the province terrain leaves at its default are the plains of the
heartland. `regions.heartland_baronies` reads them out of the title history,
the de jure tree and the province terrain rather than from a list written down
here, so that the fields follow the title tree wherever it goes, and it counts
farmland as plains so that a second run reads back what the first one wrote.

Those baronies take `medi_farmlands` as their ground, with `farmland_01` laid
thinly over it so that a province is not one sheet of the same furrows. A
barony boundary is a political line and a field is not, so the mask is carried
25 blocks past the baronies and then thinned away over a further 75, mottled
with smooth noise at about 150 blocks, and the fields interlock with the grass
beyond instead of stopping dead on a border. What the fields do not take is a
wood or a shore, since furrows under standing trees and furrows running into
the sea both read as mistakes. The same 64 baronies read as `farmlands` in
`common/province_terrain`, which `build_canvas.py` keeps when it rewrites that
file.

### The base game's own map objects

Every object the base game lays on its map is placed by coordinate: its lakes,
its animals, its bridges and its cliffs, the sprawl of Constantinople, Hadrian's
Wall and the pyramids of Giza. Those coordinates mean something only on its own
Earth, so on this world they scatter at random.
`tools/map/clear_vanilla_objects.py` writes an empty file over each one that
places objects, which is twelve of them, and leaves alone both the layer
definitions every object names and the files this mod writes for itself. Run it
again after a game update, in case Paradox adds another.

### Surf

The base game declares three foam emitters and places not one of them: its own
coast_foam.txt carries count zero on all three, so the white water in its own
game comes from the water itself. `tools/map/build_coast_foam.py` gives this
world surf the base game never had, laid only on shores with open water in front
of them and never in a sheltered channel, sized by how open that water is and
turned to face the land. Density is the thing to watch, since every instance is
a particle emitter and the base game places about seven hundred of all kinds
across its whole map: a continuous line of surf here would need seventy
thousand, so the spacing keeps it near five.

### Rivers

The game draws rivers from `map_data/rivers.png`, not from the heightmap, so a
river channel cut down to sea level becomes an inlet of the sea instead. The
canvas therefore leaves river ground where it stands, lifting a bed clear of
the water plane only where it lay under it by less than eight blocks and only
inside the finished world, because east of block 48448 WorldPainter calls the
shallow water over the unfinished ground river as well, and a whole sea of it
came up as land the first time. `build_rivers.py` then turns the river biome
into lines: the painted water is thinned to a single
thread, the threads are made into a tree rooted where the water reaches the
sea, tributaries under thirty pixels are dropped, and what is left is painted
with vanilla's own palette, green where a river rises, blue along its course
with the shade giving its width, and red on the last pixel of a tributary
where it meets a larger river.

### Trees

`build_trees.py` replaces all eighteen of the base game's tree generator files,
which otherwise lay Europe's forests across this terrain, with trees from the
world's own tree layers, the species chosen by the layer's name. Two scales of
noise thin them into woods with clearings between, since an even wash of trees
reads as a lawn. A region may override both species and density, and Alexander
named these on 19 September 2026: pine for Norkinia and Aeloen, sparse
temperate for Northern Kallonia with thick pine in Bouropheia in its far north
west, and jungle for Watol, which is rainforest and has nothing closer in the
base game.

`tools/map/build_canvas.py` builds it, and `tools/map/rebuild_full.cmd` runs
everything downstream in order: refine, pack, quadtree, masks, colour and
paper maps, ground materials, locators, trees. `tools/map/canvas_settings.py`
writes the three things that must know the size: the defines, the map table
props and the texture tiling. Without `--export` the canvas falls back to the
old sources, the 4 block export for the inner world and the 8 block overview
east of block 48448, which carry no biomes and no trees.

### The large map files

GitHub refuses any file over 100 MB, so the generated heightmaps, ground maps,
colour map, quadtree, masks and tree files are kept out of git and travel as
one archive attached to a release. A fresh clone cannot show the map without
them.

* To publish after a rebuild: `python tools/map/pack_binaries.py <out.zip>`,
  then `gh release create <tag> <out.zip> --target master`.
* To fetch: `gh release download <tag> --repo Patriam-Studios/Patriam-RoE`,
  then unzip over the mod folder. Paths inside the archive are relative to it.

### Province budget

Measured against vanilla, which ships 11301 land baronies over 14.6 Mpx of
province map, with a median barony of 1003 pixels and its smallest tenth under
471. The floor vanilla is willing to ship is 121 pixels.

Inner Patriam holds 24.70 Mpx of land on the province map. Excluding the Great
Mountain Ring, which should be impassable mountains rather than provinces,
roughly 19 Mpx is provinceable. At vanilla's median barony size that is about
19000 baronies, which is around one and two thirds of vanilla's entire world.

There is no province cap in the data. The commented `max_provinces` line in
`default.map` is vestigial, and province identity is keyed by colour, so the
theoretical ceiling is the whole RGB space. What actually costs is **counties,
not provinces**, because every county is a potential landed ruler with a court
and a family, and characters drive late game performance. Vanilla averages
2.56 baronies per county. Running four to six gives a far finer map at
vanilla's character load, so the rule for this mod is to be generous with
baronies and disciplined with counties.

Region measurements taken so far, in province map pixels:

| Region | Bounds | Land area | Baronies at median |
| --- | --- | --- | --- |
| Southern Kallonia | x 5580..6572, y 3840..5504 | 0.795 Mpx | **943 done** |

Southern Kallonia is ten landmasses: the mainland at 895 baronies, the ring
island at 4, and eight further islands. The ring island was identified by
testing each landmass for enclosed sea, and it holds 991 pixels of it inside
a 2942 pixel ring, at province x 6426 y 3901. The northern islands are
excluded, because those belong to the Ketanite Isles.

### Titles

`tools/map/build_titles.py` turns the saved assignment into the title
hierarchy. The tool records realms rather than title tiers, so each faction's
baronies are clustered into counties at roughly five each, and those counties
into duchies at roughly four each. A faction's stated tier is honoured when it
is a real Crusader Kings III tier and the size supports it, otherwise the tier
comes from how much land it holds, and every adjustment is reported when the
script runs.

Southern Kallonia currently builds to 9 kingdoms, 44 duchies, 192 counties and
943 baronies, which is 1188 titles. The generated files land in
`tools/map/build` and are not copied into `common/landed_titles` yet, for the
same reason the province map stays out of `map_data`: they would collide with
vanilla's own titles on those province numbers.

What sits in `tools/map/build` is the first pass, and its titles still carry
placeholder names such as "Kingdom of Thenithria 14 2". The names the mod
actually uses came later, from `tools/map/name_titles.py`, which writes both the
localisation and `tools/names_southern_kallonia.json`. That json is the source
of truth for every title name, and `tools/build_holdings.py` and
`tools/build_development.py` read it to decide what stands on each barony and
how rich each county is. Read it rather than the build folder, whose contents
are older than everything the mod now ships.

Regenerate rather than hand editing. The assignment is the source of truth and
the two will drift apart otherwise.

### The holdings tool

`tools/map/assign_tool.html` is published as an artifact and is how the
political map gets recorded. It loads `build/sk_idmap.png` for hit testing
and `build/sk_meta.json` for the colour to identifier palette, then paints
faction colours per barony. Saving writes one document to the artifact
database at `assignments/southern_kallonia`, holding the faction list with
tier, culture and faith, plus a map of barony identifier to faction key.
Read it with the Artifact tool, action `read_db`, db_op `get`.

### Geometry pass

`tools/map/province_pass.py` partitions one landmass into baronies. It
grows a cost weighted Dijkstra from seeds spread on a jittered grid, where
the step cost rises with slope, so provinces grow along valleys and their
borders settle on ridge lines. Because the search only ever walks over land,
no province can jump a strait or wrap round a peninsula. Seeds are then
relaxed to their province centroid and regrown, which is Lloyd's algorithm
with a geodesic distance rather than a straight line one.

The target is a size distribution like vanilla's rather than equal areas.
Southern Kallonia came out with a median barony of 834 pixels against
vanilla's 1003, a floor of 216 against vanilla's 121, and a ceiling of 1910.
The spread is tighter than vanilla's, which has a long tail of enormous
steppe and desert provinces. Weighting seed density by terrain would
loosen it if that becomes desirable.

Build output lands in `tools/map/build`, deliberately not in `map_data`.
A partial `map_data` folder would override vanilla and break the game for
anybody who enabled the mod to try the events, so nothing moves there until
`default.map`, terrain, positions and adjacencies all exist.

Province identifiers 1 to 898 are Southern Kallonia. Identifier 899 is a
placeholder covering all remaining pixels and will be replaced by real sea
zones. Names in `definition.csv` are placeholders of the form `SK_0001` and
are only ever seen by us, since the game takes displayed names from the
localisation of title keys.

### Height scaling

Vanilla sets `WATERLEVEL` to 3 out of a `WORLD_EXTENTS_Y` of 50, which is 3932
in sixteen bit, and the vanilla heightmap does put its coastlines just above
that value. Our mapping therefore is:

* WorldPainter sea level, value 126, maps to 3932.
* Above water, 160 sixteen bit units per block, putting the highest peak at
  44892 against vanilla's 48311.
* Below water, the whole depth range is stretched linearly down to zero so that
  the continental shelves stay visible.

### Height refinement, the shared curve, and what the renderer needs

The heightmap the mod first shipped was a two times upscale of a sample taken
every fourth block with every height rounded to a whole block. Gentle slopes
came out as staircases of flat terraces with a one block riser between them,
and the game drew every riser as a hard edge: black walls on hillsides and
straight seams across the plains that looked like rectangles of sea. That is
what any raw WorldPainter export does, so every export now goes through
`tools/map/refine_heightmap.py` before packing. It blurs in block space,
pins every pixel to the side of the coastline the province map cut it on,
and applies `tools/map/height_scale.py`, which is the one place that says
what a sixteen bit value means: sea at block 62 is 3932, the ground rises
320 units a block up to a knee 120 blocks above the sea, 136 a block above
it, and the highest summit lands at 60937. Every tool that reasons in blocks
imports that module rather than carrying a constant.

The base game also carries three things sized to its own Earth that a larger
canvas has to replace:

* `SURROUND_MAP_INNER_RECT` in `NGraphics`, which is where the tablecloth
  begins; and the `map_table_*.txt` objects, which park the goblets and
  scrolls around the Earth's edge and so sat on top of the northern provinces.
  Both are set for this canvas in the defines and in `gfx/map/map_object_data`.
* `gfx/map/terrain/masks`, one mask image per ground material, all 9216 by
  4608. The blend comes from `detail_index.tga` and `detail_intensity.tga`,
  so the masks hold nothing, but they must exist at the map's size:
  `tools/map/build_masks.py`. `settings.terrain` scales the texture tiling
  with the map's width for the same reason.
* `map_data/nodes.dat`, the terrain quadtree, which only the map editor's
  Save As writes. Without it the game draws through a tree sized for its
  Earth and clips everything past 9216 by 4608 to black. The format is
  decoded in `tools/map/build_nodes.py`, which reproduces vanilla's file
  exactly in layout and flags from vanilla's own heightmap.

Holdings are placed by `tools/map/build_locators2.py` by what stands on the
barony: a port on its coast, a town on flat low ground, a castle on a rise,
a temple on flat ground away from the edge, and the armies a little apart.

### Still outstanding

`packed_heightmap.png` and `indirection_heightmap.png` are generated by the
repack function in the map editor bundled at `game/tools/mapeditor`, not by
hand. The map cannot load until `provinces.png`, `definition.csv` and
`default.map` exist as well, so the heightmap is being kept as a build artefact
in `D:\Patriam-CK3-map` rather than committed here. It is 95 MB, which wants
Git LFS before it enters this repository.

## The long years

Patriamic humans were made to hold their prime, which is why Hythaerion rules
for 159 years and Araedan reaches 230. A life runs at the ordinary rate until
twenty, at a quarter of that rate from twenty to sixty, and at half of it
afterwards. The ages line up as follows: forty is worn as twenty five, sixty as
thirty, a hundred as fifty, a hundred and twenty as sixty, and 175 as eighty
seven.

Crusader Kings III has no lever for the rate of ageing itself, so the rule is
carried by two changes.

* `common/defines/00_patriam_defines.txt` maps every age that governs decline
  through that curve, and refits the health ramp to it rather than merely
  stretching it. Health begins to fail at fifty, at a lower chance that climbs
  a quarter as fast, so the wear a character carries at any age matches the
  vanilla curve at its mapped age to within one per cent. Prowess begins to
  fail at ninety, a woman bears until ninety, the fertility bands are mapped
  the same way, and a character counts as elderly at a hundred.
* `common/lifestyles/00_lifestyles.txt` quarters the experience a lifestyle
  gathers each month, since the prime years where a reign is spent now run four
  times as long. Without it every ruler would empty three lifestyle trees
  before he looked thirty.

What is not covered: events fire by the month rather than by the year, so a
long lived character still meets more of them than a short lived one.
Childhood, education and the age of majority are untouched, because the years
before twenty run at the ordinary rate.

## Imperator: Rome assets

Paradox gave Alexander written permission to use Imperator: Rome's assets in
this mod. The two games share the same mesh, asset and animation pipeline, so
a set ports by copying its folder and renaming one shader effect: Imperator's
`standard_snow` is CK3's `standard_winter`. That rename is mandatory on every
ported `.asset`, because CK3 has no `standard_snow` and a mesh whose shader
does not resolve does not draw. The other effects Imperator's buildings ask
for do exist in CK3 under the same names: `standard`, `standard_alpha_blend`,
and the decal effect `decal_world` the buildings use for their ground
footprints. Textures resolve by bare file name across the whole `gfx` tree in
both games, which is why a set's textures are copied in beside its meshes
rather than referenced where they sit.

Eight sets are ported, all under `gfx/models/buildings/imperator`.

| Folder | Set | Meshes | Worn by |
| --- | --- | --- | --- |
| `hellenistic_city` | Classical city | 3, 5, 7 and 8 variants over four tiers, plus a centre | the Greek and the Roman sets |
| `hellenistic_fort` | Square stone fort | one mesh, bare at the first castle level and villaged above it | the Greek and the Roman sets |
| `persian_city` | Eastern city | 4, 6, 6 and 6 variants over four tiers, plus a centre | `patriam_persian_building_gfx` |
| `persian_fort` | Eastern fort | one mesh, worn exactly as the square one is | `patriam_persian_building_gfx` |
| `temples` | Temple of Jupiter | one mesh, all four temple levels | `patriam_roman_building_gfx` |
| `temples` | Temples of Zeus and Artemis | two meshes, all four temple levels | `patriam_building_gfx` |
| `temples` | Mausoleum of Halicarnassus | one mesh, all four temple levels | `patriam_persian_building_gfx` |

Thenithrian takes the Roman face with
`building_gfx = { patriam_roman_building_gfx byzantine_building_gfx }`, Late
Drunathaenic takes the Greek one with
`building_gfx = { patriam_building_gfx byzantine_building_gfx }`, and Akarian
takes the Persian one with
`building_gfx = { patriam_persian_building_gfx byzantine_building_gfx }`. The
second entry in each pair covers the holdings the port does not reach yet, and
NO asset block of ours may name it, for the reason set out under the towns.
Kaegonic carries `western_building_gfx` and `western_unit_gfx` alone, being of
the Anglo Saxon cast, which is exactly what the base game's own `english`
culture carries, so nothing was ported for it.

WHY AKARIA HAS NO TEMPLE OF ITS OWN CULT. Imperator ships no Persian temple:
its Persian city set is houses and a civic centre with nothing sacred among
them, and its wonders hold one monument raised in the eastern manner, the
Mausoleum of Halicarnassus, which a satrap of the Persian king built. That is
what stands on an Akarian temple holding. It asks only for `standard`, so it
carries no shader rename, and it fires no particle, so nothing had to be
stripped from it as the Greek temples needed.

`common/buildings/00_city_buildings.txt`,
`common/buildings/00_castle_buildings.txt`,
`common/buildings/00_temple_buildings.txt` and
`common/buildings/00_tribal_buildings.txt` are all four vanilla's files carried
across whole, with asset blocks added at every level, so each must be diffed
against vanilla after a game update. Add to them and never rewrite one: the
castle file alone is 2000 lines of the base game's own.

Two things Imperator ships that had to be corrected or dropped:

* Imperator's own `western` assets point their diffuse and properties maps at
  the steppe set, which is felt and lattice rather than stone and tile. The
  matching Roman maps sit unused in the same folder under `building_01_*`, so
  the ported assets point there instead.
* Every particle these entities fire, the braziers of Artemis, the steaming
  pool of Jupiter, and the light shaft of Zeus, lives in Imperator alone. The
  states that fire them are stripped, and the Zeus light effect mesh is left
  behind with them.

Not yet checked in game: the scale of the meshes against CK3's own, the
terrain mask decal, and how the temples sit on a holding footprint they were
never cut for.

### Towns of many buildings

The two games build a settlement differently, and the difference is what first
made Thenithria a speck on the map. Imperator draws a city as a crowd of
building meshes clustered together, placed by its own `gfx/map/city_data`
according to how many people live there, so one Imperator mesh is one house.
Crusader Kings III draws a whole holding as a single entity, and its own
`building_..._city_01` mesh is an entire town. Putting one Imperator house where
the base game expected a town is why the map showed a house. Scaling that house
up to the size of a town would give one absurd building, so a holding here is
composed instead.

The base game composes entities itself. An entity may declare locators at any
position and attach other entities to them, which
`gfx/models/artifacts/props/bp1/bp1_lantern_01_a.asset` does for a flame and
which `gfx/models/buildings/all_buildings.asset` does for a whole board of
holdings, that last being a file in a parent folder attaching entities declared
in a subfolder, which is exactly the arrangement used here. A holding asset
block takes either a mesh or an entity, as `common/buildings/_buildings.info`
sets out, and the same file states that `names` may hold entities as well as
meshes, which is how one level is given several towns to choose between.

`tools/map/build_holding_models.py` writes every composite into the single file
`gfx/models/buildings/imperator/zz_patriam_holdings.asset`. Each is one entity
carrying a centrepiece mesh with a town of houses laid about it, and each level
is written three times over so that neighbouring holdings are not the same town
laid down again.

| Holding | Level 1 | Level 2 | Level 3 | Level 4 |
| --- | --- | --- | --- | --- |
| City, buildings | about 45 | about 58 | about 70 | about 79 |
| City, across | about 22 | about 25 | about 27 | about 29 |
| Fortress, buildings | the fort alone | about 16 | about 35 | about 55 |
| Fortress, across | 9 | about 21 | about 26 | about 29 |

Those are province pixels on a map 16384 of them wide, where the median barony
measures about 26 across, so a city fills its barony and a grown one presses at
its edges. Level one matters more than the three above it, because every holding
in the world begins there and a lord must pay to raise it.

The town is not a wheel. Houses are laid ring by ring from the middle outwards,
but the outline of each town is lumped by three slow waves, every house wanders
off its ring and turns on the spot, and the grand buildings are only likelier at
the heart rather than sorted into rings by rank, so thirteen to twenty two
distinct meshes stand in one town. The centrepiece keeps a square of open ground
about it, being a civic complex and not a house. The randomness is seeded, so
the same world is written every time.

ROME BUILDS IN THE SAME STONE AS GREECE. Imperator's own
`gfx/map/city_data/default.txt` gives its Roman graphical culture the very same
`hellenistic_*` meshes and the very same `hellenistic_center` as its Greek one:
the two blocks are identical but for their names, and no graphical culture in
that game ever names a `western` mesh. The `western` folder is a leftover
barbarian set, round huts and thatched cones wearing the steppe's felt and
lattice textures, and porting it as the Roman city set is what put tents and
yurts across Thenithria. It is removed.

What tells a Thenithrian city from a Drunathaenic one is therefore the plan and
not the buildings. Thenithria builds to the square, houses in insulae with a
street between one block and the next and two broader streets crossing at the
forum, inside a rectangle with its corners taken off. The Drunathaen build as
the ground allows, ring by ring under a lumped outline. The tiers are the ones
Imperator names at each population tier, except that its third tier lists six
meshes where the game ships seven, and `hellenistic_03_07`, which nothing in
Imperator ever names, is grouped with the six for the variety.

AKARIA NEEDS NO PLAN OF ITS OWN. The Roman set had to be given one only because
Rome and Greece build from the very same meshes, so nothing but the plan could
tell their towns apart. The Persian set is twenty two buildings of its own,
mudbrick and dome against colonnade and tile, so an Akarian town already reads
as nothing else and it is laid on the organic plan beside the Drunathaenic one.
Its tiers are read straight out of Imperator's `persian` block, four meshes at
the first and six at each of the three above it, and that block leaves no mesh
over the way the Hellenistic one does.

WHICH NUMBER IN A LOCATOR IS THE HEADING. A locator's `rotation` is three angles
in degrees and THE FIRST OF THEM turns the model about the vertical. The base
game writes 763 locator rotations, 715 of them with the angle in the first place
and two in the second, and those first values run right around the compass, 20,
90, 166, 180, 211 and 340, which is a heading and not a lean. The first towns
wrote the heading into the second place, which is the pitch, and every house in
the world lay on its side.

Every layout number lives in named constants at the head of that tool, and these
are the ones worth turning.

* `TOWN_RADIUS` is how far a town reaches at each level, and it is the first
  thing to turn if a holding looks wrong for its barony.
* `HOUSE_WIDTH` is 2.3, measured off the bounding boxes inside the mesh files
  themselves, where a house body runs from 0.6 to 2.8 province pixels across.
  Every Greek mesh drags a 5.09 pixel ground decal and every Persian one a 5.08
  pixel decal, which is a blend patch rather than the building, so it is ignored
  and the decals of neighbours are meant to overlap. The two sets of houses come
  out the same size, which is why one `HOUSE_WIDTH` serves all three plans.
* `BUILDING_SCALE` is 1.15 and is applied on the locator rather than on the
  mesh, so a single number resizes every house in every holding without any mesh
  being touched. `LANE` and `RING_STEP` are how crowded the result is.
* `VARIANTS` is how many towns each level offers the game.

WHICH ASSET A CULTURE PICKS, PROVEN IN GAME. When two asset blocks both answer
to a culture, the one written FIRST IN THE FILE wins, and the order of the tags
in the culture's own `building_gfx` list counts for nothing. This was paid for:
Akaria carries `patriam_persian_building_gfx` first and `byzantine_building_gfx`
after it, the Greek block used to answer to that second tag as a fallback, and
the Greek block stands before the Persian one, so Akaria was given Greek cities,
Greek forts and a Greek temple while its soldiers were Persian.

The rule that follows is simple and is now kept: NO PATRIAM ASSET BLOCK MAY NAME
`byzantine_building_gfx`. Each block answers to its own culture's tag alone, so
no two blocks ever answer to the same culture and file order never decides
anything. The cultures still carry `byzantine_building_gfx` as their second tag,
which covers the holdings the port does not reach, and vanilla's own blocks
answer to it far down the file where nothing of ours can be reached first.

Since a holding is drawn at the level of its main building and every holding in
the world starts at the first, the great seats are raised in province history
instead of waiting on a lord's purse: `660` Thenithria is given `city_04` and
`659` Kaeraenis Gralin, the royal seat, is given `castle_03`.

### Tribal holdings

A barony whose holder is tribal is drawn from `tribe_01` or `tribe_02` and not
from its castle, and the base game's generic tribal asset,
`building_western_tribal_01_a_mesh`, is a ring of timber stakes. That is what
put palisades across Southern Kallonia. This world holds no timber palisades, so
`common/buildings/00_tribal_buildings.txt` is carried across whole like the
others and both levels are given the same composed towns the cities take, a
tribal holding being simply a town that has not yet raised walls.

Why there are tribal holders at all is a separate question and an open one: 92
of the 192 counties carry no holder in history, so the game makes one for each,
and the cultures carry no innovations, which leaves the world in the tribal era.

### The forts

Crusader Kings III wraps its own early castles in a round wooden palisade, and
the cultures of the Drunathaen build square stone walls about a central keep.
Imperator ships exactly that, and it is ported whole to
`gfx/models/buildings/imperator/hellenistic_fort` as
`patriam_hellenistic_fort_mesh`. It asks for `standard_snow`, so it carries the
rename to `standard_winter` like the rest. Its paving and its wall texture are
the ones the Greek cities already carry, and since textures resolve by bare file
name across the whole `gfx` tree they are reached where they sit rather than
copied in a second time under the same names. Imperator fires a sound of its own
from the fort, out of an FMOD bank this game does not carry, so that state is
stripped and the castle levels name a sound of this game instead.

Akaria garrisons a fort of its own, Imperator's `persian_fort`, ported to
`gfx/models/buildings/imperator/persian_fort` as `patriam_persian_fort_mesh` in
exactly the same way and with the same shader rename and the same stripped
sound. Its paving is the Greek cities' again and its wall texture is its own.

Imperator ships one fort mesh to a graphical culture and no more, so the castle
levels are told apart by what gathers around it. The first level is the fort
standing bare, named as a plain mesh rather than as an entity, which is both the
simplest path the game has and the one every castle in the world takes at the
start. Above it the same fort carries a village at its gate, larger at every
level and built of the culture's own houses, so a Thenithrian fortress gathers a
Roman village, a Drunathaenic one a Greek village and an Akarian one a Persian
village. Nothing is laid within `FORT_CLEAR` of the middle, and the two forts
measure 9.0 province pixels across alike, against the 4.9 of the base game's own
fourth level castle, so one clearance serves both.

### The armies on the map

Four soldiers are ported, all under `gfx/models/units/imperator`.

| Folder | Set | Entity | Worn by |
| --- | --- | --- | --- |
| `roman_infantry` | Roman legionary, sword and scutum | `patriam_roman_infantry_01_entity` | `patriam_roman_unit_gfx` |
| `greek_infantry` | Greek hoplite, spear and aspis | `patriam_greek_infantry_01_entity` | `patriam_unit_gfx` |
| `persian_infantry` | Persian spearman in scale armour | `patriam_persian_infantry_01_entity` | `patriam_persian_unit_gfx`, tiers 2 and 4 |
| `persian_infantry` | Persian levy in a quilted coat | `patriam_persian_levies_infantry_01_entity` | `patriam_persian_unit_gfx`, tier 0 |

Thenithrian carries `unit_gfx = { patriam_roman_unit_gfx }`, Late Drunathaenic
carries `unit_gfx = { patriam_unit_gfx }` and Akarian carries
`unit_gfx = { patriam_persian_unit_gfx }`.

Imperator's Greek and Persian meshes carry no animations of their own: every
one of those assets reaches into the Roman folder for them. All three sets
therefore share one skeleton and one animation set, which is held once in
`gfx/models/units/imperator/animations` and reached by relative path from any
of the folders. Porting the Persian soldiers added no animation file at all. The shovel a soldier besieges with and the post he strikes while
the army gathers are shared in the same way, from
`patriam_imperator_props.asset` at the root of the ported folder. The drill post
is the only ported unit mesh that asked for `standard_snow`, so it is named
`standard_winter` here. Everything else asks only for `standard` and
`standard_usercolor`, which both games spell the same way.

Imperator sorts its animations into two weapon sets. Set one is the spear, and
the hoplite takes it. Set two is the sword, and the legionary takes it. A
soldier playing the wrong set would swing a weapon he is not holding. The two
sets run to the same lengths, so a legionary and a hoplite still trade blows in
time with one another.

WHICH SET A PORTED SOLDIER BELONGS TO IS READ OFF ITS OWN IMPERATOR ENTITY AND
NOT GUESSED FROM ITS WEAPON. Imperator's `persian_gfx_light_infantry`, which is
the spearman ported here, names `weapon_1` in all eighteen of its combat states
and holds `persian_spear_01`, so the Akarian soldier takes set one beside the
hoplite, and its states are the hoplite's word for word. Imperator's
`persian_gfx_heavy_infantry` names `weapon_2` in twenty two states and holds an
Arabian sword; it is not ported.

Crusader Kings III asks an army entity for twenty four states and Imperator
names its states differently, so each one carries whichever Imperator animation
reads closest. Two states have no counterpart at all. Imperator has no sick
soldier, so a sick one idles and marches exactly as a well one does and is told
apart only by the flies vanilla puts over his head. Imperator has no soldier
going home either, so disbanding borrows the animation men are recruited with.

`gfx/models/units/entity_links/00_army_entity_links.txt` is vanilla's file
carried across whole, with three blocks added at the foot for each ported
graphical culture, so it must be diffed against vanilla after a game update.
Vanilla gives each graphical culture three models across the quality tiers 0, 2
and 4. Thenithria and the Late Drunathaen have one model apiece, so all three
tiers point at the same entity and a levy looks the same as a royal army until a
second and a third rank of soldier are ported. Akaria has two, since Imperator
ships a Persian levy as well as a Persian soldier, so its levy tier is the
quilted coat and the two tiers above it the scale armour. Every graphical
culture carries a localisation entry, because the game logs a missing loc for
one that has none.

Left behind, and why:

* Imperator's light Roman levies and its Greek levies. Nothing Crusader Kings
  III asks for needs them, and they would only be worth porting as the lower
  quality tiers, which is exactly what the Persian levies were ported for.
* Imperator's Persian heavy infantry, its archers and everything it mounts. The
  heavy infantry plays the sword set and would want its own state block, and no
  army entity link asks for a horse.
* The javelin, the club and the raiding torch, for the same reason. No state
  reaches for any of them.
* The weapon impact sparks and the blood particles. Vanilla fires those from the
  weapon entity by passing it a state and a timing, and Imperator's timings were
  cut for Imperator's own state names. The weapon and the shield are therefore
  plain meshes here.
* Imperator's own sound events. The ported states use vanilla's Crusader Kings
  III unit sounds instead, since Imperator's FMOD banks are not in this game.

Not yet checked in game. The first thing to look at is the scale, which is
Imperator's own 0.1 against the 0.06 Crusader Kings III draws its own soldiers
at, and which is the only number in either asset worth turning. The second is
the `THE_RIG:` prefix the Imperator meshes carry on every bone name, since no
vanilla asset uses that form and nothing here proves this game's parser accepts
it. If the helmet or the weapon is missing while the soldier himself walks, that
prefix is the reason.

## Naming conventions

Every file and key this mod adds carries a `patriam_` prefix so that vanilla
content is never shadowed by accident. Event namespaces follow the pattern
`patriam_<subject>`.

## Rules the engine taught us

Each of these cost a crash or a broken screen once, so they are written down.

* Every `.txt` and `.yml` file the game reads needs a UTF-8 byte order mark.
  A file without one is silently skipped, and the keys in it simply never
  appear.
* A custom government must be listed in `GOVERNMENT_TYPES` inside the
  `NGovernment` define, and that define replaces the list rather than adding to
  it, so every vanilla government has to be restated beside ours.
* `change_government` belongs in title history, wrapped in
  `if = { limit = { exists = holder } holder = { change_government = X } }`.
  The same effect in character history crashes world setup outright.
* A county capital must be a castle. Vanilla seats even Venice in one, and the
  two town governments here take `primary_holding = castle_holding` for that
  reason.
* A ruler given only a kingdom or a duchy holds no ground. Hand over the
  capital county as well, or the engine complains about the ruler and about
  every county beneath them and then fills the gap with choices of its own.
* A localisation key the base game already defines must not be defined again.
  The name list tool checks vanilla before it writes.
* Culture pillars are read as `heritage_<key>_name` and `language_<key>_name`,
  never as the bare key, and a language pillar also wants a `color`.
* A bookmark character needs an entry in `common/bookmark_portraits/`, which
  the game itself writes with the `dump_bookmark_portraits` console command.
  Without one the bookmark shows a silhouette.

## Narrative architecture

Crusader Kings III has no generic scriptable journal entry type. The spine of
the linear campaign is therefore built from these pieces:

* `common/struggle/` carries the arc itself, one phase per stage of the
  conquest, with phases advanced by catalysts fired from our own events.
* `common/decisions/` carries the visible next step for the player, each one
  gated on the current struggle phase.
* `events/` carries the drama.
* `common/story_cycles/` carries pacing where an arc must advance on its own.

The struggle spine is deferred until the map and the titles exist, because a
struggle requires regions, cultures and faiths. Everything written before then
is deliberately free of any dependency on geography.
