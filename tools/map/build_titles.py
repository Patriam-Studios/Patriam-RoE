"""Turn the painted faction map into a Crusader Kings III title hierarchy.

The tool records realms, not title tiers, so every faction's baronies are
clustered into counties and those counties into duchies. Clustering is plain
Lloyd's on barony centroids, which is enough here because the geometry pass
already made the baronies compact and coastline respecting.
"""
import json, math, re, collections, unicodedata

BAR_PER_COUNTY = 5
COUNTY_PER_DUCHY = 4
MIN_KINGDOM = 15          # below this a stated kingdom is demoted and flagged

d = json.load(open("db/assignments/southern_kallonia.json"))
meta = json.load(open("sk_meta.json"))
assigned, F = d["assigned"], {f["key"]: f for f in d["factions"]}
cent = {b["id"]: (b["cx"], b["cy"]) for b in meta["baronies"]}

by_faction = collections.defaultdict(list)
for pid, key in assigned.items():
    by_faction[key].append(int(pid))

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")

def kmeans(points, k, seed=7):
    if k <= 1 or len(points) <= k:
        return list(range(len(points))) if len(points) <= k else [0] * len(points)
    pts = [cent[p] for p in points]
    step = max(1, len(pts) // k)
    ctr = [pts[min(i * step, len(pts) - 1)] for i in range(k)]
    lab = [0] * len(pts)
    for _ in range(24):
        moved = False
        for i, (x, y) in enumerate(pts):
            best, bd = 0, None
            for j, (cx, cy) in enumerate(ctr):
                dd = (x - cx) ** 2 + (y - cy) ** 2
                if bd is None or dd < bd: bd, best = dd, j
            if lab[i] != best: lab[i] = best; moved = True
        for j in range(k):
            mem = [pts[i] for i in range(len(pts)) if lab[i] == j]
            if mem: ctr[j] = (sum(p[0] for p in mem) / len(mem), sum(p[1] for p in mem) / len(mem))
        if not moved: break
    return lab

def tier_for(f, n):
    t = f["tier"]
    if t == "kingdom":  return "kingdom" if n >= MIN_KINGDOM else ("duchy" if n >= 10 else "county")
    if t in ("duchy", "county"): return t
    return "kingdom" if n >= 40 else ("duchy" if n >= 10 else "county")

def shade(hexcol, f):
    v = int(hexcol[1:], 16)
    r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
    return tuple(max(0, min(255, int(c * f))) for c in (r, g, b))

used_keys, notes = set(), []
def uniq(base):
    k, i = base, 2
    while k in used_keys:
        k = base + "_" + str(i); i += 1
    used_keys.add(k)
    return k

titles, loc = [], []
counts = collections.Counter()

for key, bars in sorted(by_faction.items(), key=lambda kv: -len(kv[1])):
    f = F[key]
    bars.sort(key=lambda p: (cent[p][1], cent[p][0]))
    n = len(bars)
    tier = tier_for(f, n)
    if tier != f["tier"]:
        notes.append(f"{f['name']}: stated {f['tier']} with {n} baronies, built as {tier}")
    base = slug(f["name"])
    col = f["colour"]

    n_county = max(1, round(n / BAR_PER_COUNTY))
    lab = kmeans(bars, n_county)
    groups = collections.defaultdict(list)
    for i, p in enumerate(bars): groups[lab[i]].append(p)
    groups = [g for g in groups.values() if g]
    groups.sort(key=lambda g: (sum(cent[p][1] for p in g) / len(g), sum(cent[p][0] for p in g) / len(g)))

    counties = []
    for ci, g in enumerate(groups, 1):
        ck = uniq("c_" + base + ("" if len(groups) == 1 else "_%02d" % ci))
        cname = f["name"] if len(groups) == 1 else f"{f['name']} {ci}"
        bl = []
        for bi, p in enumerate(sorted(g, key=lambda p: (cent[p][1], cent[p][0])), 1):
            bk = uniq("b_" + base + "_%04d" % p)
            bl.append((bk, p))
            loc.append((bk, f"{cname} {bi}"))
        counties.append((ck, cname, bl, (sum(cent[p][0] for p in g) / len(g), sum(cent[p][1] for p in g) / len(g))))
        loc.append((ck, cname))
        counts["county"] += 1; counts["barony"] += len(bl)

    def county_block(ck, cname, bl, depth):
        t = "\t" * depth
        s = [f"{t}{ck} = {{", f"{t}\tcolor = {{ {' '.join(map(str, shade(col, 1.1)))} }}"]
        for bk, p in bl:
            s.append(f"{t}\t{bk} = {{ province = {p} }}")
        s.append(f"{t}}}")
        return "\n".join(s)

    if tier == "county":
        for ck, cname, bl, _ in counties:
            titles.append(county_block(ck, cname, bl, 0))
        continue

    if tier == "duchy":
        dk = uniq("d_" + base)
        loc.append((dk, f["name"]))
        counts["duchy"] += 1
        body = [f"{dk} = {{", f"\tcolor = {{ {' '.join(map(str, shade(col, 1.0)))} }}",
                f"\tcapital = {counties[0][0]}"]
        for ck, cname, bl, _ in counties:
            body.append(county_block(ck, cname, bl, 1))
        body.append("}")
        titles.append("\n".join(body))
        continue

    n_duchy = max(1, round(len(counties) / COUNTY_PER_DUCHY))
    cpts = [c[3] for c in counties]
    class P: pass
    idx = list(range(len(counties)))
    saved = dict(cent)
    for i, c in enumerate(counties): cent[-(i + 1)] = c[3]
    dlab = kmeans([-(i + 1) for i in idx], n_duchy)
    cent.clear(); cent.update(saved)
    dgroups = collections.defaultdict(list)
    for i, c in enumerate(counties): dgroups[dlab[i]].append(c)
    dgroups = [g for g in dgroups.values() if g]
    dgroups.sort(key=lambda g: sum(c[3][1] for c in g) / len(g))

    kk = uniq("k_" + base)
    loc.append((kk, f["name"]))
    counts["kingdom"] += 1
    body = [f"{kk} = {{", f"\tcolor = {{ {' '.join(map(str, shade(col, 1.0)))} }}"]
    first_county = None
    dblocks = []
    for di, g in enumerate(dgroups, 1):
        dk = uniq("d_" + base + ("" if len(dgroups) == 1 else "_%02d" % di))
        dname = f["name"] if len(dgroups) == 1 else f"{f['name']} {di}"
        loc.append((dk, dname))
        counts["duchy"] += 1
        if first_county is None: first_county = g[0][0]
        b = [f"\t{dk} = {{", f"\t\tcolor = {{ {' '.join(map(str, shade(col, 0.9)))} }}",
             f"\t\tcapital = {g[0][0]}"]
        for ck, cname, bl, _ in g:
            b.append(county_block(ck, cname, bl, 2))
        b.append("\t}")
        dblocks.append("\n".join(b))
    body.insert(2, f"\tcapital = {first_county}")
    body.extend(dblocks); body.append("}")
    titles.append("\n".join(body))

header = ("############################################################\n"
          "# Patriam: Rise of Empires\n"
          "# Southern Kallonia, generated from the holdings tool.\n"
          "#\n"
          "# Do not hand edit. Regenerate with tools/map/build_titles.py after\n"
          "# changing the assignment, or the two will drift apart.\n"
          "#\n"
          "# Names in the localisation file are placeholders built from the\n"
          "# faction name. They are meant to be replaced.\n"
          "############################################################\n\n")
open("landed_titles_southern_kallonia.txt", "w", encoding="utf-8").write(header + "\n\n".join(titles) + "\n")

with open("patriam_titles_l_english.yml", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("﻿l_english:\n\n")
    fh.write(" # Placeholder title names for Southern Kallonia, generated.\n")
    fh.write(" # Patriamic English. No dash punctuation.\n\n")
    for k, v in loc:
        fh.write(f" {k}:0 \"{v}\"\n")

print("titles built")
for t in ("kingdom", "duchy", "county", "barony"):
    print(f"  {t:<8} {counts[t]:>5}")
print(f"  total keys {len(used_keys)}")
if notes:
    print("\ntier adjustments:")
    for x in notes: print("  " + x)
