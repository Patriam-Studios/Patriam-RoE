"""Map object locators for every province in this world.

Eight vanilla files place buildings, sieges, battles, unit stacks and
activities by province id. Vanilla's cover provinces up to 13269; placing a
holding model on province 4558 in a world that stops at 2668 dereferenced null
the moment a session started. These replace them file for file, with the same
names so they override vanilla without relying on replace_path.

Positions are the province pixel nearest its centroid, so the point is always
inside the province even when the province is concave. The vertical axis is
flipped: z is the map height minus the pixel row, verified against vanilla's
own province 1.
"""
import io, os, re, json
import numpy as np

SRC = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game\gfx\map\map_object_data"
OUT = r"C:\Users\Alexander Donnelly\Documents\Paradox Interactive\Crusader Kings III\mod\Patriam-RoE\gfx\map\map_object_data"
FILES = ["activities.txt", "building_locators.txt", "combat_locators.txt", "other_stack_locators.txt",
         "player_stack_locators.txt", "siege_locators.txt", "special_building_locators.txt", "stack_locators.txt"]

pid = np.load("full_pid.npy")
H, W = pid.shape
N = int(pid.max())
ys, xs = np.nonzero(pid > 0)
ids = pid[ys, xs]
cnt = np.bincount(ids, minlength=N + 1).astype(np.float64)
cx = np.bincount(ids, weights=xs, minlength=N + 1) / np.maximum(cnt, 1)
cy = np.bincount(ids, weights=ys, minlength=N + 1) / np.maximum(cnt, 1)
del ys, xs, ids

pos = {}
fallback = 0
for i in range(1, N + 1):
    if cnt[i] == 0:
        continue
    x, y = int(round(cx[i])), int(round(cy[i]))
    x = min(max(x, 0), W - 1); y = min(max(y, 0), H - 1)
    if pid[y, x] != i:
        fallback += 1
        found = None
        for r in (8, 32, 128, 512, 2048):
            y0, y1 = max(0, y - r), min(H, y + r + 1)
            x0, x1 = max(0, x - r), min(W, x + r + 1)
            wy, wx = np.nonzero(pid[y0:y1, x0:x1] == i)
            if len(wy):
                d = (wy + y0 - cy[i]) ** 2 + (wx + x0 - cx[i]) ** 2
                k = int(np.argmin(d)); found = (int(wx[k] + x0), int(wy[k] + y0)); break
        if found is None:
            wy, wx = np.nonzero(pid == i)
            k = int(np.argmin((wy - cy[i]) ** 2 + (wx - cx[i]) ** 2)); found = (int(wx[k]), int(wy[k]))
        x, y = found
    pos[i] = (float(x) + 0.5, float(H - y) - 0.5)
print("positions for %d provinces, %d needed a point other than the centroid" % (len(pos), fallback))

os.makedirs(OUT, exist_ok=True)
for name in FILES:
    src = io.open(os.path.join(SRC, name), encoding="utf-8-sig").read()
    head = src[:src.index("instances={")]
    body = ["\tinstances={"]
    for i in sorted(pos):
        x, z = pos[i]
        body.append("\t\t{\n\t\t\tid=%d\n\t\t\tposition={ %.6f 0.000000 %.6f }\n"
                    "\t\t\trotation={ 0.000000 0.000000 0.000000 1.000000 }\n"
                    "\t\t\tscale={ 1.000000 1.000000 1.000000 }\n\t\t}" % (i, x, z))
    body.append("\t}\n}\n")
    io.open(os.path.join(OUT, name), "w", encoding="utf-8-sig", newline="\n").write(head + "\n".join(body))
    print("wrote %-30s %d instances" % (name, len(pos)))
json.dump({str(k): v for k, v in pos.items()}, open("province_positions.json", "w"))
