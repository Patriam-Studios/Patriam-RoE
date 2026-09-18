"""Geometry pass over every landmass of a region, with the tool assets.

Southern Kallonia is the mainland plus the ring island plus the southern and
eastern islands. The northern islands belong to the Ketanite Isles and are
left out, identified by lying in the northern strip while not being the ring.
"""
import numpy as np, heapq, json
from PIL import Image
from collections import deque
Image.MAX_IMAGE_PIXELS = None

CK3_SEA, ALPHA, ROUNDS = 3932, 6.0, 3
BOX = (5560, 3820, 6600, 5530)
SPACING = 29.0
MIN_ISLAND = 150
NORTH_STRIP_Y = 4100
RING_CENTROID = (6426, 3901)

x0, y0, x1, y1 = BOX
hm = np.array(Image.open("heightmap.png"))[::2, ::2]
PH, PW = hm.shape
sub = hm[y0:y1, x0:x1].astype(np.float32)
del hm
land = sub > CK3_SEA
H, W = land.shape

gy, gx = np.gradient(sub)
slope = np.hypot(gy, gx)
del gy, gx

seen = np.zeros_like(land); comps = []
for sy in range(H):
    for sx in range(W):
        if land[sy, sx] and not seen[sy, sx]:
            q = deque([(sy, sx)]); seen[sy, sx] = True; cells = [(sy, sx)]
            while q:
                y, x = q.popleft()
                for ny, nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
                    if 0 <= ny < H and 0 <= nx < W and land[ny,nx] and not seen[ny,nx]:
                        seen[ny,nx] = True; q.append((ny,nx)); cells.append((ny,nx))
            comps.append(np.array(cells))

keep, drop = [], []
for c in comps:
    n = len(c)
    cy, cx = int(c[:,0].mean()) + y0, int(c[:,1].mean()) + x0
    if n < MIN_ISLAND:
        drop.append((n, cx, cy, "below the minimum island size")); continue
    is_ring = abs(cx - RING_CENTROID[0]) < 25 and abs(cy - RING_CENTROID[1]) < 25
    if cy < NORTH_STRIP_Y and not is_ring:
        drop.append((n, cx, cy, "northern island, Ketanite Isles")); continue
    keep.append(c)
keep.sort(key=len, reverse=True)
print(f"keeping {len(keep)} landmasses, {sum(len(c) for c in keep)} province px")
for n, cx, cy, why in sorted(drop, reverse=True):
    print(f"  excluded {n:>6} px at x {cx} y {cy}: {why}")

hi = np.percentile(slope[land], 95) or 1.0
cost = 1.0 + ALPHA * np.clip(slope / hi, 0, 1)
del slope, sub

pid = np.full((H, W), -1, dtype=np.int32)
next_id = 0
rng = np.random.default_rng(6355)

