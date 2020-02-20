
from PyQt5.QtCore import (
	QThread,
	pyqtSignal,
	QVariant
)
import os
from osgeo import (
	gdal
)
from qgis.core import (
	QgsRasterLayer,
	QgsField,
	QgsVectorLayer,
	QgsProcessingException,
	QgsExpressionContext,
	QgsExpressionContextUtils
)
import tempfile

import numpy as np

from .utils import (
	isPathValid,
	fillNoDataInPolygon,
	vectorToRaster,
	modRescale,
	randomPointsInPolygon
)


try:
	from plugins import processing
except Exception:
	import processing








class TaCreateTopoBathy(QThread):
	progress = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False
		self.progress_count = 0
		self.temp_dir = tempfile.gettempdir()

		# Get the output path
		if not self.dlg.outputPath.filePath():
			self.out_file_path = os.path.join(self.temp_dir, 'PaleoDEM_withCreatedFeatures.tif')
		else:
			self.out_file_path = self.dlg.outputPath.filePath()
		
		# The processing algorithms in Qgis starting from version 3.8 use a notation of 'TEMPORARY_OUTPUT' for memory outputs
		# while in versions below 3.8 the 'memory:' notation is used. 
		#Here we set the appropriate processing output for relevant qgis versions.
		self.context = QgsExpressionContext()
		self.context.appendScope(QgsExpressionContextUtils.globalScope())
		qgis_version = self.context.variable("qgis_short_version")
		if float(qgis_version) >= 3.8:
			self.processing_output = 'TEMPORARY_OUTPUT'
		elif qgis_version == '3.10':					#conversion of 3.10 to float gives 3.1 therefore we do not convert it
			self.processing_output = 'TEMPORARY_OUTPUT'
		elif float(qgis_version) < 3.8:
			self.processing_output = 'memory:'
		

	def run(self):
		
		self.dlg.Tabs.setCurrentIndex(1)
		# check if the provided path for the output path is valid
		if not self.killed:
			ret = isPathValid(self.out_file_path)
			if ret[0]:
				pass
			else:
				self.log.emit(ret[1])
				self.kill()
			
		if not self.killed:
			if self.dlg.featureTypeBox.currentText() == "Sea":
				self.createSea()
			elif self.dlg.featureTypeBox.currentText() == "Sea-voronoi":
				self.createSeaVoronoi()
			elif self.dlg.featureTypeBox.currentText() == "Mountain range":
				self.createMountainRange()
		
	def createSea(self):
		if not self.killed:
			
			self.log.emit('Creating open sea ... ')	
			self.log.emit('Loading raster layer ...')
			
			topo_layer = self.dlg.baseTopoBox.currentLayer()
			topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
			projection = topo_ds.GetProjection()
			geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
			height = topo_layer.height()
			width = topo_layer.width()
			topo_ds = None
			
			if topo_layer.isValid():
				self.log.emit("Raster layer is loaded properly.")
			else:
				self.log.emit("Raster layer is not valid. Please, choose a valid raster layer. ")
				self.kill()
	
			# Get the elevation and depth constrains
			min_sea_depth = self.dlg.minElevSpinBox.value()
			max_sea_depth = self.dlg.maxElevSpinBox.value()
			max_shelf_depth = self.dlg.shelfDepthSpinBox.value()
			shelf_width = self.dlg.shelfWidthSpinBox.value()
			slope_width = self.dlg.slopeWidthSpinBox.value()
			pixel_size_avrg = (topo_layer.rasterUnitsPerPixelX()+topo_layer.rasterUnitsPerPixelY())/2
			point_density = 3*0.1/pixel_size_avrg # density of points for random points inside polygon algorithm -Found empirically
	
			self.progress_count += 1
			self.progress.emit(self.progress_count)
	
			# Get the vector masks
			self.log.emit('Loading  vector layer')
			mask_layer = self.dlg.masksBox.currentLayer()
	
			if mask_layer.isValid() and mask_layer.featureCount()>0:
				self.log.emit('Mask layer is loaded properly')
			elif mask_layer.isValid() and mask_layer.featureCount() == 0:
				self.log.emit("Error: The mask layer is empty. Please add polygon features to the mask layer and try again.")
				self.kill()
			else:
				self.log.emit('Error: There is a problem with mask layer - not loaded properly')
				self.kill()
		
		 # Check if input polygon features have unique ids
		 # If not create
		if not self.killed:
			self.log.emit("Assigning unique id numbers to each geographic feature to be created ...")
			id_found  = False
			fields = mask_layer.fields().toList()
			for field in fields:
				if field.name().lower == "id":
					id_found = True
					id_field = field
				else:
					pass
				
			
			
			if  not id_found:
				id_field = QgsField("id", QVariant.Int, "integer")
				mask_layer.startEditing()
				mask_layer.addAttribute(id_field)
				mask_layer.commitChanges()
			
				
			features = mask_layer.getFeatures()
			mask_layer.startEditing()
			for current, feature in enumerate(features):
				feature[id_field.name()]=current
				mask_layer.updateFeature(feature)
				
			ret_code = mask_layer.commitChanges()
			
			if ret_code:
				self.log.emit("Id numbers assigned successfully.")
			else:
				self.log.emit("Id number assignment failed.")
				self.log.emit("For the tool to work properly, each feature should have a unique number.")
				self.log.emit("Please, assign unique numbers manually and try again.")
				self.kill()
				
		if not self.killed:
			# Densifying the vertices in the feature outlines
			# # Parameters for densification
			self.log.emit("Densifying polygon vertices... Densification interval is 0.1 (map units).")
			
			try:
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
			
				mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			
			except QgsProcessingException:
				# the algorithm name and output parameter are different in earlier versions of Qgis (E.g 3.4)
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
				
				mask_layer_densified = processing.run("qgis:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			finally:
				if not mask_layer_densified.isValid() or mask_layer_densified.featureCount()==0:
					mask_layer_densified = mask_layer
					self.log.emit("Warning: Densification of vertices for the feature outlines failed. Initial feature outlines are used. You may densify your geometries manually for smoother surface generation.")
				
					
	
			self.progress_count += 4
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Creating depth points inside feature polygons...")
			# Creating random points inside feature outline polygons
			# # Parameters for random points algorithm
			try:
				random_points_layer = randomPointsInPolygon(mask_layer_densified, point_density, pixel_size_avrg, self, 10)
			except Exception as e:
				self.log.emit("Failed to create random points inside feature polygons with the following exception: {}".format(e))
				self.kill()

				
# 			try:
# 				rp_params = {
# 					'INPUT': mask_layer_densified,
# 					'STRATEGY': 1, # type of densification - points density
# 					'VALUE': point_density, # points density value
# 					'MIN_DISTANCE': pixel_size_avrg,
# 					'OUTPUT': self.processing_output
# 				}
# 				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
# 			except QgsProcessingException as e:
# 				rp_params = {
# 					'INPUT': mask_layer_densified,
# 					'STRATEGY': 1, # type of densification - points density
# 					'EXPRESSION': str(point_density), # points density value
# 					'MIN_DISTANCE': pixel_size_avrg,
# 					'OUTPUT': self.processing_output
# 				}
# 				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
# 			finally:
# 				if not random_points_layer.isValid() or random_points_layer.featureCount()==0:
# 					self.log.emit("Error: No random points were created due to the following error: {}.".format(e))
# 					self.kill()
				
		if not self.killed:
			# Extracting geographic feature vertices
			# # Parameters for extracting vertices
			self.log.emit("Extracting polygon feature vertices...")
			try:
				ev_params = {
					'INPUT': mask_layer_densified,
					'OUTPUT': self.processing_output
				}
				extracted_vertices_layer = processing.run("native:extractvertices", ev_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Error: Feature outline vertices are not extracted because of the following error: {}. The distances cannot be calculated. Therefore the algorithm has stopped.".format(e))
				self.kill()
			else:
				if extracted_vertices_layer.featureCount() == 0:
					self.log.emit("Error: Polygon feature vertices are not extracted.")
					self.kill()
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Calculating distances to coastline...")
			# Calculating distance to nearest hub for the random points
			# # Parameters for the distamce calculation
			try:
				dc_params = {
					'INPUT': random_points_layer,
					'HUBS': extracted_vertices_layer,
					'FIELD': id_field.name(),
					'UNIT': 3, #km
					'OUTPUT': self.processing_output
				}
		
				r_points_distance_layer = processing.run("qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Error: Distance calculation for randomly created depth points falied with the following error: {}".format(e))
				self.kill()
			else: 
				if r_points_distance_layer.featureCount() == 0:
					self.log.emit("Error: There was an error while calculating distances to coastline.")
					self.kill()

			
			self.progress_count += 10
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Sampling existing bathymetry from the input raster...")
			# Sampling the existing bathymetry values from the input raster
			try:
				sampling_params = {
					'INPUT': r_points_distance_layer,
					'RASTERCOPY': topo_layer,
					'COLUMN_PREFIX': 'depth_value',
					'OUTPUT': self.processing_output
				}
				points_dist_depth_layer = processing.run("qgis:rastersampling", sampling_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Warning: Sampling the initial topography failed with the following error: {}. The depths will be calculated without taking the initial topography into account.".format(e))
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			# Finding bounding distance values
			total = 5/points_dist_depth_layer.featureCount() if points_dist_depth_layer.featureCount() else 0
			features = points_dist_depth_layer.getFeatures()
			dists = []
			for current, feat in enumerate(features):
				dist = feat.attribute("HubDist")
				if dist > shelf_width:
					dists.append(dist)
				self.progress_count += int(current*total)
				self.progress.emit(self.progress_count)
			min_dist = min(dists)
			max_dist = max(dists)
		
		if not self.killed:
			self.log.emit("Calculating depth values ... ")
			features = points_dist_depth_layer.getFeatures()
			features_out = []
			
			total = 20/points_dist_depth_layer.featureCount() if points_dist_depth_layer.featureCount() else 0
			for current, feat in enumerate(features):
				attr = feat.attributes()
				dist = feat.attribute("HubDist")
				try:
					in_depth = feat.attribute("depth_value_1")
				except Exception:
					in_depth = None
	
				if dist > shelf_width + slope_width:  
					depth = (max_sea_depth - min_sea_depth) * (dist - min_dist) / (max_dist - min_dist) + min_sea_depth
					if in_depth:
						if depth > in_depth:
							depth = in_depth
					attr.append(depth)
					feat.setAttributes(attr)
					features_out.append(feat)
				elif dist <= shelf_width:
					depth = max_shelf_depth * dist / shelf_width
					# if the calculated depth value for a point is shallower than the initial depth, the initial depth will taken.
					if depth > in_depth:
						depth = in_depth
					attr.append(depth)
					feat.setAttributes(attr)
					features_out.append(feat)
				else:
					pass
				self.progress_count += int(current*total)
				self.progress.emit(self.progress_count)
			
			crs = mask_layer.crs().toWkt()
			depth_layer = QgsVectorLayer("Point?crs=" + crs, "Depth layer", "memory")
			depth_layer_dp = depth_layer.dataProvider()
			fields = points_dist_depth_layer.fields().toList()
			depth_field = QgsField("Depth", QVariant.Double, "double")
			fields.append(depth_field)
	
			depth_layer_dp.addAttributes(fields)
			depth_layer.updateFields()
			depth_layer_dp.addFeatures(features_out)
			depth_layer_dp = None
		
		if not self.killed:
			# Rasterize the depth points layer
			# # Rasterization parameters
			
			self.log.emit("Rasterizing  depth points ...")
			try:
				points_array = vectorToRaster(
					depth_layer, # layer to rasterize
					geotransform,  #layer to take crs from
					width,
					height,
					'Depth',	#field take burn value from
					np.nan,		#no_data value
					0			#burn value 
				)
			except Exception as e:
				self.log.emit("Error: Rasterization of depth points failed with the following error: {}.".format(e))
				self.kill()
				raise e
			self.progress_count += 10
			self.progress.emit(self.progress_count)
			
		
		if not self.killed:
			
			# Get the input raster bathymetry
			bathy_layer_ds = gdal.Open(topo_layer.source())
			bathy = bathy_layer_ds.GetRasterBand(1).ReadAsArray()
	
			# Remove the existing values before assigning
			# Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
			initial_values = np.empty(bathy.shape)  # creare an empty array
			initial_values[:] = bathy[:]  # Copy the elevation values from initial raster
			
			self.log.emit("Removing the existing bathymetry within the feature polygons ... ")
			try:
				pol_array = vectorToRaster(
					mask_layer_densified,
					geotransform,
					width,
					height,
					field_to_burn=None,
					no_data=0
				)
			except Exception as e:
				self.log.emit("Error: Rasterization of polygon features outlining geographic features failed with the following error: {}.".format(e))
				self.kill()
			
			if not self.killed:
				bathy[pol_array == 1] = np.nan
				# assign values to the topography raster
				bathy[np.isfinite(points_array)] = points_array[np.isfinite(points_array)]
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Setting the coastline to zero ...")
			# Rasterize sea boundaries
			try:
				ptol_params = {
					'INPUT': mask_layer_densified,
					'OUTPUT': self.processing_output
				}
				mlayer_line = processing.run("native:polygonstolines", ptol_params)["OUTPUT"]
			except Exception as e:
				ptol_params = {
					'INPUT': mask_layer_densified,
					'OUTPUT': self.processing_output
				}
				mlayer_line = processing.run("qgis:polygonstolines", ptol_params)["OUTPUT"]
			finally:
				if not mlayer_line.isValid() or mlayer_line.featureCount()==0:
					self.log.emit("Error: Extracting polygon boundaries failed with the following error: {}.".format(e))
					self.kill()
		
			if not self.killed:
				try:
					sea_boundary_array = vectorToRaster(
						mlayer_line,
						geotransform,
						width,
						height,
						field_to_burn=None,
						no_data=0
					)
				except Exception as e:
					self.log.emit("Error: Rasterization of feature outline boundaries failed with the following error: {}.".format(e))
					self.kill()
	
			if not self.killed:
				# assign 0m values to the sea line
				bathy[(sea_boundary_array == 1) * (bathy > 0) == 1] = 0
				bathy[(sea_boundary_array == 1) * np.isnan(bathy) * np.isfinite(initial_values) * (
						initial_values > 0) == 1] = 0
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Interpolating depth values for gaps...")

			# Create a temporary raster to store modified data for interpolation
			out_file_path = os.path.join(self.temp_dir, "Interpolated_raster.tiff")
			
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
			out_file_path,
			width,
			height,
			1, #number of bands
			gdal.GDT_Float32 #data type
		)
		
				
			
			raster_for_interpolation.SetGeoTransform(geotransform)
			raster_for_interpolation.SetProjection(projection)
			band = raster_for_interpolation.GetRasterBand(1)
			band.SetNoDataValue(np.nan)
			band.WriteArray(bathy)
			raster_for_interpolation = None
			bathy = None
			
		
			
			rlayer = QgsRasterLayer(out_file_path, "Raster for interpolation", "gdal")
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
			try:
				fillNoDataInPolygon(rlayer, mask_layer, self.out_file_path)
			except Exception as e:
				self.log.emit("Error: Raster interpolation failed with the following error: {}.".format(e))
				self.kill()
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			self.log.emit("Removing some artifacts")
			# Load the raster again to remove artifacts
			final_raster = gdal.Open(self.out_file_path, gdal.GA_Update)
			bathy = final_raster.GetRasterBand(1).ReadAsArray()
	
			
			
			# Re-scale the artifacts bsl.
			try:
				in_array = bathy[(pol_array == 1) * (bathy > 0)]
				if in_array.size>0:
					bathy[(pol_array == 1) * (bathy > 0)] = modRescale(in_array, -15, -1)
					final_raster.GetRasterBand(1).WriteArray(bathy)
			except Exception:
				self.log.emit("Warning: Removing artefacts faild.")
			
			bathy = None
			final_raster = None
				
	
			# Fill the artefacts with interpolation - did not work well
			# bathy[(pol_array == 1) * (bathy > 0)] = np.nan
			# bathy[(sea_boundary_array == 1) * (bathy > 0)] = 0
			
			
			self.progress_count = 100
			self.progress.emit(self.progress_count)
			
			self.finished.emit(True, self.out_file_path)
		else:
			self.finished.emit(False, "")
			
	def createMountainRange(self):
		if not self.killed:
			
			self.log.emit('Creating mountain range ... ')	
			self.log.emit('Loading raster layer ...')
			
			topo_layer = self.dlg.baseTopoBox.currentLayer()
			topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
			projection = topo_ds.GetProjection()
			geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
			height = topo_layer.height()
			width = topo_layer.width()
			topo_ds = None
			
			if topo_layer.isValid():
				self.log.emit("Raster layer is loaded properly.")
			else:
				self.log.emit("Raster layer is not valid. Please, choose a valid raster layer. ")
				self.kill()
	
			# Get the elevation and depth constrains
			min_mount_elev = self.dlg.minElevSpinBox.value()
			max_mount_elev = self.dlg.maxElevSpinBox.value()
			ruggedness = self.dlg.shelfDepthSpinBox.value()
			slope_width = self.dlg.slopeWidthSpinBox.value()
			pixel_size_avrg = (topo_layer.rasterUnitsPerPixelX()+topo_layer.rasterUnitsPerPixelY())/2
			point_density = 10*0.1/pixel_size_avrg # density of points for random points inside polygon algorithm -Found empirically
			
			
			self.progress_count += 1
			self.progress.emit(self.progress_count)
	
			# Get the vector masks
			self.log.emit('Loading  vector layer ...')
			mask_layer = self.dlg.masksBox.currentLayer()
	
			if mask_layer.isValid() and mask_layer.featureCount()>0:
				self.log.emit('Mask layer is loaded properly.')
			elif mask_layer.isValid() and mask_layer.featureCount() == 0:
				self.log.emit("Error: The mask layer is empty. Please add polygon features to the mask layer and try again.")
				self.kill()
			else:
				self.log.emit('Error: There is a problem with mask layer - not loaded properly')
				self.kill()
		
		
		 # Check if input polygon features have unique ids
		 # If not create
		if not self.killed:
			self.log.emit("Assigning unique id numbers to each geographic feature to be created ...")
			id_found  = False
			fields = mask_layer.fields().toList()
			for field in fields:
				if field.name().lower == "id":
					id_found = True
					id_field = field
				else:
					pass
				
			
			
			if  not id_found:
				id_field = QgsField("id", QVariant.Int, "integer")
				mask_layer.startEditing()
				mask_layer.addAttribute(id_field)
				mask_layer.commitChanges()
			
				
			features = mask_layer.getFeatures()
			mask_layer.startEditing()
			for current, feature in enumerate(features):
				feature[id_field.name()]=current
				mask_layer.updateFeature(feature)
				
			ret_code = mask_layer.commitChanges()
			
			if ret_code:
				self.log.emit("Id numbers assigned successfully.")
			else:
				self.log.emit("Id number assignment failed.")
				self.log.emit("For the tool to work properly, each feature should have a unique number.")
				self.log.emit("Please, assign unique numbers manually and try again.")
				self.kill()
				
				
		if not self.killed:
			# Densifying the vertices in the feature outlines
			# # Parameters for densification
			
			try:
				self.log.emit("Densifying polygon vertices... Densification interval is {} (map units).".format(pixel_size_avrg))
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
				
				mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			except QgsProcessingException:
				# the algorithm name and output parameter are different in earlier versions of Qgis (E.g 3.4)
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
				
				mask_layer_densified = processing.run("qgis:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			finally:
				if not mask_layer_densified.isValid() or mask_layer_densified.featureCount()==0:
					mask_layer_densified = mask_layer
					self.log.emit("Warning: Densification of vertices for the feature outlines failed. Initial feature outlines are used. You may densify your geometries manually for smoother surface generation.")
				
			self.progress_count += 4
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Creating depth points inside feature polygons...")
			# Creating random points inside feature outline polygons
			try:
				random_points_layer = randomPointsInPolygon(mask_layer_densified, point_density, pixel_size_avrg, self, 10)
			except Exception as e:
				self.log.emit("Error: Failed to create random points inside polygon features. The error is: {}".format(e))
				self.kill()
			else:
				if random_points_layer.featureCount() == 0:
					self.log.emit("Error: Failed to create random points inside polygon features.")
					self.kill()
# 			# # Parameters for random points algorithm
# 			
# 			try:
# 				rp_params = {
# 					'INPUT': mask_layer_densified,
# 					'STRATEGY': 1, # type of densification - points density
# 					'VALUE': point_density, # points density value
# 					'MIN_DISTANCE': pixel_size_avrg,
# 					'OUTPUT': self.processing_output
# 				}
# 				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
# 			except QgsProcessingException:
# 				rp_params = {
# 					'INPUT': mask_layer_densified,
# 					'STRATEGY': 1, # type of densification - points density
# 					'EXPRESSION': str(point_density), # points density value
# 					'MIN_DISTANCE': pixel_size_avrg,
# 					'OUTPUT': self.processing_output
# 					}
# 				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
# 			else:
# 				pass
# 			finally:
# 				if not random_points_layer.isValid() or  random_points_layer.featureCount() == 0:
# 					self.log.emit("Error: No random points were created due to an unknown error.")
# 					self.kill()

# 			self.progress_count += 10
# 			self.progress.emit(self.progress_count)
			

		if not self.killed:
			# Extracting geographic feature vertices
			# # Parameters for extracting vertices
			try:
				ev_params = {
					'INPUT': mask_layer_densified,
					'OUTPUT': self.processing_output
				}
				extracted_vertices_layer = processing.run("native:extractvertices", ev_params)['OUTPUT']
			except QgsProcessingException as e:
				self.log.emit("Error: Extracting feature outline vertices failed with the following error: {}. The algorithm cannot proceed.".format(e))
				self.kill()				
			
					
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Calculating distances to boundaries of the mountain...")
			# Calculating distance to nearest hub for the random points
			# # Parameters for the distamce calculation
			try:
				dc_params = {
					'INPUT': random_points_layer,
					'HUBS': extracted_vertices_layer,
					'FIELD': id_field.name(),
					'UNIT': 3, #km
					'OUTPUT': self.processing_output
				}
		
				r_points_distance_layer = processing.run("qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
			except QgsProcessingException as e:
				self.log.emit("Error: Distance calculation for random points inside feature outlines failed with the following error: {}.".format(e))
				self.kill()
				
			self.progress_count += 10
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Sampling existing topography from the input raster...")
			# Sampling the existing bathymetry values from the input raster
			try:
				sampling_params = {
					'INPUT': r_points_distance_layer,
					'RASTERCOPY': topo_layer,
					'COLUMN_PREFIX': 'elev_value',
					'OUTPUT': self.processing_output
				}
				points_dist_elev_layer = processing.run("qgis:rastersampling", sampling_params)['OUTPUT']
			except QgsProcessingException as e:
				self.log.emit("Warning: Sampling existing topography/bathymetry failed. Depth calculation will be done without considering initial topography. The following error was thrown: {}".format(e))
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			# Finding bounding distance values
			total = 5/points_dist_elev_layer.featureCount() if points_dist_elev_layer.featureCount() else 0
			features = points_dist_elev_layer.getFeatures()
			dists = []
			for current, feat in enumerate(features):
				dist = feat.attribute("HubDist")
				if dist > slope_width:
					dists.append(dist)
				self.progress_count += int(current*total)
				self.progress.emit(self.progress_count)
			if len(dists)>0:
				min_dist = min(dists)
				max_dist = max(dists)
			else:
				self.log.emit("Error: List of distances is empty.")
				self.kill()
			
		
		if not self.killed:
			self.log.emit("Calculating depth values ... ")
			features = points_dist_elev_layer.getFeatures()
			features_out = []
			
			total = 20/points_dist_elev_layer.featureCount() if points_dist_elev_layer.featureCount() else 0
			for current, feat in enumerate(features):
				attr = feat.attributes()
				dist = feat.attribute("HubDist")
				try:
					in_elev = feat.attribute("elev_value_1")
				except KeyError:
					in_elev = None
	
				if dist > slope_width:  
					elev = (max_mount_elev - min_mount_elev) * (dist - min_dist) / (max_dist - min_dist) + min_mount_elev
					if in_elev:
						if elev < in_elev:
							elev = in_elev
					#change the elevation randomly by 10 percent
					max_bound = elev*ruggedness/100
					min_bound = max_bound*-1
					
					#using sin function to make mountain pattern to repeat
# 					sin_func = math.sin(max_bound)
# 					elev=abs(elev*sin_func)

					elev = elev+np.random.randint(min_bound,max_bound)
					attr.append(elev)
					feat.setAttributes(attr)
					features_out.append(feat)
				else:
					pass
				self.progress_count += int(current*total)
				self.progress.emit(self.progress_count)
			
			crs = mask_layer.crs().toWkt()
			elev_layer = QgsVectorLayer("Point?" + crs, "Topography layer", "memory")
			elev_layer_dp = elev_layer.dataProvider()
			fields = points_dist_elev_layer.fields().toList()
			elev_field = QgsField("Elev", QVariant.Double, "double")
			fields.append(elev_field)
	
			elev_layer_dp.addAttributes(fields)
			elev_layer.updateFields()
			elev_layer_dp.addFeatures(features_out)
			elev_layer_dp = None
		
		if not self.killed:
			# Rasterize the depth points layer
			# # Rasterization parameters
			
			self.log.emit("Rasterizing  elevation points ...")
			try:
				points_array = vectorToRaster(
					elev_layer, # layer to rasterize
					geotransform,  #layer to take crs from
					width,
					height,
					'Elev',	#field take burn value from
					np.nan,		#no_data value
					0			#burn value 
				)
			except Exception as e:
				self.log.emit("Error: Rasterization of depth points failed with the following error: {}.".format(e))
				self.kill()
			self.progress_count += 10
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			
			# Get the input raster topography
			try:
				topo_layer_ds = gdal.Open(topo_layer.source())
				topo = topo_layer_ds.GetRasterBand(1).ReadAsArray()
			except Exception as e:
				self.log.emit("Error: Cannot open the topography raster to modify it. The error is: {}.".format(e))
				self.kill()
	
			# Remove the existing values before assigning
			# Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
			initial_values = np.empty(topo.shape)  # creare an empty array
			initial_values[:] = topo[:]  # Copy the elevation values from initial raster
			
			self.log.emit("Removing the existing topography within the feature polygons ... ")
			try:
				pol_array = vectorToRaster(
					mask_layer_densified,
					geotransform,
					width,
					height,
					field_to_burn=None,
					no_data=0
				)
			except Exception as e:
				self.log.emit("Error: Rasterization of geographic feature polygons failed with the following error: {}.".format(e))
				self.kill()

			topo[pol_array == 1] = np.nan
			# assign values to the topography raster
			topo[np.isfinite(points_array)] = points_array[np.isfinite(points_array)]
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
					
		if not self.killed:
			self.log.emit("Interpolating depth values for gaps...")

			# Create a temporary raster to store modified data for interpolation
			out_file_path = os.path.join(self.temp_dir, "Interpolated_raster.tiff")
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
				out_file_path,
				width,
				height,
				1, #number of bands
				gdal.GDT_Float32 #data type
			)
			raster_for_interpolation.SetGeoTransform(geotransform)
			raster_for_interpolation.SetProjection(projection)
			band = raster_for_interpolation.GetRasterBand(1)
			band.SetNoDataValue(np.nan)
			band.WriteArray(topo)
			raster_for_interpolation = None
			topo = None
		
		
			
			rlayer = QgsRasterLayer(out_file_path, "Raster for interpolation", "gdal")
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
			try:
				fillNoDataInPolygon(rlayer, mask_layer_densified, self.out_file_path)
			except Exception as e:
				self.log.emit("Interpolation failed with the following error: {}.".format(e))
				self.kill()
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			self.log.emit("Removing some artefacts")
			# Load the raster again to remove artifacts
			
			final_raster = gdal.Open(self.out_file_path, gdal.GA_Update)
			topo = final_raster.GetRasterBand(1).ReadAsArray()
	
			
			
			# Re-scale the artifacts bsl.
			
			in_array = topo[(pol_array == 1) * (topo < 0)]
			if in_array.size>0:
				topo[(pol_array == 1) * (topo < 0)] = modRescale(in_array, 15, 1)
				final_raster.GetRasterBand(1).WriteArray(topo)
			topo=None
			final_raster = None
			
			
				
			self.progress_count = 100
			self.progress.emit(self.progress_count)
			
			self.finished.emit(True, self.out_file_path)
		else:
			self.finished.emit(False, "")
			

	def createSeaVoronoi(self):
		progress_count = self.progress_count
		temp_dir = self.temp_dir
		out_file_path = self.out_file_path
		self.log.emit('Loading the raster layer')
		topo_layer = self.dlg.baseTopoBox.currentLayer()
		topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
		topo_projection = topo_ds.GetProjection()
		
		
		geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
		height = topo_layer.height()
		width = topo_layer.width()
		topo_ds = None

		# Get the elevation and depth constrains
		min_depth = self.dlg.minElevSpinBox.value()
		max_depth = self.dlg.maxElevSpinBox.value()
		pixel_size_avrg = (topo_layer.rasterUnitsPerPixelX()+topo_layer.rasterUnitsPerPixelY())/2
		

		progress_count += 10
		self.progress.emit(progress_count)
		
		if topo_layer.isValid():
			self.log.emit("Raster layer is loaded properly.")
		else:
			self.log.emit("Raster layer is not valid. Please, choose a valid raster layer. ")
			self.kill()

		if not self.killed:
			# Get the vector masks
			self.log.emit('Loading the vector layer')
			mask_layer = self.dlg.masksBox.currentLayer()
		
			#Check if the mask layer is valid and contains features.

			if mask_layer.isValid() and mask_layer.featureCount()>0:
				self.log.emit('Mask layer is loaded properly')
			elif mask_layer.isValid() and mask_layer.featureCount() == 0:
				self.log.emit("Error: The mask layer is empty. Please add polygon features to the mask layer and try again.")
				self.kill()
			else:
				self.log.emit('Error: There is a problem with mask layer - not loaded properly')
				self.kill()
		
		if not self.killed:
			self.log.emit("Assigning unique id numbers to each geographic feature to be created ...")
			id_found  = False
			fields = mask_layer.fields().toList()
			for field in fields:
				if field.name().lower == "id":
					id_found = True
					id_field = field
				else:
					pass
				
			
			
			if  not id_found:
				id_field = QgsField("id", QVariant.Int, "integer")
				mask_layer.startEditing()
				mask_layer.addAttribute(id_field)
				mask_layer.commitChanges()
			
				
			features = mask_layer.getFeatures()
			mask_layer.startEditing()
			for current, feature in enumerate(features):
				feature[id_field.name()]=current
				mask_layer.updateFeature(feature)
				
			ret_code = mask_layer.commitChanges()
			
			if ret_code:
				self.log.emit("Id numbers assigned successfully.")
			else:
				self.log.emit("Error: Id number assignment failed.")
				self.log.emit("Error: For the tool to work properly, each feature should have a unique number.")
				self.log.emit("Error: Please, assign unique numbers manually and try again.")
				self.kill()
		
		if not self.killed:
			# Densifying the vertices in the feature outlines
			# # Parameters for densification
			self.log.emit("Densifying polygon vertices... Densification interval is {} (map units).".format(pixel_size_avrg))
			try:
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
			
				mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			except QgsProcessingException:
				
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': self.processing_output
				}
			
				mask_layer_densified = processing.run("qgis:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			finally:
				if not mask_layer_densified.isValid() or mask_layer_densified.featureCount()==0:
					mask_layer_densified = mask_layer
					self.log.emit("Warning: Densification of vertices for the feature outlines failed. Initial feature outlines are used. You may densify your geometries manually for smoother surface generation.")
				else:
					self.log.emit("The outlines are densified successfully.")
				
				
				
	
			
			# Extract vertices of the polygon
			self.log.emit("Extracting vertices from feature outlines...")
			ev_params = {
				'INPUT': mask_layer_densified, 
				'OUTPUT': self.processing_output
				}
			extracted_vertices = processing.run("native:extractvertices", ev_params)["OUTPUT"]
			assert extracted_vertices.isValid(), "Error: Extracted vertices layer is not valid."
			self.log.emit("Vertices extracted successfully.")
			

			# Create voronoy polygons from extracted points
			self.log.emit("Creating voronoi polygons...")
			vor_params = {
				'INPUT': extracted_vertices, 
				'BUFFER': 0, 
				'OUTPUT': self.processing_output
				}
			voronoy_polygons = processing.run("qgis:voronoipolygons", vor_params)["OUTPUT"]
			assert voronoy_polygons.isValid(), "Error: Voronoi polygons layer is not valid."
			self.log.emit("Voronoi polygons created successfully.")

			# Extract vertives of the Voronoy polygons
			vor_ev_params = {
				'INPUT': voronoy_polygons, 
				'OUTPUT': self.processing_output
				}
			extracted_vor_vertices = processing.run("native:extractvertices", vor_ev_params)["OUTPUT"]
			assert extracted_vor_vertices.isValid(), "Error: Extracted voronoi vertices layer is not valid."
			self.log.emit("Extracted vertices of voronoi polygons successfully.")

			self.progress_count += 10
			self.progress.emit(progress_count)

		if not self.killed:
			# Extract the points that lie within the polygon
			self.log.emit("Extracting voronoi points from the center of polygons ...")
			extr_params = {
				'INPUT': extracted_vor_vertices, 
				'PREDICATE': [6],
				'INTERSECT': mask_layer,
				'OUTPUT': self.processing_output
				}
			sea_center_points = processing.run("native:extractbylocation", extr_params)["OUTPUT"]
			assert sea_center_points.isValid(), "Error: The layer with central sea points extracted is not valid."
			self.log.emit("Central sea points extracted successfully.")
			

			# Find the distance from Center-points to edge-points
			self.log.emit("Calculating distance from central points to edges of polygons...")
			ex_params = {
				'INPUT': sea_center_points, 
				'HUBS': extracted_vertices,
				'FIELD': id_field.name(),
				'UNIT': 3, 
				'OUTPUT': self.processing_output
				}
			sea_points_dist = processing.run("qgis:distancetonearesthubpoints",ex_params )["OUTPUT"]
			assert sea_points_dist.isValid(), "The layer with calculated distances is not valid."
			self.log.emit("Distances calculated successfully.")
			
			progress_count += 10
			self.progress.emit(progress_count)
			
		if not self.killed:
			

			fields = sea_points_dist.fields().toList()
			depth_field = QgsField("Depth", QVariant.Double, "double")
			fid_field = QgsField("fid", QVariant.Int, "double")
			fields.append(depth_field)
			fields.append(fid_field)

			# Create a new layer to store updated points with depth values
			sea_points_depth = QgsVectorLayer("Point?" + topo_layer.crs().toWkt(), "Depth_values", "memory")
			# Get the depth layer data provider to store the features with depth values
			sea_points_depth_ds = sea_points_depth.dataProvider()
			sea_points_depth_ds.addAttributes(fields)
			sea_points_depth.updateFields()
		if not self.killed:
			feats = sea_points_dist.getFeatures()
			total = 20.0 / sea_points_dist.featureCount() if sea_points_dist.featureCount() else 0
			all_dists = []
			for current, feat in enumerate(feats):
				if self.killed:
					break
				dist = feat.attribute("HubDist")
				all_dists.append(dist)
				progress_count += int(current * total)
				self.progress.emit(progress_count)

			max_dist = max(all_dists)
			min_dist = min(all_dists)

			feats = sea_points_dist.getFeatures()
			feats_out = []
			total = 20.0 / sea_points_dist.featureCount() if sea_points_dist.featureCount() else 0
		if not self.killed:
			
			for current, feat in enumerate(feats):
				if self.killed:
					break
				attr = feat.attributes()
				dist = feat.attribute("HubDist")
				depth = (max_depth - min_depth) * (dist - min_dist) / (max_dist - min_dist) + min_depth
				
				attr.append(depth)
				feat.setAttributes(attr)
				feat["fid"]=current
				feats_out.append(feat)
				progress_count += int(current * total)
				self.progress.emit(progress_count)

		if not self.killed:
			sea_points_depth_ds.addFeatures(feats_out)
			sea_points_depth.updateExtents()
			sea_points_depth_ds = None
			

		# Rasterize layers
		# Rasterize sea points layer
		if not self.killed:
			try:
				points_array = vectorToRaster(
					sea_points_depth, 
					geotransform, 
					width, 
					height, 
					'Depth', 
					np.nan,
					0
				)
			except Exception as e:
				self.log.emit("Error: Rasterization of depth points filed with the following error: {}".format(e))
				self.kill()

			progress_count += 5
			self.progress.emit(progress_count)
			
			topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
			bathy = topo_ds.GetRasterBand(1).ReadAsArray()
			topo_ds = None

			# Remove the existing values before assigning
			# Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
			initial_values = np.empty(bathy.shape)  # creare an array filled with ones
			initial_values[:] = bathy[:]  # set the finite (not nan) values to zero
			pol_array = vectorToRaster(
				mask_layer, 
				geotransform, 
				width, 
				height,
				field_to_burn=None,
				no_data=0
				)
			
			
			bathy[pol_array == 1] = np.nan
			# assign values to the topography raster
			bathy[np.isfinite(points_array)] = points_array[np.isfinite(points_array)]
			
			
			
			
		if not self.killed:
			# Rasterize sea boundaries
			self.log.emit("Extracting polyline of sea polygon boundaries...")
			try:
				r_params = {
					'INPUT': mask_layer, 
					'OUTPUT': self.processing_output
					}
				vlayer_line = processing.run("native:polygonstolines", r_params)["OUTPUT"]
			except QgsProcessingException:
				r_params={
					'INPUT': mask_layer, 
					'OUTPUT': self.processing_output
					}
				vlayer_line = processing.run("qgis:polygonstolines", r_params)["OUTPUT"]
			assert vlayer_line.isValid(), "The layer with polygon boundaries is not valid."
				
			
			progress_count += 5
			self.progress.emit(progress_count)

		
			sea_boundary_array = vectorToRaster(
				vlayer_line, 
				geotransform, 
				width, 
				height,
				field_to_burn=None,
				no_data=0
				)
			

			progress_count += 5
			self.progress.emit(progress_count)

		if not self.killed:
			self.log.emit("Setting sea boundaries (shoreline) to 0 m elevation...")
			# assign 0m values to the sea line
			bathy[(sea_boundary_array == 1) * (bathy > 0) == 1] = 0
			bathy[(sea_boundary_array == 1) * np.isnan(bathy) * np.isfinite(initial_values) * (
					initial_values > 0) == 1] = 0
			
			out_file = os.path.join(temp_dir, "Raster_for_interpolation.tiff")
			# Create a temporary raster to store modified data for interpolation
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(out_file, width, height, 1, gdal.GDT_Float32)
			raster_for_interpolation.SetGeoTransform(geotransform)
			raster_for_interpolation.SetProjection(topo_projection)
			band = raster_for_interpolation.GetRasterBand(1)
			band.SetNoDataValue(np.nan)
			band.WriteArray(bathy)
			raster_for_interpolation = None
			bathy = None
			
			if not self.killed:
				rlayer = QgsRasterLayer(out_file, "Raster for interpolation", "gdal")
				self.log.emit("Interpolating values for empty raster cells...")
				fillNoDataInPolygon(rlayer, mask_layer, out_file_path)
				rlayer=QgsRasterLayer(out_file_path, "Raster after interpolation", "gdal")
				
				
				
				# Load the raster again to remove artefacts
				final_raster = gdal.Open(out_file_path, gdal.GA_Update)
				bathy = final_raster.GetRasterBand(1).ReadAsArray()
	
				
				# Rescale the artefacts bsl.
				in_array = bathy[(pol_array == 1) * (bathy > 0)]
				if in_array.size>0:
					bathy[(pol_array == 1) * (bathy > 0)] = modRescale(in_array, -15, -1)
					final_raster.GetRasterBand(1).WriteArray(bathy)
				bathy=None
				final_raster = None
	
				# Fill the artefacts with interpolation - did not work well
				# bathy[(pol_array == 1) * (bathy > 0)] = np.nan
				# bathy[(sea_boundary_array == 1) * (bathy > 0)] = 0
				
	
				# # Get the layer again to fill emptied cells - this strokes should be enabled (uncommented) for filling the gaps \
				# # instead of interpolation.
				# rlayer = QgsRasterLayer(out_file_path, "Raster for interpolation", "gdal")
				# fillNoData(rlayer, out_file_path)
				#
	
				progress_count = 100
				self.progress.emit(progress_count)

				self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True
