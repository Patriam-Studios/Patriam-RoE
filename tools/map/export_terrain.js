// Terrain export for the Crusader Kings III map.
//
// For every sampled block this records the biome and the density of tree and
// plant layers, which later decide the ground materials, the colour map and
// where trees go.
//
// Biome is the painted value where one was painted. Where it was left unset
// (255) WorldPainter's own inference is used instead, through getAutoBiome.
// Where even that has no answer it is recorded as unresolved, and the Python
// side falls back to elevation and slope for those blocks.
//
// usage: ScriptingTool export_terrain.js <world> <prefix> <step> [bx0 by0 bx1 by1]
//
// Writes, all at the same size:
//   <prefix>_biome.png   16 bit, value = biome id + 1, so 0 means unresolved
//   <prefix>_trees.png    8 bit, the highest tree layer density, 0 to 15
//   <prefix>_plants.png   8 bit, 1 where any plant layer is set
//   <prefix>_biomes.txt   id, name and share for every biome that occurs

var BufferedImage = Java.type('java.awt.image.BufferedImage');
var ImageIO = Java.type('javax.imageio.ImageIO');
var File = Java.type('java.io.File');
var Iface = Java.type('org.pepsoft.worldpainter.biomeschemes.Minecraft1_21Biomes').class;
var TILE = 128;

var world = wp.getWorld().fromFile(argv[1]).go();
var dim = world.getDimension(0);
var prefix = argv[2];
var step = parseInt(argv[3], 10);

var ext = dim.getExtent();
var bx0 = argv.length > 7 ? parseInt(argv[4], 10) : ext.x * TILE;
var by0 = argv.length > 7 ? parseInt(argv[5], 10) : ext.y * TILE;
var bx1 = argv.length > 7 ? parseInt(argv[6], 10) : (ext.x + ext.width) * TILE;
var by1 = argv.length > 7 ? parseInt(argv[7], 10) : (ext.y + ext.height) * TILE;
var w = Math.ceil((bx1 - bx0) / step), h = Math.ceil((by1 - by0) / step);
print('region blocks x ' + bx0 + '..' + bx1 + ' y ' + by0 + '..' + by1 + ' -> ' + w + ' x ' + h + ' at step ' + step);

var names = {};
var fields = Iface.getFields();
for (var i = 0; i < fields.length; i++) {
    var f = fields[i];
    if (f.getName().indexOf('BIOME_') === 0 && String(f.getType()) === 'int') {
        var v = f.getInt(null);
        if (!names[v]) names[v] = f.getName().substring(6).toLowerCase();
    }
}
var cb = dim.getCustomBiomes();
if (cb != null) {
    var ci = cb.iterator();
    while (ci.hasNext()) { var b = ci.next(); names[b.getId()] = 'custom: ' + b.getName(); }
}

var biomeLayer = null, treeLayers = [], plantLayers = [];
var li = dim.getAllLayers(false).iterator();
while (li.hasNext()) {
    var L = li.next();
    var cls = L.getClass().getSimpleName();
    if (L.getName() == 'Biome') biomeLayer = L;
    else if (cls == 'Bo2Layer') treeLayers.push(L);
    else if (cls == 'PlantLayer') plantLayers.push(L);
}
print('tree layers: ' + treeLayers.map(function (x) { return x.getName(); }).join(', '));
print('plant layers: ' + plantLayers.map(function (x) { return x.getName(); }).join(', '));

var biomeImg = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var treeImg = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var plantImg = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var br = biomeImg.getRaster(), tr = treeImg.getRaster(), pr = plantImg.getRaster();
var tally = {}, samples = 0;

var it = dim.getTiles().iterator();
while (it.hasNext()) {
    var tile = it.next();
    var tbx = tile.getX() * TILE, tby = tile.getY() * TILE;
    if (tbx + TILE <= bx0 || tbx >= bx1 || tby + TILE <= by0 || tby >= by1) continue;
    var sx = bx0 + Math.ceil((Math.max(tbx, bx0) - bx0) / step) * step;
    var sy = by0 + Math.ceil((Math.max(tby, by0) - by0) / step) * step;
    var tileLayers = tile.getLayers();
    var hasTree = treeLayers.filter(function (x) { return tileLayers.contains(x); });
    var hasPlant = plantLayers.filter(function (x) { return tileLayers.contains(x); });
    var hasBiome = biomeLayer != null && tileLayers.contains(biomeLayer);

    for (var by = sy; by < Math.min(tby + TILE, by1); by += step) {
        var py = (by - by0) / step;
        for (var bx = sx; bx < Math.min(tbx + TILE, bx1); bx += step) {
            var px = (bx - bx0) / step;
            var lx = bx - tbx, ly = by - tby;

            var biome = hasBiome ? tile.getLayerValue(biomeLayer, lx, ly) : 255;
            if (biome === 255) biome = dim.getAutoBiome(tile, lx, ly);
            br.setSample(px, py, 0, biome + 1);
            tally[biome] = (tally[biome] || 0) + 1;
            samples++;

            var t = 0;
            for (var k = 0; k < hasTree.length; k++) {
                var tv = tile.getLayerValue(hasTree[k], lx, ly);
                if (tv > t) t = tv;
            }
            tr.setSample(px, py, 0, t);

            var p = 0;
            for (var m = 0; m < hasPlant.length && p === 0; m++) {
                if (tile.getBitLayerValue(hasPlant[m], lx, ly)) p = 1;
            }
            pr.setSample(px, py, 0, p);
        }
    }
}

ImageIO.write(biomeImg, 'png', new File(prefix + '_biome.png'));
ImageIO.write(treeImg, 'png', new File(prefix + '_trees.png'));
ImageIO.write(plantImg, 'png', new File(prefix + '_plants.png'));

var keys = Object.keys(tally).sort(function (a, b) { return tally[b] - tally[a]; });
var lines = [];
for (var q = 0; q < keys.length; q++) {
    var id = parseInt(keys[q], 10);
    lines.push(id + '\t' + (tally[keys[q]] * 100 / samples).toFixed(3) + '\t' + (id === -1 ? 'unresolved' : (names[id] || 'unknown')));
}
var Files = Java.type('java.nio.file.Files');
var Paths = Java.type('java.nio.file.Paths');
var JString = Java.type('java.lang.String');
Files.write(Paths.get(prefix + '_biomes.txt'), new JString(lines.join('\n') + '\n').getBytes('UTF-8'));
print('wrote biome, trees, plants and biome table, ' + samples + ' samples, ' + keys.length + ' distinct biomes');
for (var z = 0; z < Math.min(12, lines.length); z++) print('  ' + lines[z]);
