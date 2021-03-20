Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography. It simplifies the reconstruction process by using the graphical user interface of QGis. It provides a complete set of tools to edit Digital Elevations Models (DEM) for paleoreconstructions. It offers a user-friendly GUI (graphical user interface) with robust algorithms geared to manipulate geographic features generating maps for different time slices.

The workflow is intuitive, and the user is provided with guiding tips for each algorithm and tool. Terra Antiqua takes as an input rotated (e.g., in Gplates) present-day topography and bathymetry (Müller et al., 2008) alongside vector masks that are used to define the continental blocks. 
  
A user's manual is available where we detail each of Terra Antiqua’s tools, its use, and technical characteristics. There, step by step indications serve as guidance for the practical use of each tool. 

Here is a quick overview of the tools availabe in this plugin:
<ul>
<li>Merge the topography and the bathymetry at a given time rotated back to their position at the time of reconstruction in Gplates.
<li>Redefining paleoshorelines (rotated to the time of reconstruction).
<li>Modifying the elevation values of a topography/bathymetry raster in a given area. A vector mask contained in a shapefile must define this area. The topography modification is either performed by linearly rescaling the existing elevation between a given maximum and minimum, or applying a mathematical formula of your own. These parameters are to be defined in the dialog interface. To define the formula minimum and maximum values for topography/bathymetry regions, polygons should be drawn for the areas of modification.
<li>Creating new topography or bathymetry in the DEM for the area defined by a polygon (mountain ranges or seas).

The secondary tools are designed to improve the DEM’s quality after the reconstruction is done.
For example, some areas may end up missing elevation values. This issue is common for paleogeographic maps because, after rotating present-day topography/bathymetry, gaps can appear between the blocks. These gaps represent areas where the topography/bathymetry was destroyed by deformation or subduction of a crust portion. These missing values can be filled by interpolation (II.3.2.2).

<li>It also has a set of secondary tools designed to improve the DEM’s quality after the reconstruction is done (filling the gaps in the DEM by interpolation, smoothing the DEM, isostatic compensation for the absence of ice mass in the poles, and copying topography/bathymetry data to paste it in another raster).
<li>The <i>Remove Artefacts</i> tool allows the user to remove the artefacts present in the data or introduced during different processing steps from the DEM raster.
<li>The <i>Prepare masks</i> tool allows to prepare several shapefiles containing masks, merging them together in order to use them as input in the <i>Compile Topo-/Bathymetry tool</i> that merges topography and bathymetry raster data. 
</ul>
  In the form of a DEM or symbolized raster, the final paleogeographic map can be saved in any raster format supported by modern GIS software.
  
To install the plugin you need to switch to Releases tab and download a zip file with the latest version, then in plugins manager of QGIS select the option for installing local packages and install it. 


(C) 2021 Magic - paleoenvironment.eu
