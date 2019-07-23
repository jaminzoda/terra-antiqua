import os
import shutil
import tempfile

import numpy as np
import processing
from PyQt5.QtCore import QThread, pyqtSignal
from osgeo import gdal, osr
from qgis.core import QgsVectorFileWriter, QgsVectorLayer, QgsRasterLayer, QgsExpression, QgsFeatureRequest, \
	QgsWkbTypes, QgsGeometry, NULL, QgsFeature

from .topotools import ArrayTools as at
from .topotools import RasterTools as rt
from .topotools import VectorTools as vt


class TopoBathyCompiler(QThread):
	change_value = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed=False


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
		paleo_dem[paleo_bathy > 0] = -0.1 #Bring the values, which are above sea level down below sea level.

		progress_count += 5
		self.change_value.emit(progress_count)

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
			self.change_value.emit(progress_count)

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
		self.change_value.emit(progress_count)

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

			progress_count+=10
			self.change_value.emit(progress_count)

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
					self.log.emit("The  shape file {} has been created and saved successfully".format(os.path.basename(out_file)))
				else:
					self.log.emit("The {} shapefile is not created because {}".format(os.path.basename(out_file), error[1]))
				if name == "ShallowSea":
					ss_temp = QgsVectorLayer(out_file, "Shallow sea masks", "ogr")
				elif name == "ContinentalShelves":
					cs_temp = QgsVectorLayer(out_file, "Continental Shelves masks", "ogr")
				elif name == "Coastline":
					coast_temp = QgsVectorLayer(out_file, "Continental Shelves masks", "ogr")

					progress_count += 4
					self.change_value.emit(progress_count)

			# Rasterize extracted masks
			ss_mask = vt.vector_to_raster(ss_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.change_value.emit(progress_count)

			cs_mask = vt.vector_to_raster(cs_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.change_value.emit(progress_count)

			coast_mask = vt.vector_to_raster(coast_temp, geotransform, ncols, nrows)

			progress_count += 5
			self.change_value.emit(progress_count)



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
				self.change_value.emit(progress_count)

			if self.dlg.selectSbathy.currentLayer() and cs_n > 0:
				# Replace continental shelf by shallow region depth where the latter is deeper and less than 2000m
				shelf_depth = self.dlg.shelfDepthBox.value()
				paleo_dem[cs_mask == 1] = shelf_depth
				paleo_dem[((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < shelf_depth)) == 1] = s_bathy[
					((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < shelf_depth)) == 1]

				progress_count += 10
				self.change_value.emit(progress_count)

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

				progress_count+=5
				self.change_value.emit(progress_count)

			if deleted_n > 2:
				if os.path.exists(os.path.join(out_path, "vector_masks")):
					shutil.rmtree(os.path.join(out_path, "vector_masks"))
				else:
					self.log.emit(
						'I created a temporary folder with some shapefiles: ' + os.path.join(out_path, "vector_masks"))
					self.log.emit('And could not delete it. You may delete it manually.')

				progress_count += 5
				self.change_value.emit(progress_count)




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
			self.change_value.emit(progress_count)

			# this line gets the user-defined directory for storing the output files and prepares some variables for rasterization process

			geotransform = bathy_ds.GetGeoTransform()  # geotransform is used for creating raster file of the mask layer
			nrows, ncols = np.shape(
				paleo_dem)  # number of columns and rows in the matrix for storing the rasterized file before saving it as a raster on the disk
			# Get the general masks layer from the dialog
			masks_layer = self.dlg.selectMasks.currentLayer()

			# Rasterize masks layer
			coast_mask = vt.vector_to_raster(masks_layer, geotransform, ncols, nrows)

			progress_count += 20
			self.change_value.emit(progress_count)

			# Fill the land area with the present day rotated topography

			# Read the Bedrock topography from the dialog
			topo = self.dlg.selectBrTopo.currentLayer()
			# Get the data provider to access the data
			topo_ds = gdal.Open(topo.dataProvider().dataSourceUri())
			# Read the data as an array of data
			topo_br = topo_ds.GetRasterBand(1).ReadAsArray()
			paleo_dem[coast_mask == 1] = topo_br[coast_mask == 1]

			progress_count += 27
			self.change_value.emit(progress_count)

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

			self.change_value.emit(100)
			self.log.emit("The resulting raster is saved at: <a href='file://{}'>{}<a/>".format(os.path.dirname(out_file_path), out_file_path))
			self.finished.emit(True, out_file_path)

	def kill(self):
		self.killed = True


class MaskMaker(QThread):
	change_value = pyqtSignal(int)
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
			out_file_path = os.path.join(temp_dir, 'Extracted_general_masks.shp')
		else:
			out_file_path = self.dlg.outputPath.filePath()

		out_path = os.path.dirname(out_file_path)

		# Combining polygons and polylines

		# Get all the input layers
		# a) Coastline masks
		if self.dlg.selectCoastlineMask.currentLayer():
			coast_mask_layer = self.dlg.selectCoastlineMask.currentLayer()
		else:
			coast_mask_layer = None
		if self.dlg.selectCoastlineMaskLine.currentLayer():
			coast_mask_line_layer = self.dlg.selectCoastlineMaskLine.currentLayer()
		else:
			coast_mask_line_layer = None

		# b) Continental Shelves masks
		if self.dlg.selectCshMask.currentLayer():
			cs_mask_layer = self.dlg.selectCshMask.currentLayer()
		else:
			cs_mask_layer = None

		if self.dlg.selectCshMaskLine.currentLayer():
			cs_mask_line_layer = self.dlg.selectCshMaskLine.currentLayer()
		else:
			cs_mask_line_layer = None

		# c) Shallow sea masks

		if self.dlg.selectSsMask.currentLayer():
			ss_mask_layer = self.dlg.selectSsMask.currentLayer()
		else:
			ss_mask_layer = None
		if self.dlg.selectSsMaskLine.currentLayer():
			ss_mask_line_layer = self.dlg.selectSsMaskLine.currentLayer()
		else:
			ss_mask_line_layer = None

		# Create a list of input layers
		layers = [(ss_mask_layer, ss_mask_line_layer, "Shallow sea"),
				  (cs_mask_layer, cs_mask_line_layer, "Continental Shelves"),
				  (coast_mask_layer, coast_mask_line_layer, "Continents")]

		# Polygonize polylines and combine them with their polygon counterparts in one temp file

		#Send progress feedback
		progress_count += 5
		self.change_value.emit(progress_count)

		#Temporary layers assigned
		ss_temp = None
		cs_temp = None
		coast_temp = None
		for poly, line, name in layers:

			if self.killed:
				break

			if line is not None:
				# Creating a temporary layer to store features
				temp = QgsVectorLayer("Polygon?crs=epsg:4326", "shallow sea temp", "memory")
				temp_provider = temp.dataProvider()
				line_features = line.getFeatures()  # getting features from the polyline layer
				attr_line = line.dataProvider().fields().toList()
				temp_provider.addAttributes(attr_line)
				temp.updateFields()
				poly_features = []
				# this loop reads the geometries of all the polyline features and creates polygon features from the geometries
				for geom in line_features:
					# Get the geometry oof features
					line_geometry = geom.geometry()

					# checking if the geometry is polyline or multipolyline
					if line_geometry.wkbType() == QgsWkbTypes.LineString:
						line_coords = line_geometry.asPolyline()
					elif line_geometry.wkbType() == QgsWkbTypes.MultiLineString:
						line_coords = line_geometry.asMultiPolyline()
					else:
						self.log.emit("The geometry is neither polyline nor multipolyline")
					poly_geometry = QgsGeometry.fromPolygonXY(line_coords)
					feature = QgsFeature()
					feature.setGeometry(poly_geometry)
					feature.setAttributes(geom.attributes())
					poly_features.append(feature)
				temp_provider.addFeatures(poly_features)
				poly_features = None
				fixed_line = processing.run('native:fixgeometries', {'INPUT': temp, 'OUTPUT': 'memory:' + name})[
					'OUTPUT']
				self.log.emit("Invalid geometries in {}  have been fixed.".format(line.name()))

				self.log.emit("polylines in {} have been polygonized.".format(line.name()))
			else:
				pass
			# parameters for layer merging
			if poly is not None:
				fixed_poly = processing.run('native:fixgeometries', {'INPUT': poly, 'OUTPUT': 'memory:' + name})[
				'OUTPUT']
				self.log.emit("Invalid geometries in {} have been fixed.".format(poly.name()))

			if line is not None and poly is not None:
				#Refactor the field types, if they are different
				fixed_line_refactored, fields_refactored = vt.refactor_fields(fixed_line, fixed_poly)

				if len(fields_refactored) == 0:
					layers_to_merge = [fixed_poly, fixed_line]
				else:
					self.log.emit("The fields {} in {} are refactored".format(fields_refactored, fixed_line.name()))
					layers_to_merge = [fixed_poly, fixed_line_refactored]

				params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:' + name}
				temp_layer = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
				fixed_poly = None
				fixed_line = None
				self.log.emit("Polygonized polylines from {} are merged with polygons from {}.".format(line.name(),poly.name()))
			elif line is None and poly is not None:
				temp_layer = fixed_poly
				fixed_poly = None
			elif poly is None and line is not None:
				temp_layer = fixed_line
			else:
				temp_layer = None
			if temp_layer is not None:
				if name == "Shallow sea":
					ss_temp = temp_layer
					temp_layer = None

				elif name == "Continental Shelves":
					cs_temp = temp_layer
					temp_layer = None

				elif name == "Continents":
					coast_temp = temp_layer
					temp_layer = None


			# Send progress feedback
			progress_count += 10
			self.change_value.emit(progress_count)


		#Check if the cancel button was pressed
		if not self.killed:
			# Extracting masks by running difference algorithm
			# Parameters for difference algorithm
			if ss_temp is not None and cs_temp is not None:
				params = {'INPUT': ss_temp, 'OVERLAY': cs_temp, 'OUTPUT': 'memory:Shallow sea'}
				ss_extracted = processing.run('native:difference', params)["OUTPUT"]
				ss_temp = None  # remove shallow sea masks layer, becasue we don't need it anymore. This will release memory.
			else:
				ss_extracted = None

			# Send progress feedback
			progress_count += 10
			self.change_value.emit(progress_count)
			self.log.emit("Shallow sea masks extracted.")

		if not self.killed:
			if cs_temp is not None and coast_temp is not None:
				params = {'INPUT': cs_temp, 'OVERLAY': coast_temp, 'OUTPUT': 'memory:Continental Shelves'}
				cs_extracted = processing.run('native:difference', params)["OUTPUT"]
				cs_temp = None
			else:
				cs_extracted = None


			# Send progress feedback
			progress_count += 10
			self.change_value.emit(progress_count)
			self.log.emit("Continental shelf  masks extracted.")

		if not self.killed:
			# Combining the extracted masks in one shape file.
			if ss_extracted is not None and cs_extracted is not None:
				# Refactor the field types, if they are different
				ss_extracted_refactored, fields_refactored = vt.refactor_fields(ss_extracted, cs_extracted)

				if len(fields_refactored) == 0:
					layers_to_merge = [ss_extracted, cs_extracted]
				else:
					self.log.emit("The fields {} in {} are refactored".format(fields_refactored, ss_extracted.name()))
					layers_to_merge = [ss_extracted_refactored, cs_extracted]

				params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:ss+cs'}
				ss_and_cs_extracted = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
			else:
				ss_and_cs_extracted =None

			# Send progress feedback
			progress_count += 10
			self.change_value.emit(progress_count)

		if not self.killed:
			# Running difference algorithm to remove geometries that overlap with the coastlines
			if ss_and_cs_extracted is not None and coast_temp is not None:
				# Parameters for difference algorithm.
				params = {'INPUT': ss_and_cs_extracted, 'OVERLAY': coast_temp, 'OUTPUT': 'memory:ss+cs'}
				masks_layer = processing.run('native:difference', params)["OUTPUT"]
			else:
				masks_layer = None

			# Send progress feedback
			progress_count += 5
			self.change_value.emit(progress_count)

			self.log.emit("Continents masks extracted.")

		if not self.killed:
			if masks_layer is not None and coast_temp is not None:
				# Refactor the field types, if they are different
				masks_layer_refactored, fields_refactored = vt.refactor_fields(masks_layer, coast_temp)

				if len(fields_refactored) == 0:
					layers_to_merge = [masks_layer, coast_temp]
				else:
					self.log.emit("The fields {} in {} are refactored".format(fields_refactored, masks_layer.name()))
					layers_to_merge = [masks_layer_refactored, coast_temp]

				params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:Final extracted masks'}

				final_masks = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
			else:
				final_masks = coast_temp

			# Send progress feedback
			progress_count += 5
			self.change_value.emit(progress_count)
			self.log.emit("Masks merged in one layer.")


		#TODO When the file is loaded to the current QGIS project, it can't be deleted.
		# First check, if it is loaded to the current project, then remove it from the project before deleting.

		# Check if the file is already created. Acts like overwrite
		if os.path.exists(out_file_path):
			deleted = QgsVectorFileWriter.deleteShapeFile(out_file_path)
			if deleted:
				pass
			else:
				self.log.emit("The shapefile {} already exists, and I could not delete it.".format(out_file_path))
				self.log.emit("In order to run this tool successfully, remove this shapefile "
				              "from the current QGIS project or restart the QGIS.")



		if not self.killed:
			# Saving the results into a shape file
			error = QgsVectorFileWriter.writeAsVectorFormat(final_masks, out_file_path, "UTF-8", final_masks.crs(),
															"ESRI Shapefile")
			if error[0] == QgsVectorFileWriter.NoError:
				self.log.emit("The extracted general masks have been saved in a shapefile at: ")
				self.log.emit("<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
			else:
				self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file_path), error[1]))
				self.killed = True

		if not self.killed:
			self.change_value.emit(100)
			self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")



	def kill(self):
		self.killed = True


