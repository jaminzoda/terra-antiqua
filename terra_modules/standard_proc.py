from PyQt5.QtCore import (
	QThread,
	pyqtSignal
)
import os
from osgeo import gdal

try:
	from plugins import processing
except Exception:
	import processing
	
	
from qgis.core import (
	QgsVectorFileWriter,
	QgsVectorLayer,
	QgsRasterLayer,
	QgsExpression,
	QgsFeatureRequest
	)
import shutil
import tempfile

import numpy as np


from.utils import (
	vectorToRaster, 
	fillNoData, 
#	rasterSmoothing,
	fillNoDataInPolygon
	)
from .gauss_smooth import rasterSmoothing



class TaStandardProcessing(QThread):
	progress = pyqtSignal(int)
	finished = pyqtSignal(bool, object)
	log = pyqtSignal(object)

	def __init__(self, dlg):
		super().__init__()
		self.dlg = dlg
		self.killed = False
		self.progress_count = 0

	def run(self):

		self.log.emit("Starting the processing...")
		processing_type = self.dlg.fillingTypeBox.currentIndex()

		# Getting the ouput path
		# TODO Must check if the path is a valid path. In case the user inputs the name of the file but not the full path.
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
				
			elif processing_type == 4:
				out_file_path = os.path.join(temp_dir, 'PaleoDEM_interpolated.tif')
			
		else:
			out_file_path = self.dlg.outputPath.filePath()

		if processing_type == 0:
			if not self.killed:
				self.log.emit("Getting the raster layer for the interpolation.")
				base_raster_layer = self.dlg.baseTopoBox.currentLayer()
				self.log.emit("Starting the interpolation.")
				self.log.emit("Interpolation method is Inverse Distance Weighting.")
				
				if self.dlg.interpInsidePolygonCheckBox.isChecked():
					mask_layer = self.dlg.masksBox.currentLayer()
					interpolated_raster = fillNoDataInPolygon(base_raster_layer, mask_layer, out_file_path)
				else:
					interpolated_raster = fillNoData(base_raster_layer, out_file_path)
				self.log.emit("Interpolation finished.")

				if self.dlg.smoothingBox.isChecked():
					self.progress_count += 20
					self.progress.emit(self.progress_count)
				else:
					self.progress_count += 40
					self.progress.emit(self.progress_count)

					
			if not self.killed:

				if self.dlg.smoothingBox.isChecked():
					self.log.emit("Starting smoothing.")
					# Get the layer for smoothing
					interpolated_raster_layer = QgsRasterLayer(interpolated_raster, 'Interpolated DEM', 'gdal')

					# Get smoothing factor
					sm_factor = self.dlg.smFactorSpinBox.value()


					# Smooth the raster
					rasterSmoothing(interpolated_raster_layer, sm_factor, feedback=self, runtime_percentage=78)
					self.log.emit("Smoothing has finished.")

					# progress_count += 40

					self.log.emit("The gaps in the raster were filled and it was smoothed successfully.")
					self.log.emit("The resulting layer is saved at: "
								  "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
					self.progress.emit(100)
					self.finished.emit(True, out_file_path)

				else:
					self.log.emit("The gaps in the raster were filled successfully.")
					self.log.emit("The resulting layer is saved at: "
								  "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
					self.progress.emit(100)
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
				self.rogress_count += 10
				self.progress.emit(self.progress_count)
			if not self.killed:
				# Get a raster layer to copy the elevation values TO
				self.log.emit("Getting the raster to copy the elevation values to.")
				to_raster_layer = self.dlg.baseTopoBox.currentLayer()
				to_raster = gdal.Open(to_raster_layer.dataProvider().dataSourceUri())
				to_array = to_raster.GetRasterBand(1).ReadAsArray()
				self.progress_count += 10
				self.progress.emit(self.progress_count)

			if not self.killed:
				self.log.emit("Getting the masks from the vector layer.")
				# Get a vector containing masks
				mask_vector_layer = self.dlg.masksBox.currentLayer()

				self.log.emit("Rasterizing the masks from the vector layer.")
				# Rasterize masks
				geotransform = to_raster.GetGeoTransform()
				nrows, ncols = to_array.shape
				mask_array = vectorToRaster(
					mask_vector_layer, 
					geotransform, 
					ncols, 
					nrows,
					field_to_burn=None,
					no_data=0
					)

				self.log.emit("The masks are rasterized.")
				self.progress_count += 40
				self.progress.emit(self.progress_count)
			if not self.killed:
				self.log.emit("Copying the elevation values.")
				# Fill the raster
				to_array[mask_array == 1] = from_array[mask_array == 1]
				self.progress_count += 20
				self.progress.emit(self.progress_count)

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

				self.progress.emit(100)
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
			if not self.killed:
				self.log.emit("Smoothing the raster.")
				smoothed_raster_layer = rasterSmoothing(raster_to_smooth_layer, smoothing_factor, out_file_path,
															feedback = self)
				self.log.emit("The raster is smoothed successfully and saved at: "
							  "<a href='file://{}'>{}</a>".format(os.path.dirname(out_file_path), out_file_path))
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
				self.progress_count += 5
				self.progress.emit(self.progress_count)

			if not self.killed:
				self.log.emit("Getting the ice topography raster layer.")
				# Get the ice surface topography raster
				topo_ice_layer = self.dlg.selectIceTopoBox.currentLayer()
				topo_ice_ds = gdal.Open(topo_ice_layer.dataProvider().dataSourceUri())
				topo_ice_data = topo_ice_ds.GetRasterBand(1).ReadAsArray()
				self.progress_count += 5
				self.progress.emit(self.progress_count)
			if not self.killed:
				# Get the masks
				self.log.emit("Getting the mask layer.")
				vlayer = self.dlg.masksBox.currentLayer()
				self.progress_count += 5
				self.progress.emit(self.progress_count)

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

					features = vlayer.getFeatures(QgsFeatureRequest(expr))
					temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
					temp_prov = temp_layer.dataProvider()
					temp_prov.addFeatures(features)

					self.progress_count += 5
					self.progress.emit(self.progress_count)

				if not self.killed:

					path = os.path.join(os.path.dirname(out_file_path), 'vector_masks')
					self.log.emit(
						"Creating a temporary folder to save extracted masks for rasterization at: {}.".format(path))
					if not os.path.exists(path):
						try:
							os.mkdir(path)
						except OSError:
							self.log.emit("Creation of the directory %s failed" % path)
						else:
							self.log.emit("Successfully created the directory %s " % path)

					out_file = os.path.join(path, 'isostat_comp_masks.shp')
					self.log.emit(
						"The shapefile {} already exists in the {} folder, therefore I am deleting it.".format(out_file,
																											   path))
					if os.path.exists(out_file):
						# function deleteShapeFile return bool True iif deleted False if not
						deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
						if deleted:
							self.log.emit(out_file + "has been deleted.")
						else:
							self.log.emit(out_file + "is not deleted.")

					self.progress_count += 5
					self.progress.emit(self.progress_count)

					error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8", vlayer.crs(),
																	"ESRI Shapefile")
					if error[0] == QgsVectorFileWriter.NoError:
						self.log.emit("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
					else:
						self.log.emit("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file),
																							 error[1]))

					self.progress_count += 5
					self.progress.emit(self.progress_count)

				if not self.killed:
					self.log.emit("Rasterizing exrtacted masks.")
					# Rasterize extracted masks
					geotransform = topo_br_ds.GetGeoTransform()
					nrows, ncols = np.shape(topo_br_data)
					v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
					r_masks = vectorToRaster(
						v_layer, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)

					self.progress_count += 10
					self.progress.emit(self.progress_count)

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
					self.progress_count += 5
					self.progress.emit(self.progress_count)

			else:
				if not self.killed:
					geotransform = topo_br_ds.GetGeoTransform()
					nrows, ncols = np.shape(topo_br_data)
					self.log.emit("Rasterizing the masks.")
					r_masks = vectorToRaster(
						vlayer, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)

					self.progress_count += 30
					self.progress.emit(self.progress_count)
			if not self.killed:
				# Compensate for ice load
				self.log.emit("Compensating for ice load.")
				rem_amount = self.dlg.iceAmountSpinBox.value()  # the amount of ice that needs to be removed.
				comp_factor = 0.3 * (topo_ice_data[r_masks == 1] - topo_br_data[r_masks == 1]) * rem_amount / 100
				comp_factor[np.isnan(comp_factor)] = 0
				comp_factor[comp_factor < 0] = 0
				topo_br_data[r_masks == 1] = topo_br_data[r_masks == 1] + comp_factor
				self.progress_count += 30
				self.progress.emit(self.progress_count)
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
				self.progress.emit(100)
				self.finished.emit(True, out_file_path)
			else:
				self.finished.emit(False, "")
		
			

	def kill(self):
		self.killed = True



