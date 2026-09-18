"""One place for how a WorldPainter height becomes a Crusader Kings III height.

Every map tool imports this rather than carrying its own constant, so the
colour map, the ground materials, the province terrain and the packer can
never disagree about what a sixteen bit value means.

WorldPainter heights are blocks. Sea level in the Patriam world is block 62 and
the world runs from minus 64 to a little under 319. The game keeps its sea at
3932 of 65535, so that value is pinned to block 62.

Above the sea the mapping is a curve with a knee. Below the knee the ground
rises at 320 units a block, which makes the relief twice what a flat 160 gave
and matches the world's own proportions, since one unit across is about four
blocks and 320 a block puts one unit up at four blocks too. Above the knee the
peaks are compressed so the highest summit still fits under 65535 with room to
spare. Below the sea the whole depth is stretched linearly down to zero so the
continental shelves stay readable.

Both directions are provided and are exact inverses of each other.
"""
import numpy as np

SEA_BLOCK = 62.0
MIN_BLOCK = -64.0
MAX_BLOCK = 318.8

CK3_SEA = 3932.0
CK3_MAX = 65535.0

KNEE_BLOCKS = 120.0          # above the sea
LOW_UNITS_PER_BLOCK = 320.0  # below the knee
HIGH_UNITS_PER_BLOCK = 136.0 # above the knee

KNEE_UNITS = CK3_SEA + KNEE_BLOCKS * LOW_UNITS_PER_BLOCK
TOP_UNITS = KNEE_UNITS + (MAX_BLOCK - SEA_BLOCK - KNEE_BLOCKS) * HIGH_UNITS_PER_BLOCK
assert TOP_UNITS < CK3_MAX, "the highest summit does not fit"

# In the sea the depth range is stretched to the whole span below sea level.
SEA_UNITS_PER_BLOCK = CK3_SEA / (SEA_BLOCK - MIN_BLOCK)


def _banded(fn, a, rows=512):
    """Apply fn to an array a band of rows at a time, so a four hundred
    megapixel map never needs several whole size temporaries at once."""
    a = np.asarray(a)
    if a.ndim < 2 or a.shape[0] <= rows:
        return fn(a)
    out = np.empty(a.shape, dtype=np.float32)
    for y in range(0, a.shape[0], rows):
        out[y:y + rows] = fn(a[y:y + rows])
    return out


def _blocks_to_units(b):
    r = b.astype(np.float32) - np.float32(SEA_BLOCK)
    out = np.float32(CK3_SEA) + r * np.float32(SEA_UNITS_PER_BLOCK)
    land = r >= 0
    out[land] = np.float32(CK3_SEA) + r[land] * np.float32(LOW_UNITS_PER_BLOCK)
    high = r > KNEE_BLOCKS
    out[high] = np.float32(KNEE_UNITS) + (r[high] - np.float32(KNEE_BLOCKS)) * np.float32(HIGH_UNITS_PER_BLOCK)
    return np.clip(out, 0, CK3_MAX)


def _units_to_blocks(u):
    u = u.astype(np.float32)
    out = np.float32(SEA_BLOCK) + (u - np.float32(CK3_SEA)) / np.float32(SEA_UNITS_PER_BLOCK)
    land = u >= CK3_SEA
    out[land] = np.float32(SEA_BLOCK) + (u[land] - np.float32(CK3_SEA)) / np.float32(LOW_UNITS_PER_BLOCK)
    high = u > KNEE_UNITS
    out[high] = np.float32(SEA_BLOCK + KNEE_BLOCKS) + (u[high] - np.float32(KNEE_UNITS)) / np.float32(HIGH_UNITS_PER_BLOCK)
    return out


def blocks_to_units(blocks):
    """WorldPainter block heights (float array) to sixteen bit game heights."""
    return _banded(_blocks_to_units, blocks)


def units_to_blocks(units):
    """The exact inverse, for tools that want to reason in blocks."""
    return _banded(_units_to_blocks, units)


def elevation_blocks(units):
    """Blocks above the sea, zero at and below it."""
    return np.maximum(units_to_blocks(units) - SEA_BLOCK, 0.0)


if __name__ == "__main__":
    probe = np.array([MIN_BLOCK, 0.0, SEA_BLOCK, 63.0, 80.0, 120.0, 182.0, 200.0, 318.0, MAX_BLOCK])
    units = blocks_to_units(probe)
    back = units_to_blocks(units)
    for p, u, b in zip(probe, units, back):
        print("block %7.2f -> units %8.1f -> block %7.2f" % (p, u, b))
    assert np.allclose(probe, back, atol=1e-6), "the mapping is not invertible"
    print("knee at %.0f units, summit at %.0f of %.0f" % (KNEE_UNITS, TOP_UNITS, CK3_MAX))
