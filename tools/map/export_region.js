// Region heightmap export for the Patriam world, with water level reporting.
//
// usage: ScriptingTool export_region.js <world> <prefix> <step> <bx0> <by0> <bx1> <by1>
// Block coordinates are inclusive of bx0/by0 and exclusive of bx1/by1.
//
// Writes <prefix>_height.png (16 bit, value = height - minHeight) and
// <prefix>_water.png (16 bit, value = water level - minHeight) so that land
// and sea can be separated exactly rather than by a guessed threshold.

var BufferedImage = Java.type('java.awt.image.BufferedImage');
var ImageIO = Java.type('javax.imageio.ImageIO');
var File = Java.type('java.io.File');

var TILE = 128;

var world = wp.getWorld().fromFile(argv[1]).go();
var dim = world.getDimension(0);
var prefix = argv[2];
var step = parseInt(argv[3], 10);
var bx0 = parseInt(argv[4], 10), by0 = parseInt(argv[5], 10);
var bx1 = parseInt(argv[6], 10), by1 = parseInt(argv[7], 10);

var range = dim.getHeightRange();
var minH = range[0];
var w = Math.ceil((bx1 - bx0) / step);
var h = Math.ceil((by1 - by0) / step);

print('world: ' + world.getName());
print('height range: ' + range[0] + ' .. ' + range[1] + '  minHeight used as zero: ' + minH);
print('region blocks: x ' + bx0 + '..' + bx1 + '  y ' + by0 + '..' + by1);
print('output: ' + w + ' x ' + h + '  at ' + step + ' blocks per pixel');

var height = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var water = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var hr = height.getRaster(), wr = water.getRaster();

// Tally water levels so the real sea level is known rather than assumed.
var waterTally = {};

var tiles = dim.getTiles();
var it = tiles.iterator();
var done = 0;
while (it.hasNext()) {
    var tile = it.next();
    var tbx = tile.getX() * TILE, tby = tile.getY() * TILE;
    if (tbx + TILE <= bx0 || tbx >= bx1 || tby + TILE <= by0 || tby >= by1) continue;

    var sx = Math.max(tbx, bx0), sy = Math.max(tby, by0);
    sx = bx0 + Math.ceil((sx - bx0) / step) * step;
    sy = by0 + Math.ceil((sy - by0) / step) * step;

    for (var by = sy; by < Math.min(tby + TILE, by1); by += step) {
        var py = (by - by0) / step;
        for (var bx = sx; bx < Math.min(tbx + TILE, bx1); bx += step) {
            var px = (bx - bx0) / step;
            var lx = bx - tbx, ly = by - tby;

            var hv = Math.round(tile.getHeight(lx, ly) - minH);
            if (hv < 0) hv = 0; if (hv > 65535) hv = 65535;
            hr.setSample(px, py, 0, hv);

            var wl = tile.getWaterLevel(lx, ly);
            waterTally[wl] = (waterTally[wl] || 0) + 1;
            var wv = Math.round(wl - minH);
            if (wv < 0) wv = 0; if (wv > 65535) wv = 65535;
            wr.setSample(px, py, 0, wv);
        }
    }
    done++;
}
print('tiles touched: ' + done);

var keys = Object.keys(waterTally).sort(function(a, b) { return waterTally[b] - waterTally[a]; });
print('water levels by frequency (level: samples):');
for (var i = 0; i < Math.min(6, keys.length); i++) {
    print('  ' + keys[i] + ': ' + waterTally[keys[i]]);
}

ImageIO.write(height, 'png', new File(prefix + '_height.png'));
print('wrote ' + prefix + '_height.png');
ImageIO.write(water, 'png', new File(prefix + '_water.png'));
print('wrote ' + prefix + '_water.png');
print('done');
