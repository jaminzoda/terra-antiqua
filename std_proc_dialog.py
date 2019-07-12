#This script creates a dialog form for our second tool in the plugin

import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'std_proc_dialog_base.ui'))

class StdProcessingDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(StdProcessingDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Specify the type for filling the gaps.
        # list of options
        options = ['Interpolation', 'Fill from another raster', 'Smoothing','Isostatic compensation']
        self.fillingTypeBox.addItems(options)
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.fillingTypeBox.currentIndexChanged.connect(self.typeOfFilling)

        #Set the default appearance of the dialog
        self.copyFromRasterBox.hide()
        self.copyFromRasterLabel.hide()
        self.selectCopyFromRasterButton.hide()
        self.masksBox.hide()
        self.selectMasksButton.hide()
        self.masksBoxLabel.hide()
        self.selectIceTopoBox.hide()
        self.selectIceTopoButton.hide()
        self.iceTopoLabel.hide()

        self.iceAmountLabel.hide()
        self.iceAmountSpinBox.hide()
        self.masksFromCoastCheckBox.hide()



        #Set the mode of QgsFileWidget to directory mode
        self.outputPath.setStorageMode(self.outputPath.SaveFile)
        self.outputPath.setFilter('*.tif;;*.tiff')

        #Base topography layer
        self.baseTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.baseTopoBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens raster layers from disk
        self.selectTopoBaseButton.clicked.connect(self.addLayerToBaseTopo)

        # Ice topography layer
        self.selectIceTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.selectIceTopoBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens raster layers from disk
        self.selectIceTopoButton.clicked.connect(self.addLayerToBaseTopo)

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
        
        #set the help text in the  help box (QTextBrowser)
        path_to_file = os.path.join(os.path.dirname(__file__), "help_text/help_Interpolation.html")
        help_file = open(path_to_file, 'r', encoding='utf-8')
        help_text = help_file.read()
        self.helpBox.setHtml(help_text)



    def typeOfFilling(self):
        current_index = self.fillingTypeBox.currentIndex()
        if current_index == 0:
            self.copyFromRasterBox.hide()
            self.copyFromRasterLabel.hide()
            self.selectCopyFromRasterButton.hide()

            self.masksBox.hide()
            self.selectMasksButton.hide()
            self.masksBoxLabel.hide()
            self.smoothingBox.show()
            self.smoothingLabel.show()
            self.smFactorSpinBox.show()

            self.selectIceTopoBox.hide()
            self.selectIceTopoButton.hide()
            self.iceTopoLabel.hide()

            self.iceAmountLabel.hide()
            self.iceAmountSpinBox.hide()
            self.masksFromCoastCheckBox.hide()

            #set the help text in the  help box (QTextBrowser)
            path_to_file = os.path.join(os.path.dirname(__file__), "help_text/help_Interpolation.html")
            help_file = open(path_to_file, 'r', encoding='utf-8')
            help_text = help_file.read()
            self.helpBox.setHtml(help_text)
        
        elif current_index == 1:
            self.copyFromRasterBox.show()
            self.copyFromRasterLabel.show()
            self.selectCopyFromRasterButton.show()
            self.masksBox.show()
            self.selectMasksButton.show()
            self.masksBoxLabel.show()
            self.smoothingBox.hide()
            self.smoothingLabel.hide()
            self.smFactorSpinBox.hide()

            self.selectIceTopoBox.hide()
            self.selectIceTopoButton.hide()
            self.iceTopoLabel.hide()

            self.iceAmountLabel.hide()
            self.iceAmountSpinBox.hide()
            self.masksFromCoastCheckBox.hide()

            #set the help text in the  help box (QTextBrowser)
            path_to_file = os.path.join(os.path.dirname(__file__),"help_text/help_FillFromAnotherRaster.html")
            help_file = open(path_to_file, 'r', encoding='utf-8')
            help_text = help_file.read()
            self.helpBox.setHtml(help_text)
                
        elif current_index==2:
            self.copyFromRasterBox.hide()
            self.copyFromRasterLabel.hide()
            self.selectCopyFromRasterButton.hide()

            self.masksBox.hide()
            self.selectMasksButton.hide()
            self.masksBoxLabel.hide()
            self.smoothingBox.hide()
            self.smoothingLabel.show()
            self.smFactorSpinBox.show()

            self.selectIceTopoBox.hide()
            self.selectIceTopoButton.hide()
            self.iceTopoLabel.hide()


            self.iceAmountLabel.hide()
            self.iceAmountSpinBox.hide()
            self.masksFromCoastCheckBox.hide()

            #set the help text in the  help box (QTextBrowser)
            path_to_file = os.path.join(os.path.dirname(__file__), "help_text/help_Smoothing.html")
            help_file = open(path_to_file, 'r', encoding='utf-8')
            help_text = help_file.read()
            self.helpBox.setHtml(help_text)

        elif current_index==3:
            self.copyFromRasterBox.hide()
            self.copyFromRasterLabel.hide()
            self.selectCopyFromRasterButton.hide()

            self.masksBox.show()
            self.selectMasksButton.show()
            self.masksBoxLabel.show()
            self.smoothingBox.hide()
            self.smoothingLabel.hide()
            self.smFactorSpinBox.hide()

            self.selectIceTopoBox.show()
            self.selectIceTopoButton.show()
            self.iceTopoLabel.show()

            self.iceAmountLabel.show()
            self.iceAmountSpinBox.show()
            self.masksFromCoastCheckBox.show()


            #set the help text in the  help box (QTextBrowser)
            path_to_file = os.path.join(os.path.dirname(__file__),"help_text/help_IsostaticCompensation.html")
            help_file = open(path_to_file, 'r', encoding='utf-8')
            help_text = help_file.read()
            self.helpBox.setHtml(help_text)




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










