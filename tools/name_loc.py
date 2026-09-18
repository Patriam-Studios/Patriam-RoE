"""Writes the localisation entries for every given name in the name lists.

CK3 looks up a character's given name as a localisation key, so a name that is
only listed and never localised shows up in the log and, in some windows, on
screen. Run with --write to put the file into the mod.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..")
WRITE = "--write" in sys.argv

src = io.open(os.path.join(MOD, "common", "culture", "name_lists",
                          "patriam_name_lists.txt"), encoding="utf-8-sig").read()

names = []
for block in re.finditer(r"(?:male_names|female_names)\s*=\s*\{(.*?)\}", src, re.S):
    for word in block.group(1).split():
        if word.startswith("#"):
            continue
        if word not in names:
            names.append(word)

VANILLA_NAMES = ("C:/Program Files (x86)/Steam/steamapps/common/Crusader Kings III"
                 "/game/localization/english/names")
vanilla = set()
for root, _dirs, files in os.walk(VANILLA_NAMES):
    for f in files:
        if f.endswith(".yml"):
            text = io.open(os.path.join(root, f), encoding="utf-8-sig", errors="replace").read()
            vanilla.update(re.findall(r"^\s*(\S+?):\d*\s", text, re.M))

# A name the base game already localises must be left alone, since two files
# claiming the same key is an error whatever the two of them say.
shared = sorted(n for n in names if n in vanilla)
names = [n for n in names if n not in vanilla]

out = ["\ufeffl_english:", "",
       " # Given names. One entry for every name the name lists offer, less the",
       " # few the base game already carries.", ""]
for n in sorted(names):
    out.append(' %s:0 "%s"' % (n, n))

path = os.path.join(MOD, "localization", "english", "patriam_names_l_english.yml")
print(len(names), "names, leaving", len(shared), "to the base game:", ", ".join(shared))
if WRITE:
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("written", path)
