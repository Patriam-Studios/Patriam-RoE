"""Map object locators, placed where the thing would actually stand.

The first pass put every holding at the centroid of its barony, which is why a
port sat in the middle of its fields. This pass chooses a spot by what stands
there:

* a town on the coast goes to the coast, on the flattest ground a step or two
  back from the water, so the city meets the sea rather than floating in it,
* a town inland goes to flat, low ground, the valley floor rather than the ridge,
* a castle goes to a rise, the highest reasonably flat ground in the barony,
  keeping clear of the province edge so the walls do not straddle a border,
* a temple goes to flat ground away from the edge, inland if it can,
* an empty barony, a wasteland or a sea zone keeps its centroid.

Every candidate is a pixel of the barony itself, at least two pixels inside its
border, so no object ever lands in a neighbour. Where a barony is too small for
that margin the margin shrinks until something qualifies. Army stacks, sieges
and battles are offset a little from the holding rather than sitting on it.

Choosing the spot is only half of it, because a holding is drawn as a composed
town of dozens of houses laid about a centrepiece and that town has a width of
its own. So every barony is also measured for the room it has at the spot
chosen: how far it is to the next province, to the water, and to ground too
steep to build on. The town is then shrunk by a scale written on its own
instance in building_locators.txt, so that a village in a narrow barony no
longer spills across the border and no house is left tilting off a cliff. Only
the buildings locator carries a scale; the stacks, sieges and activities are
markers rather than models and stay at one.

The province map is at province resolution and the heightmap at twice that,
so the heightmap is sampled every second pixel.

usage: python build_locators2.py  (run from D:/Patriam-CK3-map/full, where
full_pid.npy and map_ranges.json live, as rebuild_full.cmd runs it)
"""
import io
import json
import os
import re
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_scale as hs

Image.MAX_IMAGE_PIXELS = None
MOD = r"C:\Users\Alexander Donnelly\Documents\Paradox Interactive\Crusader Kings III\mod\Patriam-RoE"
SRC = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game\gfx\map\map_object_data"
OUT = os.path.join(MOD, "gfx", "map", "map_object_data")
FILES = ["activities.txt", "building_locators.txt", "combat_locators.txt", "other_stack_locators.txt",
         "player_stack_locators.txt", "siege_locators.txt", "special_building_locators.txt", "stack_locators.txt"]
MARGIN = 2

# The steepest ground a holding may stand on, as blocks of height for every
# province pixel of ground it crosses. One province pixel of this map is 5.19
# blocks across, and the heightmap is scaled at 320 height units a block, which
# height_scale puts at one pixel of height for every four blocks, so two blocks
# a pixel is a fall of two blocks in a little over five and the camera draws it
# at about twenty seven degrees. A house measures 2.6 province pixels across,
# some thirteen blocks, so on ground that steep the ground beneath one house
# falls better than five blocks, which is more than a storey. That is where a
# rigid mesh on a flat ground decal begins to show daylight under one corner
# and bury the other, so a town is kept back from anything steeper. It is set
# loosely rather than tightly, since a house that stands a little proud of a
# slope reads as a house on a slope, and holding every town to ground as flat as
# a table would put half of Southern Kallonia's towns in its valleys.
STEEP = 3.2

# How far a holding reaches from its middle at each level, as a radius in
# province pixels. These mirror TOWN_RADIUS and FORT_TOWN_RADIUS in
# build_holding_models.py, which is the tool that actually lays the houses out.
# Every holding in the world begins at the first level, a lord paying for the
# levels above it, so a barony whose history names no main building wants the
# first city radius.
WANTED = {("city", 1): 11.0, ("city", 2): 12.4, ("city", 3): 13.4, ("city", 4): 14.2,
          ("castle", 2): 10.6, ("castle", 3): 12.6, ("castle", 4): 14.4}

# A town may be shrunk to this much of the size it was built at and no further.
# The scale takes the houses down with the town, so shrinking hard would undo
# the very thing the towns were rebuilt for, and a barony that cramped is better
# off spilling a little than standing a village of models on a table.
MIN_SCALE = 0.70

