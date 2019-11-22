from PyQt5.QtCore import (
	QThread,
	pyqtSignal
)
import os
from osgeo import (
	gdal,
	osr
)
from qgis.core import (
	QgsVectorFileWriter,
	QgsVectorLayer,
	QgsExpression,
	QgsFeatureRequest
)
import shutil
import tempfile

import numpy as np

from .topotools import vector_to_raster


class TopoBathyCompiler(QThread):
	progress = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False

	def run(self):
		self.log.emit("The processing  has started")
		progress_count = 0
		# Get the path of the output file
		if not self.dlg.outputPath.filePath():
			temp_dir = tempfile.gettempdir()
			out_file_path = os.path.join(temp_dir, 'Compiled_DEM_Topo+Bathy.tif')
		else:
			out_file_path = self.dlg.outputPath.filePath()

		# getting the paleobathymetry layer
		bathy_layer = self.dlg.selectPaleoBathy.currentLayer()
		bathy_ds = gdal.Open(bathy_layer.dataProvider().dataSourceUri())
		paleo_bathy = bathy_ds.GetRasterBand(1).ReadAsArray()

		# creating a base grid for compiling topography and bathymetry
		paleo_dem = np.empty(paleo_bathy.shape)
		paleo_dem[:] = np.nan
		# Copy the bathymetry to the base grid. Values above sea level are set to 0.
		paleo_dem[paleo_bathy < 0] = paleo_bathy[paleo_bathy < 0]
		paleo_dem[paleo_bathy > 0] = -0.1  # Bring the values, which are above sea level down below sea level.

		progress_count += 5
		self.progress.emit(progress_count)

		if self.dlg.selectOceanAge.currentLayer():
			# getting ocean age layer
			ocean_age_layer = self.dlg.selectOceanAge.currentLayer()
			age_ds = gdal.Open(ocean_age_layer.dataProvider().dataSourceUri())
			ocean_age = age_ds.GetRasterBand(1).ReadAsArray()

			# create an empty array to store calculated ocean depth from age.
			ocean_depth = np.empty(paleo_bathy.shape)
			ocean_depth[:] = np.nan
			r_time = self.dlg.ageBox.value()

			# calculate ocean age
			ocean_age[ocean_age > 0] = ocean_age[ocean_age > 0] - r_time
			ocean_depth[ocean_age > 0] = -2620 - 330 * (np.sqrt(ocean_age[ocean_age > 0]))
			ocean_depth[ocean_age > 90] = -5750
			# Update the bathymetry, keeping mueller only where agegrid is undefined
			paleo_dem[np.isfinite(ocean_depth)] = ocean_depth[np.isfinite(ocean_depth)]

			progress_count += 5
			self.progress.emit(progress_count)

		else:
			pass

		# Get the general masks layer from the dialog
		masks_layer = self.dlg.selectMasks.currentLayer()

		# Get features by attribute from the masks layer - the attributes are fetched in the 'layer' field
		expr_ss = QgsExpression("\"layer\"='Shallow sea'")
		expr_cs = QgsExpression("\"layer\"='Continental Shelves'")
		expr_coast = QgsExpression("\"layer\"='Continents'")

		ss_features = masks_layer.getFeatures(QgsFeatureRequest(expr_ss))
		cs_features = masks_layer.getFeatures(QgsFeatureRequest(expr_cs))
		coast_features = masks_layer.getFeatures(QgsFeatureRequest(expr_coast))

		ss_n = 0
		for feature in ss_features:
			ss_n += 1

		cs_n = 0
		for feature in cs_features:
			cs_n += 1
		coast_n = 0
		for feature in coast_features:
			coast_n += 1

		progress_count += 10
		self.progress.emit(progress_count)

		if coast_n > 0:

			# Get the features again, because in the loop above they reset.
			ss_features = masks_layer.getFeatures(QgsFeatureRequest(expr_ss))
			cs_features = masks_layer.getFeatures(QgsFeatureRequest(expr_cs))
			coast_features = masks_layer.getFeatures(QgsFeatureRequest(expr_coast))

			# Create temporary layers to store extracted masks
			ss_temp = QgsVectorLayer("Polygon?crs=epsg:4326", "Temporary ss", "memory")
			ss_prov = ss_temp.dataProvider()
			cs_temp = QgsVectorLayer("Polygon?crs=epsg:4326", "Temporary cs", "memory")
			cs_prov = cs_temp.dataProvider()
			coast_temp = QgsVectorLayer("Polygon?crs=epsg:4326", "Temporary coastline", "memory")
			coast_prov = coast_temp.dataProvider()

			# Add extracted features (masks) to the temporary layers
			ss_prov.addFeatures(ss_features)
			cs_prov.addFeatures(cs_features)
			coast_prov.addFeatures(coast_features)

			# Prepare the parameters for rasterization of the masks
			out_path = os.path.dirname(out_file_path)
			geotransform = bathy_ds.GetGeoTransform()  # geotransform is used for creating raster file of the mask layer
			nrows, ncols = np.shape(
				paleo_dem)  # number of columns and rows in the matrix for storing the rasterized file before saving it as a raster on the disk

			# Save the extracted masks to be able to rasterize them
			# TODO Figure out how to use in-memory vector layer to rasterize. The gdal.RasterizeLayer takes OGRLayerSadow, whereas in-memory layers are QgsVectorLayer.
			# Create a directory for the vector masks

			if not os.path.exists(os.path.join(out_path, "vector_masks")):
				os.makedirs(os.path.join(out_path, "vector_masks"))

			# Output files
			ss_out_file = os.path.join(out_path, "vector_masks", "Shallow_sea.shp")
			cs_out_file = os.path.join(out_path, "vector_masks", "Continental_shelves.shp")
			coast_out_file = os.path.join(out_path, "vector_masks", "Coastline.shp")

			layers = [(ss_temp, ss_out_file, "ShallowSea"), (cs_temp, cs_out_file, "ContinentalShelves"),
					  (coast_temp, coast_out_file, "Coastline")]

			progress_count += 10
			self.progress.emit(progress_count)

			for layer, out_file, name in layers:
				# Check if the file is already created. Acts like overwrite
				if os.path.exists(out_file):
					deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
					if deleted:
						pass
					else:
						self.log.emit("{} is not deleted.".format(out_file))

				error = QgsVectorFileWriter.writeAsVectorFormat(layer, out_file, "UTF-8", layer.crs(), "ESRI Shapefile")
				if error[0] == QgsVectorFileWriter.NoError:
					self.log.emit(
						"The  shape file {} has been created and saved successfully".format(os.path.basename(out_file)))
				else:
					self.log.emit(
						"The {} shapefile is not created because {}".format(os.path.basename(out_file), error[1]))
				if name == "ShallowSea":
					ss_temp = QgsVectorLayer(out_file, "Shallow sea masks", "ogr")
				elif name == "ContinentalShelves":
					cs_temp = QgsVectorLayer(out_file, "Continental Shelves masks", "ogr")
				elif name == "Coastline":
					coast_temp = QgsVectorLayer(out_file, "Continental Shelves masks", "ogr")

					progress_count += 4
					self.progress.emit(progress_count)

			# Rasterize extracted masks
			ss_mask = vector_to_raster(ss_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.progress.emit(progress_count)

			cs_mask = vector_to_raster(cs_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.progress.emit(progress_count)

			coast_mask = vector_to_raster(coast_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.progress.emit(progress_count)

			# Check if the shallow sea bathhymetry raster and shallow sea masks are defined.
			if self.dlg.selectSbathy.currentLayer() and ss_n > 0:
				# getting the shallow sea bathymetry
				s_bathy_layer = self.dlg.selectSbathy.currentLayer()
				sbathy_ds = gdal.Open(s_bathy_layer.dataProvider().dataSourceUri())
				s_bathy = sbathy_ds.GetRasterBand(1).ReadAsArray()

				# Modify bathymetry according to masks
				s_bathy[s_bathy < paleo_dem] = paleo_dem[
					s_bathy < paleo_dem]  # remove parts that are deeper than current bathymetry
				paleo_dem[ss_mask == 1] = s_bathy[ss_mask == 1]

				progress_count += 10
				self.progress.emit(progress_count)

			if self.dlg.selectSbathy.currentLayer() and cs_n > 0:
				# Replace continental shelf by shallow region depth where the latter is deeper and less than 2000m
				shelf_depth = self.dlg.shelfDepthBox.value()
				paleo_dem[cs_mask == 1] = shelf_depth
				paleo_dem[((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < shelf_depth)) == 1] = s_bathy[
					((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < shelf_depth)) == 1]

				progress_count += 10
				self.progress.emit(progress_count)

			# Fill the land area with the present day rotated topography

			# Read the Bedrock topography from the dialog
			topo = self.dlg.selectBrTopo.currentLayer()
			# Get the data provider to access the data
			topo_ds = gdal.Open(topo.dataProvider().dataSourceUri())
			# Read the data as a an array of data
			topo_br = topo_ds.GetRasterBand(1).ReadAsArray()
			paleo_dem[coast_mask == 1] = topo_br[coast_mask == 1]

			# Close all the temporary vector layers
			cs_temp = None
			ss_temp = None
			coast_temp = None

			# Remove the shapefiles of the temporary vector layers from the disk. Also remove the temporary folder created for them.
			temp_files = [ss_out_file, cs_out_file, coast_out_file]
			deleted_n = 0
			for out_file in temp_files:
				if os.path.exists(out_file):
					deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
					if deleted:
						deleted_n += 1

				progress_count += 5
				self.progress.emit(progress_count)

			if deleted_n > 2:
				if os.path.exists(os.path.join(out_path, "vector_masks")):
					shutil.rmtree(os.path.join(out_path, "vector_masks"))
				else:
					self.log.emit(
						'I created a temporary folder with some shapefiles: ' + os.path.join(out_path, "vector_masks"))
					self.log.emit('And could not delete it. You may delete it manually.')

				progress_count += 5
				self.progress.emit(progress_count)




		else:

			# getting the paleobathymetry layer
			bathy_layer = self.dlg.selectPaleoBathy.currentLayer()
			bathy_ds = gdal.Open(bathy_layer.dataProvider().dataSourceUri())
			paleo_bathy = bathy_ds.GetRasterBand(1).ReadAsArray()

			# creating a base grid for compiling topography and bathymetry
			paleo_dem = np.empty(paleo_bathy.shape)
			paleo_dem[:] = np.nan
			paleo_dem[paleo_bathy < 0] = paleo_bathy[paleo_bathy < 0]
			paleo_dem[paleo_bathy < -12000] = np.nan
			paleo_dem[paleo_bathy > 0] = 0

			progress_count += 20
			self.progress.emit(progress_count)

			# this line gets the user-defined directory for storing the output files and prepares some variables for rasterization process

			geotransform = bathy_ds.GetGeoTransform()  # geotransform is used for creating raster file of the mask layer
			nrows, ncols = np.shape(
				paleo_dem)  # number of columns and rows in the matrix for storing the rasterized file before saving it as a raster on the disk
			# Get the general masks layer from the dialog
			masks_layer = self.dlg.selectMasks.currentLayer()

			# Rasterize masks layer
			coast_mask = vector_to_raster(masks_layer, geotransform, ncols, nrows)

			progress_count += 20
			self.progress.emit(progress_count)

			# Fill the land area with the present day rotated topography

			# Read the Bedrock topography from the dialog
			topo = self.dlg.selectBrTopo.currentLayer()
			# Get the data provider to access the data
			topo_ds = gdal.Open(topo.dataProvider().dataSourceUri())
			# Read the data as an array of data
			topo_br = topo_ds.GetRasterBand(1).ReadAsArray()
			paleo_dem[coast_mask == 1] = topo_br[coast_mask == 1]

			progress_count += 27
			self.progress.emit(progress_count)

		if self.killed is True:
			self.finished.emit(False)
		else:
			nrows, ncols = np.shape(paleo_dem)
			geotransform = bathy_ds.GetGeoTransform()

			raster = gdal.GetDriverByName('GTiff').Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
			raster.SetGeoTransform(geotransform)
			crs = osr.SpatialReference()
			crs.ImportFromEPSG(4326)
			raster.SetProjection(crs.ExportToWkt())
			raster.GetRasterBand(1).WriteArray(paleo_dem)
			raster.GetRasterBand(1).SetNoDataValue(np.nan)
			raster = None

			self.progress.emit(100)
			self.log.emit(
				"The resulting raster is saved at: <a href='file://{}'>{}<a/>".format(os.path.dirname(out_file_path),
																					  out_file_path))
			self.finished.emit(True, out_file_path)

	def kill(self):
		self.killed = True









