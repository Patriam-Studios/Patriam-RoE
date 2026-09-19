@echo off
rem Everything downstream of the canvas, in order. Run after build_canvas.py
rem --write (or after a fresh WorldPainter export has been refined into
rem map_data/heightmap.png, in which case skip the first two lines).
rem
rem Each step reads what the one before it wrote, so they run one at a time.
rem Together they take a little under half an hour.

setlocal
set HERE=%~dp0
set MOD=%HERE%..\..
set FULL=D:\Patriam-CK3-map\full
set PW=16384
set PH=6656

echo === 1. refine the raw canvas heightmap into game heights
python "%HERE%refine_heightmap.py" --from-export "%FULL%\canvas_blocks.png" --sigma 1.0 "%FULL%\heightmap.png" || goto :fail
copy /Y "%FULL%\heightmap.png" "%MOD%\map_data\heightmap.png" >nul || goto :fail

echo === 2. pack the heightmap
python "%HERE%pack_heightmap.py" "%MOD%\map_data\heightmap.png" "%MOD%\map_data" || goto :fail

echo === 3. terrain quadtree
python "%HERE%build_nodes.py" "%MOD%\map_data\heightmap.png" "%MOD%\map_data" || goto :fail

echo === 3b. rivers from the river biome
python "%HERE%build_rivers.py" "%FULL%\full" "%MOD%\map_data" --write || goto :fail

echo === 5. colour map and paper map
python "%HERE%build_textures.py" "%MOD%\map_data\heightmap.png" "%MOD%\gfx\map\terrain" "%FULL%\full" || goto :fail

echo === 6. ground materials (from biomes when the export exists, else from elevation)
python "%HERE%build_terrain.py" "%FULL%\full" "%MOD%\map_data\heightmap.png" "%MOD%\map_data" "%MOD%\gfx\map\terrain" || goto :fail

echo === 6b. material masks, filled from the splat maps for the map editor
python "%HERE%build_masks.py" %PW% %PH% "%MOD%\map_data" "%MOD%\gfx\map\terrain" || goto :fail

echo === 7. map object locators
pushd "%FULL%"
python "%HERE%build_locators2.py" || (popd & goto :fail)
popd

echo === 7b. the fires of Vurkia
python "%HERE%build_vurkia.py" "%FULL%\full" --write || goto :fail

echo === 7c. take the base game's own map objects off this world
python "%HERE%clear_vanilla_objects.py" --write || goto :fail

echo === 7d. surf along the shores
python "%HERE%build_coast_foam.py" --write || goto :fail

echo === 8. trees from the WorldPainter tree layers
if exist "%FULL%\full_trees.png" (
    python "%HERE%build_trees.py" "%FULL%\full" --write || goto :fail
)

echo === all steps done
exit /b 0

:fail
echo === a step failed, see above
exit /b 1