class TopoModifier(QThread):
	change_value = pyqtSignal(int)
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
			out_file_path = os.path.join(temp_dir, 'PaleoDEM_modified_topography.tif')
		else:
			out_file_path = self.dlg.outputPath.filePath()

		out_path = os.path.dirname(out_file_path)

		self.log.emit('The processing algorithm has started.')


		# Get the topography as an array

		self.log.emit('Getting the raster layer')
		topo_layer = self.dlg.baseTopoBox.currentLayer()
		topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
		topo = topo_ds.GetRasterBand(1).ReadAsArray()
		geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
		nrows, ncols = np.shape(topo)

		if topo is not None:
			self.log.emit(('Size of the Topography raster: ', str(topo.shape)))
		else:
			self.log.emit('There is a problem with reading the Topography raster')

		# Get the vector masks
		self.log.emit('Getting the vector layer')
		mask_layer = self.dlg.masksBox.currentLayer()

		#Send progress feedback
		progress_count += 3
		self.change_value.emit(progress_count)

		if mask_layer.isValid:
			self.log.emit('The mask layer is loaded properly')
		else:
			self.log.emit('There is a problem with the mask layer - not loaded properly')

		if not self.killed:
			if self.dlg.useAllMasksBox.isChecked():
				# Get features from the mask_layer
				features = mask_layer.getFeatures()
				feats = mask_layer.getFeatures()

				#Count features
				feats_count = 0
				for feat in feats:
					feats_count += 1


			# Modifying the topography raster with different formula for different masks
			else:
				# Get features by attribute from the masks layer - the attributes are fetched in the selected field.
				field = self.dlg.maskNameField.currentField()
				value = self.dlg.maskNameText.text()

				self.log.emit(('Fetching the ', value, ' masks from the field: ', field))

				#TODO add ability to specify several names for the masks
				expr = QgsExpression(QgsExpression().createFieldEqualityExpression(field, value))
				features = mask_layer.getFeatures(QgsFeatureRequest(expr))



				# Make sure if any feature is returned by our query above
				# If the field name or the name of mask is not specified correctly, our feature iterator (features)
				# will be empty and "any" statement will return false.

				assert (any(True for _ in features)), \
					"Your query did not return any record. Please, check if you specified correct field " \
					"for the names of masks, and that you have typed the name of a mask correctly."

				# Get the features in the feature iterator again, because during the assertion
				# we already iterated over the iterator and it is empty now.
				features = mask_layer.getFeatures(QgsFeatureRequest(expr))

				# Count features
				feats = mask_layer.getFeatures(QgsFeatureRequest(expr))
				feats_count = 0
				for feat in feats:
					feats_count += 1

		if not self.killed:
			# Create a directory for temporary vector files
			path = os.path.join(out_path, "vector_masks")

			# Send progress feedback
			progress_count += 3
			self.change_value.emit(progress_count)

			if not os.path.exists(path):
				try:
					os.mkdir(path)
				except OSError:
					self.log.emit("Creation of the directory %s failed" % path)
				else:
					self.log.emit("Successfully created the directory %s " % path)
			else:
				self.log.emit("The folder raster_masks is already created.")

			# Send progress feedback
			progress_count += 2
			self.change_value.emit(progress_count)

		if not self.killed:
			# Check if the formula mode of topography modification is checked
			# Otherwise minimum and maximum values will be used to calculate the formula
			if self.dlg.formulaCheckBox.isChecked():

				# Get the fields
				fields = mask_layer.fields().toList()

				# Get the field names to be able to fetch formulas from the attributes table
				field_names = [i.name() for i in fields]

				# If formula field is not selected, the whole topography
				# raster is modified with one formula, which is taken from the textbox in the dialog.
				# Check if formula field is specified.
				# The QgsFieldCombobox returns string with the name of field -
				# we check if it is empty - empty string = False (bool) in python
				if self.dlg.formulaField.currentField():
					formula_field = self.dlg.formulaField.currentField()
					# Get the position of the formula field in the table of attributes
					# This will help us to get the formula of a mask by it's position
					formula_pos = field_names.index(formula_field)
					formula = None
				else:
					formula = self.dlg.formulaText.text()
					formula_pos = None
					self.log.emit(('formula for topography modification is: ', formula))

				# Send progress feedback
				progress_count += 3
				self.change_value.emit(progress_count)

				# Get the minimum and maximum bounding values for selecting the elevation values that should be modified.
				# Values outside the bounding values will not be touched.
				if self.dlg.minMaxValuesFromAttrCheckBox.isChecked() and self.dlg.minValueField.currentField():
					min_value_field = self.dlg.minValueField.currentField()

					# Get the position of the formula field in the table of attributes
					# This will help us to get the formula of a mask by it's position
					min_value_pos = field_names.index(min_value_field)
					min_value = None

				elif self.dlg.minMaxValuesFromSpinCheckBox.isChecked():
					min_value = self.dlg.minValueSpin.value()
					min_value_field = None
					min_value_pos = None
				else:
					min_value = None
					min_value_field = None
					min_value_pos = None

				# Send progress feedback
				progress_count += 3
				self.change_value.emit(progress_count)

				if self.dlg.minMaxValuesFromAttrCheckBox.isChecked() and self.dlg.maxValueField.currentField():
					max_value_field = self.dlg.maxValueField.currentField()
					# Get the position of the formula field in the table of attributes
					# This will help us to get the formula of a mask by it's position
					max_value_pos = field_names.index(max_value_field)
					max_value = None
				elif self.dlg.minMaxValuesFromSpinCheckBox.isChecked():
					max_value = self.dlg.maxValueSpin.value()
					max_value_field = None
					max_value_pos = None
				else:
					max_value = None
					max_value_field = None
					max_value_pos = None

				# Send progress feedback
				progress_count += 4
				self.change_value.emit(progress_count)

				mask_number = 0
				for feat in features:
					if self.killed:
						break
					mask_number += 1
					# Get the formula, min and max values, if they are different for each feature.
					if formula is None:
						feat_formula = feat.attributes()[formula_pos]
					else:
						feat_formula = formula

					# Check if the formula field contains the formula
					if feat_formula == NULL or ('x' in feat_formula) is False:
						self.log.emit("Mask " + str(mask_number) + " does not contain any formula.")
						self.log.emit("You might want to check if the field for formula is "
							"specified correctly in the plugin dialog.")
						continue
					if min_value is None and min_value_field is not None:
						feat_min_value = feat.attributes()[min_value_pos]
					elif min_value is None:
						feat_min_value = None
					else:
						feat_min_value = min_value

					if max_value is None and max_value_field is not None:
						feat_max_value = feat.attributes()[max_value_pos]
					elif max_value is None:
						feat_max_value = None
					else:
						feat_max_value = max_value

					# Create a temporary layer to store the extracted masks
					temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
					temp_dp = temp_layer.dataProvider()
					temp_dp.addAttributes(fields)
					temp_layer.updateFields()

					temp_dp.addFeature(feat)

					# Create a temporary shapefile to store extracted masks before rasterizing them
					out_file = os.path.join(path, 'masks_for_topo_modification.shp')

					if os.path.exists(out_file):
						deleted = QgsVectorFileWriter.deleteShapeFile(out_file)

					error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8",
																	temp_layer.crs(), "ESRI Shapefile")
					if error[0] == QgsVectorFileWriter.NoError:
						self.log.emit("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
					else:
						self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file), error[1]))

					# Rasterize extracted masks
					v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
					r_masks = vt.vector_to_raster(v_layer, geotransform, ncols, nrows)
					v_layer = None

					# Modify the topography
					x = topo
					in_array = x[r_masks == 1]
					x[r_masks == 1] = at.mod_formula(in_array, feat_formula, feat_min_value, feat_max_value)

					# Send progress feedback
					progress_count += 70/feats_count
					self.change_value.emit(progress_count)

			else:
				# Get the final minimum and maximum values either from a
				# specified field in the attribute table or from the spinboxes.
				if self.dlg.minMaxFromAttrCheckBox.isChecked():
					# Get the fields from the layer
					fields = mask_layer.fields().toList()
					# Get the field names to be able to fetch minimum and maximum values from the attributes table
					field_names = [i.name() for i in fields]
					# Get the names of fields with the minimum and maximum values.
					fmin_field = self.dlg.minField.currentField()
					fmax_field = self.dlg.maxField.currentField()
					# Get the position of the minimum and maximum fields in the table of attributes
					# This will help us to get the values of a mask by their positions
					fmin_pos = field_names.index(fmin_field)
					fmax_pos = field_names.index(fmax_field)

					# Send progress feedback
					progress_count += 5
					self.change_value.emit(progress_count)

					mask_number = 0
					for feat in features:
						if self.killed:
							break
						mask_number += 1
						fmin = feat.attributes()[fmin_pos]
						fmax = feat.attributes()[fmax_pos]
						# Check if the min and max fields contain any value
						if fmin == NULL or fmax == NULL:
							self.log.emit("Mask " + str(mask_number) +
								" does not contain final maximum or/and minimum values specified in the attributes table.")
							self.log.emit("You might want to check if the fields for minimum and "
								"maximum values are specified correctly in the plugin dialog.")
							continue

						# Create a temporary layer to store the extracted masks
						temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
						temp_dp = temp_layer.dataProvider()
						temp_dp.addAttributes(fields)
						temp_layer.updateFields()

						temp_dp.addFeature(feat)

						# Create a temporary shapefile to store extracted masks before rasterizing them
						out_file = os.path.join(path, 'masks_for_topo_modification.shp')

						if os.path.exists(out_file):
							deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
						error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8",
																		temp_layer.crs(), "ESRI Shapefile")
						if error[0] == QgsVectorFileWriter.NoError:
							self.log.emit("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
						else:
							self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file),
																					   error[1]))

						# Rasterize extracted masks
						v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
						r_masks = vt.vector_to_raster(v_layer, geotransform, ncols, nrows)
						v_layer = None

						# Modify the topography
						x = topo
						in_array = x[r_masks == 1]
						self.log.emit(in_array)
						x[r_masks == 1] = at.mod_min_max(in_array, fmin, fmax)

						# Send progress feedback
						progress_count += 75 / feats_count
						self.change_value.emit(progress_count)
				else:
					if not self.killed:
						fmin = self.dlg.minSpin.value()
						fmax = self.dlg.maxSpin.value()

						# Create a temporary layer to store the extracted masks
						temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
						temp_dp = temp_layer.dataProvider()
						temp_dp.addFeatures(features)

						# Send progress feedback
						progress_count += 10
						self.change_value.emit(progress_count)

						# Create a temporary shapefile to store extracted masks before rasterizing them
						out_file = os.path.join(path, 'masks_for_topo_modification.shp')

						if os.path.exists(out_file):
							deleted = QgsVectorFileWriter.deleteShapeFile(out_file)

						error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8",
																		temp_layer.crs(), "ESRI Shapefile")


						if error == QgsVectorFileWriter.NoError:
							self.log.emit("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
						else:
							self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file), error[1]))

						# Send progress feedback
						progress_count += 10
						self.change_value.emit(progress_count)

					if not self.killed:
						# Rasterize extracted masks
						v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
						r_masks = vt.vector_to_raster(v_layer, geotransform, ncols, nrows)
						v_layer = None

						# Send progress feedback
						progress_count += 30
						self.change_value.emit(progress_count)

					if not self.killed:
						# Modify the topography
						x = topo
						in_array = x[r_masks == 1]
						x[r_masks == 1] = at.mod_min_max(in_array, fmin, fmax)

						# Send progress feedback
						progress_count += 30
						self.change_value.emit(progress_count)

		# Delete temporary files and folders
		self.log.emit('Trying to delete the temporary files and folders.')

		if os.path.exists(out_file):
			deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
			if deleted:
				self.log.emit(
					"The {} shapefile is deleted successfully.".format(os.path.basename(out_file)))
			else:
				self.log.emit("The {} shapefile is NOT deleted.".format(os.path.basename(out_file)))

		if os.path.exists(path):
			try:
				shutil.rmtree(path)
			except OSError:
				self.log.emit("The directory {} is not deleted.".format(path))
			else:
				self.log.emit("The directory {} is successfully deleted".format(path))

		# Send progress feedback
		progress_count += 5
		self.change_value.emit(progress_count)

		if not self.killed:
			# Check if raster was modified. If the x matrix was assigned.
			if 'x' in locals():
				# Write the resulting raster array to a raster file
				driver = gdal.GetDriverByName('GTiff')
				if os.path.exists(out_file_path):
					driver.Delete(out_file_path)

				raster = driver.Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
				raster.SetGeoTransform(geotransform)
				crs = osr.SpatialReference()
				crs.ImportFromEPSG(4326)
				raster.SetProjection(crs.ExportToWkt())
				raster.GetRasterBand(1).WriteArray(x)
				raster = None
				self.finished.emit(True, out_file_path)
				progress_count = 100
				self.change_value.emit(progress_count)
			else:
				self.log.emit("The plugin did not succeed because one or more parameters were set incorrectly.")
				self.log.emit("Please, check the log above.")
				self.finished.emit(False, "")
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True


