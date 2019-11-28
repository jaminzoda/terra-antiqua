
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
	QgsProject,
	QgsVectorLayer,
	QgsVectorFileWriter,
	QgsProcessingException
)
import tempfile

import numpy as np
from plugins import processing

from .topotools import (
	is_path_valid,
	fill_no_data,
	vector_to_raster,
	mod_rescale
)
from terra_antiqua.terra_modules.topotools import fill_no_data_in_polygon
import math





class FeatureCreator(QThread):
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

	def run(self):
		
		self.dlg.Tabs.setCurrentIndex(1)
		# check if the provided path for the output path is valid
		if not self.killed:
			ret = is_path_valid(self.out_file_path)
			if ret[0]:
				pass
			else:
				self.log.emit(ret[1])
				self.kill()
			
		if not self.killed:
			if self.dlg.featureTypeBox.currentText() == "Sea":
				self.create_sea()
			elif self.dlg.featureTypeBox.currentText() == "Sea-voronoi":
				self.create_sea_voronoi()
			elif self.dlg.featureTypeBox.currentText() == "Mountain range":
				self.create_mountain_range()
		
	def create_sea(self):
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
			d_params = {
				'INPUT': mask_layer,
				'INTERVAL': pixel_size_avrg,
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
			
			mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
	
			self.progress_count += 4
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Creating depth points inside feature polygons...")
			# Creating random points inside feature outline polygons
			# # Parameters for random points algorithm
			
			try:
				rp_params = {
					'INPUT': mask_layer_densified,
					'STRATEGY': 1, # type of densification - points density
					'VALUE': point_density, # points density value
					'MIN_DISTANCE': None,
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
			except QgsProcessingException:
				rp_params = {
					'INPUT': mask_layer_densified,
					'STRATEGY': 1, # type of densification - points density
					'EXPRESSION': point_density, # points density value
					'MIN_DISTANCE': None,
					'OUTPUT': 'TEMPORARY_OUTPUT'
					}
				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Random points creation failed with the following Error:")
				self.log.emit(str(e))
					
			
			
			self.progress_count += 10
			self.progress.emit(self.progress_count)
			
			
			# Extracting geographic feature vertices
			# # Parameters for extracting vertices
			ev_params = {
				'INPUT': mask_layer_densified,
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
			extracted_vertices_layer = processing.run("native:extractvertices", ev_params)['OUTPUT']
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Calculating distances to coastline...")
			# Calculating distance to nearest hub for the random points
			# # Parameters for the distamce calculation
			dc_params = {
				'INPUT': random_points_layer,
				'HUBS': extracted_vertices_layer,
				'FIELD': id_field.name(),
				'UNIT': 3,
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
	
			r_points_distance_layer = processing.run("qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
			
			self.progress_count += 10
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Sampling existing bathymetry from the input raster...")
			# Sampling the existing bathymetry values from the input raster
			sampling_params = {
				'INPUT': r_points_distance_layer,
				'RASTERCOPY': topo_layer,
				'COLUMN_PREFIX': 'depth_value',
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
			points_dist_depth_layer = processing.run("qgis:rastersampling", sampling_params)['OUTPUT']
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
				in_depth = feat.attribute("depth_value_1")
	
				if dist > shelf_width + slope_width:  
					depth = (max_sea_depth - min_sea_depth) * (dist - min_dist) / (max_dist - min_dist) + min_sea_depth
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
			depth_layer = QgsVectorLayer("Point?" + crs, "Depth layer", "memory")
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
			points_array = vector_to_raster(
				depth_layer, # layer to rasterize
				geotransform,  #layer to take crs from
				width,
				height,
				'Depth',	#field take burn value from
				np.nan,		#no_data value
				0			#burn value 
			)
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
			pol_array = vector_to_raster(
				mask_layer_densified,
				geotransform,
				width,
				height
			)

			bathy[pol_array == 1] = np.nan
			# assign values to the topography raster
			bathy[np.isfinite(points_array)] = points_array[np.isfinite(points_array)]
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Setting the coastline to zero ...")
			# Rasterize sea boundaries
			ptol_params = {
				'INPUT': mask_layer_densified,
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
			mlayer_line = processing.run("native:polygonstolines", ptol_params)["OUTPUT"]
	
			sea_boundary_array = vector_to_raster(
				mlayer_line,
				geotransform,
				width,
				height
			)
	
			# assign 0m values to the sea line
			bathy[(sea_boundary_array == 1) * (bathy > 0) == 1] = 0
			bathy[(sea_boundary_array == 1) * np.isnan(bathy) * np.isfinite(initial_values) * (
					initial_values > 0) == 1] = 0
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
		if not self.killed:
			self.log.emit("Interpolating depth values for gaps...")

			# Create a temporary raster to store modified data for interpolation
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
				self.out_file_path,
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
		
		
			out_file_path = os.path.join(self.temp_dir, "Interpolated_raster.tiff")
			rlayer = QgsRasterLayer(self.out_file_path, "Raster for interpolation", "gdal")
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
			
			fill_no_data(rlayer, out_file_path)
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			self.log.emit("Removing some artifacts")
			# Load the raster again to remove artifacts
			final_raster = gdal.Open(out_file_path, gdal.GA_Update)
			bathy = final_raster.GetRasterBand(1).ReadAsArray()
	
			
			
			# Re-scale the artifacts bsl.
			in_array = bathy[(pol_array == 1) * (bathy > 0)]
			if in_array.size>0:
				bathy[(pol_array == 1) * (bathy > 0)] = mod_rescale(in_array, -15, -1)
				final_raster.GetRasterBand(1).WriteArray(bathy)
			
			bathy = None
			final_raster = None
				
	
			# Fill the artefacts with interpolation - did not work well
			# bathy[(pol_array == 1) * (bathy > 0)] = np.nan
			# bathy[(sea_boundary_array == 1) * (bathy > 0)] = 0
			
			
			self.progress_count = 100
			self.progress.emit(self.progress_count)
			
			self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")
			
	def create_mountain_range(self):
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
				self.log.emit("Densifying polygon vertices... Densification interval is 0.1 (map units).")
				d_params = {
					'INPUT': mask_layer,
					'INTERVAL': pixel_size_avrg,
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
				
				mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
			except Exception:
				mask_layer_densified = mask_layer
				self.log.emit("Warning: Densification of vertices for the feature outlines failed with the following exception: {}. Initial feature outlines are used.".format())
				
			self.progress_count += 4
			self.progress.emit(self.progress_count)
		
		if not self.killed:
			self.log.emit("Creating depth points inside feature polygons...")
			# Creating random points inside feature outline polygons
			# # Parameters for random points algorithm
			
			try:
				rp_params = {
					'INPUT': mask_layer_densified,
					'STRATEGY': 1, # type of densification - points density
					'VALUE': point_density, # points density value
					'MIN_DISTANCE': None,
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
			except QgsProcessingException:
				self.log.emit("got an exception")
				rp_params = {
					'INPUT': mask_layer_densified,
					'STRATEGY': 1, # type of densification - points density
					'EXPRESSION': point_density, #point_density, # points density value
					'MIN_DISTANCE': None,
					'OUTPUT': 'TEMPORARY_OUTPUT'
					}
				random_points_layer = processing.run("qgis:randompointsinsidepolygons", rp_params)['OUTPUT']
# 			except QgsProcessingException as e:
# 				self.log.emit("Random points creation failed with the following Error:")
# 				self.log.emit(str(e))
# 			
			
			
			self.progress_count += 10
			self.progress.emit(self.progress_count)
			
			
			# Extracting geographic feature vertices
			# # Parameters for extracting vertices
			try:
				ev_params = {
					'INPUT': mask_layer_densified,
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
				extracted_vertices_layer = processing.run("native:extractvertices", ev_params)['OUTPUT']
			except Exception as e:
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
					'UNIT': 3,
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
		
				r_points_distance_layer = processing.run("qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Error: Distance calculation for random points inside feature outlines failed with the error: {}".format(e))
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
					'OUTPUT': 'TEMPORARY_OUTPUT'
				}
				points_dist_elev_layer = processing.run("qgis:rastersampling", sampling_params)['OUTPUT']
			except Exception as e:
				self.log.emit("Warning: Sampling existing topography/bathymetry failed with the following exception: {}. Depth calculation will be done without considering initial topography.".format(e))
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
				points_array = vector_to_raster(
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
				pol_array = vector_to_raster(
					mask_layer_densified,
					geotransform,
					width,
					height
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
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
				self.out_file_path,
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
		
		
			out_file_path = os.path.join(self.temp_dir, "Interpolated_raster.tiff")
			rlayer = QgsRasterLayer(self.out_file_path, "Raster for interpolation", "gdal")
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)
			
			try:
				fill_no_data_in_polygon(rlayer, mask_layer_densified, out_file_path)
			except Exception as e:
				self.log.emit("Interpolation failed with the following error: {}.".format(e))
				self.kill()
			
			self.progress_count += 5
			self.progress.emit(self.progress_count)

		if not self.killed:
			self.log.emit("Removing some artefacts")
			# Load the raster again to remove artifacts
			
			final_raster = gdal.Open(out_file_path, gdal.GA_Update)
			topo = final_raster.GetRasterBand(1).ReadAsArray()
	
			
			
			# Re-scale the artifacts bsl.
			
			in_array = topo[(pol_array == 1) * (topo < 0)]
			if in_array.size>0:
				topo[(pol_array == 1) * (topo < 0)] = mod_rescale(in_array, 15, 1)
				final_raster.GetRasterBand(1).WriteArray(topo)
			topo=None
			final_raster = None
			
			
				
			self.progress_count = 100
			self.progress.emit(self.progress_count)
			
			self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")
			

	def create_sea_voronoi(self):
		progress_count = self.progress_count
		temp_dir = self.temp_dir
		out_file_path = self.out_file_path
		self.log.emit('Loading the raster layer')
		topo_layer = self.dlg.baseTopoBox.currentLayer()
		topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
		topo_projection = topo_ds.GetProjection()
		bathy = topo_ds.GetRasterBand(1).ReadAsArray()
		geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
		nrows, ncols = np.shape(bathy)

		# Get the elevation and depth constrains
		min_depth = self.dlg.minElevSpinBox.value()
		max_depth = self.dlg.maxElevSpinBox.value()
		pixel_size_avrg = (topo_layer.rasterUnitsPerPixelX()+topo_layer.rasterUnitsPerPixelY())/2
		

		progress_count += 10
		self.progress.emit(progress_count)

		if bathy is not None:
			self.log.emit(('Size of the Topography raster: {}'.format(bathy.shape)))
		else:
			self.log.emit('There is a problem with reading the Topography raster.')
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
			d_params = {
				'INPUT': mask_layer,
				'INTERVAL': pixel_size_avrg,
				'OUTPUT': 'TEMPORARY_OUTPUT'
			}
			
			mask_layer_densified = processing.run("native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
	
			
			# Extract vertices of the polygon
			extracted_vertices = \
				processing.run("native:extractvertices", {'INPUT': mask_layer_densified, 'OUTPUT': 'TEMPORARY_OUTPUT'})["OUTPUT"]

			# Create voronoy polygons from extracted points
			voronoy_polygons = processing.run("qgis:voronoipolygons",
											  {'INPUT': extracted_vertices, 'BUFFER': 0, 'OUTPUT': 'TEMPORARY_OUTPUT'})[
				"OUTPUT"]

			# Extract vertives of the Voronoy polygons
			extracted_vor_vertices = \
				processing.run("native:extractvertices", {'INPUT': voronoy_polygons, 'OUTPUT': 'TEMPORARY_OUTPUT'})[
					"OUTPUT"]

			self.progress_count += 10
			self.progress.emit(progress_count)

		if not self.killed:
			# Extract the points that lie within the polygon
			sea_center_points = processing.run("native:extractbylocation",
											   {'INPUT': extracted_vor_vertices, 'PREDICATE': [6],
												'INTERSECT': mask_layer,
												'OUTPUT': 'TEMPORARY_OUTPUT'})["OUTPUT"]

			# Find the distance from Center-points to edge-points
			sea_points_dist = processing.run("qgis:distancetonearesthubpoints",
											 {'INPUT': sea_center_points, 'HUBS': extracted_vertices,
											  'FIELD': id_field.name(),
											  'UNIT': 3, 'OUTPUT': 'TEMPORARY_OUTPUT'})["OUTPUT"]
			progress_count += 10
			self.progress.emit(progress_count)
		if not self.killed:
			# Create a new layer to store updated points with depth values
			sea_points_depth = QgsVectorLayer("Point?crs=epsg:4326", "Depth_values", "memory")

			fields = sea_points_dist.fields().toList()
			depth_field = QgsField("Depth", QVariant.Double, "double")
			fields.append(depth_field)

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
				feats_out.append(feat)
				progress_count += int(current * total)
				self.progress.emit(progress_count)

		if not self.killed:
			sea_points_depth_ds.addFeatures(feats_out)
			sea_points_depth.updateFields()
			sea_points_depth_ds = None
			out_file = os.path.join(temp_dir, "Point_layer_with_depths.shp")
			error = QgsVectorFileWriter.writeAsVectorFormat(sea_points_depth, out_file, "UTF-8", sea_points_depth.crs(),
															"ESRI Shapefile")
			if error[0] == QgsVectorFileWriter.NoError:
				pass
			else:
				self.log.emit(
					"ERROR: There was a problem writing the temporary shapefile that stores calculated depths for geographic features to be created.")
				self.killed()

		# Rasterize layers
		# Rasterize sea points layer
		if not self.killed:
			points_raster = processing.run("gdal:rasterize",
										   {'INPUT': out_file, 'FIELD': 'Depth', 'BURN': 0, 'UNITS': 0, 'WIDTH': ncols,
											'HEIGHT': nrows, 'EXTENT': topo_layer, 'NODATA': np.nan, 'OPTIONS': '',
											'DATA_TYPE': 5,
											'INIT': None, 'INVERT': False, 'OUTPUT': 'TEMPORARY_OUTPUT'})["OUTPUT"]

			progress_count += 5
			self.progress.emit(progress_count)

			points_raster_ds = gdal.Open(points_raster)
			points_array = points_raster_ds.GetRasterBand(1).ReadAsArray()

			# Remove the existing values before assigning
			# Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
			initial_values = np.empty(bathy.shape)  # creare an array filled with ones
			initial_values[:] = bathy[:]  # set the finite (not nan) values to zero
			pol_array = vector_to_raster(mask_layer, geotransform, ncols, nrows)
			bathy[pol_array == 1] = np.nan
			# assign values to the topography raster
			bathy[np.isfinite(points_array)] = points_array[np.isfinite(points_array)]

		if not self.killed:
			# Rasterize sea boundaries
			vlayer_line = processing.run("native:polygonstolines", {'INPUT': mask_layer, 'OUTPUT': 'TEMPORARY_OUTPUT'})[
				"OUTPUT"]
			out_file = os.path.join(temp_dir, "sea_polygon_to_line.shp")
			error = QgsVectorFileWriter.writeAsVectorFormat(vlayer_line, out_file, "UTF-8", vlayer_line.crs(),
															"ESRI Shapefile")
			if error[0] == QgsVectorFileWriter.NoError:
				pass
			else:
				self.log.emit(
					"ERROR: There was some problem saving a temporary layer with the boundaries of the geographic features.")
				self.log.emit("ERROR: The algorithm will exit now.")
				self.killed()

			progress_count += 5
			self.progress.emit(progress_count)

			vlayer_line = QgsVectorLayer(out_file, "Polygon-lines", "ogr")
			sea_boundary_array = vector_to_raster(vlayer_line, geotransform, ncols, nrows)

			progress_count += 5
			self.progress.emit(progress_count)

		if not self.killed:
			# assign 0m values to the sea line
			bathy[(sea_boundary_array == 1) * (bathy > 0) == 1] = 0
			bathy[(sea_boundary_array == 1) * np.isnan(bathy) * np.isfinite(initial_values) * (
					initial_values > 0) == 1] = 0

			out_file = os.path.join(temp_dir, "Raster_for_interpolation.tiff")
			# Create a temporary raster to store modified data for interpolation
			raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(out_file, ncols, nrows, 1, gdal.GDT_Float32)
			raster_for_interpolation.SetGeoTransform(geotransform)
			raster_for_interpolation.SetProjection(topo_projection)
			band = raster_for_interpolation.GetRasterBand(1)
			band.SetNoDataValue(np.nan)
			band.WriteArray(bathy)
			raster_for_interpolation = None
			bathy = None

			rlayer = QgsRasterLayer(out_file, "Raster for interpolation", "gdal")
			fill_no_data(rlayer, out_file_path)

			# Load the raster again to remove artefacts
			final_raster = gdal.Open(out_file_path, gdal.GA_Update)
			bathy = final_raster.GetRasterBand(1).ReadAsArray()

			
			# Rescale the artefacts bsl.
			in_array = bathy[(pol_array == 1) * (bathy > 0)]
			if in_array.size>0:
				bathy[(pol_array == 1) * (bathy > 0)] = mod_rescale(in_array, -15, -1)
				final_raster.GetRasterBand(1).WriteArray(bathy)
			bathy=None
			final_raster = None

			# Fill the artefacts with interpolation - did not work well
			# bathy[(pol_array == 1) * (bathy > 0)] = np.nan
			# bathy[(sea_boundary_array == 1) * (bathy > 0)] = 0
			

			# # Get the layer again to fill emptied cells - this strokes should be enabled (uncommented) for filling the gaps \
			# # instead of interpolation.
			# rlayer = QgsRasterLayer(out_file_path, "Raster for interpolation", "gdal")
			# fill_no_data(rlayer, out_file_path)
			#

			progress_count = 100
			self.progress.emit(progress_count)

			self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True
