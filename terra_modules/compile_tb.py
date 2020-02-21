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

from .utils import vectorToRaster, modRescale, bufferAroundGeometries



class TaCompileTopoBathy(QThread):
	progress = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False
		self.temp_dir = None
		self.ouput = None
		self.progress_count = 0
		self.masks_layer = None
		self.topo_layer = None
		self.bathy_layer = None
		self.ocean_age_layer = None
		self.s_bathy_layer = None
		self.crs = None
		self.reconstruction_time = None
		self.shelf_depth = None
		self.remove_overlap = None
	
	def getParameters(self):
		if not self.killed:
			# Get the path of the output file
			if not self.dlg.outputPath.filePath():
				self.temp_dir = tempfile.gettempdir()
				self.output = os.path.join(self.temp_dir, 'Compiled_DEM_Topo+Bathy.tif')
			else:
				self.output = self.dlg.outputPath.filePath()
		
		if not self.killed:
			# Get the general masks layer from the dialog
			self.masks_layer = self.dlg.selectMasks.currentLayer()
			if self.masks_layer.isValid() and self.masks_layer.featureCount()>0:
				self.log.emit("The layer with continental blocks is loaded properly.")
			elif self.masks_layer.isValid() and self.masks_layer.featureCount()==0:
				self.log.emit("Error: The continental blocks' layer is empty. Please, add polygon features in it and try again.")
				self.kill()
			else:
				self.log.emit("Error: The masks layer is not valid. Please, select a valid layer.")
			
		if not self.killed:
			# Read the Bedrock topography from the dialog
			self.topo_layer = self.dlg.selectBrTopo.currentLayer()
			if self.topo_layer.isValid():
				self.log.emit("The topography raster layer is loaded properly.")
			else:
				self.log.emit("Error: The topography raster layer is not valid. Please select a valid raster layer.")
				self.kill()
				
		if not self.killed:
			# getting the paleobathymetry layer
		
			self.bathy_layer = self.dlg.selectPaleoBathy.currentLayer()
			if self.bathy_layer.isValid():
				self.log.emit("The bathymetry raster layer is loaded properly.")
			else:
				self.log.emit("Error: The bathymetry raster layer is not valid. Please select a valid raster layer.")
				self.kill()
		
		if not self.killed:
			# getting ocean age layer
			if self.dlg.selectOceanAge.currentLayer():
				
				self.ocean_age_layer = self.dlg.selectOceanAge.currentLayer()
				if self.ocean_age_layer.isValid():
					self.log.emit("The ocean age layer is loaded properly.")
				else:
					self.log.emit("Warning: The ocean age layer is not valid. Please, select a valid layer." )
		
		if not self.killed:
			# getting the shallow sea bathymetry
			if self.dlg.selectSbathy.currentLayer():
				
				self.s_bathy_layer = self.dlg.selectSbathy.currentLayer()
				if self.s_bathy_layer.isValid():
					self.log.emit("The shallow sea bathymetry layer is loaded properly.")
				else:
					self.log.emit("Warning: The shallow sea bathymetry  layer is not valid. Please, select a valid layer." )

		if not self.killed:
			#getting the topography layer coordinate reference system (crs)
			self.crs = self.topo_layer.crs()
			self.reconstruction_time = self.dlg.ageBox.value()
			self.shelf_depth = self.dlg.shelfDepthBox.value()

		if not self.killed:
			#Remove overlapping bethymetry? This option is intended to remove overlapping bathymetry. 
			#Overlaping bathymetry emerges when for an area between tectonic blocks we get an empty area, 
			#which has bethymetry values coming from the bathymetry raster. 
			if self.dlg.removeOverlapBathyCheckBox.isChecked():
				self.remove_overlap = True
			else:
				self.remove_overlap = False



	def run(self):
		self.log.emit("Reading the input data and parameters...")
		self.getParameters()
				
		if not self.killed:
			bathy_ds = gdal.Open(self.bathy_layer.dataProvider().dataSourceUri())
			paleo_bathy = bathy_ds.GetRasterBand(1).ReadAsArray()
	
			# creating a base grid for compiling topography and bathymetry
			paleo_dem = np.empty(paleo_bathy.shape)
			paleo_dem[:] = np.nan
			# Copy the bathymetry to the base grid. Values above sea level are set to 0.
			paleo_dem[paleo_bathy < 0] = paleo_bathy[paleo_bathy < 0]
			paleo_dem[paleo_bathy > 0] = -0.1  # Bring the values, which are above sea level down below sea level.

			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			if self.ocean_age_layer:
				
				age_ds = gdal.Open(self.ocean_age_layer.dataProvider().dataSourceUri())
				ocean_age = age_ds.GetRasterBand(1).ReadAsArray()
	
				# create an empty array to store calculated ocean depth from age.
				ocean_depth = np.empty(paleo_bathy.shape)
				ocean_depth[:] = np.nan
				
	
				# calculate ocean age
				ocean_age[ocean_age > 0] = ocean_age[ocean_age > 0] - self.reconstruction_time
				ocean_depth[ocean_age > 0] = -2620 - 330 * (np.sqrt(ocean_age[ocean_age > 0]))
				ocean_depth[ocean_age > 90] = -5750
				# Update the bathymetry, keeping mueller only where agegrid is undefined
				paleo_dem[np.isfinite(ocean_depth)] = ocean_depth[np.isfinite(ocean_depth)]
	
				self.progress_count += 5
				self.progress.emit(self.progress_count)
	
			else:
				pass

		
		if not self.killed:
			# Get features by attribute from the masks layer - the attributes are fetched in the 'layer' field
			expr_ss = QgsExpression("\"layer\"='Shallow sea'")
			expr_cs = QgsExpression("\"layer\"='Continental Shelves'")
			expr_coast = QgsExpression("\"layer\"='Continents'")
	
			ss_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_ss))
			cs_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_cs))
			coast_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_coast))
	
			ss_n = 0
			for feature in ss_features:
				ss_n += 1
	
			cs_n = 0
			for feature in cs_features:
				cs_n += 1
			coast_n = 0
			for feature in coast_features:
				coast_n += 1
	
			self.progress_count += 10
			self.progress.emit(self.progress_count)
		if not self.killed:
			if coast_n > 0:
	
				# Get the features again, because in the loop above they reset.
				ss_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_ss))
				cs_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_cs))
				coast_features = self.masks_layer.getFeatures(QgsFeatureRequest(expr_coast))
	
				# Create temporary layers to store extracted masks
				ss_temp = QgsVectorLayer("Polygon?crs={}".format(self.crs.authid()), "Temporary ss", "memory")
				ss_prov = ss_temp.dataProvider()
				cs_temp = QgsVectorLayer("Polygon?crs={}".format(self.crs.authid()), "Temporary cs", "memory")
				cs_prov = cs_temp.dataProvider()
				coast_temp = QgsVectorLayer("Polygon?crs={}".format(self.crs.authid()), "Temporary coastline", "memory")
				coast_prov = coast_temp.dataProvider()
	
				# Add extracted features (masks) to the temporary layers
				ss_prov.addFeatures(ss_features)
				cs_prov.addFeatures(cs_features)
				coast_prov.addFeatures(coast_features)
	
				# Prepare the parameters for rasterization of the masks
				out_path = os.path.dirname(self.output)
				geotransform = bathy_ds.GetGeoTransform()  # geotransform is used for creating raster file of the mask layer
				nrows, ncols = np.shape(
					paleo_dem)  # number of columns and rows in the matrix for storing the rasterized file before saving it as a raster on the disk
				
				if not self.killed:
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
		
					self.progress_count += 10
					self.progress.emit(self.progress_count)
		
					for layer, out_file, name in layers:
						if self.killed:
							break
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
		
							self.progress_count += 4
							self.progress.emit(self.progress_count)
			
				if not self.killed:
		
					# Rasterize extracted masks
					ss_mask = vectorToRaster(
						ss_temp, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)
		
					self.progress_count += 5
					self.progress.emit(self.progress_count)
		
					cs_mask = vectorToRaster(
						cs_temp, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)
		
					self.progress_count += 5
					self.progress.emit(self.progress_count)
		
					coast_mask = vectorToRaster(
						coast_temp, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)
		
					self.progress_count += 5
					self.progress.emit(self.progress_count)
				
				if not self.killed:
		
					# Check if the shallow sea bathhymetry raster and shallow sea masks are defined.
					if self.s_bathy_layer and ss_n > 0:
						
						sbathy_ds = gdal.Open(self.s_bathy_layer.dataProvider().dataSourceUri())
						s_bathy = sbathy_ds.GetRasterBand(1).ReadAsArray()
		
						# Modify bathymetry according to masks
						s_bathy[s_bathy < paleo_dem] = paleo_dem[
							s_bathy < paleo_dem]  # remove parts that are deeper than current bathymetry
						paleo_dem[ss_mask == 1] = s_bathy[ss_mask == 1]
		
						self.progress_count += 10
						self.progress.emit(self.progress_count)
				
				if not self.killed:
					if self.s_bathy_layer and cs_n > 0:
						# Replace continental shelf by shallow region depth where the latter is deeper and less than 2000m
						
						paleo_dem[cs_mask == 1] = self.shelf_depth
						paleo_dem[((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < self.shelf_depth)) == 1] = s_bathy[
							((cs_mask == 1) * (s_bathy > -2000) * (s_bathy < self.shelf_depth)) == 1]
		
						self.progress_count += 10
						self.progress.emit(self.progress_count)
		
					# Fill the land area with the present day rotated topography
		
				if not self.killed:
					# Get the data provider to access the data
					topo_ds = gdal.Open(self.topo_layer.dataProvider().dataSourceUri())
					# Read the data as a an array of data
					topo_br = topo_ds.GetRasterBand(1).ReadAsArray()
					paleo_dem[coast_mask == 1] = topo_br[coast_mask == 1]

				# This is needed to remove bathymetry between continental blocks inside the coastlines area. 	
				if not self.killed:
					if self.remove_overlap:
						buffer_layer = bufferAroundGeometries(coast_temp, 0.5, 100)
						buffer_array = vectorToRaster(
							buffer_layer, 
							geotransform, 
							ncols, 
							nrows,
							field_to_burn = None,
							no_data = 0
							)
						
						#Remove negative values inside the buffered regions
						paleo_dem[(buffer_array == 1)*(paleo_dem < -1000)==1] = np.nan

		
					# Close all the temporary vector layers
					cs_temp = None
					ss_temp = None
					coast_temp = None
		
					# Remove the shapefiles of the temporary vector layers from the disk. Also remove the temporary folder created for them.
					temp_files = [ss_out_file, cs_out_file, coast_out_file]
					deleted_n = 0
					for out_file in temp_files:
						if self.killed:
							break
						if os.path.exists(out_file):
							deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
							if deleted:
								deleted_n += 1
		
						self.progress_count += 5
						self.progress.emit(self.progress_count)
		
					if deleted_n > 2:
						if os.path.exists(os.path.join(out_path, "vector_masks")):
							shutil.rmtree(os.path.join(out_path, "vector_masks"))
						else:
							self.log.emit(
								'I created a temporary folder with some shapefiles: ' + os.path.join(out_path, "vector_masks"))
							self.log.emit('And could not delete it. You may delete it manually.')
		
						self.progress_count += 5
						self.progress.emit(self.progress_count)




			else:
				if not self.killed:
					# creating a base grid for compiling topography and bathymetry
					paleo_dem = np.empty(paleo_bathy.shape)
					paleo_dem[:] = np.nan
					paleo_dem[paleo_bathy < 0] = paleo_bathy[paleo_bathy < 0]
					paleo_dem[paleo_bathy < -12000] = np.nan
					try:
						paleo_dem[paleo_bathy > 0] = modRescale(paleo_dem[paleo_bathy>0], -15, -0.1)
					except ValueError:
						pass
		
					self.progress_count += 20
					self.progress.emit(self.progress_count)
		
				if not self.killed:
					geotransform = bathy_ds.GetGeoTransform()  # geotransform is used for creating raster file of the mask layer
					nrows, ncols = np.shape(
						paleo_dem)  # number of columns and rows in the matrix for storing the rasterized file before saving it as a raster on the disk
				
		
					# Rasterize masks layer
					coast_mask = vectorToRaster(
						self.masks_layer, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)
		
					self.progress_count += 20
					self.progress.emit(self.progress_count)
	
				# Fill the land area with the present day rotated topography
	
				if not self.killed:
					topo_ds = gdal.Open(self.topo_layer.dataProvider().dataSourceUri())
					# Read the data as an array of data
					topo_br = topo_ds.GetRasterBand(1).ReadAsArray()
					paleo_dem[coast_mask == 1] = topo_br[coast_mask == 1]
		
					self.progress_count += 27
					self.progress.emit(self.progress_count)
				if not self.killed:
					if self.remove_overlap:
						buffer_layer = bufferAroundGeometries(self.masks_layer, 0.5, 100)
						buffer_array = vectorToRaster(
							buffer_layer, 
							geotransform, 
							ncols, 
							nrows,
							field_to_burn = None,
							no_data = 0
							)
					
						#Remove negative values inside the buffered regions
						paleo_dem[(buffer_array == 1)*(paleo_dem < 0)==1] = np.nan
		
		if not self.killed:
			nrows, ncols = np.shape(paleo_dem)
			geotransform = bathy_ds.GetGeoTransform()

			raster = gdal.GetDriverByName('GTiff').Create(self.output, ncols, nrows, 1, gdal.GDT_Float32)
			raster.SetGeoTransform(geotransform)
			raster.SetProjection(self.crs.toWkt())
			raster.GetRasterBand(1).WriteArray(paleo_dem)
			raster.GetRasterBand(1).SetNoDataValue(np.nan)
			raster = None

			self.progress.emit(100)
			self.log.emit(
				"The resulting raster is saved at: <a href='file://{}'>{}<a/>".format(os.path.dirname(self.output),
																					  self.output))
			self.finished.emit(True, self.output)
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True









