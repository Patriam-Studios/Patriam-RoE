// Whole world export for the Crusader Kings III map, in one load of the world.
//
// Writes, for every sampled block, all at the same size:
//   <prefix>_height.png   16 bit, value = (height - minHeight) * 64, so a block
//                         has sixty four steps and no slope is rounded into a
//                         staircase. That was the cause of the terraces.
//   <prefix>_water.png    16 bit, value = (water level - minHeight) * 64
//   <prefix>_biome.png    16 bit, value = biome id + 1, 0 means unresolved
//   <prefix>_trees.png     8 bit, the strongest tree layer at that block, 0 to 15
//   <prefix>_treelayer.png 8 bit, which tree layer that was, its index in
//                         <prefix>_layers.txt plus one, 0 where there is none
//   <prefix>_plants.png    8 bit, 1 where any plant layer is set
//   <prefix>_biomes.txt   id, share and name for every biome that occurs
//   <prefix>_layers.txt   the tree and plant layers found, one a line
//
// The step must divide 128 (the WorldPainter tile), and the region defaults to
// the whole world. A step of 2 over the whole world is 42496 by 17280, which
// Java can hold in one raster, unlike the one to one export that could not.
//
// usage: java -Xmx44g -cp "<WorldPainter dir>/lib/*" \
//            org.pepsoft.worldpainter.tools.ScriptingTool \
//            export_full.js <world> <prefix> <step> [bx0 by0 bx1 by1]

var BufferedImage = Java.type('java.awt.image.BufferedImage');
var ImageIO = Java.type('javax.imageio.ImageIO');
var File = Java.type('java.io.File');
var Files = Java.type('java.nio.file.Files');
var Paths = Java.type('java.nio.file.Paths');
var JString = Java.type('java.lang.String');
var Iface = Java.type('org.pepsoft.worldpainter.biomeschemes.Minecraft1_21Biomes').class;
var TILE = 128;
var SCALE = 64;

var world = wp.getWorld().fromFile(argv[1]).go();
var dim = world.getDimension(0);
var prefix = argv[2];
var step = parseInt(argv[3], 10);
if (TILE % step !== 0) throw 'step must divide ' + TILE;

var ext = dim.getExtent();
var range = dim.getHeightRange();
var minH = range[0];
var bx0 = argv.length > 7 ? parseInt(argv[4], 10) : ext.x * TILE;
var by0 = argv.length > 7 ? parseInt(argv[5], 10) : ext.y * TILE;
var bx1 = argv.length > 7 ? parseInt(argv[6], 10) : (ext.x + ext.width) * TILE;
var by1 = argv.length > 7 ? parseInt(argv[7], 10) : (ext.y + ext.height) * TILE;
var w = Math.ceil((bx1 - bx0) / step), h = Math.ceil((by1 - by0) / step);
print('world: ' + world.getName() + '  height range ' + range[0] + '..' + range[1] + '  minHeight as zero: ' + minH);
print('blocks x ' + bx0 + '..' + bx1 + ' y ' + by0 + '..' + by1 + ' -> ' + w + ' x ' + h + ' at step ' + step);

// Biome names, Minecraft's own and then the custom ones of this world.
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
var layerLines = [];
for (var t1 = 0; t1 < treeLayers.length; t1++) layerLines.push('tree\t' + t1 + '\t' + treeLayers[t1].getName());
for (var p1 = 0; p1 < plantLayers.length; p1++) layerLines.push('plant\t' + p1 + '\t' + plantLayers[p1].getName());
print('tree layers: ' + treeLayers.map(function (x) { return x.getName(); }).join(', '));
print('plant layers: ' + plantLayers.map(function (x) { return x.getName(); }).join(', '));

var heightImg = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var waterImg = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var biomeImg = new BufferedImage(w, h, BufferedImage.TYPE_USHORT_GRAY);
var treeImg = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var plantImg = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var layerImg = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_GRAY);
var hr = heightImg.getRaster(), wr = waterImg.getRaster(), br = biomeImg.getRaster();
var tr = treeImg.getRaster(), pr = plantImg.getRaster(), lr = layerImg.getRaster();
var tally = {}, samples = 0, tilesDone = 0, waterTally = {};