# WHAT ACTUALLY CROWDS A TOWN. Only another barony does. Open water does not:
# a port is meant to stand on its shore, and houses may come down to the
# waterline, so the sea allows this much reach past the last dry pixel. Steep
# ground is the same kind of soft edge, a town being free to climb the first
# pixels of a slope before its houses begin to tilt.
SHORE = 3.0
CLIMB = 4.0

# Room is not one consideration among others, it is the gate. The scoring that
# follows it drove towns onto coasts, ridges and borders, which left the median
# holding five province pixels from the next barony where its own ground offered
# ten, so every town overhung its neighbours whatever it was scaled to. A spot
# is now only considered if it keeps this much of the best room the barony has,
# or all the room the holding could use, whichever asks less; the old scoring
# then chooses among the spots that qualify, so a port still meets the sea and a
# keep still takes the high ground, but neither does it standing on a border.
ROOM_KEEP = 0.80

# How far outside a barony the room around it is measured. Anything beyond the
# largest wanted radius above is room the holding could not use anyway.
ROOM_PAD = 32

pid = np.load("full_pid.npy")
H, W = pid.shape
N = int(pid.max())
ranges = json.load(open("map_ranges.json"))
print("province map %d x %d, %d provinces, baronies 1..%d" % (W, H, N, ranges["sk_last"]))

# What stands on each barony, from the province history.
hist = io.open(os.path.join(MOD, "history", "provinces", "00_patriam_southern_kallonia.txt"), encoding="utf-8-sig").read()
holding = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d+) = \{[^}]*?holding = ([a-z_]+)", hist, re.M | re.S)}
print("holdings known for %d baronies" % len(holding))

# What each barony has been built up to, from the buildings its history grants
# it. A holding is drawn at the level of its main building, so a barony granted
# city_04 is a capital and needs the room a capital takes. A barony granted
# nothing is at the first level like everything else in the world.
level = {}
for m in re.finditer(r"^(\d+) = \{(.*?)^\}", hist, re.M | re.S):
    block = re.search(r"buildings = \{(.*?)\}", m.group(2), re.S)
    named = re.findall(r"\b(city|castle)_0(\d)\b", block.group(1)) if block else []
    if named:
        kind, lv = max(named, key=lambda t: t[1])
        level[int(m.group(1))] = (kind, int(lv))
print("raised above the first level:", {k: "%s_%02d" % v for k, v in sorted(level.items())})

# Centroids for everything, as the fallback and for the sea and the wastes.
# Summed a band of rows at a time, since indexing every pixel of a hundred
# megapixel map at once wants more memory than is worth spending on it.
cnt = np.zeros(N + 1, dtype=np.float64)
sx_ = np.zeros(N + 1, dtype=np.float64)
sy_ = np.zeros(N + 1, dtype=np.float64)
for r0 in range(0, H, 256):
    band = pid[r0:r0 + 256]
    ys, xs = np.nonzero(band > 0)
    ids = band[ys, xs]
    cnt += np.bincount(ids, minlength=N + 1)
    sx_ += np.bincount(ids, weights=xs, minlength=N + 1)
    sy_ += np.bincount(ids, weights=ys + r0, minlength=N + 1)
cx = sx_ / np.maximum(cnt, 1)
cy = sy_ / np.maximum(cnt, 1)
del sx_, sy_

# Bounding boxes of the baronies only, found in one pass.
objs = ndimage.find_objects(pid, max_label=ranges["sk_last"])

# The Southern Kallonia box with a margin. Only this much of the heightmap is
# read, cropped straight from the file, since the whole thing is eight hundred
# megabytes and everything that needs a height lives in this box.
boxes = [o for o in objs if o is not None]
y0 = max(0, min(o[0].start for o in boxes) - 16); y1 = min(H, max(o[0].stop for o in boxes) + 16)
x0 = max(0, min(o[1].start for o in boxes) - 16); x1 = min(W, max(o[1].stop for o in boxes) + 16)
hm_img = Image.open(os.path.join(MOD, "map_data", "heightmap.png"))
assert hm_img.size == (W * 2, H * 2), "heightmap does not halve to the province map"
hm = np.array(hm_img.crop((x0 * 2, y0 * 2, x1 * 2, y1 * 2)))[::2, ::2]
del hm_img
elev_box = hs.elevation_blocks(hm).astype(np.float32)
land_box = hm > hs.CK3_SEA
del hm
sea_dist = ndimage.distance_transform_edt(land_box).astype(np.float32)
gy, gx = np.gradient(elev_box)
slope = np.hypot(gx, gy).astype(np.float32)
del gx, gy
# How far it is from any pixel to the nearest ground too steep to build on.
steep_dist = ndimage.distance_transform_edt(slope <= STEEP).astype(np.float32)


