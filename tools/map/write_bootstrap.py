"""Minimum content to make the Patriam map load and be playable.

Culture and faith are vanilla keys on purpose. The aim here is to see the map,
and Patriam's own cultures and faiths are content that should not block that.
They are swapped in later by rewriting two fields in the province history.
"""
import json, re, os, collections, unicodedata

MOD = r"C:\Users\Alexander Donnelly\Documents\Paradox Interactive\Crusader Kings III\mod\Patriam-RoE"
PLACEHOLDER_CULTURE = "greek"
PLACEHOLDER_FAITH = "orthodox"
START = "6355.1.1"

def w(rel, text, bom=False):
    p = os.path.join(MOD, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n").write(text)
    return p

R = json.load(open("map_ranges.json"))
d = json.load(open("db/assignments/southern_kallonia.json"))
F = {f["key"]: f for f in d["factions"]}
assigned = d["assigned"]

lt = open("landed_titles_southern_kallonia.txt", encoding="utf-8").read()

# Which faction holds each top level title, matched by the generated key stem.
def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")

tops = re.findall(r"^([kdc]_[a-z0-9_]+) = \{", lt, re.M)
print(f"{len(tops)} top level titles")

by_faction = collections.defaultdict(list)
for pid, key in assigned.items():
    by_faction[key].append(int(pid))

# Map each faction to the top level title whose stem matches its name.
stem_to_top = {}
for t in tops:
    stem_to_top.setdefault(re.sub(r"^[kdc]_", "", t), t)
holders, chars = [], []
cid = 100000
for key, bars in sorted(by_faction.items(), key=lambda kv: -len(kv[1])):
    f = F[key]
    s = slug(f["name"])
    cand = [t for t in tops if re.sub(r"^[kdc]_", "", t).startswith(s)]
    if not cand:
        print("  no title found for", f["name"]); continue
    cid += 1
    nm = f["name"].split()[-1]
    chars.append(f'{cid} = {{\n\tname = "{nm}"\n\treligion = {PLACEHOLDER_FAITH}\n'
                 f'\tculture = {PLACEHOLDER_CULTURE}\n\t6310.1.1 = {{ birth = yes }}\n'
                 f'\t6390.1.1 = {{ death = yes }}\n}}')
    # The ruler takes the first matching title, which is the largest for the faction.
    holders.append(f'{cand[0]} = {{\n\t{START} = {{ holder = {cid} }}\n}}')

w("history/characters/00_patriam_rulers.txt", "\n".join(chars) + "\n")
w("history/titles/00_patriam_titles.txt", "\n".join(holders) + "\n")
print(f"wrote {len(chars)} rulers and {len(holders)} title holders")

# Province history for the baronies only. Sea and impassable need none.
lines = []
for i in range(1, R["sk_last"] + 1):
    lines.append(f"{i} = {{\n\tculture = {PLACEHOLDER_CULTURE}\n\treligion = {PLACEHOLDER_FAITH}\n"
                 f"\tholding = castle_holding\n}}")
w("history/provinces/00_patriam_southern_kallonia.txt", "\n".join(lines) + "\n")
print(f"wrote province history for {R['sk_last']} baronies")

w("common/defines/00_patriam_defines.txt",
  "# The Patriam canvas, and the era this campaign runs in.\n"
  "NJominiMap = {\n"
  f"\tWORLD_EXTENTS_X = {11840 - 1}\n"
  "\tWORLD_EXTENTS_Y = 50\n"
  f"\tWORLD_EXTENTS_Z = {8448 - 1}\n"
  "\tWATERLEVEL = 3\n"
  "}\n")

w("common/bookmarks/bookmarks/00_patriam.txt",
  "bm_patriam_rise_of_empires = {\n"
  f"\tstart_date = {START}\n"
  "\tis_playable = yes\n"
  "\tdefault = yes\n"
  "}\n")

w("localization/english/patriam_bookmarks_l_english.yml",
  "\ufeffl_english:\n\n"
  ' bm_patriam_rise_of_empires:0 "Rise of Empires"\n'
  ' bm_patriam_rise_of_empires_desc:0 "Southern Kallonia in 6355 after the arrival of the Drunathaen. '
  'Thenithria is one kingdom among many, and Hythaerion has not yet been born who will make it the centre of the world."\n')
print("wrote defines, bookmark and bookmark localisation")

# The descriptor has to declare which vanilla folders we are replacing outright.
REPLACE = ["map_data", "common/landed_titles", "common/province_terrain",
           "history/provinces", "history/titles", "history/characters",
           "history/wars", "common/bookmarks/bookmarks", "common/bookmarks/groups"]
for name in ("descriptor.mod", "../Patriam-RoE.mod"):
    p = os.path.join(MOD, name)
    s = open(p, encoding="utf-8-sig").read()
    s = re.sub(r'^replace_path=".*"\n?', "", s, flags=re.M)
    block = "".join(f'replace_path="{r}"\n' for r in REPLACE)
    if "path=" in s:
        s = re.sub(r'(path=".*"\n?)', block + r"\1", s, count=1)
    else:
        s = s.rstrip("\n") + "\n" + block
    open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"declared {len(REPLACE)} replace_path entries in both descriptors")
