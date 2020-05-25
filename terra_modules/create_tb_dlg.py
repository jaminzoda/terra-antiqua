

import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
from .utils import loadHelp

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '../ui/create_tb.ui'))


class TaCreateTopoBathyDlg(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaCreateTopoBathyDlg, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        
        # Define the list of geographic features can be created
        geo_features_list = ["Sea", "Mountain range"]
        self.featureTypeBox.addItems(geo_features_list)
        
        #Connect feature type combobox with function that change the dialog according to feature type.
        self.featureTypeBox.currentIndexChanged.connect(self.selectFeatureType)
        
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
        loadHelp(self)    
    def selectFeatureType(self):
        if self.featureTypeBox.currentText() == "Sea":
            self.maxElevSpinBox.setMaximum(0)
            self.maxElevSpinBox.setMinimum(-9999)
            self.maxElevSpinBox.setValue(-5750)
            self.maxElevLabel.setText("Maximum sea depth (in m):")
            
            self.minElevSpinBox.setMaximum(0)
            self.minElevSpinBox.setMinimum(-9999)
            self.minElevSpinBox.setValue(-4000)
            self.minElevLabel.setText("Minimum sea depth (in m):")
            
            self.shelfDepthSpinBox.show()
            self.shelfWidthSpinBox.show()
            self.shelfDepthSpinBox.setMaximum(0)
            self.shelfDepthSpinBox.setMinimum(-1000)
            self.shelfDepthSpinBox.setValue(-200)
            self.shelfDepthLabel.show()
            self.shelfDepthLabel.setText("Maximum shelf depth (in m):")
            self.shelfWidthLabel.show()
            
            self.slopeWidthSpinBox.setValue(100)
            self.slopeWidthLabel.setText("Width of continental slope (in km):")
            
        elif self.featureTypeBox.currentText() == "Mountain range":
            self.maxElevSpinBox.setMaximum(9999)
            self.maxElevSpinBox.setMinimum(0)
            self.maxElevSpinBox.setValue(5000)
            self.maxElevLabel.setText("Maximum ridge elevation (in m):")
            
            self.minElevSpinBox.setMaximum(9999)
            self.minElevSpinBox.setMinimum(0)
            self.minElevSpinBox.setValue(3000)
            self.minElevLabel.setText("Minimum ridge elevation (in m):")
            
            self.shelfDepthSpinBox.show()
            self.shelfDepthSpinBox.setMaximum(100)
            self.shelfDepthSpinBox.setMinimum(0)
            self.shelfDepthSpinBox.setValue(30)
            self.shelfDepthLabel.show()
            self.shelfDepthLabel.setText("Ruggedness of the mountains (in %):")
            self.shelfWidthSpinBox.hide()
            self.shelfWidthLabel.hide()
            
            self.slopeWidthSpinBox.setValue(5)
            self.slopeWidthLabel.setText("Width of mountain slope (in km):")
            
            
            
            

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

    def setProgressValue(self, value):
        self.progressBar.setValue(value)

    def resetProgressValue(self):
        self.progressBar.setValue(0)
