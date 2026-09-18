@echo off
rem Whole world export from WorldPainter, one load of the world.
rem
rem Needs about 44 GB of heap, so run it after a reboot, with WorldPainter and
rem the game closed. If the JVM says the paging file is too small, the Windows
rem commit limit is exhausted again: reboot and try once more.
rem
rem Output lands in D:\Patriam-CK3-map\full as full_height.png, full_water.png,
rem full_biome.png, full_trees.png, full_plants.png, full_biomes.txt and
rem full_layers.txt, all at 42496 by 17280, two blocks a pixel. That is the
rem folder and the prefix the rest of the chain looks in.

set WP=%LOCALAPPDATA%\Programs\WorldPainter
set JAVA=C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot\bin\java.exe
set WORLD=C:\Worldpainter\Maps\Sixth Edition of the Patriam Map.world
set OUT=D:\Patriam-CK3-map\full\full
set HERE=%~dp0

"%JAVA%" -Xmx44g -Xms8g -cp "%WP%\lib\*" org.pepsoft.worldpainter.tools.ScriptingTool "%HERE%export_full.js" "%WORLD%" "%OUT%" 2 > "D:\Patriam-CK3-map\full\export_full.log" 2>&1

echo exit code %ERRORLEVEL%
type "D:\Patriam-CK3-map\full\export_full.log"