def land_room(i, ry, rx):
    """How far it is from every pixel of this barony's box to the nearest pixel
    of another barony, measured on a box padded by the room a holding could use.
    Sea and wasteland are not counted, since neither holds a town of its own."""
    ay, ax = max(0, ry.start - ROOM_PAD), max(0, rx.start - ROOM_PAD)
    by, bx = min(H, ry.stop + ROOM_PAD), min(W, rx.stop + ROOM_PAD)
    box = pid[ay:by, ax:bx]
    others = (box >= 1) & (box <= ranges["sk_last"]) & (box != i)
    d = ndimage.distance_transform_edt(~others).astype(np.float32)
    return d[ry.start - ay:ry.stop - ay, rx.start - ax:rx.stop - ax]


def choose(i, kind):
    sl = objs[i - 1]
    if sl is None:
        return None
    ry, rx = sl
    sub = pid[ry, rx] == i
    # inside the barony by a margin, shrinking the margin for tiny baronies
    inner = sub
    for m in range(MARGIN, 0, -1):
        cand = ndimage.binary_erosion(sub, iterations=m, border_value=0)
        if cand.sum() >= 6:
            inner = cand
            break
    ly0, lx0 = ry.start - y0, rx.start - x0
    d = sea_dist[ly0:ly0 + sub.shape[0], lx0:lx0 + sub.shape[1]]
    s = slope[ly0:ly0 + sub.shape[0], lx0:lx0 + sub.shape[1]]
    e = elev_box[ly0:ly0 + sub.shape[0], lx0:lx0 + sub.shape[1]]
    coastal = bool((d[sub] <= 1.5).any())
    rel = (e - e[sub].min()) / max(1.0, float(e[sub].max() - e[sub].min()))

    if kind == "city_holding" and coastal:
        # a step or two back from the water, then as flat as can be
        score = -np.abs(d - 2.0) * 3.0 - s * 4.0 - rel * 2.0
    elif kind == "city_holding":
        score = -s * 4.0 - rel * 3.0 + np.minimum(d, 6.0) * 0.3
    elif kind == "castle_holding":
        score = rel * 4.0 - s * 2.5 + np.minimum(d, 4.0) * 0.4
    elif kind == "church_holding":
        score = -s * 3.0 - rel * 1.0 + np.minimum(d, 5.0) * 0.6
    else:
        return None
    # whatever kind it is, it must first have room to stand in
    wanted = WANTED.get(level.get(i, ("city", 1)), WANTED[("city", 1)])
    room = land_room(i, ry, rx)
    roomy = inner & (room >= min(wanted, float(room[inner].max()) * ROOM_KEEP))
    if roomy.any():
        inner = roomy
    score = np.where(inner, score, -1e9)
    k = int(np.argmax(score))
    yy, xx = divmod(k, sub.shape[1])
    if not inner[yy, xx]:
        return None
    return rx.start + xx, ry.start + yy


