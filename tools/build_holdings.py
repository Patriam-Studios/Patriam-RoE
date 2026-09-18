"""Writes province history: culture, faith, and what stands on each barony.

A county holds a seat, a town, and a temple where it has the land for them, and
the rest of its baronies are left empty for a lord to build on. Where a barony
was named for what stands on it, the name decides: a fire temple is a temple, a
market or a quay is a town, a keep or a watchtower is a castle. A city state and
a merchant monarchy seat themselves in their town rather than a castle, since
that is what their government requires.

Run with --write to put the file into the mod.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..")
WRITE = "--write" in sys.argv

names = json.load(io.open(os.path.join(HERE, "names_southern_kallonia.json"), encoding="utf-8"))
asg = json.load(io.open("D:/Patriam-CK3-map/db/assignments/southern_kallonia.json", encoding="utf-8"))
asg = asg.get("data", asg)
faction = {f["key"]: f for f in asg["factions"]}
realm_of = {int(p): faction[k] for p, k in asg["assigned"].items() if k in faction}

CULTURE = {"Thenithrian": "thenithrian", "Late Drunathaenic": "late_drunathaenic",
           "Kaegonic": "kaegonic", "Akarian": "akarian"}
TOWN_SEATED = {"city state"}  # tiers whose government seats itself in a town

TEMPLE_WORDS = ("Aethiros", "Myraethiros")
TOWN_WORDS = ("Aelithos", "Bairaen", "Kaeraenis", "Kaeraen", "Othaeris", "Imaerin")
CASTLE_WORDS = ("Kaenithros", "Gralithros", "Aelothir", "Kaenothir", "Ithros", "Aekilothir")


def named_kind(name):
    if any(w in name for w in TEMPLE_WORDS):
        return "church_holding"
    if any(w in name for w in TOWN_WORDS):
        return "city_holding"
    if any(w in name for w in CASTLE_WORDS):
        return "castle_holding"
    return None


rows, tally = {}, {}
for k in names:
    for d in k["duchies"]:
        for c in d["counties"]:
            bars = c["baronies"]
            realm = realm_of.get(bars[0]["province"], {})
            wants_town = realm.get("tier") in TOWN_SEATED or realm.get("name") == "Ketan"
            kinds = [None] * len(bars)
            kinds[0] = "castle_holding"  # vanilla seats even Venice in a castle
            for i, b in enumerate(bars[1:], start=1):
                kinds[i] = named_kind(b["name"])
            # A county wants a town and a temple if it has the land for them, and a
            # city state or a merchant realm wants its town before anything else.
            for wanted in (("city_holding", "church_holding") if not wants_town else ("city_holding", "church_holding")):
                if wanted in kinds:
                    continue
                for i in range(1, len(bars)):
                    if kinds[i] is None:
                        kinds[i] = wanted
                        break
            developed = sum(1 for x in kinds if x)
            for i in range(1, len(bars)):
                if kinds[i] and developed > 4:
                    if kinds[i] == "castle_holding":
                        kinds[i] = None
                        developed -= 1
            for b, kind in zip(bars, kinds):
                rows[b["province"]] = (CULTURE.get(realm.get("culture"), "late_drunathaenic"), kind)
                tally[kind] = tally.get(kind, 0) + 1

out = ["\ufeff############################################################",
       "# Patriam: Rise of Empires. Province history for Southern Kallonia.",
       "#",
       "# Culture follows the political map. Every province holds to Myraethanen.",
       "# A barony left empty is a slot for a lord to build on.",
       "############################################################",
       ""]
for pid in sorted(rows):
    culture, kind = rows[pid]
    out.append("%d = {" % pid)
    out.append("\tculture = %s" % culture)
    out.append("\treligion = myraethanen")
    out.append("\tholding = %s" % (kind if kind else "none"))
    out.append("}")

path = os.path.join(MOD, "history", "provinces", "00_patriam_southern_kallonia.txt")
print("holdings:", {(k or "none"): v for k, v in tally.items()})
if WRITE:
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("written", path, len(rows), "provinces")
else:
    print("dry run,", len(rows), "provinces")
