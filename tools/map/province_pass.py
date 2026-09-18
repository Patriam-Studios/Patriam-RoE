"""Geometry pass: partition a landmass into baronies.

Growth is a cost weighted Dijkstra from spread seeds across the land mask, so
provinces grow along valleys and their borders settle on ridge lines, and no
province ever jumps a strait because the search only ever walks over land.
Seeds are then relaxed to the centroid of their province and regrown, which is
Lloyd's algorithm with a geodesic distance instead of a straight line one.

Aiming for a size distribution like vanilla's rather than for equal areas,
because real provinces are not equal and vanilla's spread is the proven target.
"""
import numpy as np, heapq, sys, csv
from PIL import Image
from collections import deque
Image.MAX_IMAGE_PIXELS = None

CK3_SEA = 3932
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 900
ROUNDS = 3
ALPHA = 6.0          # how strongly ridges repel province borders
SEED_XY = (6148, 4500)   # a point inside Southern Kallonia, province pixels
PAD_BOX = (5560, 3820, 6600, 5530)

print("loading heightmap")
hm = np.array(Image.open("heightmap.png"))[::2, ::2]     # province resolution
PH, PW = hm.shape
print(f"province map {PW} x {PH}")

x0, y0, x1, y1 = PAD_BOX
sub = hm[y0:y1, x0:x1].astype(np.float32)
land = sub > CK3_SEA
del hm

# Isolate the one landmass, so neighbouring islands inside the box are ignored.
sy, sx = SEED_XY[1] - y0, SEED_XY[0] - x0
assert land[sy, sx], "seed is not on land"
mask = np.zeros_like(land); q = deque([(sy, sx)]); mask[sy, sx] = True
while q:
    y, x = q.popleft()
    for ny, nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
        if 0 <= ny < land.shape[0] and 0 <= nx < land.shape[1] and land[ny,nx] and not mask[ny,nx]:
            mask[ny,nx] = True; q.append((ny,nx))
area = int(mask.sum())
print(f"landmass: {area} province px, box {land.shape[1]} x {land.shape[0]}")

# Slope, used to make ridge crossings expensive.
gy, gx = np.gradient(sub)
slope = np.hypot(gy, gx)
hi = np.percentile(slope[mask], 95) or 1.0
cost = 1.0 + ALPHA * np.clip(slope / hi, 0, 1)
cost[~mask] = np.inf
del sub, gy, gx, slope, land

# Seeds on a jittered grid, so they start evenly spread.
rng = np.random.default_rng(6355)
spacing = max(2.0, np.sqrt(area / TARGET))
seeds = []
H, W = mask.shape
yy = np.arange(spacing / 2, H, spacing)
xx = np.arange(spacing / 2, W, spacing)
for cy in yy:
    for cx in xx:
        jy = int(cy + rng.uniform(-spacing / 4, spacing / 4))
        jx = int(cx + rng.uniform(-spacing / 4, spacing / 4))
        if 0 <= jy < H and 0 <= jx < W and mask[jy, jx]:
            seeds.append((jy, jx))
print(f"spacing {spacing:.1f} px -> {len(seeds)} seeds")

INF = np.inf
def grow(seeds):
    dist = np.full(mask.shape, INF, dtype=np.float32)
    owner = np.full(mask.shape, -1, dtype=np.int32)
    heap = []
    for i, (y, x) in enumerate(seeds):
        dist[y, x] = 0.0; owner[y, x] = i; heap.append((0.0, y, x))
    heapq.heapify(heap)
    while heap:
        d, y, x = heapq.heappop(heap)
        if d > dist[y, x]: continue
        o = owner[y, x]
        for ny, nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
            if 0 <= ny < H and 0 <= nx < W:
                c = cost[ny, nx]
                if c == INF: continue
                nd = d + c
                if nd < dist[ny, nx]:
                    dist[ny, nx] = nd; owner[ny, nx] = o
                    heapq.heappush(heap, (nd, ny, nx))
    return owner

for r in range(ROUNDS):
    owner = grow(seeds)
    counts = np.bincount(owner[owner >= 0], minlength=len(seeds))
    filled = int((owner >= 0).sum())
    print(f"  round {r+1}: {filled}/{area} px assigned, "
          f"{(counts > 0).sum()} non empty, median {int(np.median(counts[counts>0]))} px")
    if r == ROUNDS - 1: break
    # Relax each seed to its province centroid, snapped back onto the province.
    ys, xs = np.nonzero(owner >= 0)
    ids = owner[ys, xs]
    cy = np.bincount(ids, weights=ys, minlength=len(seeds))
    cx = np.bincount(ids, weights=xs, minlength=len(seeds))
    new = []
    for i in range(len(seeds)):
        if counts[i] == 0: continue
        ty, tx = cy[i] / counts[i], cx[i] / counts[i]
        sel = ids == i
        py, px = ys[sel], xs[sel]
        k = np.argmin((py - ty) ** 2 + (px - tx) ** 2)
        new.append((int(py[k]), int(px[k])))
    seeds = new

# Renumber to a dense set of province ids starting at 1.
counts = np.bincount(owner[owner >= 0], minlength=len(seeds))
keep = np.nonzero(counts > 0)[0]
remap = np.full(len(seeds), -1, dtype=np.int32)
remap[keep] = np.arange(len(keep))
pid = np.where(owner >= 0, remap[np.clip(owner, 0, None)], -1)
n = len(keep)
sizes = np.bincount(pid[pid >= 0], minlength=n)
print(f"\n{n} baronies")
print("size distribution in province map px, vanilla in brackets:")
for q, van in ((1, 271), (5, 386), (10, 471), (25, 664), (50, 1003), (75, 1656), (90, 2520), (99, 4241)):
    print(f"  p{q:<2} = {int(np.percentile(sizes, q)):>6}   [vanilla {van}]")
print(f"  min {sizes.min()}  max {sizes.max()}  mean {sizes.mean():.0f}")

np.save("sk_pid.npy", pid)
np.save("sk_box.npy", np.array(PAD_BOX))
print("\nsaved sk_pid.npy and sk_box.npy")
