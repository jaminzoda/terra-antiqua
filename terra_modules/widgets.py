import os
from PyQt5 import QtWidgets, QtCore
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel, QgsRasterLayer, QgsProject, QgsVectorLayer

class TaHelpBrowser(QtWidgets.QTextBrowser):
    visibilityChanged = QtCore.pyqtSignal(bool)
    def __init__(self, parent=None):
        super(TaHelpBrowser, self).__init__()
        self.collapsed=False
    def hideEvent(self, event):
        if event.type() == event.Hide:
            self.visibilityChanged.emit(False)
    def showEvent(self, event):
        if event.type() == event.Show:
            self.visibilityChanged.emit(True)

class TaMapLayerComboBox(QtWidgets.QWidget):
    def __init__(self, label = None):
        super(TaMapLayerComboBox, self).__init__()
        self.cmb = QgsMapLayerComboBox(self)
        self.cmb.setLayer(None)
        self.cmb.setAllowEmptyLayer(True)
        self.openButton = QtWidgets.QToolButton(self)
        self.openButton.setText('...')
        self.openButton.setIconSize(QtCore.QSize(16,16))
        if not label:
            self.label = QtWidgets.QLabel('')
        else:
            self.label = QtWidgets.QLabel(label)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.cmb)
        self.layout.addWidget(self.openButton)
        self.vlayout = QtWidgets.QVBoxLayout()
        self.vlayout.addWidget(self.label)
        self.vlayout.addLayout(self.layout)
        self.vlayout.setSpacing(6)
        self.vlayout.setContentsMargins(QtCore.QMargins(0,0,0,0))
        self.setLayout(self.vlayout)
        self.setLayerType()

    def setLabel(self, label):
        self.label.setText(label)

    def getMainWidget(self):
        return self.cmb

class TaRasterLayerComboBox(TaMapLayerComboBox):
    def __init__(self, label=None):
        super(TaRasterLayerComboBox, self).__init__(label)
        self.openButton.pressed.connect(self.openRasterFromDisk)

    def openRasterFromDisk(self):
        fd = QtWidgets.QFileDialog()
        filter = "Raster files (*.jpg *.tif *.grd *.nc *.png *.tiff)"
        fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)

        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            rlayer = QgsRasterLayer(fname, name, 'gdal')
            QgsProject.instance().addMapLayer(rlayer)
            self.cmb.setLayer(rlayer)

    def setLayerType(self):
        self.cmb.setFilters(QgsMapLayerProxyModel.RasterLayer)



class TaVectorLayerComboBox(TaMapLayerComboBox):
    def __init__(self, label=None):
        super(TaVectorLayerComboBox, self).__init__(label)
        self.openButton.pressed.connect(self.openVectorFromDisk)

    def openVectorFromDisk(self):
        fd = QtWidgets.QFileDialog()
        filter = "Vector files (*.shp)"
        fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)

        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            vlayer = QgsVectorLayer(fname, name, 'ogr')
            QgsProject.instance().addMapLayer(vlayer)
            self.cmb.setLayer(vlayer)

    def setLayerType(self, layer_type=None):
        if not layer_type:
            layer_type = QgsMapLayerProxyModel.PolygonLayer
        else:
            if layer_type == 'Polygon':
                layer_type = QgsMapLayerProxyModel.PolygonLayer
            elif layer_type == 'Polyline':
                layer_type = QgsMapLayerProxyModel.LineLayer
            elif layer_type == 'Point':
                layer_type = QgsMapLayerProxyModel.PointLayer
            else:
                layer_type = QgsMapLayerProxyModel.VectorLayer
        self.cmb.setFilters(layer_type)

