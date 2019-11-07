# This script creates a dialog form for our second tool in the plugin

import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'feature_creator_dialog_base.ui'))


class FeatureCreatorDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(FeatureCreatorDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Set the mode of QgsFileWidget to directory mode
        self.outputPath.setStorageMode(self.outputPath.SaveFile)
        self.outputPath.setFilter('*.tif;;*.tiff')
        # Base topography layer
        self.baseTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.baseTopoBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens raster layers from disk
        self.selectTopoBaseButton.clicked.connect(self.addLayerToBaseTopo)

        # Input masks layer
        self.masksBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.masksBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens vector layers from disk
        self.selectMasksButton.clicked.connect(self.addLayerToMasks)

        self.logText.clear()
        self.logText.setReadOnly(True)

        # Set the run button enabled only when the user selected input layers.
        self.runButton.setEnabled(False)
        self.masksBox.layerChanged.connect(self.enableRunButton)
        self.baseTopoBox.layerChanged.connect(self.enableRunButton)

        # set the help text in the  help box (QTextBrowser)
        path_to_file = os.path.join(os.path.dirname(__file__), "help_text/help_FeatureCreator.html")
        help_file = open(path_to_file, 'r', encoding='utf-8')
        help_text = help_file.read()
        self.helpBox.setHtml(help_text)

    def enableRunButton(self):
        if self.baseTopoBox.currentLayer() != None and self.masksBox.currentLayer() != None:
            self.runButton.setEnabled(True)
            self.warningLabel.setText('')
        else:
            self.warningLabel.setText('Please, select all the mandatory fields.')
            self.warningLabel.setStyleSheet('color:red')

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

    def set_progress_value(self, value):
        self.progressBar.setValue(value)

    def reset_progress_value(self):
        self.progressBar.setValue(0)
