"""Complete map_data for Patriam: Rise of Empires.

Southern Kallonia keeps provinces 1 to 943 from the geometry pass. Everything
else on the canvas is still one placeholder, which Crusader Kings III will not
accept, so this splits the remainder into real sea zones and into impassable
ground for the landmasses that are not provinced yet.

Partitioning runs at a quarter of province resolution and is then upscaled,
because a connected component pass over a hundred million pixels in Python is
not worth the wait. Southern Kallonia is composited back at full resolution so
its coastlines stay exact.
"""
import numpy as np, json
from PIL import Image
from collections import deque
Image.MAX_IMAGE_PIXELS = None

CK3_SEA = 3932
D = 4                 # partition scale
SEA_CELL = 130        # sea zone grid, in working pixels
LAND_CELL = 170       # impassable grid, in working pixels

hm = np.array(Image.open("heightmap.png"))
prov_h = hm[::2, ::2]
PH, PW = prov_h.shape
land = prov_h > CK3_SEA
del hm, prov_h
print(f"province map {PW} x {PH}, land {land.mean()*100:.1f}%")

# Southern Kallonia at full resolution, from the geometry pass.
pid_region = np.load("sk_pid.npy")
bx0, by0, bx1, by1 = np.load("sk_box.npy")
sk = np.zeros((PH, PW), dtype=np.int32)
sk[by0:by1, bx0:bx1] = np.where(pid_region >= 0, pid_region + 1, 0)
print(f"Southern Kallonia occupies {int((sk > 0).sum())} px as provinces 1..{int(sk.max())}")
NEXT = int(sk.max()) + 1

h2, w2 = PH // D, PW // D
land_s = land[:h2*D, :w2*D].reshape(h2, D, w2, D).all(axis=(1, 3))
sk_s = (sk[:h2*D, :w2*D].reshape(h2, D, w2, D) > 0).any(axis=(1, 3))
sea_s = ~land[:h2*D, :w2*D].reshape(h2, D, w2, D).any(axis=(1, 3))

def partition(mask, target, first_id):
    """Grid the mask, then split each cell into contiguous pieces.

    Cell size is derived from a cell COUNT so the grid divides the map evenly.
    A fixed cell size leaves a thin strip at the right and bottom edges, and
    the sea inside such a strip is contiguous for the whole width or height of
    the map, which produced two provinces that bordered almost everything."""
    H, W = mask.shape
    ncy = max(1, round(H / target)); ncx = max(1, round(W / target))
    ch = -(-H // ncy); cw = -(-W // ncx)
    lab = np.zeros(mask.shape, dtype=np.int32)
    nid = first_id
    for cy in range(0, H, ch):
        for cx in range(0, W, cw):
            sub = mask[cy:cy+ch, cx:cx+cw]
            if not sub.any(): continue
            seen = np.zeros(sub.shape, dtype=bool)
            for sy in range(sub.shape[0]):
                for sx in range(sub.shape[1]):
                    if sub[sy, sx] and not seen[sy, sx]:
                        q = deque([(sy, sx)]); seen[sy, sx] = True; cells = [(sy, sx)]
                        while q:
                            y, x = q.popleft()
                            for ny, nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
                                if 0 <= ny < sub.shape[0] and 0 <= nx < sub.shape[1] \
                                   and sub[ny, nx] and not seen[ny, nx]:
                                    seen[ny, nx] = True; q.append((ny, nx)); cells.append((ny, nx))
                        if len(cells) < 4: continue      # specks merge into a neighbour later
                        a = np.array(cells)
                        lab[cy + a[:,0], cx + a[:,1]] = nid
                        nid += 1
    return lab, nid

other_land_s = land_s & ~sk_s
imp_s, NEXT = partition(other_land_s, LAND_CELL, NEXT)
imp_first, imp_last = int(sk.max()) + 1, NEXT - 1
print(f"impassable provinces: {imp_first}..{imp_last}  ({imp_last - imp_first + 1})")

sea_lab_s, NEXT = partition(sea_s, SEA_CELL, NEXT)
sea_first, sea_last = imp_last + 1, NEXT - 1
print(f"sea zones: {sea_first}..{sea_last}  ({sea_last - sea_first + 1})")

# Upscale the partition and composite Southern Kallonia over it at full size.
def up(a):
    return np.repeat(np.repeat(a, D, axis=0), D, axis=1)
full = np.zeros((PH, PW), dtype=np.int32)
full[:h2*D, :w2*D] = up(imp_s) + up(sea_lab_s)
full[sk > 0] = sk[sk > 0]

# Any pixel still unclaimed takes the nearest claimed value. Gaps are only ever
# along boundaries, so a handful of dilations closes them.
for step in range(40):
    gaps = full == 0
    n = int(gaps.sum())
    if n == 0:
        print(f"gaps closed after {step} dilations"); break
    src = np.zeros_like(full)
    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
        # Shift without wrapping. np.roll wraps, which teleported a handful of
        # pixels to the opposite edge of the map and gave two provinces a
        # bounding box spanning the whole world.
        sh = np.zeros_like(full)
        ys = slice(max(dy,0), full.shape[0] + min(dy,0))
        xs = slice(max(dx,0), full.shape[1] + min(dx,0))
        yd = slice(max(-dy,0), full.shape[0] + min(-dy,0))
        xd = slice(max(-dx,0), full.shape[1] + min(-dx,0))
        sh[ys, xs] = full[yd, xd]
        src = np.where((src == 0) & gaps & (sh != 0), sh, src)
    if not (src != 0).any():
        print(f"WARNING {n} pixels could not be filled"); break
    full = np.where(src != 0, src, full)
else:
    print(f"WARNING {int((full == 0).sum())} pixels still unclaimed")

np.save("full_pid.npy", full)
print(f"total provinces: {int(full.max())}")
json.dump({"sk_last": int(sk.max()), "imp_first": imp_first, "imp_last": imp_last,
           "sea_first": sea_first, "sea_last": sea_last, "total": int(full.max())},
          open("map_ranges.json", "w"), indent=1)
print("saved full_pid.npy and map_ranges.json")
