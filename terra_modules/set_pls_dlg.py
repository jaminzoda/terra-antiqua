

import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer

from .utils import loadHelp

FORM_CLASS, _ = uic.loadUiType(os.path.join(
	os.path.dirname(__file__), '../ui/set_pls.ui'))

class TaSetPaleoshorelinesDlg(QtWidgets.QDialog, FORM_CLASS):
	def __init__(self, parent=None):
		"""Constructor."""
		super(TaSetPaleoshorelinesDlg, self).__init__(parent)
		# Set up the user interface from Designer through FORM_CLASS2.
		# After self.setupUi() you can access any designer object by doing
		# self.<objectname>, and you can use autoconnect slots - see
		# http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
		# #widgets-and-dialogs-with-auto-connect
		self.setupUi(self)

		#Set the mode of QgsFileWidget to directory mode
		self.outputPath.setStorageMode(self.outputPath.SaveFile)
		self.outputPath.setFilter('*.tif;;*.tiff')
		#Base topography layer
		self.baseTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
		self.baseTopoBox.setLayer(None)
		# Connect the tool buttons to the file dialog that opens raster layers from disk
		self.selectTopoBaseButton.clicked.connect(self.addLayerToBaseTopo)


		#Input masks layer
		self.masksBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
		self.masksBox.setLayer(None)
		# Connect the tool buttons to the file dialog that opens vector layers from disk
		self.selectMasksButton.clicked.connect(self.addLayerToMasks)

		self.logText.clear()
		self.logText.setReadOnly(True)

		# Select modification mode
		self.selectModificationModeInterpolate(1)
		self.interpolateCheckBox.stateChanged.connect(self.selectModificationModeInterpolate)
		self.rescaleCheckBox.stateChanged.connect(self.selectModificationModeRescale)

	   #Set the run button enabled only when the user selected input layers.
		self.runButton.setEnabled(False)
		self.masksBox.layerChanged.connect(self.enableRunButton)
		self.baseTopoBox.layerChanged.connect(self.enableRunButton)
		
		loadHelp(self)

	def enableRunButton(self):
		if  self.baseTopoBox.currentLayer()!=None and self.masksBox.currentLayer()!=None:
			self.runButton.setEnabled(True)
			self.warningLabel.setText('')
		else:
			self.warningLabel.setText('Please, select all the mandatory fields.')
			self.warningLabel.setStyleSheet('color:red')

	def selectModificationModeInterpolate(self, state):
		if state > 0:
			self.rescaleCheckBox.setChecked(False)
			self.maxElevSpinBox.setEnabled(False)
			self.maxDepthSpinBox.setEnabled(False)
			self.interpolateCheckBox.setChecked(True)
		else:
			self.rescaleCheckBox.setChecked(True)
			self.maxElevSpinBox.setEnabled(True)
			self.maxDepthSpinBox.setEnabled(True)
			self.interpolateCheckBox.setChecked(False)

	def selectModificationModeRescale(self, state):
		if state > 0:
			self.rescaleCheckBox.setChecked(True)
			self.maxElevSpinBox.setEnabled(True)
			self.maxDepthSpinBox.setEnabled(True)
			self.interpolateCheckBox.setChecked(False)
		else:
			self.rescaleCheckBox.setChecked(False)
			self.maxElevSpinBox.setEnabled(False)
			self.maxDepthSpinBox.setEnabled(False)
			self.interpolateCheckBox.setChecked(True)

	def addLayerToBaseTopo(self):
		self.openRasterFromDisk(self.baseTopoBox)

	def addLayerToMasks(self):
		self.openVectorFromDisk(self.masksBox)

	def openVectorFromDisk(self, box):
		fd = QFileDialog()
		filter = "Vector files (*.shp)"
		fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)

		if fname:
			name, _ = os.path.splitext(os.path.basename(fname))
			vlayer = QgsVectorLayer(fname, name, 'ogr')
			QgsProject.instance().addMapLayer(vlayer)
			box.setLayer(vlayer)

	def openRasterFromDisk(self, box):
		fd = QFileDialog()
		filter = "Raster files (*.jpg *.tif *.grd *.nc *.png *.tiff)"
		fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)

		if fname:
			name, _ = os.path.splitext(os.path.basename(fname))
			rlayer = QgsRasterLayer(fname, name, 'gdal')
			QgsProject.instance().addMapLayer(rlayer)
			box.setLayer(rlayer)

	def setProgressValue(self, value):
		self.progressBar.setValue(value)

	def resetProgressValue(self):
		self.progressBar.setValue(0)
