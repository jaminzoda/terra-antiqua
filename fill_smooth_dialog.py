#This script creates a dialog form for our second tool in the plugin
import os

from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
import os
import datetime


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'fill_smooth_dialog_base.ui'))

class FillSmoothDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(FillSmoothDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Specify the type for filling the gaps.
        # list of options
        options = ['Interpolation', 'Fill from another raster', 'Smoothing']
        self.fillingTypeBox.addItems(options)
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.fillingTypeBox.currentIndexChanged.connect(self.typeOfFilling)


        #Set the mode of QgsFileWidget to directory mode
        self.outputPath.setStorageMode(self.outputPath.GetDirectory)

        #Base topography layer
        self.baseTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.baseTopoBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens raster layers from disk
        self.selectTopoBaseButton.clicked.connect(self.addLayerToBaseTopo)

        #Raster to copy elevation data from  for filling the gaps
        self.copyFromRasterBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.copyFromRasterBox.setLayer(None)
        self.selectCopyFromRasterButton.clicked.connect(self.addLayerToBaseTopo)

        #Input masks layer
        self.masksBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.masksBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens vector layers from disk
        self.selectMasksButton.clicked.connect(self.addLayerToMasks)

        self.logText.clear()
        self.logText.setReadOnly(True)


       #Set the run button enabled only when the user selected input layers.
        self.runButton.setEnabled(False)
        self.masksBox.layerChanged.connect(self.enableRunButton)
        self.baseTopoBox.layerChanged.connect(self.enableRunButton)

        #Set the type of interpolation
        self.interpolateAllCheckBox.setChecked(True)
        self.interpolateAllCheckBox.stateChanged.connect(self.allRasterInterpolationChecked)
        self.interpolateInMaskCheckBox.stateChanged.connect(self.inMaskInterpolationChecked)


    def typeOfFilling(self):
        current_index = self.fillingTypeBox.currentIndex()
        if current_index == 0:
            self.copyFromRasterBox.hide()
            self.copyFromRasterLabel.hide()
            self.selectCopyFromRasterButton.hide()
            self.interpolateAllCheckBox.show()
            self.interpolateInMaskCheckBox.show()
            self.masksBox.show()
            self.selectMasksButton.show()
            self.masksBoxLabel.show()

        elif current_index == 1:
            self.copyFromRasterBox.show()
            self.copyFromRasterLabel.show()
            self.selectCopyFromRasterButton.show()
            self.interpolateAllCheckBox.hide()
            self.interpolateInMaskCheckBox.hide()
            self.masksBox.show()
            self.selectMasksButton.show()
            self.masksBoxLabel.show()
        elif current_index==2:
            self.copyFromRasterBox.hide()
            self.copyFromRasterLabel.hide()
            self.selectCopyFromRasterButton.hide()
            self.interpolateAllCheckBox.hide()
            self.interpolateInMaskCheckBox.hide()
            self.masksBox.hide()
            self.selectMasksButton.hide()
            self.masksBoxLabel.hide()
            self.smoothingBox.hide()

    def allRasterInterpolationChecked(self,state):
        if state>0:
            self.interpolateInMaskCheckBox.setChecked(False)
            self.masksBox.setEnabled(False)
            self.selectMasksButton.setEnabled(False)
    def inMaskInterpolationChecked(self,state):
        if state>0:
            self.interpolateAllCheckBox.setChecked(False)
            self.masksBox.setEnabled(True)
            self.selectMasksButton.setEnabled(True)





    def enableRunButton(self):
        if  self.baseTopoBox.currentLayer()!=None:
            self.runButton.setEnabled(True)
            self.warningLabel.setText('')
        else:
            self.warningLabel.setText('Plaese, select all the base raster file.')
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

    def log(self,msgs):
        #get the current time
        time=datetime.datetime.now()
        time=str(time.hour)+':'+str(time.minute)+':'+str(time.second)
        msg=' '
        for m in msgs:
            msg=msg+' '+m

        # inserting log messages into the qplantextedit widget
        self.logText.textCursor().insertText(time+' - '+msg+' \n')

       #log_handler.setFormatter(logging.Formatter('\n %(asctime)s - %(levelname)s - %(message)s'))









