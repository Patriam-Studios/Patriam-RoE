"""Zip the generated map files that are too large for git, for a release.

GitHub refuses any file over 100 MB, and the ground maps alone are four times
that, so everything .gitignore keeps out of map_data and gfx travels as one
archive attached to a release instead.

usage: python pack_binaries.py <out.zip>
"""
import os
import subprocess
import sys
import zipfile

MOD = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
files = subprocess.run(["git", "ls-files", "-o", "-i", "--exclude-standard", "--", "map_data", "gfx"],
                       cwd=MOD, capture_output=True, text=True, check=True).stdout.splitlines()
assert files, "nothing ignored under map_data or gfx; has the map been built?"
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in files:
        z.write(os.path.join(MOD, f), f)
        print(f)
print("%d files, %.0f MB" % (len(files), os.path.getsize(sys.argv[1]) / 1048576.0))
