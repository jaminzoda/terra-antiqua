import os
from PyQt5 import QtWidgets, QtCore
from qgis.gui import QgsMapLayerComboBox, QgsPropertyOverrideButton, QgsSpinBox
from qgis.core import (
    QgsMapLayerProxyModel,
    QgsRasterLayer,
    QgsProject,
    QgsVectorLayer,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsPropertyDefinition,
    QgsProperty
)

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

class TaSpinBox(QtWidgets.QWidget):
    def __init__(self):
        super(TaSpinBox, self).__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.spinBox = QgsSpinBox()
        self.spinBox.setMinimum(-12000)
        self.spinBox.setMaximum(12000)
        self.spinBox.setClearValue(0)
        self.overrideButton = QgsPropertyOverrideButton(self)
        self.overrideButton.registerEnabledWidget(self.spinBox, False)
        self.layout.addWidget(self.spinBox)
        self.layout.addWidget(self.overrideButton)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(QtCore.QMargins(0,0,0,0))
        self.setLayout(self.layout)
        self.dataType =None
        self.spinBox.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.initOverrideButton("generalProperty", "Blank property")

    def initOverrideButton(self, property_name, property_descr, layer=None):
        if self.dataType:
            if  self.dataType.lower() == 'integer':
                definition = QgsPropertyDefinition(property_name, property_descr,
                                               QgsPropertyDefinition.Integer)
            elif self.dataType.lower() == 'double':
                definition = QgsPropertyDefinition(property_name, property_descr,
                                               QgsPropertyDefinition.Double)
            else:
                raise Exception("Wrong data type: {}".format(self.dataType))
        else:
            definition = QgsPropertyDefinition(property_name, property_descr,
                                               QgsPropertyDefinition.Integer)

        if layer:
            self.overrideButton.registerExpressionContextGenerator(layer)
            self.overrideButton.init(0, QgsProperty(), definition, layer, False)
        else:
            self.overrideButton.init(0, QgsProperty(), definition)


    def setDataType(self, dataType:str):
        """Sets the type of data set in SpinBox. Must be called before
        initOverrideButton. Accepts Integer and Double.
        :param dataType: A string defining the data type for the spinbox. Can be
        integer or double.
        """
        self.dataType = dataType

    def setAllowedValueRange(self, min, max):
        """ Sets allowed value range for the spinbox to bound the maximum and
        minimum values that the spinbox can receive.
        :param min: minimum value.
        :param nax: maximum value.
        """
        self.spinBox.setMinimum(min)
        self.spinBox.setMaximum(max)


class TaCheckBox(QtWidgets.QCheckBox):
    def __init__(self, label):
        super(TaCheckBox, self).__init__(label)
        self.enabled_widgets = []
        self.linked_widgets = []
        self.natural_behavior = None




    def registerEnabledWidgets(self, widgets:list, natural:bool = False):
        """Registers widgets that get disabled when the checkbox is checked.
        If natural is True, the widgets get enabled, when the checkbox is
        checked."""

        for widget in widgets:
            self.enabled_widgets.append(widget)
        self.stateChanged.connect(self.setWidgetsEnabled)
        self.natural_behavior = natural
        self.setWidgetsEnabled(self.isChecked())

    def setWidgetsEnabled(self, state):
        for widget in self.enabled_widgets:
            if state:
                widget.setEnabled(not self.natural_behavior)
            else:
                widget.setEnabled(self.natural_behavior)


    def enabledWidgets(self):
        return self.enabled_widgets

    def registerLinkedWidget(self, widget:QtWidgets.QWidget):
        self.linked_widgets.append(widget)
        try:
            widget.layerChanged.connect(self.setSelfEnabled)
        except Exception as e:
            raise e


        try:
            for widget in self.linked_widgets:
                if widget.currentLayer():
                    self.setSelfEnabled(widget.currentLayer())
                else:
                    self.setSelfEnabled(None)
        except Exception:
            pass


    def setSelfEnabled(self, layer):
        if layer and layer.selectedFeatureCount()>0:
            self.setEnabled(True)
        else:
            self.setEnabled(False)
    def linkedWidgets(self):
        return self.linked_widgets




class TaExpressionWidget(QtWidgets.QWidget):
    def __init__(self, parent = None):
        super(TaExpressionWidget, self).__init__(parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.lineEdit = QtWidgets.QLineEdit(self)
        self.overrideButton = QgsPropertyOverrideButton(self)
        self.overrideButton.registerEnabledWidget(self.lineEdit, False)
        self.overrideButton.registerExpressionWidget(self.lineEdit)
        self.layout.addWidget(self.lineEdit)
        self.layout.addWidget(self.overrideButton)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(QtCore.QMargins(0,0,0,0))
        self.setLayout(self.layout)

    def initOverrideButton(self, property_name, property_descr, layer):
        definition = QgsPropertyDefinition(property_name, property_descr,
                                               QgsPropertyDefinition.String)

        self.overrideButton.registerExpressionContextGenerator(layer)
        self.overrideButton.init(0, QgsProperty(), definition, layer, False)