for ci, cells in enumerate(keep):
    m = np.zeros((H, W), dtype=bool); m[cells[:,0], cells[:,1]] = True
    by0, by1 = cells[:,0].min(), cells[:,0].max()
    bx0, bx1 = cells[:,1].min(), cells[:,1].max()
    local_cost = np.where(m, cost, np.inf)

    seeds = []
    for cy in np.arange(by0 + SPACING/2, by1 + 1, SPACING):
        for cx in np.arange(bx0 + SPACING/2, bx1 + 1, SPACING):
            jy = int(cy + rng.uniform(-SPACING/4, SPACING/4))
            jx = int(cx + rng.uniform(-SPACING/4, SPACING/4))
            if by0 <= jy <= by1 and bx0 <= jx <= bx1 and m[jy, jx]:
                seeds.append((jy, jx))
    if not seeds:   # island smaller than one grid cell still becomes one barony
        k = len(cells) // 2
        seeds = [(int(cells[k,0]), int(cells[k,1]))]

    for r in range(ROUNDS):
        dist = np.full((H, W), np.inf, dtype=np.float32)
        own = np.full((H, W), -1, dtype=np.int32)
        heap = []
        for i, (y, x) in enumerate(seeds):
            dist[y, x] = 0.0; own[y, x] = i; heap.append((0.0, y, x))
        heapq.heapify(heap)
        while heap:
            d, y, x = heapq.heappop(heap)
            if d > dist[y, x]: continue
            o = own[y, x]
            for ny, nx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
                if 0 <= ny < H and 0 <= nx < W:
                    c = local_cost[ny, nx]
                    if c == np.inf: continue
                    nd = d + c
                    if nd < dist[ny, nx]:
                        dist[ny, nx] = nd; own[ny, nx] = o
                        heapq.heappush(heap, (nd, ny, nx))
        if r == ROUNDS - 1: break
        ys, xs = np.nonzero(own >= 0); ids = own[ys, xs]
        cnt = np.bincount(ids, minlength=len(seeds))
        sy_ = np.bincount(ids, weights=ys, minlength=len(seeds))
        sx_ = np.bincount(ids, weights=xs, minlength=len(seeds))
        new = []
        for i in range(len(seeds)):
            if cnt[i] == 0: continue
            ty, tx = sy_[i]/cnt[i], sx_[i]/cnt[i]
            sel = ids == i; py, px = ys[sel], xs[sel]
            k = np.argmin((py-ty)**2 + (px-tx)**2)
            new.append((int(py[k]), int(px[k])))
        seeds = new

    cnt = np.bincount(own[own >= 0], minlength=len(seeds))
    used = np.nonzero(cnt > 0)[0]
    remap = np.full(len(seeds), -1, dtype=np.int32)
    remap[used] = np.arange(len(used)) + next_id
    sel = own >= 0
    pid[sel] = remap[own[sel]]
    next_id += len(used)
    print(f"  landmass {ci+1}: {len(cells):>7} px -> {len(used):>4} baronies")

n = next_id
sizes = np.bincount(pid[pid >= 0], minlength=n)
print(f"\n{n} baronies total")
for q, van in ((10, 471), (25, 664), (50, 1003), (75, 1656), (90, 2520)):
    print(f"  p{q:<2} = {int(np.percentile(sizes, q)):>6}   [vanilla {van}]")
print(f"  min {sizes.min()}  max {sizes.max()}")

# Palette on a step 16 grid, so a browser nudging a colour still rounds true.
vals = np.arange(0, 256, 16)
cube = np.array([(r,g,b) for r in vals for g in vals for b in vals])
cube = cube[cube.sum(axis=1) > 0]
rng2 = np.random.default_rng(6355); rng2.shuffle(cube)
cols = cube[:n+1]
assert len({tuple(c) for c in cols}) == n+1

canvas = np.empty((PH, PW, 3), dtype=np.uint8); canvas[:] = cols[n]
reg = canvas[y0:y1, x0:x1]; has = pid >= 0; reg[has] = cols[pid[has]]
Image.fromarray(canvas).save("provinces.png", optimize=True)
del canvas, reg
with open("definition.csv", "w", newline="", encoding="utf-8") as f:
    f.write("0;0;0;0;x;x;\n")
    for i in range(n):
        r, g, b = cols[i]; f.write(f"{i+1};{r};{g};{b};SK_{i+1:04d};x;\n")
    r, g, b = cols[n]; f.write(f"{n+1};{r};{g};{b};PLACEHOLDER_OCEAN;x;\n")
print(f"wrote provinces.png and definition.csv ({n+2} rows)")

# Tool assets: the region at native resolution for hit testing, plus metadata.
idmap = np.zeros((H, W, 3), dtype=np.uint8)
idmap[has] = cols[pid[has]]
Image.fromarray(idmap).save("sk_idmap.png", optimize=True)
ys, xs = np.nonzero(has); ids = pid[ys, xs]
cnt = np.bincount(ids, minlength=n)
cy_ = np.bincount(ids, weights=ys, minlength=n) / cnt
cx_ = np.bincount(ids, weights=xs, minlength=n) / cnt
meta = {
    "region": "Southern Kallonia",
    "width": int(W), "height": int(H),
    "provinceBox": {"x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1)},
    "palette": {f"{int(r)},{int(g)},{int(b)}": i + 1 for i, (r, g, b) in enumerate(cols[:n])},
    "baronies": [
        {"id": i + 1, "cx": round(float(cx_[i]), 1), "cy": round(float(cy_[i]), 1), "area": int(cnt[i])}
        for i in range(n)
    ],
}
json.dump(meta, open("sk_meta.json", "w"), separators=(",", ":"))
print(f"wrote sk_idmap.png ({W} x {H}) and sk_meta.json")
