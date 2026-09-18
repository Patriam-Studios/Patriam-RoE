// Surface terrain export: the terrain type WorldPainter holds for every block.
//
// A block's terrain is what was painted on it, grass or sand or stone or one
// of the world's own custom mixed terrains, and it is kept apart from the
// biome. It is the better guide to a ground texture, since it is the surface
// itself rather than the climate around it.
//
// Writes, at the same size as export_full.js does for the same step:
//   <prefix>_surface.png   8 bit, the terrain's ordinal plus one
//   <prefix>_surfaces.txt  ordinal, share and name of every terrain that
//                          occurs; a custom terrain carries the name it was
//                          given in the world
//
// usage: java -Xmx40g -cp "<WorldPainter dir>/lib/*" \
//            org.pepsoft.worldpainter.tools.ScriptingTool \
//            export_surface.js <world> <prefix> <step>

var BufferedImage = Java.type('java.awt.image.BufferedImage');
var ImageIO = Java.type('javax.imageio.ImageIO');
var File = Java.type('java.io.File');
var Files = Java.type('java.nio.file.Files');
var Paths = Java.type('java.nio.file.Paths');
var JString = Java.type('java.lang.String');
var Terrain = Java.type('org.pepsoft.worldpainter.Terrain');
var TILE = 128;

var world = wp.getWorld().fromFile(argv[1]).go();
var dim = world.getDimension(0);
var prefix = argv[2];
var step = parseInt(argv[3], 10);
if (TILE % step !== 0) throw 'step must divide ' + TILE;

var ext = dim.getExtent();
var bx0 = ext.x * TILE, by0 = ext.y * TILE;
var bx1 = (ext.x + ext.width) * TILE, by1 = (ext.y + ext.height) * TILE;
var w = Math.ceil((bx1 - bx0) / step), h = Math.ceil((by1 - by0) / step);
print('world: ' + world.getName() + '  ' + w + ' x ' + h + ' at step ' + step);

var img = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var r = img.getRaster();
var tally = {}, byOrdinal = {}, samples = 0, tilesDone = 0;

var it = dim.getTiles().iterator();
while (it.hasNext()) {
    var tile = it.next();
    var tbx = tile.getX() * TILE, tby = tile.getY() * TILE;
    for (var ly = 0; ly < TILE; ly += step) {
        var py = (tby - by0 + ly) / step;
        for (var lx = 0; lx < TILE; lx += step) {
            var px = (tbx - bx0 + lx) / step;
            var t = tile.getTerrain(lx, ly);
            var o = t.ordinal();
            r.setSample(px, py, 0, o + 1);
            tally[o] = (tally[o] || 0) + 1;
            if (!byOrdinal[o]) byOrdinal[o] = t;
            samples++;
        }
    }
    tilesDone++;
    if (tilesDone % 20000 === 0) print('  tiles ' + tilesDone);
}
ImageIO.write(img, 'png', new File(prefix + '_surface.png'));
print('wrote surface, ' + samples + ' samples');

function nameOf(t) {
    var name = String(t.getName());
    try {
        if (t.isCustom()) {
            var idx = t.getCustomTerrainIndex();
            var mm = null;
            try { mm = Terrain.getCustomMaterial(idx); } catch (e1) {}
            if (mm == null) { try { mm = world.getMixedMaterial(idx); } catch (e2) {} }
            if (mm != null) name = 'custom: ' + mm.getName();
            else name = 'custom ' + idx + ': ' + name;
        }
    } catch (e) {}
    return name;
}

var keys = Object.keys(tally).sort(function (a, b) { return tally[b] - tally[a]; });
var lines = [];
for (var q = 0; q < keys.length; q++) {
    var o2 = parseInt(keys[q], 10);
    lines.push(o2 + '\t' + (tally[keys[q]] * 100 / samples).toFixed(3) + '\t' + nameOf(byOrdinal[o2]));
}
Files.write(Paths.get(prefix + '_surfaces.txt'), new JString(lines.join('\n') + '\n').getBytes('UTF-8'));
print(keys.length + ' distinct terrains:');
for (var z = 0; z < lines.length; z++) print('  ' + lines[z]);
print('done');
