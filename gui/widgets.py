# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


import os
from PyQt5 import QtWidgets, QtCore, QtGui
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsPropertyOverrideButton,
    QgsSpinBox,
    QgsDoubleSpinBox,
    QgsFilterLineEdit,
    QgsCollapsibleGroupBox
)
from qgis.core import (
    QgsMapLayerProxyModel,
    QgsRasterLayer,
    QgsProject,
    QgsVectorLayer,
    QgsPropertyDefinition,
    QgsProperty
)


class TaButtonGroup(QtWidgets.QWidget):
    def __init__(self):
        super(TaButtonGroup, self).__init__()
        self.add = QtWidgets.QToolButton()
        self.add.setAutoRaise(True)
        self.add.setIcon(QtGui.QIcon(':/addButton.png'))
        self.add.setToolTip("Add row")
        self.remove = QtWidgets.QToolButton()
        self.remove.setIcon(QtGui.QIcon(':/removeButton.png'))
        self.remove.setAutoRaise(True)
        self.remove.setToolTip("Remove row")
        self.up = QtWidgets.QToolButton()
        self.up.setIcon(QtGui.QIcon(':/arrow_up.png'))
        self.up.setAutoRaise(True)
        self.up.setToolTip("Move row up")
        self.down = QtWidgets.QToolButton()
        self.down.setIcon(QtGui.QIcon(':/arrow_down.png'))
        self.down.setAutoRaise(True)
        self.down.setToolTip("Move row down")
        self.hLayout = QtWidgets.QHBoxLayout(self)
        self.hLayout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.hLayout.addStretch()
        self.hLayout.addWidget(self.up)
        self.hLayout.addWidget(self.down)
        self.hLayout.addWidget(self.add)
        self.hLayout.addWidget(self.remove)
        self.setLayout(self.hLayout)


