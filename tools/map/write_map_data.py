"""Write the finished map_data set for Patriam: Rise of Empires."""
import numpy as np, json, os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

MOD = r"C:\Users\Alexander Donnelly\Documents\Paradox Interactive\Crusader Kings III\mod\Patriam-RoE"
MD = os.path.join(MOD, "map_data")
os.makedirs(MD, exist_ok=True)
os.makedirs(os.path.join(MOD, "common", "province_terrain"), exist_ok=True)

CK3_SEA = 3932
R = json.load(open("map_ranges.json"))
pid = np.load("full_pid.npy")
PH, PW = pid.shape
N = int(pid.max())
print(f"province map {PW} x {PH}, {N} provinces")

# Palette: a step 16 grid so colours stay far apart and survive any nudging.
vals = np.arange(0, 256, 16)
cube = np.array([(r, g, b) for r in vals for g in vals for b in vals])
cube = cube[cube.sum(axis=1) > 0]
rng = np.random.default_rng(6355); rng.shuffle(cube)
assert len(cube) >= N, f"only {len(cube)} colours for {N} provinces"
cols = cube[:N]
assert len({tuple(c) for c in cols}) == N

img = np.zeros((PH, PW, 3), dtype=np.uint8)
nz = pid > 0
img[nz] = cols[pid[nz] - 1]
Image.fromarray(img).save(os.path.join(MD, "provinces.png"), optimize=True)
print("wrote provinces.png")
del img

def name_for(i):
    if i <= R["sk_last"]:      return f"SK_{i:04d}"
    if i <= R["imp_last"]:     return f"WASTE_{i:04d}"
    return f"SEA_{i:04d}"

with open(os.path.join(MD, "definition.csv"), "w", newline="", encoding="utf-8") as f:
    f.write("0;0;0;0;x;x;\n")
    for i in range(1, N + 1):
        r, g, b = cols[i - 1]
        f.write(f"{i};{r};{g};{b};{name_for(i)};x;\n")
print(f"wrote definition.csv, {N + 1} rows")

# rivers.png: palette image, 255 is land with no river, 254 is sea.
hm = np.array(Image.open("heightmap.png"))
land = hm[::2, ::2] > CK3_SEA
riv = np.where(land, 255, 254).astype(np.uint8)
rim = Image.fromarray(riv, mode="P")
pal = [0] * 768
pal[254*3:254*3+3] = [255, 0, 128]
pal[255*3:255*3+3] = [255, 255, 255]
pal[3*3:3*3+3] = [0, 225, 255]
rim.putpalette(pal)
rim.save(os.path.join(MD, "rivers.png"), optimize=True)
print("wrote rivers.png")
del riv, rim

# Terrain from elevation. Sea and coastal sea come from the defaults.
elev = hm[::2, ::2].astype(np.int32) - CK3_SEA
del hm
sums = np.bincount(pid[nz], weights=elev[nz], minlength=N + 1)
cnts = np.bincount(pid[nz], minlength=N + 1)
mean = np.divide(sums, np.maximum(cnts, 1))
SCALE = 160.0                      # sixteen bit units per block, from the build
lines = ["default_land=plains", "default_sea=sea", "default_coastal_sea=coastal_sea"]
tally = {}
for i in range(1, N + 1):
    if i > R["imp_last"]:
        continue                   # sea zones take the default
    blocks = mean[i] / SCALE
    if i > R["sk_last"]:
        t = "mountains"            # not provinced yet, blocked off
    elif blocks > 46:  t = "mountains"
    elif blocks > 17:  t = "hills"
    else:              t = "plains"
    tally[t] = tally.get(t, 0) + 1
    if t != "plains":
        lines.append(f"{i}={t}")
p = os.path.join(MOD, "common", "province_terrain", "00_province_terrain.txt")
open(p, "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
print("wrote province_terrain:", tally)

open(os.path.join(MD, "default.map"), "w", encoding="utf-8", newline="\n").write(f"""definitions = "definition.csv"
provinces = "provinces.png"
rivers = "rivers.png"
topology = "heightmap.heightmap"
adjacencies = "adjacencies.csv"
island_region = "island_region.txt"
seasons = "seasons.txt"

#############
# SEA ZONES
#############
sea_zones = RANGE {{ {R['sea_first']} {R['sea_last']} }}

#####################
# IMPASSABLE TERRAIN
#####################
# Everything inside the Great Mountain Ring that is not Southern Kallonia yet.
# These become real provinces as each region is provinced in turn.
impassable_mountains = RANGE {{ {R['imp_first']} {R['imp_last']} }}
""")
print("wrote default.map")

# The reader scans for a terminating row of minus ones and never stops
# without one. A header alone made the game read past the end of a 59 byte
# file forever, which is what "Initializing Game" was actually doing.
open(os.path.join(MD, "adjacencies.csv"), "w", newline="", encoding="utf-8").write(
    "From;To;Type;Through;start_x;start_y;stop_x;stop_y;Comment\n"
    "-1;-1;;-1;-1;-1;-1;-1;\n")
open(os.path.join(MD, "island_region.txt"), "w", encoding="utf-8", newline="\n").write(
    "# Island regions, meaning no land path to the mainland.\n"
    "# The game uses these to shorten path finding.\n"
    "# Filled in once the counties of the offshore islands are named.\n")
open(os.path.join(MD, "seasons.txt"), "w", encoding="utf-8", newline="\n").write(
    "winter = {\n\tstart_date=00.12.01\n\tend_date=00.02.31\n}\n\n"
    "spring = {\n\tstart_date=00.03.01\n\tend_date=00.05.31\n}\n\n"
    "summer = {\n\tstart_date=00.06.01\n\tend_date=00.08.31\n}\n\n"
    "autumn = {\n\tstart_date=00.09.01\n\tend_date=00.11.30\n}\n")
open(os.path.join(MD, "heightmap.heightmap"), "w", encoding="utf-8-sig", newline="\n").write(
    'heightmap_file="map_data/packed_heightmap.png"\n'
    'indirection_file="map_data/indirection_heightmap.png"\n'
    f'original_heightmap_size={{ {PW*2} {PH*2} }}\n'
    'tile_size=65\n'
    'should_wrap_x=no\n'
    'level_offsets={ { 0 0 } { 0 1397 } { 0 3129 } { 0 3690 } { 0 3861 } }\n'
    'max_compress_level=4\n'
    'empty_tile_offset={ 255 127 }\n')
print("wrote adjacencies.csv, island_region.txt, seasons.txt, heightmap.heightmap")
print(f"\nranges: baronies 1..{R['sk_last']}, impassable {R['imp_first']}..{R['imp_last']}, "
      f"sea {R['sea_first']}..{R['sea_last']}")
