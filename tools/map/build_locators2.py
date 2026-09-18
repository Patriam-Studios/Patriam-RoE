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

The province map is at province resolution and the heightmap at twice that,
so the heightmap is sampled every second pixel.

usage: python build_locators2.py  (run from D:/Patriam-CK3-map, where full_pid.npy lives)
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

pid = np.load("full_pid.npy")
H, W = pid.shape
N = int(pid.max())
ranges = json.load(open("map_ranges.json"))
print("province map %d x %d, %d provinces, baronies 1..%d" % (W, H, N, ranges["sk_last"]))

# What stands on each barony, from the province history.
hist = io.open(os.path.join(MOD, "history", "provinces", "00_patriam_southern_kallonia.txt"), encoding="utf-8-sig").read()
holding = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d+) = \{[^}]*?holding = ([a-z_]+)", hist, re.M | re.S)}
print("holdings known for %d baronies" % len(holding))

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
        body.append("\t\t{\n\t\t\tid=%d\n\t\t\tposition={ %.6f 0.000000 %.6f }\n"
                    "\t\t\trotation={ 0.000000 0.000000 0.000000 1.000000 }\n"
                    "\t\t\tscale={ 1.000000 1.000000 1.000000 }\n\t\t}" % (i, x + 0.5, (H - y) - 0.5))
    body.append("\t}\n}\n")
    io.open(os.path.join(OUT, name), "w", encoding="utf-8-sig", newline="\n").write(head + "\n".join(body))
    print("wrote %-30s %d instances" % (name, len(pos)))
json.dump({str(k): [v[0] + 0.5, (H - v[1]) - 0.5] for k, v in pos.items()}, open("province_positions.json", "w"))
