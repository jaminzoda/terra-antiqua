from PyQt5.QtCore import (
	QThread,
	pyqtSignal
)
import os
from osgeo import (
	gdal,
	osr
)

try:
	from plugins import processing
except Exception:
	import processing
	
from qgis.core import (
	QgsVectorFileWriter,
	QgsVectorLayer,
	QgsExpression,
	NULL,
	QgsFeatureRequest
)
import shutil
import tempfile

import numpy as np

from .utils import (
	 vectorToRaster,
	 modFormula,
	 modMinMax,
	 modRescale
	 )



class TaModifyTopoBathy(QThread):
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
			self.log.emit('Size of the Topography raster: {}'.format(topo.shape))
		else:
			self.log.emit('There is a problem with reading the Topography raster')

		# Get the vector masks
		self.log.emit('Getting the vector layer')
		vlayer = self.dlg.masksBox.currentLayer()

		# Send progress feedback
		progress_count += 3
		self.progress.emit(progress_count)

		if vlayer.isValid:
			self.log.emit('The mask layer is loaded properly')
		else:
			self.log.emit('There is a problem with the mask layer - not loaded properly')

		if not self.killed:
			if self.dlg.useAllMasksBox.isChecked():
				# Get features from the vlayer
				features = vlayer.getFeatures()
				feats = vlayer.getFeatures()

				# Count features
				feats_count = 0
				for feat in feats:
					feats_count += 1


			# Modifying the topography raster with different formula for different masks
			else:
				# Get features by attribute from the masks layer - the attributes are fetched in the selected field.
				field = self.dlg.maskNameField.currentField()
				value = self.dlg.maskNameText.text()

				self.log.emit('Fetching the {0} masks from the field {1}'.format(value, field))

				# TODO add ability to specify several names for the masks
				expr = QgsExpression(QgsExpression().createFieldEqualityExpression(field, value))
				features = vlayer.getFeatures(QgsFeatureRequest(expr))

				# Make sure if any feature is returned by our query above
				# If the field name or the name of mask is not specified correctly, our feature iterator (features)
				# will be empty and "any" statement will return false.

				assert (any(True for _ in features)), \
					"Your query did not return any record. Please, check if you specified correct field " \
					"for the names of masks, and that you have typed the name of a mask correctly."

				# Get the features in the feature iterator again, because during the assertion
				# we already iterated over the iterator and it is empty now.
				features = vlayer.getFeatures(QgsFeatureRequest(expr))

				# Count features
				feats = vlayer.getFeatures(QgsFeatureRequest(expr))
				feats_count = 0
				for feat in feats:
					feats_count += 1

		if not self.killed:
			# Create a directory for temporary vector files
			path = os.path.join(out_path, "vector_masks")

			# Send progress feedback
			progress_count += 3
			self.progress.emit(progress_count)

			if not os.path.exists(path):
				try:
					os.mkdir(path)
				except OSError:
					self.log.emit("Creation of the directory {} failed".format(path))
				else:
					self.log.emit("Successfully created the directory {}".format(path))
			else:
				self.log.emit("The folder raster_masks is already created.")

			# Send progress feedback
			progress_count += 2
			self.progress.emit(progress_count)

		if not self.killed:
			# Check if the formula mode of topography modification is checked
			# Otherwise minimum and maximum values will be used to calculate the formula
			if self.dlg.formulaCheckBox.isChecked():

				# Get the fields
				fields = vlayer.fields().toList()

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
					self.log.emit('Formula for topography modification is: {}'.format(formula))

				# Send progress feedback
				progress_count += 3
				self.progress.emit(progress_count)

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
				self.progress.emit(progress_count)

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
				self.progress.emit(progress_count)

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
						self.log.emit("Mask {} does not contain any formula.".format(mask_number))
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
						self.log.emit("Failed to create the {0} shapefile because {1}.".format(os.path.basename(out_file),
																							 error[1]))

					# Rasterize extracted masks
					v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
					r_masks = vectorToRaster(
						v_layer, 
						geotransform, 
						ncols, 
						nrows,
						field_to_burn=None,
						no_data=0
						)
					v_layer = None

					# Modify the topography
					x = topo
					in_array = x[r_masks == 1]
					x[r_masks == 1] = modFormula(in_array, feat_formula, feat_min_value, feat_max_value)

					# Send progress feedback
					progress_count += 70 / feats_count
					self.progress.emit(progress_count)

			else:
				# Get the final minimum and maximum values either from a
				# specified field in the attribute table or from the spinboxes.
				if self.dlg.minMaxFromAttrCheckBox.isChecked():
					# Get the fields from the layer
					fields = vlayer.fields().toList()
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
					self.progress.emit(progress_count)

					mask_number = 0
					for feat in features:
						if self.killed:
							break
						mask_number += 1
						fmin = feat.attributes()[fmin_pos]
						fmax = feat.attributes()[fmax_pos]
						# Check if the min and max fields contain any value
						if fmin == NULL or fmax == NULL:
							self.log.emit("Mask {} does not contain final maximum or/and minimum values specified in the attributes table.". format(mask_number))
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
							self.log.emit(
								"The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
						else:
							self.log.emit(
								"Failed to create the {0} shapefile because {1}.".format(os.path.basename(out_file),
																					   error[1]))

						# Rasterize extracted masks
						v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
						r_masks = vectorToRaster(
							v_layer, 
							geotransform, 
							ncols, 
							nrows,
							field_to_burn=None,
							no_data=0
							)
						v_layer = None

						# Modify the topography
						x = topo
						in_array = x[r_masks == 1]
						x[r_masks == 1] = modRescale(in_array, fmin, fmax)

						# Send progress feedback
						progress_count += 75 / feats_count
						self.progress.emit(progress_count)
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
						self.progress.emit(progress_count)

						# Create a temporary shapefile to store extracted masks before rasterizing them
						out_file = os.path.join(path, 'masks_for_topo_modification.shp')

						if os.path.exists(out_file):
							deleted = QgsVectorFileWriter.deleteShapeFile(out_file)

						error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8",
																		temp_layer.crs(), "ESRI Shapefile")

						if error == QgsVectorFileWriter.NoError:
							self.log.emit(
								"The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
						else:
							self.log.emit(
								"Failed to create the {0} shapefile because {1}.".format(os.path.basename(out_file),
																					   error[1]))

						# Send progress feedback
						progress_count += 10
						self.progress.emit(progress_count)

					if not self.killed:
						# Rasterize extracted masks
						v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
						r_masks = vectorToRaster(
							v_layer, 
							geotransform, 
							ncols, 
							nrows,
							field_to_burn=None,
							no_data=0
							)
						v_layer = None

						# Send progress feedback
						progress_count += 30
						self.progress.emit(progress_count)

					if not self.killed:
						# Modify the topography
						x = topo
						in_array = x[r_masks == 1]
						x[r_masks == 1] = modRescale(in_array, fmin, fmax)

						# Send progress feedback
						progress_count += 30
						self.progress.emit(progress_count)

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
		self.progress.emit(progress_count)

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
				self.progress.emit(progress_count)
			else:
				self.log.emit("The plugin did not succeed because one or more parameters were set incorrectly.")
				self.log.emit("Please, check the log above.")
				self.finished.emit(False, "")
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True