class PaleoShorelines(QThread):
	change_value = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False

	def run(self):
		# Get the output path
		if not self.dlg.outputPath.filePath():
			temp_dir = tempfile.gettempdir()
			out_file_path = os.path.join(temp_dir, 'PaleoDEM_Paleoshorelines_set.tif')
		else:
			out_file_path = self.dlg.outputPath.filePath()

		progress_count = 0

		self.log.emit('Starting')

		self.dlg.Tabs.setCurrentIndex(1)

		self.log.emit('Getting the raster layer')
		topo_layer = self.dlg.baseTopoBox.currentLayer()
		topo_extent = topo_layer.extent()
		topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
		topo = topo_ds.GetRasterBand(1).ReadAsArray()
		geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
		nrows, ncols = np.shape(topo)

		#Get the elevation and depth constrains
		max_elev = self.dlg.maxElevSpinBox.value()
		max_depth = self.dlg.maxDepthSpinBox.value()

		progress_count += 10
		self.change_value.emit(progress_count)

		if topo is not None:
			self.log.emit(('Size of the Topography raster: {}'.format(topo.shape)))
		else:
			self.log.emit('There is a problem with reading the Topography raster')

		# Get the vector masks
		self.log.emit('Getting the vector layer')
		mask_layer = self.dlg.masksBox.currentLayer()

		if mask_layer.isValid:
			self.log.emit('The mask layer is loaded properly')
		else:
			self.log.emit('There is a problem with the mask layer - not loaded properly')

		progress_count += 10
		self.change_value.emit(progress_count)
		if not self.killed:
			r_masks = vt.vector_to_raster(mask_layer, geotransform, ncols, nrows)
			# The bathymetry values that are above sea level are taken down below sea level
			in_array = topo[(r_masks == 0) * (topo > 0) == 1]
			topo[(r_masks == 0) * (topo > 0) == 1] = at.mod_rescale(in_array, max_depth, -0.1)

			progress_count += 30
			self.change_value.emit(progress_count)

		if not self.killed:
			# The topography values that are below sea level are taken up above sea level
			in_array = topo[(r_masks == 1) * (topo < 0) == 1]
			topo[(r_masks == 1) * (topo < 0) == 1] = at.mod_rescale(in_array, 0.1, max_elev)

			progress_count += 30
			self.change_value.emit(progress_count)

		if not self.killed:
			# Check if raster was modified. If the x matrix was assigned.
			if 'topo' in locals():

				driver = gdal.GetDriverByName('GTiff')
				if os.path.exists(out_file_path):
					driver.Delete(out_file_path)

				raster = driver.Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
				raster.SetGeoTransform(geotransform)
				crs = osr.SpatialReference()
				crs.ImportFromEPSG(4326)
				raster.SetProjection(crs.ExportToWkt())
				raster.GetRasterBand(1).WriteArray(topo)
				raster = None

				progress_count += 10
				self.change_value.emit(progress_count)

				self.log.emit("The raster was modified successfully and saved at: <a href='file://{}'>{}</a>.".format(
					os.path.dirname(out_file_path), out_file_path))

				self.finished.emit(True, out_file_path)

				self.change_value.emit(100)

			else:
				self.log.emit("The plugin did not succeed because one or more parameters were set incorrectly.")
				self.log.emit("Please, check the log above.")
				self.finished.emit(False, "")
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True


