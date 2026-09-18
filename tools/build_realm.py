"""Builds the name lists, dynasties, rulers, title history, bookmark and localisation.

Names come from the Myrenvaldi rules: a man's name closes on a consonant, a
woman's on a vowel, nothing runs past three syllables, and every one is checked
against the tongue before it is written. The canon names are seeded first so
that the stock a player meets is the stock Alexander gave.

Run with --write to put the files into the mod.
"""
import importlib.util
import io
import json
import os
import random
import re
import sys

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LORE = "D:/Main/Patriam/Lore Documents"
HERE = os.path.dirname(os.path.abspath(__file__))
WRITE = "--write" in sys.argv

spec = importlib.util.spec_from_file_location("chk", LORE + "/myrenvaldi_check.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

# Canon first. Persons only: places and houses are left out.
CANON_MEN = ["Hythaerion", "Kasparion", "Anathaen", "Jaenaryn", "Taengyn", "Araelon", "Aetos", "Tharaen", "Aerys",
             "Aerif", "Hyrion", "Kyraen", "Araeon", "Ithion", "Amnaeron", "Thraenon", "Myliros",
             "Araethos", "Irithos", "Araelos", "Namaeron", "Bairaes", "Hylaearon", "Imaeros",
             "Kalaegran", "Kaenor", "Myrkaenos", "Gaenthos", "Aelothos", "Aegos"]
CANON_WOMEN = ["Myrene", "Vaena", "Hynera", "Druthara", "Araela"]

ONSETS = ["hy", "myr", "kal", "kae", "ith", "aeth", "thaen", "gral", "ara", "thaer", "aekil", "imaer",
          "mnaer", "oph", "thol", "dae", "kraeth", "lariam", "atsior", "drath", "kord", "naeth",
          "hyl", "krath", "gaen", "iraen", "onar", "thur", "vald", "myraeth", "aelir", "taen"]
MIDDLES = ["", "ae", "i", "ae", "o", "aer", "ith", "an", "ael", "ir", "aen"]
MALE_END = ["on", "os", "or", "yn", "en", "ys", "aes", "aen", "in", "ir"]
FEMALE_END = ["a", "e", "era", "ara", "ena", "aela", "ia", "aena"]

rng = random.Random(6363)


def syllables(w):
    return len(re.findall("[aeiouy]+", w.lower()))


def ok_name(w):
    return (not chk.check(w.lower()) and w[0].lower() not in "rlsfy"
            and 2 <= syllables(w) <= 3)


def build(endings, want, seed):
    out, seen = list(seed), {s.lower() for s in seed}
    guard = 0
    while len(out) < want and guard < 20000:
        guard += 1
        w = rng.choice(ONSETS) + rng.choice(MIDDLES) + rng.choice(endings)
        w = w[0].upper() + w[1:]
        if ok_name(w) and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out


men = build(MALE_END, 70, CANON_MEN)
women = build(FEMALE_END, 45, CANON_WOMEN)
houses = []
seen_h = set()
while len(houses) < 60:
    w = (rng.choice(ONSETS) + rng.choice(["", "ae", "i", "an", "aer"]) + "ii")
    w = w[0].upper() + w[1:]
    if not chk.check(w.lower()) and w[0].lower() not in "rlsfy" and 2 <= syllables(w) <= 4 and w.lower() not in seen_h:
        seen_h.add(w.lower())
        houses.append(w)
print("names: %d men, %d women, %d houses" % (len(men), len(women), len(houses)))

# Provisional, and marked as such in the file: neither tongue exists yet.
KAEGONIC_MEN = ["Oustarn", "Irajaen", "Karjk", "Oegith", "Kyryng", "Aeklan", "Hajaen", "Raegon", "Raehun", "Arkaeon"]
KAEGONIC_WOMEN = ["Kaegona", "Oegitha", "Raeguna", "Irajaena", "Kyrynga"]
AKARIAN_MEN = ["Antaar", "Akros", "Kaaron", "Akarion", "Antaros", "Kaaristo", "Akrastan", "Antakion"]
AKARIAN_WOMEN = ["Akaria", "Kaarona", "Antaara", "Akrisa", "Antalia"]

# The realms, from the holdings tool, and the titles they hold
asg = json.load(io.open("D:/Patriam-CK3-map/db/assignments/southern_kallonia.json", encoding="utf-8"))
asg = asg.get("data", asg)
factions = asg["factions"]
CULTURE = {"Thenithrian": "thenithrian", "Late Drunathaenic": "late_drunathaenic",
           "Kaegonic": "kaegonic", "Akarian": "akarian"}

src = io.open(MOD + "/common/landed_titles/01_patriam_southern_kallonia.txt", encoding="utf-8-sig").read()
titles = re.findall(r"^\t*([ekdcb]_[a-z0-9_]+) = \{", src, re.M)
RANK = {"k": 3, "d": 2, "c": 1}

# Every kingdom and duchy names its capital county in the de jure tree. A ruler
# given only a kingdom or a duchy holds no ground, which the engine complains
# about and then papers over with a county of its own choosing, so the capital
# is handed over explicitly instead.
CAPITAL = {}
_stack = []
for _line in src.splitlines():
    _depth = len(_line) - len(_line.lstrip("\t"))
    _open = re.match(r"^\t*([ekdcb]_[a-z0-9_]+) = \{", _line)
    if _open:
        del _stack[_depth:]
        _stack.append(_open.group(1))
        continue
    _cap = re.match(r"^\t*capital = (c_[a-z0-9_]+)", _line)
    if _cap and _stack:
        CAPITAL.setdefault(_stack[min(_depth - 1, len(_stack) - 1)], _cap.group(1))


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# What rank of title each painted tier wants. Houses sit just under duchies, so
# that where two realms carry the same name the duchy takes the duchy title and
# the house takes a county under it rather than the other way about.
WANTS = {"kingdom": 3.0, "duchy": 2.5, "house": 2.0, "county": 1.2, "city state": 1.0}


def candidates(slug):
    """Every title whose key belongs to this realm, best fit first."""
    out = []
    for t in titles:
        tier, key = t[0], t[2:]
        if tier not in RANK:
            continue
        if key == slug or re.match(r"^%s_\d+$" % re.escape(slug), key):
            out.append(t)
    return out


def claim_titles(realms):
    """One title per realm, claimed in order of the rank each realm wants.

    Two realms painted with the same name would otherwise land on the same
    title and the second would quietly overwrite the first.
    """
    claimed, taken = {}, set()
    order = sorted(range(len(realms)), key=lambda i: -WANTS.get(realms[i]["tier"], 1.0))
    for i in order:
        f = realms[i]
        want = WANTS.get(f["tier"], 1.0)
        best = sorted(candidates(slugify(f["name"])),
                      key=lambda t: (abs(RANK[t[0]] - want), -RANK[t[0]], t))
        for t in best:
            if t not in taken:
                taken.add(t)
                claimed[i] = t
                break
        else:
            print("  no title found for realm", f["name"])
    return claimed


names_used = set()
pool = {"thenithrian": list(men), "late_drunathaenic": list(men), "kaegonic": list(KAEGONIC_MEN),
        "akarian": list(AKARIAN_MEN)}
house_pool = list(houses)
characters, holders, loc_dyn = [], [], []

# Hythaerion and his father
HY_ID, FATHER_ID = 6001, 6002
characters.append({
    "id": HY_ID, "name": "Hythaerion", "dynasty": "dynasty_kasparidii", "culture": "thenithrian",
    "father": FATHER_ID, "birth": "6338.1.1", "death": "6514.1.1",
    "traits": ["brave", "ambitious", "education_martial_4"],
    "note": "Hythaerion the Conqueror. Seventeen at the start, and he dies in 6514 as canon.",
})
characters.append({
    "id": FATHER_ID, "name": "Kasparion", "dynasty": "dynasty_kasparidii", "culture": "thenithrian",
    "birth": "6262.1.1", "death": "6354.12.31",
    "note": "Hythaerion's father, who holds Thenithria until the last days of 6354.",
})
names_used.update({"hythaerion", "kasparion"})

next_id = 6100
CLAIMED = claim_titles(factions)
for index, f in enumerate(factions):
    culture = CULTURE.get(f["culture"], "late_drunathaenic")
    title = CLAIMED.get(index)
    if title is None:
        continue
    if title == "k_kingdom_of_thenithria":
        holders.append((title, "6300.1.1", FATHER_ID, "6354.12.31", HY_ID))
        seat = CAPITAL.get(title)
        if seat:
            holders.append((seat, "6300.1.1", FATHER_ID, "6354.12.31", HY_ID))
        continue
    name = None
    for cand in pool[culture]:
        if cand.lower() not in names_used:
            name = cand
            break
    names_used.add(name.lower())
    house = house_pool.pop(0)
    dyn = "dynasty_" + house.lower()
    loc_dyn.append((house, culture))
    government = None
    if f["name"] == "Ketan":
        government = "merchant_monarchy_government"
    elif f["tier"] == "house":
        government = "house_government"
    elif f["tier"] == "city state":
        government = "city_state_government"
    birth = 6355 - rng.randint(26, 58)
    characters.append({
        "id": next_id, "name": name, "dynasty": dyn, "culture": culture,
        "birth": "%d.%d.%d" % (birth, rng.randint(1, 12), rng.randint(1, 28)),
        "government": government,
        "note": "Holds %s, the realm painted as %s." % (title, f["name"]),
    })
    holders.append((title, "6355.1.1", next_id, None, None, government))
    if title[0] != "c":
        seat = CAPITAL.get(title)
        if seat:
            holders.append((seat, "6355.1.1", next_id, None, None, None))
        else:
            print("  no capital county for", title)
    next_id += 1

print("characters: %d, titles held: %d" % (len(characters), len(holders)))

# The files
def name_list(key, male, female, dynasties, note):
    out = ["%s = {" % key, "\t# %s" % note, "", "\tmale_names = {"]
    out += ["\t\t" + " ".join(male[i:i + 8]) for i in range(0, len(male), 8)]
    out += ["\t}", "", "\tfemale_names = {"]
    out += ["\t\t" + " ".join(female[i:i + 8]) for i in range(0, len(female), 8)]
    out += ["\t}", "", "\tdynasty_names = {"]
    out += ["\t\t\"dynn_patriam_%s\"" % d for d in dynasties]
    out += ["\t}", "", "\tfather_name_chance = 20", "\tmother_name_chance = 5",
            "\tpat_grf_name_chance = 30", "\tmat_grf_name_chance = 20",
            "\tpat_grm_name_chance = 20", "\tmat_grm_name_chance = 30", "}", ""]
    return "\n".join(out)


name_lists = "\n".join([
    "############################################################",
    "# Patriam: Rise of Empires. Name lists.",
    "#",
    "# The Myrenvaldi names follow the rules of the tongue: a man's name closes",
    "# on a consonant, a woman's on a vowel, and none runs past three syllables.",
    "# Every canon name is seeded first. The Kaegonic and Akarian lists are",
    "# PROVISIONAL and thin, since neither tongue has been built yet.",
    "############################################################",
    "",
    name_list("name_list_thenithrian", men, women, houses[:40],
              "Thenithria itself. Myrenvaldi, the purest surviving Drunathaen."),
    name_list("name_list_late_drunathaenic", men[6:] + men[:6], women[3:] + women[:3], houses[20:],
              "The older Drunathaen realms, who speak the same tongue."),
    name_list("name_list_kaegonic", KAEGONIC_MEN, KAEGONIC_WOMEN,
              ["Kaegonhar", "Oustarnii", "Arkaeonii"],
              "Provisional. Built from canon Kaegonic words until the tongue exists."),
    name_list("name_list_akarian", AKARIAN_MEN, AKARIAN_WOMEN,
              ["Akarii", "Kaaronii", "Antaarii"],
              "Provisional. Built from canon Akarian words until the tongue exists."),
])

dyn_lines = ["############################################################",
             "# Patriam: Rise of Empires. Dynasties.",
             "############################################################",
             "",
             "dynasty_kasparidii = {",
             "\tname = \"dynn_patriam_Kasparidii\"",
             "\tculture = \"thenithrian\"",
             "}",
             ""]
for house, culture in loc_dyn:
    dyn_lines += ["dynasty_%s = {" % house.lower(), "\tname = \"dynn_patriam_%s\"" % house,
                  "\tculture = \"%s\"" % culture, "}", ""]
dynasties_file = "\n".join(dyn_lines)

char_lines = ["############################################################",
              "# Patriam: Rise of Empires. The rulers of Southern Kallonia in 6355.",
              "#",
              "# Hythaerion holds the Kingdom of Thenithria, inherited from his",
              "# father in the last days of 6354. Every other realm painted on the map",
              "# has one ruler of its own culture and faith.",
              "############################################################",
              ""]
for c in characters:
    char_lines.append("%d = { # %s" % (c["id"], c["note"]))
    char_lines.append("\tname = \"%s\"" % c["name"])
    char_lines.append("\tdynasty = %s" % c["dynasty"])
    char_lines.append("\treligion = myraethanen")
    char_lines.append("\tculture = %s" % c["culture"])
    if c.get("father"):
        char_lines.append("\tfather = %d" % c["father"])
    for t in c.get("traits", []):
        char_lines.append("\ttrait = %s" % t)
    char_lines.append("\t%s = { birth = yes }" % c["birth"])
    if c.get("death"):
        char_lines.append("\t%s = { death = yes }" % c["death"])
    char_lines.append("}")
characters_file = "\n".join(char_lines) + "\n"

title_lines = ["############################################################",
               "# Patriam: Rise of Empires. Who holds what in 6355.",
               "############################################################",
               ""]
for entry in holders:
    title, date, who, date2, who2 = entry[:5]
    government = entry[5] if len(entry) > 5 else None
    title_lines.append("%s = {" % title)
    if government:
        # The government is set here rather than on the character, since the
        # engine wants the title in hand before the form of rule changes. This
        # is the shape vanilla uses for its own clan and feudal conversions.
        title_lines.append("\t%s = {" % date)
        title_lines.append("\t\tholder = %d" % who)
        title_lines.append("\t\teffect = {")
        title_lines.append("\t\t\tif = {")
        title_lines.append("\t\t\t\tlimit = { exists = holder }")
        title_lines.append("\t\t\t\tholder = { change_government = %s }" % government)
        title_lines.append("\t\t\t}")
        title_lines.append("\t\t}")
        title_lines.append("\t}")
    else:
        title_lines.append("\t%s = { holder = %d }" % (date, who))
    if date2:
        title_lines.append("\t%s = { holder = %d }" % (date2, who2))
    title_lines.append("}")
titles_file = "\n".join(title_lines) + "\n"

bookmark = """﻿bm_patriam_rise_of_empires = {
	start_date = 6355.1.1
	is_playable = yes
	group = bm_group_patriam

	weight = { value = 100 }

	character = {
		name = "bookmark_patriam_hythaerion"
		dynasty = dynasty_kasparidii
		dynasty_splendor_level = 2
		type = male
		birth = 6338.1.1
		title = k_kingdom_of_thenithria
		government = feudal_government
		culture = thenithrian
		religion = myraethanen
		difficulty = "BOOKMARK_CHARACTER_DIFFICULTY_MEDIUM"
		history_id = 6001
		position = { 400 400 }
		animation = personality_bold
	}
}
"""

# Localisation
loc = ["\ufeffl_english:", "", " # Cultures, pillars, the faith, and the houses.", ""]
CULTURE_LOC = [("thenithrian", "Thenithrian", "Thenithrians"),
               ("late_drunathaenic", "Late Drunathaenic", "Late Drunathaen"),
               ("kaegonic", "Kaegonic", "Kaegons"),
               ("akarian", "Akarian", "Akarians")]
for key, name, plural in CULTURE_LOC:
    loc.append(" %s:0 \"%s\"" % (key, name))
    loc.append(" %s_collective_noun:0 \"%s\"" % (key, plural))
    loc.append(" name_list_%s:0 \"%s\"" % (key, name))
    loc.append(" %s_prefix:0 \"%s\"" % (key, name))
loc.append("")
# The engine looks a pillar up as <key>_name, and a heritage also wants the
# noun for the people who carry it.
for key, name, plural in [("heritage_drunathaen", "Drunathaen", "Drunathaens"),
                          ("heritage_kaegonic", "Kaegonic", "Kaegons"),
                          ("heritage_senkarian", "Senkarian", "Senkarians"),
                          ("language_myrenvaldi", "Myrenvaldi", None),
                          ("language_kaegonic", "Kaegonic", None),
                          ("language_akarian", "Akarian", None)]:
    loc.append(" %s_name:0 \"%s\"" % (key, name))
    if plural:
        loc.append(" %s_collective_noun:0 \"%s\"" % (key, plural))
loc.append("")
loc += [" # The ranks of Thenithria, in its own tongue.",
        " baron_feudal_male_thenithrian:0 \"Kaeran\"",
        " baron_feudal_female_thenithrian:0 \"Kaerana\"",
        " count_feudal_male_thenithrian:0 \"Ephotsan\"",
        " count_feudal_female_thenithrian:0 \"Ephotsana\"",
        " duke_feudal_male_thenithrian:0 \"Hylos\"",
        " duke_feudal_female_thenithrian:0 \"Hylosa\"",
        " king_feudal_male_thenithrian:0 \"Taenor\"",
        " king_feudal_female_thenithrian:0 \"Taenora\"",
        " emperor_feudal_male_thenithrian:0 \"Aetaenor\"",
        " emperor_feudal_female_thenithrian:0 \"Aetaenora\"",
        ""]
loc += [" # Myraethanen, the host of those who keep the source fire.",
        " myraethanen_religion:0 \"Myraethanen\"",
        " myraethanen_religion_adj:0 \"Myraethanen\"",
        " myraethanen_religion_adherent:0 \"Keeper of the Flame\"",
        " myraethanen_religion_adherent_plural:0 \"Keepers of the Flame\"",
        " myraethanen:0 \"Myraethanen\"",
        " myraethanen_adj:0 \"Myraethanen\"",
        " myraethanen_adherent:0 \"Keeper of the Flame\"",
        " myraethanen_adherent_plural:0 \"Keepers of the Flame\"",
        " myraethanen_thaeraethos:0 \"Thaeraethos\"",
        " myraethanen_thaeraethos_2:0 \"the Sun and the Flame\"",
        " myraethanen_thaeraethos_possessive:0 \"Thaeraethos'\"",
        " myraethanen_source_fire:0 \"the Source Fire\"",
        " myraethanen_source_fire_possessive:0 \"the Source Fire's\"",
        " myraethanen_hearth_flame:0 \"the Hearth Flame\"",
        " myraethanen_hearth_flame_possessive:0 \"the Hearth Flame's\"",
        " myraethanen_the_dark:0 \"the Dark\"",
        " myraethanen_the_dark_possessive:0 \"the Dark's\"",
        " myraethanen_the_cold:0 \"the Cold\"",
        " myraethanen_aethiros:0 \"fire temple\"",
        " myraethanen_aethiros_2:0 \"aethiros\"",
        " myraethanen_aethiros_3:0 \"house of the flame\"",
        " myraethanen_aethiros_plural:0 \"fire temples\"",
        " myraethanen_symbol:0 \"Source Flame\"",
        " myraethanen_symbol_2:0 \"the Flame\"",
        " myraethanen_symbol_3:0 \"the Rising Sun\"",
        " myraethanen_text:0 \"the Aethiraen\"",
        " myraethanen_text_2:0 \"the Book of the Flame\"",
        " myraethanen_text_3:0 \"the Rites of Fire\"",
        " myraethanen_religious_head:0 \"Hylaethan\"",
        " myraethanen_religious_head_title:0 \"High Priest of the Flame\"",
        " myraethanen_devotee:0 \"faithful\"",
        " myraethanen_devotee_plural:0 \"faithful\"",
        " myraethanen_priest:0 \"aethan\"",
        " myraethanen_priest_plural:0 \"aethanii\"",
        " myraethanen_high_priest:0 \"hylaethan\"",
        " myraethanen_high_priest_plural:0 \"hylaethanii\"",
        " myraethanen_divine_realm:0 \"the Source Fire\"",
        " myraethanen_divine_realm_2:0 \"the Flame\"",
        " myraethanen_divine_realm_3:0 \"the Sun\"",
        " myraethanen_afterlife:0 \"the Source Fire\"",
        " myraethanen_afterlife_2:0 \"the Flame\"",
        " myraethanen_afterlife_3:0 \"the light beyond the pyre\"",
        " myraethanen_bad_afterlife:0 \"the Cold\"",
        " myraethanen_bad_afterlife_2:0 \"the Dark\"",
        " myraethanen_bad_afterlife_3:0 \"the ash that no fire takes\"",
        " holy_order_keepers_of_the_flame:0 \"Keepers of the Flame\"",
        " holy_order_the_aethanii:0 \"The Aethanii\"",
        ""]
SITES = [("thenithria", "Thenithria", "the oldest source flame in Southern Kallonia"),
         ("gaeniri_aethiros", "Gaeniri Aethiros", "the fire temple of the mountain"),
         ("keraeni_aethiros", "Keraeni Aethiros", "the fire temple of the island"),
         ("kalaeni_aethiros", "Kalaeni Aethiros", "the fire temple of the plain"),
         ("atsiraeni_aethiros", "Atsiraeni Aethiros", "the fire temple of the strait")]
for key, name, desc in SITES:
    loc.append(" holy_site_%s_name:0 \"%s\"" % (key, name))
    loc.append(" holy_site_%s_effect_name:0 \"From [holy_site|E] #weak ($holy_site_%s_name$)#!\"" % (key, key))
loc.append("")
loc.append(" dynn_patriam_Kasparidii:0 \"Kasparidii\"")
for house, culture in loc_dyn:
    loc.append(" dynn_patriam_%s:0 \"%s\"" % (house, house))
loc.append("")
loc_file = "\n".join(loc) + "\n"

# The painted map has Thenithria at kingdom tier, so the text names Thenithria
# plainly rather than calling it a city state and disagreeing with the map.
bm_loc = ("\ufeffl_english:\n\n"
          " bm_group_patriam:0 \"6355\"\n\n"
          " bm_patriam_rise_of_empires:0 \"Rise of Empires\"\n"
          " bm_patriam_rise_of_empires_desc:0 \"Southern Kallonia, 6355 after the arrival of the Drunathaen."
          " Fifty realms hold the continent between them, and Thenithria is one of them."
          " Its new ruler is seventeen years old.\"\n"
          " bookmark_patriam_hythaerion:0 \"Hythaerion\"\n"
          " bookmark_patriam_hythaerion_subheading:0 \"$BOOKMARK_SUBHEADING_DEFAULT$\"\n"
          " bookmark_patriam_hythaerion_desc:0 \"Hythaerion has held Thenithria for a few days,"
          " inherited from his father, and he has already sent for the muster."
          " Before he is done the continent will answer to one throne, Senkaria and Taienmar will fall,"
          " and Ketan will pay tribute to a city of white elmin.\"\n")

FILES = [
    (MOD + "/common/culture/name_lists/patriam_name_lists.txt", name_lists),
    (MOD + "/common/dynasties/patriam_dynasties.txt", dynasties_file),
    (MOD + "/history/characters/00_patriam_rulers.txt", characters_file),
    (MOD + "/history/titles/00_patriam_titles.txt", titles_file),
    (MOD + "/common/bookmarks/bookmarks/00_patriam.txt", bookmark),
    (MOD + "/localization/english/patriam_cultures_l_english.yml", loc_file),
    (MOD + "/localization/english/patriam_bookmarks_l_english.yml", bm_loc),
]

DASH = re.compile("[\u2010-\u2015\u2212]|(?<=[A-Za-z])-(?=[A-Za-z])")
for path, text in FILES:
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    bad = DASH.findall(body)
    assert not bad, (path, bad[:3])
    if not text.startswith("﻿"):
        # The game wants a byte order mark on every file it reads.
        text = "﻿" + text
    if WRITE:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        io.open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("written %-72s %6d bytes" % (os.path.basename(path), len(text.encode("utf-8"))))
    else:
        print("would write %-68s %6d bytes" % (os.path.basename(path), len(text.encode("utf-8"))))
print("men sample:", ", ".join(men[29:39]))
print("women sample:", ", ".join(women[5:13]))
print("houses sample:", ", ".join(houses[:8]))