pos, kinds_used = {}, {}
for i in range(1, N + 1):
    if cnt[i] == 0:
        continue
    kind = holding.get(i, "none") if i <= ranges["sk_last"] else "none"
    p = choose(i, kind) if kind in ("city_holding", "castle_holding", "church_holding") else None
    if p is None:
        x, y = int(round(cx[i])), int(round(cy[i]))
        x = min(max(x, 0), W - 1); y = min(max(y, 0), H - 1)
        if pid[y, x] != i:
            sl = objs[i - 1] if i <= ranges["sk_last"] else None
            if sl is not None:
                wy, wx = np.nonzero(pid[sl] == i)
                k = int(np.argmin((wy + sl[0].start - cy[i]) ** 2 + (wx + sl[1].start - cx[i]) ** 2))
                x, y = int(wx[k] + sl[1].start), int(wy[k] + sl[0].start)
            else:
                wy, wx = np.nonzero(pid == i)
                k = int(np.argmin((wy - cy[i]) ** 2 + (wx - cx[i]) ** 2))
                x, y = int(wx[k]), int(wy[k])
        p = (x, y)
        kinds_used["centroid"] = kinds_used.get("centroid", 0) + 1
    else:
        kinds_used[kind] = kinds_used.get(kind, 0) + 1
    pos[i] = p
print("placed:", kinds_used)


def fits(i):
    """How much of its built size the holding of this barony has room for, as a
    scale for all three axes of its instance.

    The room is the smallest of three reaches from the spot chosen: to the next
    barony, which is the border the town must not cross at all, to the water,
    which it may come down to and stand a few pixels along, and to ground
    steeper than STEEP, which it may climb the first pixels of before its houses
    begin to tilt."""
    x, y = pos[i]
    ry, rx = objs[i - 1]
    room = min(float(land_room(i, ry, rx)[y - ry.start, x - rx.start]),
               float(sea_dist[y - y0, x - x0]) + SHORE,
               float(steep_dist[y - y0, x - x0]) + CLIMB)
    wanted = WANTED.get(level.get(i, ("city", 1)), WANTED[("city", 1)])
    return min(1.0, max(MIN_SCALE, room / wanted))


scale = {i: fits(i) for i in sorted(pos)
         if i <= ranges["sk_last"] and objs[i - 1] is not None}
assert scale and all(MIN_SCALE <= s <= 1.0 for s in scale.values()), "a holding was scaled out of bounds"
sizes = np.array(sorted(scale.values()))
print("fitted %d holdings: %d shrunk, median %.3f, smallest %.3f, %d at the floor of %.2f"
      % (len(sizes), int((sizes < 1.0).sum()), np.median(sizes), sizes.min(),
         int((sizes <= MIN_SCALE).sum()), MIN_SCALE))


def nudge(i, dx, dy):
    """A point offset from the holding but still inside the barony, or the holding itself."""
    x, y = pos[i]
    for f in (1.0, 0.5):
        nx, ny = int(round(x + dx * f)), int(round(y + dy * f))
        if 0 <= nx < W and 0 <= ny < H and pid[ny, nx] == i:
            return nx, ny
    return x, y


OFFSETS = {
    "building_locators.txt": (0, 0),
    "special_building_locators.txt": (0, 0),
    "siege_locators.txt": (3, 1),
    "combat_locators.txt": (-3, 3),
    "player_stack_locators.txt": (3, -2),
    "other_stack_locators.txt": (-3, -2),
    "stack_locators.txt": (2, 3),
    "activities.txt": (-2, -3),
}
os.makedirs(OUT, exist_ok=True)
for name in FILES:
    src = io.open(os.path.join(SRC, name), encoding="utf-8-sig").read()
    head = src[:src.index("instances={")]
    dx, dy = OFFSETS[name]
    body = ["\tinstances={"]
    for i in sorted(pos):
        x, y = nudge(i, dx, dy) if (dx or dy) else pos[i]
        s = scale.get(i, 1.0) if name == "building_locators.txt" else 1.0
        body.append("\t\t{\n\t\t\tid=%d\n\t\t\tposition={ %.6f 0.000000 %.6f }\n"
                    "\t\t\trotation={ 0.000000 0.000000 0.000000 1.000000 }\n"
                    "\t\t\tscale={ %.6f %.6f %.6f }\n\t\t}" % (i, x + 0.5, (H - y) - 0.5, s, s, s))
    body.append("\t}\n}\n")
    io.open(os.path.join(OUT, name), "w", encoding="utf-8-sig", newline="\n").write(head + "\n".join(body))
    print("wrote %-30s %d instances" % (name, len(pos)))
json.dump({str(k): [v[0] + 0.5, (H - v[1]) - 0.5] for k, v in pos.items()}, open("province_positions.json", "w"))
