"""Title hierarchy with a complete de jure tree.

Every county sits in a duchy, every duchy in a kingdom, every kingdom in the
empire. Bare counties and duchies at the top level are not how Crusader Kings
III lays out land, and a world containing them may never finish resolving.

De jure and de facto are different things here. A faction holds only the titles
it actually owns. The wrapper titles above it exist on the map and are held by
nobody, which is ordinary.
"""
import json, re, collections, unicodedata, random

BAR_PER_COUNTY, COUNTY_PER_DUCHY, DUCHY_PER_KINGDOM = 5, 4, 4
MIN_KINGDOM = 15
EMPIRE_KEY, EMPIRE_NAME = "e_southern_kallonia", "Southern Kallonia"

d = json.load(open("db/assignments/southern_kallonia.json"))
meta = json.load(open("sk_meta.json"))
F = {f["key"]: f for f in d["factions"]}
cent = {b["id"]: (b["cx"], b["cy"]) for b in meta["baronies"]}
by_faction = collections.defaultdict(list)
for pid, key in d["assigned"].items():
    by_faction[key].append(int(pid))


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")


def kmeans(pts, k):
    if k <= 1 or len(pts) <= 1:
        return [0] * len(pts)
    k = min(k, len(pts))
    step = max(1, len(pts) // k)
    ctr = [pts[min(i * step, len(pts) - 1)] for i in range(k)]
    lab = [0] * len(pts)
    for _ in range(30):
        moved = False
        for i, (x, y) in enumerate(pts):
            best, bd = 0, None
            for j, (cx, cy) in enumerate(ctr):
                dd = (x - cx) ** 2 + (y - cy) ** 2
                if bd is None or dd < bd:
                    bd, best = dd, j
            if lab[i] != best:
                lab[i] = best
                moved = True
        for j in range(k):
            mem = [pts[i] for i in range(len(pts)) if lab[i] == j]
            if mem:
                ctr[j] = (sum(p[0] for p in mem) / len(mem), sum(p[1] for p in mem) / len(mem))
        if not moved:
            break
    return lab


def mid(items):
    return (sum(i[0] for i in items) / len(items), sum(i[1] for i in items) / len(items))


used = set()


def uniq(base):
    k, i = base, 2
    while k in used:
        k = base + "_" + str(i)
        i += 1
    used.add(k)
    return k


def col(seed):
    r = random.Random(seed)
    return " ".join(str(r.randint(45, 210)) for _ in range(3))


loc = []
counties = []
faction_kingdoms = {}
loose_duchies = []
tiers = {}

for key, bars in sorted(by_faction.items(), key=lambda kv: -len(kv[1])):
    f = F[key]
    base = slug(f["name"])
    n = len(bars)
    t = f["tier"]
    if t == "kingdom":
        tier = "kingdom" if n >= MIN_KINGDOM else ("duchy" if n >= 10 else "county")
    elif t in ("duchy", "county"):
        tier = t
    else:
        tier = "kingdom" if n >= 40 else ("duchy" if n >= 10 else "county")
    tiers[key] = tier

    bars.sort(key=lambda p: (cent[p][1], cent[p][0]))
    lab = kmeans([cent[p] for p in bars], max(1, round(n / BAR_PER_COUNTY)))
    groups = collections.defaultdict(list)
    for i, p in enumerate(bars):
        groups[lab[i]].append(p)
    g = sorted([v for v in groups.values() if v], key=lambda s: mid([cent[p] for p in s])[1])

    mine = []
    for ci, grp in enumerate(g, 1):
        ck = uniq("c_" + base + ("" if len(g) == 1 else "_%02d" % ci))
        cname = f["name"] if len(g) == 1 else f["name"] + " " + str(ci)
        bl = []
        for bi, p in enumerate(sorted(grp, key=lambda q: (cent[q][1], cent[q][0])), 1):
            bk = uniq("b_" + base + "_%04d" % p)
            bl.append((bk, p))
            loc.append((bk, cname + " " + str(bi)))
        loc.append((ck, cname))
        rec = (ck, cname, bl, mid([cent[p] for p in grp]), key)
        counties.append(rec)
        mine.append(rec)

    if tier == "county":
        continue

    nd = 1 if tier == "duchy" else max(1, round(len(mine) / COUNTY_PER_DUCHY))
    dl = kmeans([c[3] for c in mine], nd)
    dg = collections.defaultdict(list)
    for i, c in enumerate(mine):
        dg[dl[i]].append(c)
    dg = sorted([v for v in dg.values() if v], key=lambda s: mid([c[3] for c in s])[1])
    duchies = []
    for di, grp in enumerate(dg, 1):
        dk = uniq("d_" + base + ("" if len(dg) == 1 else "_%02d" % di))
        dname = f["name"] if len(dg) == 1 else f["name"] + " " + str(di)
        loc.append((dk, dname))
        duchies.append({"key": dk, "counties": grp, "c": mid([c[3] for c in grp])})
    if tier == "kingdom":
        kk = uniq("k_" + base)
        loc.append((kk, f["name"]))
        faction_kingdoms[key] = (kk, duchies)
    else:
        loose_duchies.extend(duchies)

# Bare counties become de jure duchies, grouped by where they sit.
bare = [c for c in counties if tiers[c[4]] == "county"]
if bare:
    lab = kmeans([c[3] for c in bare], max(1, round(len(bare) / COUNTY_PER_DUCHY)))
    gg = collections.defaultdict(list)
    for i, c in enumerate(bare):
        gg[lab[i]].append(c)
    ordered = sorted([v for v in gg.values() if v], key=lambda s: mid([c[3] for c in s])[1])
    for i, grp in enumerate(ordered, 1):
        dk = uniq("d_kallonia_march_%02d" % i)
        loc.append((dk, "March of " + grp[0][1].split()[0]))
        loose_duchies.append({"key": dk, "counties": grp, "c": mid([c[3] for c in grp])})

kingdoms = [(v[0], v[1]) for v in faction_kingdoms.values()]
if loose_duchies:
    lab = kmeans([x["c"] for x in loose_duchies], max(1, round(len(loose_duchies) / DUCHY_PER_KINGDOM)))
    gg = collections.defaultdict(list)
    for i, x in enumerate(loose_duchies):
        gg[lab[i]].append(x)
    ordered = sorted([v for v in gg.values() if v], key=lambda s: mid([x["c"] for x in s])[1])
    for i, grp in enumerate(ordered, 1):
        kk = uniq("k_kallonia_%02d" % i)
        loc.append((kk, "Kallonia " + str(i)))
        kingdoms.append((kk, grp))

loc.append((EMPIRE_KEY, EMPIRE_NAME))

out = [
    "############################################################",
    "# Patriam: Rise of Empires. Southern Kallonia.",
    "# Generated by tools/map/build_titles2.py. Do not hand edit.",
    "#",
    "# Every county sits in a duchy, every duchy in a kingdom, every kingdom",
    "# in the empire. This is de jure only. Who actually holds what lives in",
    "# history/titles and is a far smaller realm than this tree.",
    "############################################################",
    "",
    EMPIRE_KEY + " = {",
    "\tcolor = { " + col(EMPIRE_KEY) + " }",
    "\tcapital = " + kingdoms[0][1][0]["counties"][0][0],
]
for kk, duchies in kingdoms:
    out.append("\t" + kk + " = {")
    out.append("\t\tcolor = { " + col(kk) + " }")
    out.append("\t\tcapital = " + duchies[0]["counties"][0][0])
    for dd in duchies:
        out.append("\t\t" + dd["key"] + " = {")
        out.append("\t\t\tcolor = { " + col(dd["key"]) + " }")
        out.append("\t\t\tcapital = " + dd["counties"][0][0])
        for ck, cname, bl, _, _ in dd["counties"]:
            out.append("\t\t\t" + ck + " = {")
            out.append("\t\t\t\tcolor = { " + col(ck) + " }")
            for bk, p in bl:
                out.append("\t\t\t\t" + bk + " = { province = " + str(p) + " }")
            out.append("\t\t\t}")
        out.append("\t\t}")
    out.append("\t}")
out.append("}")
open("landed_titles_southern_kallonia.txt", "w", encoding="utf-8-sig", newline="\n").write("\n".join(out) + "\n")

with open("patriam_titles_l_english.yml", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("﻿l_english:\n\n # Placeholder title names, generated.\n\n")
    for k, v in loc:
        fh.write(" " + k + ":0 \"" + v + "\"\n")

nd = sum(len(x) for _, x in kingdoms)
nc = sum(len(dd["counties"]) for _, x in kingdoms for dd in x)
nb = sum(len(c[2]) for _, x in kingdoms for dd in x for c in dd["counties"])
print("empire 1, kingdoms %d, duchies %d, counties %d, baronies %d" % (len(kingdoms), nd, nc, nb))
print("counties generated %d, baronies generated %d" % (len(counties), sum(len(c[2]) for c in counties)))
print("total keys %d, localised %d" % (len(used) + 1, len(loc)))
