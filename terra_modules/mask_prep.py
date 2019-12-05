
from PyQt5.QtCore import QThread, pyqtSignal
import os
from qgis.core import (
	QgsVectorLayer,
	QgsWkbTypes,
	QgsGeometry,
	QgsFeatureRequest,
	QgsVectorFileWriter
	)
import tempfile
try:
	from plugins import processing
except Exception:
	import processing
	
from .topotools import refactor_fields


class MaskMaker(QThread):
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

		# Send progress feedback
		progress_count += 5
		self.progress.emit(progress_count)

		# Temporary layers assigned
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
					feature = QgsFeatureRequest()
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
				# Refactor the field types, if they are different
				fixed_line_refactored, fields_refactored = refactor_fields(fixed_line, fixed_poly)

				if len(fields_refactored) == 0:
					layers_to_merge = [fixed_poly, fixed_line]
				else:
					self.log.emit("The fields {} in {} are refactored".format(fields_refactored, fixed_line.name()))
					layers_to_merge = [fixed_poly, fixed_line_refactored]

				params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:' + name}
				temp_layer = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
				fixed_poly = None
				fixed_line = None
				self.log.emit(
					"Polygonized polylines from {} are merged with polygons from {}.".format(line.name(), poly.name()))
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
			self.progress.emit(progress_count)

		# Check if the cancel button was pressed
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
			self.progress.emit(progress_count)
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
			self.progress.emit(progress_count)
			self.log.emit("Continental shelf  masks extracted.")

		if not self.killed:
			# Combining the extracted masks in one shape file.
			if ss_extracted is not None and cs_extracted is not None:
				# Refactor the field types, if they are different
				ss_extracted_refactored, fields_refactored = refactor_fields(ss_extracted, cs_extracted)

				if len(fields_refactored) == 0:
					layers_to_merge = [ss_extracted, cs_extracted]
				else:
					self.log.emit("The fields {} in {} are refactored".format(fields_refactored, ss_extracted.name()))
					layers_to_merge = [ss_extracted_refactored, cs_extracted]

				params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:ss+cs'}
				ss_and_cs_extracted = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
			else:
				ss_and_cs_extracted = None

			# Send progress feedback
			progress_count += 10
			self.progress.emit(progress_count)

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
			self.progress.emit(progress_count)

			self.log.emit("Continents masks extracted.")

		if not self.killed:
			if masks_layer is not None and coast_temp is not None:
				# Refactor the field types, if they are different
				masks_layer_refactored, fields_refactored = refactor_fields(masks_layer, coast_temp)

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
			self.progress.emit(progress_count)
			self.log.emit("Masks merged in one layer.")

		# TODO When the file is loaded to the current QGIS project, it can't be deleted.
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
				self.log.emit(
					"Failed to create the {} shapefile because {}.".format(os.path.basename(out_file_path), error[1]))
				self.killed = True

		if not self.killed:
			self.progress.emit(100)
			self.finished.emit(True, out_file_path)
		else:
			self.finished.emit(False, "")

	def kill(self):
		self.killed = True
