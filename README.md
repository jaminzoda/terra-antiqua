Terra Antiqua is a QGIS plugin for paleogeographic reconstructions and paleogeographic map creation. 
This plugin has utilities and tools for:
<ul>
<li>Merging reconstructed topography and bathymetry data that are rotated to the time of reconstruction in Gplates; 
Defining paleoshorelines (also rotated to the time of reconstruction);
<li>Modifying topography and bathymetry with formula or by defining new maximum and minimum elevation/depth values for various regions. To define the formula minimum and maximum values for topography/bathymetry regions, polygons should be drawn for the areas of modification;
<li>Creating new topography and bathymetry (mountain ranges and sea);
<li>It also has utilities that provide easy to use standard processing tools such filling the gaps in the raster files by interpolation, smoothing the raster files, compensation for isostasy and copying topography/bathymetry data and pasting in other rasters;
<li>The Remove Artefacts tool allows users to remove artefacts that are often created in datasets during processing;
<li>The Prepare masks tool allows to prepare several shapefiles containing masks, merging them together in order to use them as input in the Compile TopoBathymetry tool that merges topography and bathymetry raster data. 
</ul>
To install the plugin you need to switch to Releases tab and download a zip file with the latest version, then in plugins manager of QGIS select the option for installing local packages and install it. 


(C) 2019 Magic - paleoenvironment.eu
