"""Take the base game's map objects off this world.

Every object the base game lays on its map is placed by coordinate: its lakes,
its animals, its bridges and its cliffs, the sprawl of Constantinople, Hadrian's
Wall, the pyramids of Giza and the Tower of London. Those coordinates mean
something only on its own Earth. Left alone they scatter across Patriam, so a
lake sits in open ocean and a wall runs over a mountain nobody built it on.

A file of the same name overrides the base game's, so each one that places
objects is replaced by an empty file, except the ones this mod writes itself:
the holding and stack locators, the map table, the trees, and anything of our
own making.

The layer definitions are left alone. They declare the layers every object
names, ours among them, and emptying those would take our own trees and smoke
off the map with everything else.

usage: python clear_vanilla_objects.py [--write]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "..")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
SRC = os.path.join(GAME, "gfx", "map", "map_object_data")
OUT = os.path.join(MOD, "gfx", "map", "map_object_data")
WRITE = "--write" in sys.argv

# What this mod writes for itself, which must never be emptied.
OURS = {
    "activities.txt", "building_locators.txt", "combat_locators.txt",
    "other_stack_locators.txt", "player_stack_locators.txt", "siege_locators.txt",
    "special_building_locators.txt", "stack_locators.txt",
    "map_table_ce1.txt", "map_table_ep3.txt", "map_table_tgp.txt", "map_table_western.txt",
}
HEADER = ("# Patriam: Rise of Empires. The base game places %s on its own Earth by\n"
          "# coordinate, which lands them at random on this world. A file of this name\n"
          "# overrides it, so nothing is placed. Written by tools/map/clear_vanilla_objects.py.\n")
WHAT = {
    "animals.txt": "herds of animals",
    "audio_emitters.txt": "the sounds of its towns and its wilds",
    "bridges.txt": "bridges",
    "changan_building.txt": "the buildings of Chang'an",
    "cliffs_coastline.txt": "coastal cliffs",
    "cliffs_rock.txt": "rock cliffs",
    "coast_foam.txt": "the foam along its shores",
    "env_effects.txt": "mist and the haze of its deserts",
    "great_wall_china.txt": "the Great Wall",
    "great_wall_china_gate.txt": "the gates of the Great Wall",
    "lakes.txt": "lakes",
    "special.txt": "its landmarks, from Stonehenge to the pyramids of Giza",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    cleared, kept, skipped = [], [], []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".txt"):
            continue
        body = io.open(os.path.join(SRC, name), encoding="utf-8-sig", errors="replace").read()
        if "object={" not in body:
            skipped.append((name, "locators" if "id=" in body else "layer definitions"))
            continue
        if name in OURS:
            kept.append(name)
            continue
        cleared.append(name)
        if WRITE:
            io.open(os.path.join(OUT, name), "w", encoding="utf-8-sig", newline="\n").write(
                HEADER % WHAT.get(name, "objects"))
    print("cleared %d files of the base game's objects:" % len(cleared))
    for n in cleared:
        print("   %-30s %s" % (n, WHAT.get(n, "objects")))
    print("left to this mod's own tools: %s" % ", ".join(kept))
    for what in ("layer definitions", "locators"):
        names = [n for n, kind in skipped if kind == what]
        print("left alone, %s: %s" % (what, ", ".join(names)))
    if not WRITE:
        print("dry run, nothing written")


if __name__ == "__main__":
    main()