class TaTableWidget(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super(TaTableWidget, self).__init__(parent)
        self.layerItems = []

    def moveRowDown(self):
        row = self.currentRow()
        column = self.currentColumn()
        if row < self.rowCount()-1 and self.rowCount() > 1:
            self.insertRow(row+2)
            for i in range(self.columnCount()):
                self.setCellWidget(row+2, i, self.cellWidget(row, i))
                self.setCurrentCell(row+2, column)
            self.removeRow(row)

    def moveRowUp(self):
        row = self.currentRow()
        column = self.currentColumn()
        if row > 0:
            self.insertRow(row-1)
            for i in range(self.columnCount()):
                self.setCellWidget(row-1, i, self.cellWidget(row+1, i))
                self.setCurrentCell(row-1, column)
            self.removeRow(row+1)


class TaHelpBrowser(QtWidgets.QTextBrowser):
    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super(TaHelpBrowser, self).__init__()
        self.collapsed = False

    def hideEvent(self, event):
        if event.type() == event.Hide:
            self.visibilityChanged.emit(False)

    def showEvent(self, event):
        if event.type() == event.Show:
            self.visibilityChanged.emit(True)


class TaAbstractMapLayerComboBox(QgsMapLayerComboBox):
    enabled = QtCore.pyqtSignal(bool)

    def __init__(self, parent):
        super().__init__(parent)

    def setLayerType(self, layer_type: str = None):
        """Sets the layer type to be displayed in the combobox.

        :param layer_type: The type of the layer the a combobox can accept. Can be Raster, Polygon, Polyline and Point.
        :type layer_type: str.

        """
        if not layer_type:
            layer_type = QgsMapLayerProxyModel.RasterLayer
        else:
            if layer_type == 'Polygon':
                layer_type = QgsMapLayerProxyModel.PolygonLayer
            elif layer_type == 'Polyline':
                layer_type = QgsMapLayerProxyModel.LineLayer
            elif layer_type == 'Point':
                layer_type = QgsMapLayerProxyModel.PointLayer
            else:
                layer_type = QgsMapLayerProxyModel.VectorLayer
        self.setFilters(layer_type)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.EnabledChange:
            self.enabled.emit(self.isEnabled())


class TaMapLayerComboBox(QtWidgets.QWidget):
    def __init__(self, label=None):
        super(TaMapLayerComboBox, self).__init__()
        self.cmb = TaAbstractMapLayerComboBox(self)
        self.cmb.setLayer(None)
        self.cmb.setAllowEmptyLayer(True)
        self.openButton = QtWidgets.QToolButton(self)
        self.openButton.setText('...')
        self.openButton.setIconSize(QtCore.QSize(16, 16))
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
        self.vlayout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setLayout(self.vlayout)
        self.associatedWidgets = []
        self.associatedWidgets.append(self.openButton)
        self.cmb.enabled.connect(self.setAssociatedWidgetsEnabled)

    def setLabel(self, label):
        self.label.setText(label)

    def getMainWidget(self):
        return self.cmb

    def currentLayer(self):
        return self.cmb.currentLayer()

    def setCurrentLayer(self, layer):
        self.cmb.setLayer(layer)

    def setAssociatedWidgetsEnabled(self, state):
        for widget in self.associatedWidgets:
            widget.setEnabled(state)

    def setAssociatedWidget(self, widget: QtWidgets.QWidget):
        self.associatedWidgets.append(widget)


class TaRasterLayerComboBox(TaMapLayerComboBox):
    def __init__(self, label=None):
        super(TaRasterLayerComboBox, self).__init__(label)
        self.openButton.pressed.connect(self.openRasterFromDisk)
        self.cmb.setLayerType()

    def openRasterFromDisk(self):
        fd = QtWidgets.QFileDialog()
        filter = "Raster files (*.jpg *.tif *.grd *.nc *.png *.tiff)"
        fname, _ = fd.getOpenFileName(
            caption='Select a vector layer', directory=None, filter=filter)

        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            rlayer = QgsRasterLayer(fname, name, 'gdal')
            QgsProject.instance().addMapLayer(rlayer)
            self.cmb.setLayer(rlayer)


class TaVectorLayerComboBox(TaMapLayerComboBox):
    def __init__(self, label=None):
        super(TaVectorLayerComboBox, self).__init__(label)
        self.openButton.pressed.connect(self.openVectorFromDisk)
        # default type for vector layers = polygon
        # If need to add polyline layer combobox, type should be set
        # when defining parameters for each dialog
        self.cmb.setLayerType('Polygon')

    def openVectorFromDisk(self):
        fd = QtWidgets.QFileDialog()
        filter = "Vector files (*.shp)"
        fname, _ = fd.getOpenFileName(
            caption='Select a vector layer', directory=None, filter=filter)

        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            vlayer = QgsVectorLayer(fname, name, 'ogr')
            QgsProject.instance().addMapLayer(vlayer)
            self.cmb.setLayer(vlayer)


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
        self.layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setLayout(self.layout)
        self.dataType = None
        self.spinBox.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.initOverrideButton("generalProperty", "Blank property")

    def initOverrideButton(self, property_name, property_descr, layer=None):
        if self.dataType:
            if self.dataType.lower() == 'integer':
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
            self.overrideButton.init(
                0, QgsProperty(), definition, layer, False)
        else:
            self.overrideButton.init(0, QgsProperty(), definition)

    def setDataType(self, dataType: str):
        """Sets the type of data set in SpinBox. Must be called before
        initOverrideButton. Accepts Integer and Double.

        :dataType: A string defining the data type for the spinbox. Can be 'integer' or 'double'.

        :type: str

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

    def setValue(self, value):
        """Sets value for the spinbox.
        param value: value to be set.
        type value: int. """
        self.spinBox.setValue(value)

    def value(self):
        """Returns the value set in the spinBox."""
        return self.spinBox.value()


class TaDoubleSpinBox(QtWidgets.QWidget):
    def __init__(self):
        super(TaDoubleSpinBox, self).__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.spinBox = QgsDoubleSpinBox()
        self.overrideButton = QgsPropertyOverrideButton(self)
        self.overrideButton.registerEnabledWidget(self.spinBox, False)
        self.layout.addWidget(self.spinBox)
        self.layout.addWidget(self.overrideButton)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setLayout(self.layout)
        self.dataType = None
        self.spinBox.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.initOverrideButton("generalProperty", "Blank property")

    def initOverrideButton(self, property_name, property_descr, layer=None):
        if self.dataType:
            if self.dataType.lower() == 'integer':
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
            self.overrideButton.init(
                0, QgsProperty(), definition, layer, False)
        else:
            self.overrideButton.init(0, QgsProperty(), definition)

    def setDataType(self, dataType: str):
        """Sets the type of data set in SpinBox. Must be called before
        initOverrideButton. Accepts Integer and Double.

        :dataType: A string defining the data type for the spinbox. Can be 'integer' or 'double'.

        :type: str

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

    def setValue(self, value):
        """Sets value for the spinbox.
        param value: value to be set.
        type value: int. """
        self.spinBox.setValue(value)

    def value(self):
        """Returns the value set in the spinBox."""
        return self.spinBox.value()


class TaCheckBox(QtWidgets.QCheckBox):
    def __init__(self, label):
        super(TaCheckBox, self).__init__(label)
        self.enabled_widgets = []
        self.linked_widgets = []
        self.natural_behavior = None
        self.default_checked_state = None

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.EnabledChange and not self.isEnabled():
            self.setChecked(False)
        if event.type() == QtCore.QEvent.EnabledChange and self.isEnabled():
            if self.default_checked_state:
                self.setChecked(self.default_checked_state)

    def setDefaultCheckedState(self, state: bool) -> None:
        """Sets the default checked state of the checkbox to checked or unchecked
        :param state: Checked state. If True, the checkbox is checked otherwise it is unchecked.
        """
        self.default_checked_state = state

    def registerEnabledWidgets(self, widgets: list, natural: bool = False):
        """Registers widgets that get enabled when the checkbox is checked.

        :param widgets: A list of widgets that need to be registered with the checkbox.
        :type widgets: list.
        :param natural: If natural is True, the widgets get disabled, when the checkbox is
        checked. If it is False the checbox get enabled.
        :type natural: bool.

        """

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

    def registerLinkedWidget(self, widget: QtWidgets.QWidget):
        """Registers TaVectorLayerComboBox widgets to retrieve number of selected features.
        If the linked widget contains any selected features, the checkbox gets enabled.
        :param widget: A vector layer combobox.
        :type widget: TaVectorLayerComboBox or QgsMapLayerComboBox.
        """
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
        if layer and layer.selectedFeatureCount() > 0:
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def linkedWidgets(self):
        return self.linked_widgets


class TaExpressionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TaExpressionWidget, self).__init__(parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.lineEdit = QgsFilterLineEdit(self)
        self.overrideButton = QgsPropertyOverrideButton(self)
        self.overrideButton.registerEnabledWidget(self.lineEdit, False)
        self.overrideButton.registerExpressionWidget(self.lineEdit)
        self.layout.addWidget(self.lineEdit)
        self.layout.addWidget(self.overrideButton)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.setLayout(self.layout)
        self.initOverrideButton("general Property", "Blank Property")

    def initOverrideButton(self, property_name, property_descr, layer=None):
        definition = QgsPropertyDefinition(property_name, property_descr,
                                           QgsPropertyDefinition.String)

        if layer:
            self.overrideButton.registerExpressionContextGenerator(layer)
            self.overrideButton.init(
                0, QgsProperty(), definition, layer, False)
        else:
            self.overrideButton.init(0, QgsProperty(), definition)


class TaColorSchemeWidget(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_to_color_schemes = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "../resources/color_schemes"))
        self.color_scheme_names = []
        self.populateColorSchemes()
        self.setDefaultColorScheme()

    def populateColorSchemes(self):
        file_names = []
        for (dirpath, dirnames, filenames) in os.walk(self.path_to_color_schemes):
            file_names.extend(filenames)
        for file in file_names:
            with open(os.path.join(self.path_to_color_schemes, file)) as f:
                lines = f.readlines()
                if len(lines) > 0:
                    color_scheme_name = lines[0].strip()
                    color_scheme_name = color_scheme_name.replace("#", "")
                    self.color_scheme_names.append(color_scheme_name)
        self.addItems(self.color_scheme_names)

    def setDefaultColorScheme(self):
        for i in self.color_scheme_names:
            if i == "Terra Antiqua color scheme":
                self.setCurrentText(i)
