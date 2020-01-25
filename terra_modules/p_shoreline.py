from PyQt5.QtCore import QThread, pyqtSignal
import os
from osgeo import gdal, osr, gdalconst
from qgis.core import QgsRasterLayer
import tempfile

import numpy as np

from .topotools import (
	polygons_to_polylines,
	vector_to_raster,
	fill_no_data,
	mod_rescale
	)



class PaleoShorelines(QThread):
	progress = pyqtSignal(int)
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

		# Get the elevation and depth constrains
		max_elev = self.dlg.maxElevSpinBox.value()
		max_depth = self.dlg.maxDepthSpinBox.value()

		progress_count += 10
		self.progress.emit(progress_count)

		if topo is not None:
			self.log.emit(('Size of the Topography raster: {}'.format(topo.shape)))
		else:
			self.log.emit('There is a problem with reading the Topography raster')
			self.kill()

		# Get the vector masks
		self.log.emit('Getting the vector layer')
		vlayer = self.dlg.masksBox.currentLayer()

		if vlayer.isValid() and vlayer.featureCount()>0:
			self.log.emit('The mask layer is loaded properly')
		elif vlayer.isValid() and vlayer.featureCount()==0:
			self.log.emit("Error: The mask layer has no features. Please add polygon features to it and try again.")
			self.kill()
		else:
			self.log.emit('There is a problem with the mask layer - not loaded properly')
			self.kill()

		progress_count += 10
		self.progress.emit(progress_count)

		# Check which type of modification is chosen

		if self.dlg.interpolateCheckBox.isChecked():
			if not self.killed:
				self.log.emit('The interpolation mode is selected.')
				self.log.emit('In this mode the difference area between paleoshorelines and present day shorelines')
				self.log.emit(
					'will be set to NAN values, after which the values of these cells will be interpolated from adjacent cells.')

			if not self.killed:
				# Converting polygons to polylines in order to set the shoreline values to 0
				path_to_polylines = os.path.join(os.path.dirname(vlayer.source()), "polylines_from_polygons.shp")
				pshoreline = polygons_to_polylines(vlayer, path_to_polylines)
				pshoreline_rmask = vector_to_raster(
					pshoreline, 
					geotransform, 
					ncols, 
					nrows,
					field_to_burn=None,
					no_data=0
					)
				# Setting shorelines to 0 m
				topo[pshoreline_rmask == 1] = 0

			progress_count += 10
			self.progress.emit(progress_count)

			if not self.killed:
				# Getting the raster masks of the land and sea area
				r_masks = vector_to_raster(
					vlayer, 
					geotransform, 
					ncols, 
					nrows,
					field_to_burn=None,
					no_data=0
					)
				

			if not self.killed:
				# Setting the inland values that are below sea level, and in-sea values that are above sea level to
				# NAN (empty cell)
				# Creating an empty matrix to copy values from topo before setting them to NaN
				topo_values_copied = np.empty(topo.shape)
				topo_values_copied[:] = np.nan
				topo_values_copied[(r_masks == 1) * (topo < 0) == 1] = topo[(r_masks == 1) * (topo < 0) == 1]
				topo_values_copied[(r_masks == 0) * (topo > 0) == 1] = topo[(r_masks == 0) * (topo > 0) == 1]
				topo[(r_masks == 1) * (topo < 0) == 1] = np.nan
				topo[(r_masks == 0) * (topo > 0) == 1] = np.nan

			progress_count += 10
			self.progress.emit(progress_count)

			if not self.killed:
				# Check if raster was modified. If the x matrix was assigned.
				if 'topo' in locals():

					driver = gdal.GetDriverByName('GTiff')
					if os.path.exists(out_file_path):
						driver.Delete(out_file_path)

					raster = driver.Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
					raster.SetGeoTransform(geotransform)
					crs = topo_layer.crs().toWkt()
					raster.SetProjection(crs)
					raster.GetRasterBand(1).SetNoDataValue(np.nan)
					raster.GetRasterBand(1).WriteArray(topo)
					raster = None

					progress_count += 5
					self.progress.emit(progress_count)

					raster_layer = QgsRasterLayer(out_file_path, "PaleoShorelines_without_theGaps_filled", "gdal")

					raster_layer_interpolated = os.path.join(os.path.dirname(out_file_path),
															 "PaleoShorelines_with-gaps_filled.tiff")
					ret = fill_no_data(raster_layer, raster_layer_interpolated)

					progress_count += 10
					self.progress.emit(progress_count)

					# Read the resulting raster to check if the interpolation was done correctly.
					# If some areas are interpolated between to zero values of shorelines (i.e. large areas were
					# assigned zero values), the old values will used and rescaled below/above sea level
					raster_layer_ds = gdal.Open(raster_layer_interpolated, gdalconst.GA_Update)
					topo_modified = raster_layer_ds.GetRasterBand(1).ReadAsArray()
					
					array_to_rescale_bsl = topo_values_copied[np.isfinite(topo_values_copied) * (topo_modified == 0)
															  * (r_masks == 0) == 1]
					
					array_to_rescale_asl = topo_values_copied[np.isfinite(topo_values_copied) * (topo_modified == 0)
															  * (r_masks == 1) == 1]
					if array_to_rescale_bsl.size>0 and np.isfinite(array_to_rescale_bsl).size>0:
						topo_modified[np.isfinite(topo_values_copied) * (topo_modified == 0) * (r_masks == 0) == 1] = \
							mod_rescale(array_to_rescale_bsl, -5, -0.1)
						
					if array_to_rescale_asl.size>0 and np.isfinite(array_to_rescale_asl).size>0:
						topo_modified[np.isfinite(topo_values_copied) * (topo_modified == 0) * (r_masks == 1) == 1] = \
							mod_rescale(array_to_rescale_asl, 0.1, 5)

					progress_count += 5
					self.progress.emit(progress_count)

					# Removing final artefacts from the sea and land. Some pixels that are close to the shoreline
					# touch pixels on the other side of the shoreline and get wrong value during the interpolation

					# Pixel values of the sea that are asl
					data_to_fill_bsl = topo_values_copied[(r_masks == 0) * (topo_modified > 0) *
														  (np.isfinite(topo_values_copied)) == 1]
					if data_to_fill_bsl.size>0 and np.isfinite(data_to_fill_bsl).size>0:
						topo_modified[(r_masks == 0) * (topo_modified > 0) * np.isfinite(topo_values_copied) == 1] \
							= mod_rescale(data_to_fill_bsl, -5, -0.1)

					progress_count += 5
					self.progress.emit(progress_count)

					# Pixel values of land that are bsl
					data_to_fill_asl = topo_values_copied[(r_masks == 1) * (topo_modified < 0) *
														  np.isfinite(topo_values_copied) == 1]
					if data_to_fill_asl.size>0 and np.isfinite(data_to_fill_asl).size>0:
						topo_modified[(r_masks == 1) * (topo_modified < 0) * np.isfinite(topo_values_copied) == 1] \
							= mod_rescale(data_to_fill_asl, 0.1, 5)

					progress_count += 5
					self.progress.emit(progress_count)

					# Still removing artifacts
					topo_modified[(r_masks == 0) * (topo_modified > 0)] = np.nan
					topo_modified[(r_masks == 1) * (topo_modified < 0)] = np.nan

					progress_count += 5
					self.progress.emit(progress_count)

					# Updating the raster with the modified values
					raster_layer_ds.GetRasterBand(1).WriteArray(topo_modified)
					raster_layer_ds = None

					progress_count += 5
					self.progress.emit(progress_count)

					self.log.emit(
						"The raster was modified successfully and saved at: <a href='file://{}'>{}</a>.".format(
							os.path.dirname(raster_layer_interpolated), raster_layer_interpolated))

					self.finished.emit(True, raster_layer_interpolated)

					self.progress.emit(100)

				else:
					self.log.emit("The plugin did not succeed because one or more parameters were set incorrectly.")
					self.log.emit("Please, check the log above.")
					self.finished.emit(False, "")
			else:
				self.finished.emit(False, "")



		elif self.dlg.rescaleCheckBox.isChecked():
			if not self.killed:
				r_masks = vector_to_raster(
					vlayer, 
					geotransform, 
					ncols, 
					nrows,
					field_to_burn=None,
					no_data=0
					)
				# The bathymetry values that are above sea level are taken down below sea level
				in_array = topo[(r_masks == 0) * (topo > 0) == 1]
				topo[(r_masks == 0) * (topo > 0) == 1] = mod_rescale(in_array, max_depth, -0.1)

				progress_count += 30
				self.progress.emit(progress_count)

			if not self.killed:
				# The topography values that are below sea level are taken up above sea level
				in_array = topo[(r_masks == 1) * (topo < 0) == 1]
				topo[(r_masks == 1) * (topo < 0) == 1] = mod_rescale(in_array, 0.1, max_elev)

				progress_count += 30
				self.progress.emit(progress_count)

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
					self.progress.emit(progress_count)

					self.log.emit(
						"The raster was modified successfully and saved at: <a href='file://{}'>{}</a>.".format(
							os.path.dirname(out_file_path), out_file_path))

					self.finished.emit(True, out_file_path)

					self.progress.emit(100)

				else:
					self.log.emit("The plugin did not succeed because one or more parameters were set incorrectly.")
					self.log.emit("Please, check the log above.")
					self.finished.emit(False, "")
			else:
				self.finished.emit(False, "")

	def kill(self):
		self.killed = True
