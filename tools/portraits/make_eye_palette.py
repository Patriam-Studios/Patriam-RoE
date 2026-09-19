"""Violet eyes for the Senkarian peoples.

Every eye in this game is a point picked out of one palette,
gfx/portraits/eye_palette.dds, where the across axis runs from brown at the
left, through amber and green, to blue at the right, and the down axis runs
from pale to dark. There is no violet anywhere in it, and the Senkarians are
famous for violet eyes.

So the palette is overridden. Nothing of Patriam looks out of brown eyes: the
Drunathaen and the Norkinians have blue, grey or green, the Kaegonic blue or
green, the Senkarians gold or violet, and the Ketanites blue, green or gold.
The whole brown band at the left is therefore free ground, and it is repainted
as violet, keeping the lightness of every pixel it replaces so that the ramp
from pale lilac at the top to near black at the bottom matches the rest of the
palette and shades the same way on a face.

The file is 256 by 256 pixels of uncompressed blue, green, red and alpha with
no mip levels, so its own 128 byte header is reused and only the pixels change.

usage: python make_eye_palette.py [--write]
"""
import io
import os
import sys

GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
SRC = os.path.join(GAME, "gfx", "portraits", "eye_palette.dds")
MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(MOD, "gfx", "portraits", "eye_palette.dds")
WRITE = "--write" in sys.argv

# How much of the palette is repainted, as a part of its width. The brown band
# runs from the left edge to about a quarter across, and amber begins a little
# beyond that, so this stops short of the amber the Senkarians and the Ketanites
# are given.
BAND = 0.26

# The violet the band is painted in, dark to pale. Every pixel keeps its own
# lightness and takes its colour from this ramp, so the eye shades as the rest
# of the palette does.
DARK = (54, 16, 84)
PALE = (198, 152, 246)


def violet(lightness, saturation):
    """The violet at this lightness, nought at the darkest and one at the palest.
    Saturation runs from nought at the left of the band, where the violet is
    greyed almost to slate, to one at its right, where it is at its fullest."""
    base = [DARK[i] + (PALE[i] - DARK[i]) * lightness for i in range(3)]
    grey = sum(base) / 3.0
    return tuple(int(round(max(0.0, min(255.0, grey + (c - grey) * (0.65 + 0.35 * saturation)))))
                 for c in base)


def main():
    raw = io.open(SRC, "rb").read()
    header, pixels = raw[:128], bytearray(raw[128:])
    width = height = 256
    assert len(pixels) == width * height * 4, "the palette is not 256 by 256 of uncompressed colour"

    # The lightness comes from how far down the palette the pixel lies rather
    # than from the brown it replaces, since that brown is dark throughout and
    # keeping its lightness would leave every violet eye nearly black. The rest
    # of the palette runs pale at the top to dark at the bottom, and so does
    # this band.
    edge = int(width * BAND)
    changed = 0
    for y in range(height):
        light = (1.0 - y / (height - 1.0)) ** 0.85
        for x in range(edge):
            i = (y * width + x) * 4
            nr, ng, nb = violet(light, x / (edge - 1.0))
            pixels[i], pixels[i + 1], pixels[i + 2] = nb, ng, nr
            changed += 1
    print("repainted %d pixels, the leftmost %d columns of %d, as violet"
          % (changed, edge, width))

    # what the ethnicities will actually read out of the new band
    for name, u, v in (("pale violet", 0.20, 0.08), ("violet", 0.22, 0.30),
                       ("deep violet", 0.16, 0.55), ("slate violet", 0.03, 0.30),
                       ("amber, untouched", 0.32, 0.18)):
        i = (int(v * height) * width + int(u * width)) * 4
        print("   %-18s u %.2f v %.2f -> rgb (%d, %d, %d)"
              % (name, u, v, pixels[i + 2], pixels[i + 1], pixels[i]))

    if not WRITE:
        print("dry run, nothing written")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "wb").write(header + bytes(pixels))
    assert os.path.getsize(OUT) == len(raw), "the written palette is not the size of the one it overrides"
    print("wrote %s, %d bytes" % (os.path.relpath(OUT, MOD), os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
