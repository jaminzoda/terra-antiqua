"""
/***************************************************************************
 DEMBuilder
                                 A QGIS plugin
 The plugin creates a paleoDEM by combyning present day topography and paleobathimetry, and modiying the final topography by introducing masks.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-03-18
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Jovid Aminov
        email                : jovid.aminov@outlook.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import shutil
import os.path
import sys
import logging
import datetime
import numpy as np
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QAction, QToolBar
from osgeo import gdal, osr, ogr
from qgis.core import QgsVectorFileWriter, QgsRasterLayer, QgsVectorLayer, QgsExpression, QgsFeatureRequest, \
	QgsMessageLog, QgsRasterBandStats, QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer, \
	QgsWkbTypes, QgsProject, QgsGeometry, NULL, QgsFeature

import processing
# Import the code for the dialog
from .dem_builder_dialog import DEMBuilderDialog
from .mask_maker_dialog import MaskMakerDialog
from .topo_modifier_dialog import TopoModifierDialog
from .paleoshorelines_dialog import PaleoshorelinesDialog
from .std_proc_dialog import StdProcessingDialog
from .topotools import RasterTools as rt
from .topotools import ArrayTools as at
from .topotools import VectorTools as vt
from .algs import TopoBathyCompiler, MaskMaker, TopoModifier


# Initialize Qt resources from file resources.py

class DEMBuilder:
	"""QGIS Plugin Implementation."""

	def __init__(self, iface):
		"""Constructor.

		:param iface: An interface instance that will be passed to this class
			which provides the hook by which you can manipulate the QGIS
			application at run time.
		:type iface: QgsInterface
		"""
		# Save reference to the QGIS interface
		self.iface = iface
		# initialize plugin directory
		self.plugin_dir = os.path.dirname(__file__)
		# initialize locale
		locale = QSettings().value('locale/userLocale')[0:2]
		locale_path = os.path.join(
			self.plugin_dir,
			'i18n',
			'DEMBuilder_{}.qm'.format(locale))

		if os.path.exists(locale_path):
			self.translator = QTranslator()
			self.translator.load(locale_path)

			if qVersion() > '4.3.3':
				QCoreApplication.installTranslator(self.translator)

		# Declare instance attributes
		self.actions = []
		self.menu = self.tr(u'&Paleogeography')

		# Create a separate toolbar for the tool
		self.pg_toolBar = iface.mainWindow().findChild(QToolBar, u'Paleogeography')
		if not self.pg_toolBar:
			self.pg_toolBar = iface.addToolBar(u'Paleogeography')
			self.pg_toolBar.setObjectName(u'Paleogeography')

		# Check if plugin was started the first time in current QGIS session
		# Must be set in initGui() to survive plugin reloads
		self.first_start = None

	# Create the tool dialog

	# noinspection PyMethodMayBeStatic
	def tr(self, message):
		"""Get the translation for a string using Qt translation API.

		We implement this ourselves since we do not inherit QObject.

		:param message: String for translation.
		:type message: str, QString

		:returns: Translated version of message.
		:rtype: QString
		"""
		# noinspection PyTypeChecker,PyArgumentList,PyCallByClass
		return QCoreApplication.translate('DEMBuilder', message)

	def add_action(
			self,
			icon_path,
			text,
			callback,
			enabled_flag=True,
			add_to_menu=True,
			add_to_toolbar=True,
			status_tip=None,
			whats_this=None,
			parent=None):
		"""Add a toolbar icon to the toolbar.

		:param icon_path: Path to the icon for this action. Can be a resource
			path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
		:type icon_path: str

		:param text: Text that should be shown in menu items for this action.
		:type text: str

		:param callback: Function to be called when the action is triggered.
		:type callback: function

		:param enabled_flag: A flag indicating if the action should be enabled
			by default. Defaults to True.
		:type enabled_flag: bool

		:param add_to_menu: Flag indicating whether the action should also
			be added to the menu. Defaults to True.
		:type add_to_menu: bool

		:param add_to_toolbar: Flag indicating whether the action should also
			be added to the toolbar. Defaults to True.
		:type add_to_toolbar: bool

		:param status_tip: Optional text to show in a popup when mouse pointer
			hovers over the action.
		:type status_tip: str

		:param parent: Parent widget for the new action. Defaults None.
		:type parent: QWidget

		:param whats_this: Optional text to show in the status bar when the
			mouse pointer hovers over the action.

		:returns: The action that was created. Note that the action is also
			added to self.actions list.
		:rtype: QAction
		"""

		icon = QIcon(icon_path)
		action = QAction(icon, text, parent)
		action.triggered.connect(callback)
		action.setEnabled(enabled_flag)

		if status_tip is not None:
			action.setStatusTip(status_tip)

		if whats_this is not None:
			action.setWhatsThis(whats_this)

		if add_to_toolbar:
			# Adds plugin icon to Plugins toolbar
			self.pg_toolBar.addAction(action)

		if add_to_menu:
			self.iface.addPluginToMenu(
				self.menu,
				action)

		self.actions.append(action)

		return action

	def initGui(self):
		"""Create the menu entries and toolbar icons inside the QGIS GUI."""

		dem_builder_icon = os.path.join(self.plugin_dir, 'icon.png')
		mask_prep_icon = os.path.join(self.plugin_dir, 'mask.png')
		topo_modifier_icon = os.path.join(self.plugin_dir, 'topomod.png')
		p_coastline_icon = os.path.join(self.plugin_dir, 'paleocoastlines.png')
		std_proc_icon = os.path.join(self.plugin_dir, 'fill_smooth.png')

		self.add_action(
			dem_builder_icon,
			text=self.tr(u'Topography and bathymetry compiler'),
			callback=self.load_topo_bathy_compiler,
			parent=self.iface.mainWindow())

		self.add_action(
			topo_modifier_icon,
			text=self.tr(u'Topoggraphy modifier'),
			callback=self.load_topo_modifier,
			parent=self.iface.mainWindow())
		self.add_action(
			p_coastline_icon,
			text=self.tr(u'Paleoshorelines reconstructor'),
			callback=self.paleocoastlines_dlg_load,
			parent=self.iface.mainWindow())
		self.add_action(
			std_proc_icon,
			text=self.tr(u'Standard processing tools'),
			callback=self.std_processing_dlg_load,
			parent=self.iface.mainWindow())

		self.pg_toolBar.addSeparator()

		self.add_action(
			mask_prep_icon,
			text=self.tr(u'Mask preparator'),
			callback=self.load_mask_maker,
			parent=self.iface.mainWindow())

		# will be set False in run()
		self.first_start = True

	def unload(self):
		"""Removes the plugin menu item and icon from QGIS GUI."""
		for action in self.actions:
			self.iface.removePluginMenu(
				self.tr(u'&Paleogeography'),
				action)
			self.iface.removeToolBarIcon(action)

	def load_topo_bathy_compiler(self):

		# Create the dialog with elements (after translation) and keep reference
		# Only create GUI ONCE in callback, so that it will only load when the plugin is started
		# if self.first_start == True:
		# 	self.first_start = False
		self.dlg = DEMBuilderDialog()
		# Show the dialog
		self.dlg.show()
		self.dlg.Tabs.setCurrentIndex(0)
		# When the run button is pressed, topography modification algorithm is run.
		self.dlg.runButton.clicked.connect(self.start_topo_bathy_compiler)
		self.dlg.cancelButton.clicked.connect(self.stop_topo_bathy_compiler)

	def start_topo_bathy_compiler(self):
		self.dlg.Tabs.setCurrentIndex(1)
		self.dlg.cancelButton.setEnabled(True)
		self.dlg.runButton.setEnabled(False)
		self.tbc_thread = TopoBathyCompiler(self.dlg)
		self.tbc_thread.change_value.connect(self.dlg.set_progress_value)
		self.tbc_thread.log.connect(self.tbc_print_log)
		self.tbc_thread.start()
		self.tbc_thread.finished.connect(self.tbc_add_result_to_canvas)

	def stop_topo_bathy_compiler(self):
		self.tbc_thread.kill()
		self.dlg.reset_progress_value()
		self.dlg.cancelButton.setEnabled(False)
		self.dlg.runButton.setEnabled(True)
		self.tbc_print_log("The paleoDEM was NOT compiled, because the user canceled processing.")
		self.tbc_print_log("Or something went wrong. Please, refer to the log above for more details.")
		self.dlg.warningLabel.setText('Error!')
		self.dlg.warningLabel.setStyleSheet('color:red')

	def finish_topo_bathy_compiler(self):
		self.dlg.cancelButton.setEnabled(False)
		self.dlg.runButton.setEnabled(True)
		self.dlg.warningLabel.setText('Done!')
		self.dlg.warningLabel.setStyleSheet('color:green')

	def tbc_add_result_to_canvas(self, finished, out_file_path):
		if finished is True:
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]
			rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
			if rlayer:
				# Rendering a symbology style for the resulting raster layer.
				rt.set_raster_symbology(rlayer)
				self.tbc_print_log("The compiler has compiled topography and bathymetry sucessfully,")
				self.tbc_print_log("and added the resulting paleoDEM to the map canvas.")
			else:
				self.tbc_print_log("The topography and bathymetry compiling algorithm has extracted masks successfully,")
				self.tbc_print_log("however the resulting layer did not load. You may need to load it manually.")
			self.finish_topo_bathy_compiler()
		else:
			self.stop_topo_bathy_compiler()

	def tbc_print_log(self, msg):
		# get the current time
		time = datetime.datetime.now()
		time = "{}:{}:{}".format(time.hour, time.minute, time.second)
		self.dlg.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))



	def load_mask_maker(self):

		# Create the tool dialog
		self.dlg2 = MaskMakerDialog()
		# show the dialog
		self.dlg2.show()

		self.dlg2.Tabs.setCurrentIndex(0)
		# When the run button is clicked, the MaskMaker algorithm is ran.
		self.dlg2.runButton.clicked.connect(self.start_mask_maker)
		self.dlg2.cancelButton.clicked.connect(self.stop_mask_maker)

	def start_mask_maker(self):
		self.dlg2.Tabs.setCurrentIndex(1)
		self.dlg2.cancelButton.setEnabled(True)
		self.dlg2.runButton.setEnabled(False)
		self.mm_thread = MaskMaker(self.dlg2)
		self.mm_thread.change_value.connect(self.dlg2.set_progress_value)
		self.mm_thread.log.connect(self.mm_print_log)
		self.mm_thread.start()
		self.mm_thread.finished.connect(self.mm_add_result_to_canvas)

	def stop_mask_maker(self):
		self.mm_thread.kill()
		self.dlg2.reset_progress_value()
		self.dlg2.cancelButton.setEnabled(False)
		self.dlg2.runButton.setEnabled(True)
		self.mm_print_log("The paleoDEM was NOT compiled, because the user canceled processing.")
		self.mm_print_log("Or something went wrong. Please, refer to the log above for more details.")
		self.dlg2.warningLabel.setText('Error!')
		self.dlg2.warningLabel.setStyleSheet('color:red')

	def finish_mask_maker(self):
		self.dlg2.cancelButton.setEnabled(False)
		self.dlg2.runButton.setEnabled(True)
		self.dlg2.warningLabel.setText('Done!')
		self.dlg2.warningLabel.setStyleSheet('color:green')

	def mm_add_result_to_canvas(self, finished, out_file_path):
		if finished is True:
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]
			vlayer = self.iface.addVectorLayer(out_file_path, file_name, "ogr")
			if vlayer:
				self.mm_print_log("The mask preparation algorithm has extracted masks successfully,")
				self.mm_print_log("and added the resulting layer to the map canvas.")
			else:
				self.mm_print_log("The mask preparation algorithm has extracted masks successfully,")
				self.mm_print_log("however the resulting layer did not load. You may need to load it manually.")
			self.finish_mask_maker()
		else:
			self.stop_mask_maker()
	def mm_print_log(self, msg):
		# get the current time
		time = datetime.datetime.now()
		time = "{}:{}:{}".format(time.hour, time.minute, time.second)
		self.dlg2.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))



	def load_topo_modifier(self):

		# Get the dialog
		self.dlg3 = TopoModifierDialog()

		# show the dialog
		self.dlg3.show()
		self.dlg3.Tabs.setCurrentIndex(0) #make sure the parameters tab is displayed on load.
		# When the run button is pressed, topography modification algorithm is ran.
		self.dlg3.runButton.clicked.connect(self.start_topo_modifier)
		self.dlg3.cancelButton.clicked.connect(self.stop_topo_modifier)

	def start_topo_modifier(self):
		self.dlg3.Tabs.setCurrentIndex(1) #switch to the log tab.
		self.dlg3.cancelButton.setEnabled(True)
		self.dlg3.runButton.setEnabled(False)
		self.tm_thread = TopoModifier(self.dlg3)
		self.tm_thread.change_value.connect(self.dlg3.set_progress_value)
		self.tm_thread.log.connect(self.tm_print_log)
		self.tm_thread.start()
		self.tm_thread.finished.connect(self.tm_add_result_to_canvas)

	def stop_topo_modifier(self):
		self.tm_thread.kill()
		self.dlg3.reset_progress_value()
		self.dlg3.cancelButton.setEnabled(False)
		self.dlg3.runButton.setEnabled(True)
		self.tm_print_log("The topography was NOT modified, because the user canceled processing.")
		self.tm_print_log("Or something went wrong. Please, refer to the log above for more details.")
		self.dlg3.warningLabel.setText('Error!')
		self.dlg3.warningLabel.setStyleSheet('color:red')

	def finish_topo_modifier(self):
		self.dlg3.cancelButton.setEnabled(False)
		self.dlg3.runButton.setEnabled(True)
		self.dlg3.warningLabel.setText('Done!')
		self.dlg3.warningLabel.setStyleSheet('color:green')

	def tm_add_result_to_canvas(self, finished, out_file_path):
		if finished is True:
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]
			rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
			if rlayer:
				rt.set_raster_symbology(rlayer)
				self.tm_print_log("The algorithm has modified the topography of selected regions successfully,")
				self.tm_print_log("and added the resulting layer to the map canvas with the following name: {}.".format(file_name))
			else:
				self.tm_print_log("The algorithm has modified the topography of selected regions successfully,")
				self.tm_print_log("however the resulting layer did not load. You may need to load it manually.")
			self.finish_topo_modifier()
		else:
			self.stop_topo_modifier()

	def tm_print_log(self, msg):
		# get the current time
		time = datetime.datetime.now()
		time = "{}:{}:{}".format(time.hour, time.minute, time.second)
		self.dlg3.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))

	def paleocoastlines_dlg_load(self):
		self.dlg4 = PaleoshorelinesDialog()

		# show the dialog
		self.dlg4.show()
		# Run the dialog event loop
		# result = self.dlg4.exec_()

		# # Set up logging to use the dlg4 text widget as a handler
		# self.log_widget=self.dlg4.logText

		# See if OK was pressed
		# if result:

		self.dlg4.runButton.pressed.connect(self.run_paleocoastlines)

	def run_paleocoastlines(self):
		# get the log widget
		log = self.dlg4.log

		log('Starting')

		self.dlg4.Tabs.setCurrentIndex(1)

		log('Getting the raster layer')
		topo_layer = self.dlg4.baseTopoBox.currentLayer()
		topo_extent = topo_layer.extent()
		topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
		topo = topo_ds.GetRasterBand(1).ReadAsArray()
		geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
		nrows, ncols = np.shape(topo)

		if not topo is None:
			log(('Size of the Topography raster: ', str(topo.shape)))
		else:
			log('There is a problem with reading the Topography raster')

		# Get the vector masks
		log('Getting the vector layer')
		mask_layer = self.dlg4.masksBox.currentLayer()

		if mask_layer.isValid:
			log('The mask layer is loaded properly')
		else:
			log('There is a problem with the mask layer - not loaded properly')

		r_masks = vt.vector_to_raster(mask_layer, geotransform, ncols, nrows)
		# The bathymetry values that are above sea level are taken down below sea level
		in_array = topo[(r_masks == 0) * (topo > 0) == 1]
		topo[(r_masks == 0) * (topo > 0) == 1] = at.mod_rescale(in_array, -100, -0.05)

		# The topography values that are below sea level are taken up above sea level
		in_array = topo[(r_masks == 1) * (topo < 0) == 1]
		topo[(r_masks == 1) * (topo < 0) == 1] = at.mod_rescale(in_array, 0.05, 100)

		# Check if raster was modified. If the x matrix was assigned.
		if 'topo' in locals():
			# Write the resulting raster array to a raster file
			out_file_path = self.dlg4.outputPath.filePath()

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

			# Add the resulting layer to the Qgis map canvas.
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]  # Name of the file to be added.
			rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")

			# Rendering a symbology style for the resulting raster layer
			rt.set_raster_symbology(rlayer)

			log("The raster was modified successfully.")

		else:
			log("The plugin did not succeed because one or more parameters were set incorrectly.")
			log("Please, check the log above.")

	def std_processing_dlg_load(self):
		self.dlg5 = StdProcessingDialog()

		# show the dialog
		self.dlg5.show()

		self.dlg5.runButton.pressed.connect(self.run_std_processing)

	def run_std_processing(self):
		processing_type = self.dlg5.fillingTypeBox.currentIndex()

		if processing_type == 0:
			base_raster_layer = self.dlg5.baseTopoBox.currentLayer()
			out_file_path = self.dlg5.outputPath.filePath()
			interpolated_raster = rt.fill_no_data(base_raster_layer, out_file_path)

			if self.dlg5.smoothingBox.isChecked():
				# Get the layer for smoothing
				interpolated_raster_layer = QgsRasterLayer(interpolated_raster, 'Interpolated DEM', 'gdal')

				# Get smoothing factor
				sm_factor = self.dlg5.smFactorSpinBox.value()
				# Smooth the raster
				rt.raster_smoothing(interpolated_raster_layer, sm_factor)

			# Add the interolated raster to the map canvas
			if self.dlg5.addToCanvasCheckBox.isChecked():
				# Get the name of the file from its path to add the raster with this name to the map canvas.
				file_name = os.path.splitext(os.path.basename(interpolated_raster))[0]
				resulting_layer = self.iface.addRasterLayer(interpolated_raster, file_name, "gdal")
				# Apply a colour palette to the added layer
				rt.set_raster_symbology(resulting_layer)

		elif processing_type == 1:
			# Get a raster layer to copy the elevation values FROM
			from_raster_layer = self.dlg5.copyFromRasterBox.currentLayer()
			from_raster = gdal.Open(from_raster_layer.dataProvider().dataSourceUri())
			from_array = from_raster.GetRasterBand(1).ReadAsArray()

			# Get a raster layer to copy the elevation values TO
			to_raster_layer = self.dlg5.baseTopoBox.currentLayer()
			to_raster = gdal.Open(to_raster_layer.dataProvider().dataSourceUri())
			to_array = to_raster.GetRasterBand(1).ReadAsArray()

			# Get a vector coontaining masks
			mask_vector_layer = self.dlg5.masksBox.currentLayer()

			# Get the path for saving the resulting raster
			filled_raster_path = self.dlg5.outputPath.filePath()

			# Rasterize masks
			geotransform = to_raster.GetGeoTransform()
			nrows, ncols = to_array.shape
			out_path = os.path.dirname(self.dlg5.outputPath.filePath())

			mask_array = vt.vector_to_raster(mask_vector_layer, geotransform, ncols, nrows)

			# Fill the raster
			to_array[mask_array == 1] = from_array[mask_array == 1]

			# Create a new raster for the result
			output_raster = gdal.GetDriverByName('GTiff').Create(filled_raster_path, ncols, nrows, 1, gdal.GDT_Float32)
			output_raster.SetGeoTransform(geotransform)
			crs = to_raster_layer.crs()
			output_raster.SetProjection(crs.toWkt())
			output_band = output_raster.GetRasterBand(1)
			output_band.SetNoDataValue(np.nan)
			output_band.WriteArray(to_array)
			output_band.FlushCache()
			output_raster = None

			# Add the interpolated raster to the map canvas
			if self.dlg5.addToCanvasCheckBox.isChecked():
				# Get the name of the file from its path to add the raster with this name to the map canvas.
				file_name = os.path.splitext(os.path.basename(filled_raster_path))[0]
				resulting_layer = self.iface.addRasterLayer(filled_raster_path, file_name, "gdal")
				# Apply a colour palette to the added layer
				rt.set_raster_symbology(resulting_layer)
		elif processing_type == 2:
			raster_to_smooth_layer = self.dlg5.baseTopoBox.currentLayer()
			smoothing_factor = self.dlg5.smFactorSpinBox.value()
			output_file = self.dlg5.outputPath.filePath()

			smoothed_raster_layer = rt.raster_smoothing(raster_to_smooth_layer, smoothing_factor, output_file)

			# Add the smoothed raster to the map canvas
			if self.dlg5.addToCanvasCheckBox.isChecked():
				# Get the name of the file from its path to add the raster with this name to the map canvas.
				file_path = smoothed_raster_layer.dataProvider().dataSourceUri()
				file_name = os.path.splitext(os.path.basename(file_path))[0]
				resulting_layer = self.iface.addRasterLayer(file_path, file_name, "gdal")
				# Apply a colour palette to the added layer
				rt.set_raster_symbology(resulting_layer)

		elif processing_type == 3:
			# Get the output file path
			out_file_path = self.dlg5.outputPath.filePath()
			# Get the bedrock topography raster
			topo_br_layer = self.dlg5.baseTopoBox.currentLayer()
			topo_br_ds = gdal.Open(topo_br_layer.dataProvider().dataSourceUri())
			topo_br_data = topo_br_ds.GetRasterBand(1).ReadAsArray()

			# Get the ice surface topography raster
			topo_ice_layer = self.dlg5.selectIceTopoBox.currentLayer()
			topo_ice_ds = gdal.Open(topo_ice_layer.dataProvider().dataSourceUri())
			topo_ice_data = topo_ice_ds.GetRasterBand(1).ReadAsArray()

			# Get the masks
			mask_layer = self.dlg5.masksBox.currentLayer()

			if self.dlg5.masksFromCoastCheckBox.isChecked():
				# Get features from the masks layer
				expr = QgsExpression(
					"lower(\"NAME\") LIKE '%greenland%' OR lower(\"NAME\") LIKE '%antarctic%' OR lower(\"NAME\") LIKE '%marie byrd%' OR lower(\"NAME\") LIKE '%ronne ice%' OR lower(\"NAME\") LIKE '%thurston%' OR lower(\"NAME\") LIKE '%admundsen%'")

				features = mask_layer.getFeatures(QgsFeatureRequest(expr))
				temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
				temp_prov = temp_layer.dataProvider()
				temp_prov.addFeatures(features)

				path = os.path.join(os.path.dirname(out_file_path), 'vector_masks')
				if not os.path.exists(path):
					try:
						os.mkdir(path)
					except OSError:
						print("Creation of the directory %s failed" % path)
					else:
						print("Successfully created the directory %s " % path)

				out_file = os.path.join(path, 'isostat_comp_masks.shp')
				if os.path.exists(out_file):
					# function deleteShapeFile return bool True iif deleted False if not
					deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
					if deleted:
						print(out_file + "has been deleted.")
					else:
						print(out_file + "is not deleted.")

				error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8", mask_layer.crs(),
																"ESRI Shapefile")
				if error[0] == QgsVectorFileWriter.NoError:
					print("The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
				else:
					print("Failed to create the {} shapefile because {}.".format(os.path.basename(out_file), error[1]))

				# Rasterize extracted masks
				geotransform = topo_br_ds.GetGeoTransform()
				nrows, ncols = np.shape(topo_br_data)
				v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
				r_masks = vt.vector_to_raster(v_layer, geotransform, ncols, nrows)

				# Close  the temporary vector layer
				v_layer = None

				# Remove the shapefile of the temporary vector layer from the disk. Also remove the temporary folder created for it.

				if os.path.exists(out_file):
					deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
					if deleted:
						if os.path.exists(path):
							shutil.rmtree(path)
						else:
							print('I created a temporary folder with a shapefile at: ' + os.path.join(path))
							print('And could not delete it. You may need delete it manually.')


			else:
				geotransform = topo_br_ds.GetGeoTransform()
				nrows, ncols = np.shape(topo_br_data)
				r_masks = vt.vector_to_raster(mask_layer, geotransform, ncols, nrows)

			# Compensate for ice load
			rem_amount = self.dlg5.iceAmountSpinBox.value()  # the amount of ice that needs to be removed.
			comp_factor = 0.3 * (topo_ice_data[r_masks == 1] - topo_br_data[r_masks == 1]) * rem_amount / 100
			comp_factor[np.isnan(comp_factor)] = 0
			comp_factor[comp_factor < 0] = 0
			topo_br_data[r_masks == 1] = topo_br_data[r_masks == 1] + comp_factor

			# Create a new raster for the result
			output_raster = gdal.GetDriverByName('GTiff').Create(out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
			output_raster.SetGeoTransform(geotransform)
			crs = topo_br_layer.crs()
			output_raster.SetProjection(crs.toWkt())
			output_band = output_raster.GetRasterBand(1)
			output_band.SetNoDataValue(np.nan)
			output_band.WriteArray(topo_br_data)
			output_band.FlushCache()
			output_raster = None

			# Add the interpolated raster to the map canvas
			if self.dlg5.addToCanvasCheckBox.isChecked():
				# Get the name of the file from its path to add the raster with this name to the map canvas.
				file_name = os.path.splitext(os.path.basename(out_file_path))[0]
				resulting_layer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
				# Apply a colour palette to the added layer
				rt.set_raster_symbology(resulting_layer)
