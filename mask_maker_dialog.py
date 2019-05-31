#This script creates a dialog form for our second tool in the plugin
import os

from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'mask_maker_dialog_base.ui'))

class MaskMakerDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(MaskMakerDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.selectCoastlineMask.clear()
        self.selectCoastlineMask.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.selectCoastlineMask.setLayer(None)
        self.selectCoastlineMaskLine.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.selectCoastlineMaskLine.setLayer(None)

        # Continental shelves polygon and poliline layers
        self.selectCshMask.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.selectCshMask.setLayer(None)
        self.selectCshMaskLine.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.selectCshMaskLine.setLayer(None)
        # Shallow sea
        self.selectSsMask.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.selectSsMask.setLayer(None)
        self.selectSsMaskLine.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.selectSsMaskLine.setLayer(None)
        self.outputFile.setStorageMode(self.outputFile.GetDirectory)
        self.selectCoastButton.clicked.connect(self.addLayerToCoastPolygon)
        self.selectCoastLineButton.clicked.connect(self.addLayerToCoastPolyline)
        self.selectCsButton.clicked.connect(self.addLayerToCshPolygon)
        self.selectCsLineButton.clicked.connect(self.addLayerToCshPolyline)
        self.selectSsButton.clicked.connect(self.addLayerToSsPolygon)
        self.selectSsLineButton.clicked.connect(self.addLayerToSsPolyline)


    def addLayerToCoastPolygon(self):
        self.openVectorFromDisk(self.selectCoastlineMask)
    def addLayerToCoastPolyline(self):
        self.openVectorFromDisk(self.selectCoastlineMaskLine)
    def addLayerToCshPolygon(self):
        self.openVectorFromDisk(self.selectCshMask)
    def addLayerToCshPolyline(self):
        self.openVectorFromDisk(self.selectCshMaskLine)
    def addLayerToSsPolygon(self):
        self.openVectorFromDisk(self.selectSsMask)
    def addLayerToSsPolyline(self):
        self.openVectorFromDisk(self.selectSsMaskLine)


    def openVectorFromDisk(self,box):
        fd = QFileDialog()
        filter = "Vector files (*.shp)"
        fname=fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)[0]

        if fname:
            name = os.path.splitext(os.path.basename(fname))[0]
            vlayer = QgsVectorLayer(fname, name, 'ogr')
            QgsProject.instance().addMapLayer(vlayer)
            box.setLayer(vlayer)