class StandardProcessing(QThread):
	change_value = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False

	def run(self):
		progress_count = 0

		self.log.emit("Starting the processing...")
		processing_type = self.dlg.fillingTypeBox.currentIndex()

		#Getting the ouput path
        #TODO Must check if the path is a valid path. In case the user inputs the name of the file but not the full path.
		if not self.dlg.outputPath.filePath():
			temp_dir = tempfile.gettempdir()
			if processing_type == 0:
				out_file_path = os.path.join(temp_dir, 'PaleoDEM_interpolated.tif')
			elif processing_type == 1:
				out_file_path = os.path.join(temp_dir, 'PaleoDEM_with_copied_values.tif')
			elif processing_type == 2:
				out_file_path = os.path.join(temp_dir, 'PaleoDEM_smoothed.tif')
			elif processing_type == 3:
				out_file_path = os.path.join(temp_dir, 'PaleoDEM_isostat_compensated.tif')
		else:
			out_file_path = self.dlg.outputPath.filePath()

		if processing_type == 0:
			if not self.killed:
				#rt.progress_changed.connect(self.set_change_value)
				self.log.emit("Getting the raster layer for the interpolation.")
				base_raster_layer = self.dlg.baseTopoBox.currentLayer()
				progress_count += 5
				self.change_value.emit(progress_count)
				self.log.emit("Starting the interpolation.")
				self.log.emit("Interpolation method is Inverse Distance Weighting.")
				interpolated_raster = rt.fill_no_data(base_raster_layer, out_file_path)
				self.log.emit("Interpolation finished.")

				progress_count += 40
				self.change_value.emit(progress_count)
			if not self.killed:

				if self.dlg.smoothingBox.isChecked():
					self.log.emit("Starting smoothing.")
					# Get the layer for smoothing
					interpolated_raster_layer = QgsRasterLayer(interpolated_raster, 'Interpolated DEM', 'gdal')

					# Get smoothing factor
					sm_factor = self.dlg.smFactorSpinBox.value()

					progress_count += 10
					self.change_value.emit(progress_count)

					# Smooth the raster
					rt.raster_smoothing(interpolated_raster_layer, sm_factor)
					self.log.emit("Smoothing has finished.")

					#progress_count += 40

					self.log.emit("The gaps in the raster were filled and it was smoothed successfully.")
					self.log.emit("The resulting layer is saved at: "
					              "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path),out_file_path))
					self.change_value.emit(100)
					self.finished.emit(True, out_file_path)

				else:
					self.log.emit("The gaps in the raster were filled successfully.")
					self.log.emit("The resulting layer is saved at: "
					              "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
					self.change_value.emit(100)
					self.finished.emit(True, out_file_path)
			else:
				self.finished.emit(False, "")


		elif processing_type == 1:
			self.log.emit("Starting to copy the elevation values from another raster.")
			if not self.killed:

				# Get a raster layer to copy the elevation values FROM
				self.log.emit("Getting the raster layer to copy the elevation values from.")
				from_raster_layer = self.dlg.copyFromRasterBox.currentLayer()
				from_raster = gdal.Open(from_raster_layer.dataProvider().dataSourceUri())
				from_array = from_raster.GetRasterBand(1).ReadAsArray()
				progress_count += 10
				self.change_value.emit(progress_count)
			if not self.killed:
				# Get a raster layer to copy the elevation values TO
				self.log.emit("Getting the raster to copy the elevation values to.")
				to_raster_layer = self.dlg.baseTopoBox.currentLayer()
				to_raster = gdal.Open(to_raster_layer.dataProvider().dataSourceUri())
				to_array = to_raster.GetRasterBand(1).ReadAsArray()
				progress_count += 10
				self.change_value.emit(progress_count)

			if not self.killed:
				self.log.emit("Getting the masks from the vector layer.")
				# Get a vector containing masks
				mask_vector_layer = self.dlg.masksBox.currentLayer()



				self.log.emit("Rasterizing the masks from the vector layer.")
				# Rasterize masks
				geotransform = to_raster.GetGeoTransform()
				nrows, ncols = to_array.shape
				mask_array = vt.vector_to_raster(mask_vector_layer, geotransform, ncols, nrows)

				self.log.emit("The masks are rasterized.")
				progress_count += 40
				self.change_value.emit(progress_count)
			if not self.killed:
				self.log.emit("Copying the elevation values.")
				# Fill the raster
				to_array[mask_array == 1] = from_array[mask_array == 1]
				progress_count += 20
				self.change_value.emit(progress_count)

			if not self.killed:
				self.log.emit("Saving the resulting raster.")
				# Create a new raster for the result
				output_raster = gdal.GetDriverByName('GTiff').Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
				output_raster.SetGeoTransform(geotransform)
				crs = to_raster_layer.crs()
				output_raster.SetProjection(crs.toWkt())
				output_band = output_raster.GetRasterBand(1)
				output_band.SetNoDataValue(np.nan)
				output_band.WriteArray(to_array)
				output_band.FlushCache()
				output_raster = None

				self.change_value.emit(100)
				self.log.emit("The ellevation values were successfully copied.")
				self.log.emit("The the resulting layer was saved at: "
				              "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
				self.finished.emit(True, out_file_path)
			else:
				self.finished.emit(False, "")


		elif processing_type == 2:
			self.log.emit("Starting smoothing...")
			if not self.killed:

				self.log.emit("Getting the raster layer to smooth.")
				raster_to_smooth_layer = self.dlg.baseTopoBox.currentLayer()
				smoothing_factor = self.dlg.smFactorSpinBox.value()
				output_file = self.dlg.outputPath.filePath()
				progress_count += 20
				self.change_value.emit(progress_count)
			if not self.killed:
				self.log.emit("Smoothing the raster.")
				smoothed_raster_layer = rt.raster_smoothing(raster_to_smooth_layer, smoothing_factor, out_file_path)
				self.log.emit("The raster is smoothed successfully and saved at: "
				              "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
				self.change_value.emit(100)
				self.finished.emit(True, out_file_path)
			else:
				self.finished.emit(False, "")



		elif processing_type == 3:
			self.log.emit("Starting isostatic compensation of Greenland and Antarctic...")
			# Get the bedrock topography raster
			if not self.killed:
				self.log.emit("Getting the bedrock topography raster layer.")
				topo_br_layer = self.dlg.baseTopoBox.currentLayer()
				topo_br_ds = gdal.Open(topo_br_layer.dataProvider().dataSourceUri())
				topo_br_data = topo_br_ds.GetRasterBand(1).ReadAsArray()
				progress_count += 5
				self.change_value.emit(progress_count)

			if not self.killed:
				self.log.emit("Getting the ice topography raster layer.")
				# Get the ice surface topography raster
				topo_ice_layer = self.dlg.selectIceTopoBox.currentLayer()
				topo_ice_ds = gdal.Open(topo_ice_layer.dataProvider().dataSourceUri())
				topo_ice_data = topo_ice_ds.GetRasterBand(1).ReadAsArray()
				progress_count += 5
				self.change_value.emit(progress_count)
			if not self.killed:
				# Get the masks
				self.log.emit("Getting the mask layer.")
				mask_layer = self.dlg.masksBox.currentLayer()
				progress_count += 5
				self.change_value.emit(progress_count)


			if self.dlg.masksFromCoastCheckBox.isChecked():

				if not self.killed:
					self.log.emit("Retrieving the masks with the following names (case insensitive): "
					              "Greeanland,"
					              "Antarctic (Including East Antarctic and Antarctic peninsula),"
					              "Matie Byrd Land, "
					              "Ronne Ice Shelf, "
					              "Thurston Island, "
					              "and Admundsen Terrane.")
					# Get features from the masks layer
					expr = QgsExpression(
						"lower(\"NAME\") LIKE '%greenland%' OR lower(\"NAME\") LIKE '%antarctic%' OR lower(\"NAME\") LIKE '%marie byrd%' OR lower(\"NAME\") LIKE '%ronne ice%' OR lower(\"NAME\") LIKE '%thurston%' OR lower(\"NAME\") LIKE '%admundsen%'")

					features = mask_layer.getFeatures(QgsFeatureRequest(expr))
					temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
					temp_prov = temp_layer.dataProvider()
					temp_prov.addFeatures(features)

					progress_count += 5
					self.change_value.emit(progress_count)



				if not self.killed:

					path = os.path.join(os.path.dirname(out_file_path), 'vector_masks')
					self.log.emit("Creating a temporary folder to save extracted masks for rasterization at: {}.".format(path))
					if not os.path.exists(path):
						try:
							os.mkdir(path)
						except OSError:
							self.log.emit("Creation of the directory %s failed" % path)
						else:
							self.log.emit("Successfully created the directory %s " % path)

					out_file = os.path.join(path, 'isostat_comp_masks.shp')
					self.log.emit("The shapefile {} already exists in the {} folder, therefore I am deleting it.".format(out_file, path))
					if os.path.exists(out_file):
						# function deleteShapeFile return bool True iif deleted False if not
						deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
						if deleted:
							self.log.emit(out_file + "has been deleted.")
						else:
							self.log.emit(out_file + "is not deleted.")

					progress_count += 5
					self.change_value.emit(progress_count)

					error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8", mask_layer.crs(),
																	"ESRI Shapefile")
					if error[0] == QgsVectorFileWriter.NoError:
						self.log.emit("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
					else:
						self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file), error[1]))

					progress_count += 5
					self.change_value.emit(progress_count)

				if not self.killed:
					self.log.emit("Rasterizing exrtacted masks.")
					# Rasterize extracted masks
					geotransform = topo_br_ds.GetGeoTransform()
					nrows, ncols = np.shape(topo_br_data)
					v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
					r_masks = vt.vector_to_raster(v_layer, geotransform, ncols, nrows)

					progress_count += 10
					self.change_value.emit(progress_count)

					# Close  the temporary vector layer
					v_layer = None

					# Remove the shapefile of the temporary vector layer from the disk. Also remove the temporary folder created for it.
					self.log.emit("Removing the temporary shapefile created for rasterization.")
					if os.path.exists(out_file):
						deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
						if deleted:
							if os.path.exists(path):
								shutil.rmtree(path)
							else:
								self.log.emit('I created a temporary folder with a shapefile at: ' + os.path.join(path))
								self.log.emit('And could not delete it. You may need delete it manually.')
					progress_count += 5
					self.change_value.emit(progress_count)

			else:
				if not self.killed:
					geotransform = topo_br_ds.GetGeoTransform()
					nrows, ncols = np.shape(topo_br_data)
					self.log.emit("Rasterizing the masks.")
					r_masks = vt.vector_to_raster(mask_layer, geotransform, ncols, nrows)

					progress_count += 30
					self.change_value.emit(progress_count)
			if not self.killed:
				# Compensate for ice load
				self.log.emit("Compensating for ice load.")
				rem_amount = self.dlg.iceAmountSpinBox.value()  # the amount of ice that needs to be removed.
				comp_factor = 0.3 * (topo_ice_data[r_masks == 1] - topo_br_data[r_masks == 1]) * rem_amount / 100
				comp_factor[np.isnan(comp_factor)] = 0
				comp_factor[comp_factor < 0] = 0
				topo_br_data[r_masks == 1] = topo_br_data[r_masks == 1] + comp_factor
				progress_count += 30
				self.change_value.emit(progress_count)
			if not self.killed:
				# Create a new raster for the result
				self.log.emit("Saving the resulting layer.")
				output_raster = gdal.GetDriverByName('GTiff').Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
				output_raster.SetGeoTransform(geotransform)
				crs = topo_br_layer.crs()
				output_raster.SetProjection(crs.toWkt())
				output_band = output_raster.GetRasterBand(1)
				output_band.SetNoDataValue(np.nan)
				output_band.WriteArray(topo_br_data)
				output_band.FlushCache()
				output_raster = None

				self.log.emit("The topography is compensated for the ice load successfully and the result is saved at: "
				              "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
				self.change_value.emit(100)
				self.finished.emit(True, out_file_path)
			else:
				self.finished.emit(False, "")


	def kill(self):
		self.killed = True

	def set_change_value(self, value):
		self.change_value.emit(value)
