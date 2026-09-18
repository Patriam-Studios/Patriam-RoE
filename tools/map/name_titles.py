"""Names the whole of Southern Kallonia in Myrenvaldi and writes the localisation.

The land decides each name: terrain from the mod's own province terrain file, and
whether the barony touches the sea, read from the province raster. Realm names given in the holdings tool are kept, and each realm's capital county
and capital holding carry the realm's name. Ketan's island is left in its own
name and waits on a Ketanite tongue.

Run with --write to update the localisation file. Without it, nothing is written.
"""
import importlib.util
import io
import json
import os
import random
import re
import sys

import numpy as np

MOD = "C:/Users/Alexander Donnelly/Documents/Paradox Interactive/Crusader Kings III/mod/Patriam-RoE"
LORE = "D:/Main/Patriam/Lore Documents"
HERE = os.path.dirname(os.path.abspath(__file__))
WRITE = "--write" in sys.argv

spec = importlib.util.spec_from_file_location("chk", LORE + "/myrenvaldi_check.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)
import lex_stock as S  # the word pools, every one of them a lexicon entry

# The whole title tree
src = io.open(MOD + "/common/landed_titles/01_patriam_southern_kallonia.txt", encoding="utf-8-sig").read()
empire = None
kingdoms = []
for line in src.splitlines():
    m = re.match(r"(\t*)(e|k|d|c|b)_([a-z0-9_]+) = \{(?: province = (\d+) \})?", line)
    if not m:
        continue
    tabs, tier, slug, prov = len(m.group(1)), m.group(2), m.group(3), m.group(4)
    key = "%s_%s" % (tier, slug)
    if tier == "e":
        empire = {"key": key, "kingdoms": kingdoms}
    elif tier == "k":
        kingdoms.append({"key": key, "duchies": []})
    elif tier == "d":
        kingdoms[-1]["duchies"].append({"key": key, "counties": []})
    elif tier == "c":
        kingdoms[-1]["duchies"][-1]["counties"].append({"key": key, "baronies": []})
    else:
        kingdoms[-1]["duchies"][-1]["counties"][-1]["baronies"].append({"key": key, "province": int(prov)})

baronies = [b for k in kingdoms for d in k["duchies"] for c in d["counties"] for b in c["baronies"]]
print("tree: %d kingdoms, %d duchies, %d counties, %d baronies"
      % (len(kingdoms), sum(len(k["duchies"]) for k in kingdoms),
         sum(len(c) for k in kingdoms for d in k["duchies"] for c in [d["counties"]]),
         len(baronies)))

# Who holds what, from the holdings tool
asg = json.load(io.open("D:/Patriam-CK3-map/db/assignments/southern_kallonia.json", encoding="utf-8"))
asg = asg.get("data", asg)
faction = {f["key"]: f for f in asg["factions"]}
holder = {int(p): faction[k]["name"] for p, k in asg["assigned"].items() if k in faction}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


realm_of_slug = {slugify(f["name"]): f for f in asg["factions"]}

# Terrain, area, and which baronies touch the sea
terrain = {}
for line in io.open(MOD + "/common/province_terrain/00_province_terrain.txt", encoding="utf-8-sig"):
    m = re.match(r"(\d+)=([a-z_]+)", line.strip())
    if m:
        terrain[int(m.group(1))] = m.group(2)

SEA = 1737
pid = np.load("D:/Patriam-CK3-map/full_pid.npy", mmap_mode="r")
coastal, area = set(), np.zeros(SEA, dtype=np.int64)
for y0 in range(0, pid.shape[0], 1024):
    block = np.asarray(pid[y0:y0 + 1025])
    area += np.bincount(block[:-1].ravel(), minlength=SEA)[:SEA]
    for a, b in ((block[:-1], block[1:]), (block[:, :-1], block[:, 1:])):
        for x, y in ((a, b), (b, a)):
            m = (x > 0) & (x < SEA) & (y >= SEA)
            if m.any():
                coastal.update(int(v) for v in np.unique(x[m]))
print("coastal baronies: %d of %d" % (len([p for p in coastal if p <= 943]), len(baronies)))

rng = random.Random(6355)
used = set()
heads_used = {}


def syllables(word):
    return len(re.findall("[aeiouy]+", word.lower()))


def legal(name):
    return all(not chk.check(part.lower()) for part in name.split(" "))


def named(name):
    return all(p[0].lower() not in "rlsfy" for p in name.split(" "))


def short(name, cap=4):
    return all(syllables(part) <= cap for part in name.split(" "))


def gen(word):
    if word.endswith("s"):
        return word[:-1] + "tsi"
    if word[-1] in "aeiouy":
        return word + "thi"
    return word + "i"


def fuse(a, b):
    joined = a + b
    if not chk.check(joined):
        return joined
    linked = a + "a" + b if a[-1] not in "aeiouy" else a + b
    if not chk.check(linked):
        return linked
    return a + " " + b[0].upper() + b[1:]


def pick(pool):
    least = min(heads_used.get(h[0], 0) for h in pool)
    choice = rng.choice([h for h in pool if heads_used.get(h[0], 0) == least])
    heads_used[choice[0]] = heads_used.get(choice[0], 0) + 1
    return choice


def kin(a, b):
    return a[:4] == b[:4] or a.startswith(b[:5]) or b.startswith(a[:5])


def heads_for(province):
    t = terrain.get(province, "plains")
    heads = list(S.HEADS.get(t, S.HEADS["plains"]))
    if province in coastal:
        heads = S.COAST + heads
    return heads


def coin(province, grand=False):
    heads = heads_for(province)
    for attempt in range(200):
        head, head_sense = pick(heads)
        roll = rng.random()
        if grand and roll < 0.5:
            word, word_sense = pick(S.SETTLEMENT)
            if kin(head, word):
                continue
            name, meaning = gen(head) + " " + word, "the " + word_sense + " of the " + head_sense
        elif grand and roll < 0.62:
            name, meaning = "ae" + head, "the great " + head_sense
        elif roll < 0.38:
            word, word_sense = pick(S.SETTLEMENT)
            if kin(head, word):
                continue
            name, meaning = gen(head) + " " + word, "the " + word_sense + " of the " + head_sense
        elif roll < 0.5:
            word, word_sense = pick(S.SETTLEMENT)
            other, other_sense = pick(S.SETTLEMENT)
            if kin(word, other):
                continue
            name, meaning = gen(word) + " " + other, "the " + other_sense + " of the " + word_sense
        elif roll < 0.6:
            word, word_sense = pick(S.SETTLEMENT)
            qual, qual_sense = pick(S.QUALITIES)
            if kin(word, qual):
                continue
            name, meaning = fuse(word, qual), "the " + qual_sense + " " + word_sense
        elif roll < 0.68:
            name, meaning = head + "ii", "the folk of the " + head_sense
        elif roll < 0.76:
            name, meaning = head, "the " + head_sense
        else:
            qual, qual_sense = pick(S.QUALITIES)
            if kin(head, qual):
                continue
            name, meaning = fuse(head, qual), "the " + qual_sense + " " + head_sense
        name = " ".join(w[0].upper() + w[1:] for w in name.split(" "))
        cap = 4 if attempt < 120 else 5
        if legal(name) and named(name) and short(name, cap) and name.lower() not in used:
            used.add(name.lower())
            return name, meaning
    raise RuntimeError("no name for province %d" % province)


def region_name(provinces, forbidden=(), fallback="plains"):
    """A land name for a duchy or a kingdom, on a root nothing near it uses."""
    terrains = [terrain.get(p, "plains") for p in provinces] or [fallback]
    common = max(set(terrains), key=terrains.count)
    pool = S.HEADS.get(common, S.HEADS["plains"]) + [h for hs in S.HEADS.values() for h in hs] + S.COAST
    for head, head_sense in pool:
        if head in forbidden:
            continue
        for suffix in ("ia", "onia", "aenia"):
            cand = (head + suffix).capitalize()
            if (not chk.check(cand.lower()) and named(cand) and syllables(cand) <= 4
                    and cand.lower() not in used and cand.lower() != "kallonia"):
                used.add(cand.lower())
                return cand, "the land of the " + head_sense, head
    raise RuntimeError("no region name")


def realm_display(name):
    return re.sub(r"^(Kingdom|Empire|Duchy|County) of ", "", name)


# Names. The realm names from the holdings tool are kept; the rest are coined.
loc, report = {}, []
kingdom_roots = set()
loc[empire["key"]] = "Southern Kallonia"
KETAN = [f for f in asg["factions"] if f["name"] == "Ketan"][0]["name"]
ketan_provinces = {p for p, n in holder.items() if n == KETAN}

for k in kingdoms:
    kprov = [b["province"] for d in k["duchies"] for c in d["counties"] for b in c["baronies"]]
    kslug = k["key"][2:]
    realm = realm_of_slug.get(kslug)
    if realm:
        kname, kmeaning = realm_display(realm["name"]), "the realm given in the holdings tool"
        used.add(kname.lower())
    else:
        kname, kmeaning, kroot = region_name(kprov, kingdom_roots)
        kingdom_roots.add(kroot)
    loc[k["key"]] = kname
    pending_seat = kname if realm else None
    krep = {"key": k["key"], "name": kname, "meaning": kmeaning, "duchies": []}
    report.append(krep)
    heads_used.clear()
    duchy_roots = set()
    for di, d in enumerate(k["duchies"]):
        dprov = [b["province"] for c in d["counties"] for b in c["baronies"]]
        dslug = re.sub(r"_\d+$", "", d["key"][2:])
        drealm = realm_of_slug.get(dslug)
        if drealm and realm_display(drealm["name"]).lower() not in used:
            dname, dmeaning = realm_display(drealm["name"]), "the realm given in the holdings tool"
            used.add(dname.lower())
            if pending_seat is None:
                pending_seat = dname
        else:
            dname, dmeaning, droot = region_name(dprov, duchy_roots | kingdom_roots)
            duchy_roots.add(droot)
        loc[d["key"]] = dname
        drep = {"key": d["key"], "name": dname, "meaning": dmeaning, "counties": []}
        krep["duchies"].append(drep)
        for ci, c in enumerate(d["counties"]):
            cslug = re.sub(r"_\d+$", "", c["key"][2:])
            crealm = realm_of_slug.get(cslug)
            seat = crealm and realm_display(crealm["name"]).lower() not in used
            for bi, b in enumerate(c["baronies"]):
                if b["province"] in ketan_provinces:
                    name, meaning = "Ketan", "held by Ketan, and left for a Ketanite tongue"
                    if name.lower() in used:
                        name = "Ketan"
                    used.add(name.lower())
                elif bi == 0 and pending_seat and ci == 0:
                    name, meaning = pending_seat, "the seat of the realm, and the city that names it"
                    pending_seat = None
                elif bi == 0 and seat:
                    name = realm_display(crealm["name"])
                    meaning = "the seat of the realm given in the holdings tool"
                    used.add(name.lower())
                    seat = False
                else:
                    name, meaning = coin(b["province"], grand=(bi == 0))
                loc[b["key"]] = name
                b["name"], b["meaning"] = name, meaning
            cname = c["baronies"][0]["name"]
            loc[c["key"]] = cname
            drep["counties"].append({"key": c["key"], "name": cname,
                                     "meaning": c["baronies"][0]["meaning"],
                                     "baronies": [{"key": b["key"], "province": b["province"], "name": b["name"],
                                                   "meaning": b["meaning"], "terrain": terrain.get(b["province"], "plains"),
                                                   "coastal": b["province"] in coastal} for b in c["baronies"]]})

print("titles named: %d (%d unique names)" % (len(loc), len(set(loc.values()))))
json.dump(report, io.open(os.path.join(HERE, "names_southern_kallonia.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

if WRITE:
    path = MOD + "/localization/english/patriam_titles_l_english.yml"
    out = ["\ufeffl_english:", "", " # Title names in Myrenvaldi, built from the land each title holds.", ""]
    for k in report:
        out.append(" %s:0 \"%s\"" % (k["key"], k["name"]))
        for d in k["duchies"]:
            out.append(" %s:0 \"%s\"" % (d["key"], d["name"]))
            for c in d["counties"]:
                for b in c["baronies"]:
                    out.append(" %s:0 \"%s\"" % (b["key"], b["name"]))
                out.append(" %s:0 \"%s\"" % (c["key"], c["name"]))
        out.append("")
    out.insert(4, " %s:0 \"%s\"" % (empire["key"], loc[empire["key"]]))
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("written", path, os.path.getsize(path), "bytes")
else:
    print("dry run, nothing written")