var it = dim.getTiles().iterator();
while (it.hasNext()) {
    var tile = it.next();
    var tbx = tile.getX() * TILE, tby = tile.getY() * TILE;
    if (tbx + TILE <= bx0 || tbx >= bx1 || tby + TILE <= by0 || tby >= by1) continue;
    var sx = bx0 + Math.ceil((Math.max(tbx, bx0) - bx0) / step) * step;
    var sy = by0 + Math.ceil((Math.max(tby, by0) - by0) / step) * step;
    var tileLayers = tile.getLayers();
    var hasTree = [], hasTreeIdx = [];
    for (var ti = 0; ti < treeLayers.length; ti++) {
        if (tileLayers.contains(treeLayers[ti])) { hasTree.push(treeLayers[ti]); hasTreeIdx.push(ti); }
    }
    var hasPlant = plantLayers.filter(function (x) { return tileLayers.contains(x); });
    var hasBiome = biomeLayer != null && tileLayers.contains(biomeLayer);

    for (var by = sy; by < Math.min(tby + TILE, by1); by += step) {
        var py = (by - by0) / step;
        for (var bx = sx; bx < Math.min(tbx + TILE, bx1); bx += step) {
            var px = (bx - bx0) / step;
            var lx = bx - tbx, ly = by - tby;

            var hv = Math.round((tile.getHeight(lx, ly) - minH) * SCALE);
            if (hv < 0) hv = 0; if (hv > 65535) hv = 65535;
            hr.setSample(px, py, 0, hv);

            var wl = tile.getWaterLevel(lx, ly);
            waterTally[wl] = (waterTally[wl] || 0) + 1;
            var wv = Math.round((wl - minH) * SCALE);
            if (wv < 0) wv = 0; if (wv > 65535) wv = 65535;
            wr.setSample(px, py, 0, wv);

            var biome = hasBiome ? tile.getLayerValue(biomeLayer, lx, ly) : 255;
            if (biome === 255) biome = dim.getAutoBiome(tile, lx, ly);
            br.setSample(px, py, 0, biome + 1);
            tally[biome] = (tally[biome] || 0) + 1;
            samples++;

            var t = 0, tl = 0;
            for (var k = 0; k < hasTree.length; k++) {
                var tv = tile.getLayerValue(hasTree[k], lx, ly);
                if (tv > t) { t = tv; tl = hasTreeIdx[k] + 1; }
            }
            tr.setSample(px, py, 0, t);
            lr.setSample(px, py, 0, tl);

            var p = 0;
            for (var m = 0; m < hasPlant.length && p === 0; m++) {
                if (tile.getBitLayerValue(hasPlant[m], lx, ly)) p = 1;
            }
            pr.setSample(px, py, 0, p);
        }
    }
    tilesDone++;
    if (tilesDone % 20000 === 0) print('  tiles ' + tilesDone);
}
print('tiles touched: ' + tilesDone + ', samples ' + samples);

ImageIO.write(heightImg, 'png', new File(prefix + '_height.png')); print('wrote height');
heightImg.flush();
ImageIO.write(waterImg, 'png', new File(prefix + '_water.png')); print('wrote water');
waterImg.flush();
ImageIO.write(biomeImg, 'png', new File(prefix + '_biome.png')); print('wrote biome');
biomeImg.flush();
ImageIO.write(treeImg, 'png', new File(prefix + '_trees.png')); print('wrote trees');
ImageIO.write(plantImg, 'png', new File(prefix + '_plants.png')); print('wrote plants');
ImageIO.write(layerImg, 'png', new File(prefix + '_treelayer.png')); print('wrote treelayer');

var keys = Object.keys(tally).sort(function (a, b) { return tally[b] - tally[a]; });
var lines = [];
for (var q = 0; q < keys.length; q++) {
    var id = parseInt(keys[q], 10);
    lines.push(id + '\t' + (tally[keys[q]] * 100 / samples).toFixed(3) + '\t' + (id === -1 ? 'unresolved' : (names[id] || 'unknown')));
}
Files.write(Paths.get(prefix + '_biomes.txt'), new JString(lines.join('\n') + '\n').getBytes('UTF-8'));
Files.write(Paths.get(prefix + '_layers.txt'), new JString(layerLines.join('\n') + '\n').getBytes('UTF-8'));
var wkeys = Object.keys(waterTally).sort(function (a, b) { return waterTally[b] - waterTally[a]; });
print('water levels by frequency:');
for (var z = 0; z < Math.min(6, wkeys.length); z++) print('  ' + wkeys[z] + ': ' + waterTally[wkeys[z]]);
print(keys.length + ' distinct biomes, the largest:');
for (var y2 = 0; y2 < Math.min(15, lines.length); y2++) print('  ' + lines[y2]);
print('done');
