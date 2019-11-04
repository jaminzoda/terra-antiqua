"""
/***************************************************************************
 TerraAntiqua
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
import datetime
import os
import os.path

from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QToolBar

from .algs import TopoBathyCompiler, MaskMaker, TopoModifier, PaleoShorelines, StandardProcessing, FeatureCreator
from .feature_creator_dialog import FeatureCreatorDialog
from .mask_maker_dialog import MaskMakerDialog
from .paleoshorelines_dialog import PaleoshorelinesDialog
from .std_proc_dialog import StdProcessingDialog
# Import the code for the dialog
from .terra_antiqua_dialog import TerraAntiquaDialog
from .topo_modifier_dialog import TopoModifierDialog
from .topotools import RasterTools as rt


# Initialize Qt resources from file resources.py

class TerraAntiqua:
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
			'TerraAntiqua_{}.qm'.format(locale))

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
		return QCoreApplication.translate('TerraAntiqua', message)

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

	feat_create_icon = os.path.join(self.plugin_dir, 'feat_create.png')

		self.add_action(
			dem_builder_icon,
			text=self.tr(u'Topography and bathymetry compiler'),
			callback=self.load_topo_bathy_compiler,
			parent=self.iface.mainWindow())

		self.add_action(
			topo_modifier_icon,
			text=self.tr(u'Topography modifier'),
			callback=self.load_topo_modifier,
			parent=self.iface.mainWindow())
		self.add_action(
			p_coastline_icon,
			text=self.tr(u'Paleoshorelines reconstructor'),
			callback=self.load_paleoshorelines,
			parent=self.iface.mainWindow())
		self.add_action(
			std_proc_icon,
			text=self.tr(u'Standard processing tools'),
			callback=self.load_std_processing,
			parent=self.iface.mainWindow())

		self.pg_toolBar.addSeparator()


self.add_action(
	feat_create_icon,
	text=self.tr(u'Geographic feature creator'),
	callback=self.load_feature_creator,
	parent=self.iface.mainWindow())

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
		self.dlg = TerraAntiquaDialog()
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

	def load_paleoshorelines(self):
		self.dlg4 = PaleoshorelinesDialog()

		# show the dialog
		self.dlg4.show()

		# When the run button is clicked, the MaskMaker algorithm is ran.
		self.dlg4.runButton.clicked.connect(self.start_paleoshorelines)
		self.dlg4.cancelButton.clicked.connect(self.stop_paleoshorelines)

	def start_paleoshorelines(self):
		self.dlg4.Tabs.setCurrentIndex(1)  # switch to the log tab.
		self.dlg4.cancelButton.setEnabled(True)
		self.dlg4.runButton.setEnabled(False)
		self.ps_thread = PaleoShorelines(self.dlg4)
		self.ps_thread.change_value.connect(self.dlg4.set_progress_value)
		self.ps_thread.log.connect(self.ps_print_log)
		self.ps_thread.start()
		self.ps_thread.finished.connect(self.ps_add_result_to_canvas)

	def stop_paleoshorelines(self):
		self.ps_thread.kill()
		self.dlg4.reset_progress_value()
		self.dlg4.cancelButton.setEnabled(False)
		self.dlg4.runButton.setEnabled(True)
		self.ps_print_log("The topography was NOT modified, because the user canceled processing.")
		self.ps_print_log("Or something went wrong. Please, refer to the log above for more details.")
		self.dlg4.warningLabel.setText('Error!')
		self.dlg4.warningLabel.setStyleSheet('color:red')

	def finish_paleoshorelines(self):
		self.dlg4.cancelButton.setEnabled(False)
		self.dlg4.runButton.setEnabled(True)
		self.dlg4.warningLabel.setText('Done!')
		self.dlg4.warningLabel.setStyleSheet('color:green')

	def ps_add_result_to_canvas(self, finished, out_file_path):
		if finished is True:
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]
			rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
			if rlayer:
				rt.set_raster_symbology(rlayer)
				self.ps_print_log("The paleoshorelines are set successfully,")
				self.ps_print_log(
					"and the resulting layer is added to the map canvas with the following name: {}.".format(file_name))
			else:
				self.ps_print_log("The algorithm has set  paleoshorelines successfully,")
				self.ps_print_log("however the resulting layer did not load. You may need to load it manually.")
			self.finish_paleoshorelines()
		else:
			self.stop_paleoshorelines()

	def ps_print_log(self, msg):
		# get the current time
		time = datetime.datetime.now()
		time = "{}:{}:{}".format(time.hour, time.minute, time.second)
		self.dlg4.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))

	def load_std_processing(self):
		self.dlg5 = StdProcessingDialog()

		# show the dialog
		self.dlg5.show()

		# When the run button is clicked, the MaskMaker algorithm is ran.
		self.dlg5.runButton.clicked.connect(self.start_std_processing)
		self.dlg5.cancelButton.clicked.connect(self.stop_std_processing)

	def start_std_processing(self):
		self.dlg5.Tabs.setCurrentIndex(1)  # switch to the log tab.
		self.dlg5.cancelButton.setEnabled(True)
		self.dlg5.runButton.setEnabled(False)
		self.std_p_thread = StandardProcessing(self.dlg5)
		self.std_p_thread.change_value.connect(self.dlg5.set_progress_value)
		self.std_p_thread.log.connect(self.std_p_print_log)
		self.std_p_thread.start()
		self.std_p_thread.finished.connect(self.std_p_add_result_to_canvas)

	def stop_std_processing(self):
		self.std_p_thread.kill()
		self.dlg5.reset_progress_value()
		self.dlg5.cancelButton.setEnabled(False)
		self.dlg5.runButton.setEnabled(True)
		self.std_p_print_log("The processing was not successful, because the user canceled processing.")
		self.std_p_print_log("Or something went wrong. Please, refer to the log above for more details.")
		self.dlg5.warningLabel.setText('Error!')
		self.dlg5.warningLabel.setStyleSheet('color:red')

	def finish_std_processing(self):
		self.dlg5.cancelButton.setEnabled(False)
		self.dlg5.runButton.setEnabled(True)
		self.dlg5.warningLabel.setText('Done!')
		self.dlg5.warningLabel.setStyleSheet('color:green')

	def std_p_add_result_to_canvas(self, finished, out_file_path):
		if finished is True:
			file_name = os.path.splitext(os.path.basename(out_file_path))[0]
			rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
			if rlayer:
				rt.set_raster_symbology(rlayer)
				self.std_p_print_log("The processing is finished successfully,")
				self.std_p_print_log(
					"and the resulting layer is added to the map canvas with the following name: {}.".format(file_name))
			else:
				self.std_p_print_log("The processing was finished successfully,")
				self.std_p_print_log("however the resulting layer did not load. You may need to load it manually.")
			self.finish_std_processing()
		else:
			self.stop_std_processing()

	def std_p_print_log(self, msg):
		# get the current time
		time = datetime.datetime.now()
		time = "{}:{}:{}".format(time.hour, time.minute, time.second)
		self.dlg5.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))


def load_feature_creator(self):
	self.dlg6 = FeatureCreatorDialog()

	# show the dialog
	self.dlg6.show()

	# When the run button is clicked, the MaskMaker algorithm is ran.
	self.dlg6.runButton.clicked.connect(self.start_feature_creator)
	self.dlg6.cancelButton.clicked.connect(self.stop_feature_creator)


def start_feature_creator(self):
	self.dlg6.Tabs.setCurrentIndex(1)  # switch to the log tab.
	self.dlg6.cancelButton.setEnabled(True)
	self.dlg6.runButton.setEnabled(False)
	self.fc_thread = FeatureCreator(self.dlg6)
	self.fc_thread.change_value.connect(self.dlg6.set_progress_value)
	self.fc_thread.log.connect(self.fc_print_log)
	self.fc_thread.start()
	self.fc_thread.finished.connect(self.fc_add_result_to_canvas)


def stop_feature_creator(self):
	self.fc_thread.kill()
	self.dlg6.reset_progress_value()
	self.dlg6.cancelButton.setEnabled(False)
	self.dlg6.runButton.setEnabled(True)
	self.fc_print_log("The topography was NOT modified, because the user canceled processing.")
	self.fc_print_log("Or something went wrong. Please, refer to the log above for more details.")
	self.dlg6.warningLabel.setText('Error!')
	self.dlg6.warningLabel.setStyleSheet('color:red')


def finish_feature_creator(self):
	self.dlg6.cancelButton.setEnabled(False)
	self.dlg6.runButton.setEnabled(True)
	self.dlg6.warningLabel.setText('Done!')
	self.dlg6.warningLabel.setStyleSheet('color:green')


def fc_add_result_to_canvas(self, finished, out_file_path):
	if finished is True:
		file_name = os.path.splitext(os.path.basename(out_file_path))[0]
		rlayer = self.iface.addRasterLayer(out_file_path, file_name, "gdal")
		if rlayer:
			rt.set_raster_symbology(rlayer)
			self.fc_print_log("The geographic features are created successfully,")
			self.fc_print_log(
				"and the resulting layer is added to the map canvas with the following name: {}.".format(file_name))
		else:
			self.fc_print_log("The algorithm has set  paleoshorelines successfully,")
			self.fc_print_log("however the resulting layer did not load. You may need to load it manually.")
		self.finish_feature_creator()
	else:
		self.stop_feature_creator()


def fc_print_log(self, msg):
	# get the current time
	time = datetime.datetime.now()
	time = "{}:{}:{}".format(time.hour, time.minute, time.second)
	self.dlg6.logText.textCursor().insertHtml("{} - {} <br>".format(time, msg))
