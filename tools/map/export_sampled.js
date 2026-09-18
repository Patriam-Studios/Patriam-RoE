// Sampled heightmap export for the Patriam world.
//
// The full world is 84992 x 34560 blocks, which no single BufferedImage can
// hold, and which is far larger than any Crusader Kings III map needs. This
// script therefore samples every Nth block and writes one PNG per step, all
// from a single load of the world.
//
// usage: java -Xmx34g -cp "<WorldPainter dir>/lib/*" \
//            org.pepsoft.worldpainter.tools.ScriptingTool \
//            export_sampled.js <world file> <output prefix> <step>[,<step>...]
//
// Output is 16 bit greyscale, value = (height - minHeight), absent tiles = 0.

var BufferedImage = Java.type('java.awt.image.BufferedImage');
var ImageIO = Java.type('javax.imageio.ImageIO');
var File = Java.type('java.io.File');

var TILE = 128;

var world = wp.getWorld().fromFile(argv[1]).go();
var dim = world.getDimension(0);
var prefix = argv[2];
var steps = argv[3].split(',');

var ext = dim.getExtent();
var range = dim.getHeightRange();
var minH = range[0];

print('world: ' + world.getName());
print('extent (tiles): x=' + ext.x + ' y=' + ext.y + ' w=' + ext.width + ' h=' + ext.height);
print('extent (blocks): w=' + (ext.width * TILE) + ' h=' + (ext.height * TILE));
print('height range: ' + range[0] + ' .. ' + range[1]);

// Collect which tiles actually exist, so absent ones stay at zero.
var tiles = dim.getTiles();
var present = {};
var it = tiles.iterator();
var count = 0;
while (it.hasNext()) {
    var t = it.next();
    present[t.getX() + ':' + t.getY()] = t;
    count++;
}
print('tiles present: ' + count + ' of ' + (ext.width * ext.height));

for (var s = 0; s < steps.length; s++) {
    var step = parseInt(steps[s], 10);
    var w = Math.ceil((ext.width * TILE) / step);
    var h = Math.ceil((ext.height * TILE) / step);
    print('--- step ' + step + ' -> ' + w + ' x ' + h);

    var img = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
    var raster = img.getRaster();

    // Walk the tiles that exist rather than the whole bounding box, so empty
    // ocean costs nothing.
    for (var key in present) {
        var tile = present[key];
        var tbx = tile.getX() * TILE;   // tile origin in block coordinates
        var tby = tile.getY() * TILE;

        // First sampled block at or after this tile's origin.
        var startX = Math.ceil(tbx / step) * step;
        var startY = Math.ceil(tby / step) * step;

        for (var by = startY; by < tby + TILE; by += step) {
            var py = Math.floor((by - ext.y * TILE) / step);
            if (py < 0 || py >= h) continue;
            for (var bx = startX; bx < tbx + TILE; bx += step) {
                var px = Math.floor((bx - ext.x * TILE) / step);
                if (px < 0 || px >= w) continue;
                var val = Math.round(tile.getHeight(bx - tbx, by - tby) - minH);
                if (val < 0) val = 0;
                if (val > 65535) val = 65535;
                raster.setSample(px, py, 0, val);
            }
        }
    }

    var out = new File(prefix + '_step' + step + '.png');
    ImageIO.write(img, 'png', out);
    print('wrote ' + out.getPath());
    img.flush();
}
print('done');
