# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
from typing import List, Tuple

from numpy import double
from ..gui.widgets import (
    TaCheckBox,
    TaMapLayerComboBox,
    TaRasterCompilerTableWidget,
    TaVectorCompilerTableWidget
)
from .settings import TaSettings
from qgis.core import (
    QgsMapLayer,
    QgsProject
)
from qgis.gui import (
    QgsFileWidget,
    QgsDoubleSpinBox,
    QgsSpinBox
)
from PyQt5.QtCore import QVariant, QObject
from PyQt5.QtWidgets import (
    QWidget,
    QCheckBox
)


class TaProcessingParameter(QObject):
    MapLayerProcessingParameter = 1
    VectorLayerListProcessingParameter = 2
    RasterLayerListProcessingParameter = 3
    OutputPathProcessingParameter = 4
    CheckableProcessingParameter = 5
    NumericDoubleProcessingParameter = 6
    NumericIntProcessingParameter = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_name = ''
        self.parameter_type = ''
        self.parameter_group = ''
        self.linked_widget = None
        self.parameter_value = None
        self.project = QgsProject.instance()

    def registerLinkedWidget(self, widget: QWidget) -> None:
        self.linked_widget = widget

    def parameterName(self) -> None:
        return self.parameter_name

    def parameterType(self) -> None:
        return self.parameter_type

    def parameterGroup(self) -> None:
        return self.parameter_group

    def setParameterName(self, p_name: str) -> None:
        self.parameter_name = p_name

    def setParameterType(self, p_type: str) -> None:
        self.parameter_type = p_type

    def setParameterGroup(self, p_group: str) -> None:
        self.parameter_group = p_group

    def getValue(self):
        """Gets the parameter value from the
        corresponding field of the linked parameter widget"""
        pass

    def setValue(self):
        """Sets the parameter value to the
        corresponding field of the linked parameter widget."""
        pass

    def value(self):
        """Returns the parameter value currently
        stored in self.parameter_value variable."""
        return self.parameter_value

    def saveValue(self, settings: TaSettings) -> None:
        """Saves the parameter value to the configuration file on disk

        :param settings: a settings object to save value with.
        :type settings: TaSettings."""
        pass

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        """Restores the parameter value from the configuration file.
        :param settings: a settings object to save value with.
        :type settings: TaSettings. """
        pass


class TaOutputPathProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.OutputPathProcessingParameter

    def getValue(self):
        return self.linked_widget.filePath()

    def setValue(self):
        self.linked_widget.setFilePath(self.parameter_value)

    def saveValue(self, settings: TaSettings):
        settings.setValue(
            f"values/{self.parameter_name}", self.parameter_value)

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        self.parameter_value = settings.value(f"values/{p_key}")


class TaMapLayerProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.MapLayerProcessingParameter

    def getValue(self) -> QgsMapLayer:
        return self.linked_widget.currentLayer()

    def setValue(self) -> None:
        self.linked_widget.setLayer(self.parameter_value)

    def saveValue(self, settings) -> None:
        settings.setValue(f"values/{self.parameter_name}",
                          self.parameter_value.name())

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        if not isinstance(val, str):
            val = str(val)
        val = self.project.mapLayersByName(val)
        if len(val) > 0 and val[0].isValid():
            val = val[0]
            self.parameter_value = val


class TaVectorLayerListProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.VectorLayerListProcessingParameter

    def getValue(self) -> List[Tuple[QgsMapLayer, str]]:
        param = [(self.linked_widget.table.cellWidget(i, 0).currentLayer(),
                  self.linked_widget.table.cellWidget(i, 1).currentText())
                 for i in range(self.linked_widget.table.rowCount())]
        return param

    def setValue(self):
        for i in range(len(self.parameter_value)):
            if not i == 0:
                self.linked_widget.addRow(None)
            self.linked_widget.table.cellWidget(i, 0).setLayer(
                self.parameter_value[i][0])
            self.linked_widget.table.cellWidget(i, 1).setCurrentText(
                self.parameter_value[i][1])

    def saveValue(self, settings) -> None:
        # Get layer names before saving
        val = [(l.name(), c) for l, c in self.parameter_value]
        settings.setValue(f"values/{self.parameter_name}", val)

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        assert(isinstance(val, list))
        self.parameter_value = [(self.project.mapLayersByName(ln)[0],
                                str(cat)) for ln, cat in val]
        # Check if the map layers are found.
        if len(self.parameter_value) == 0:
            self.parameter_value = None  # if not, set the parameter value to None


class TaRasterLayerListProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.RasterLayerListProcessingParameter

    def getValue(self) -> Tuple[QgsMapLayer, bool]:
        if self.linked_widget.table.columnCount() > 2:
            param = [(self.linked_widget.table.cellWidget(i, 0).currentLayer(),
                      self.linked_widget.table.cellWidget(i, 2).findChild(QWidget,
                                                                          name="apply_mask_checkbox").isChecked())
                     for i in range(0, self.linked_widget.table.rowCount())]
        else:
            param = [(self.linked_widget.table.cellWidget(j, 0).currentLayer(), False)
                     for j in range(0, self.linked_widget.table.rowCount())]
        return param

    def setValue(self):
        if any([i for _, i in self.parameter_value]):
            self.linked_widget.addColumn()
            for i in range(len(self.parameter_value)):
                if not i == 0:
                    self.linked_widget.addRow(None)
                self.linked_widget.table.cellWidget(i, 0).setLayer(
                    self.parameter_value[i][0])
                self.linked_widget.table.cellWidget(i, 2).findChild(QWidget,
                                                                    name="apply_mask_checkbox").setChecked(self.parameter_value[i][1])
        else:
            for i in range(len(self.parameter_value)):
                if not i == 0:
                    self.linked_widget.addRow(None)
                self.linked_widget.table.cellWidget(i, 0).setLayer(
                    self.parameter_value[i][0])

    def saveValue(self, settings) -> None:
        # Get layer names before saving
        val = [(l.name(), c) for l, c in self.parameter_value]
        settings.setValue(f"values/{self.parameter_name}", val)

    # TODO handle empty list from QgsProject.mapLayersByName()
    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        assert(isinstance(val, list))
        self.parameter_value = [(self.project.mapLayersByName(ln)[0],
                                bool(mask_applied)) for ln, mask_applied in val]
        self.parameter_name = p_key


class TaCheckableProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.CheckableProcessingParameter

    def getValue(self) -> bool:
        return self.linked_widget.isChecked()

    def setValue(self) -> None:
        self.linked_widget.setChecked(self.parameter_value)

    def saveValue(self, settings: TaSettings) -> None:
        settings.setValue(
            f"values/{self.parameter_name}", int(self.parameter_value))

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        if not isinstance(val, int):
            val = int(val)
        self.parameter_value = bool(val)


class TaNumericIntProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.NumericIntProcessingParameter

    def getValue(self) -> int:
        return self.linked_widget.value()

    def setValue(self) -> None:
        self.linked_widget.setValue(self.parameter_value)

    def saveValue(self, settings: TaSettings) -> None:
        settings.setValue(
            f"values/{self.parameter_name}", self.parameter_value)

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        if not isinstance(val, int):
            val = int(val)
        self.parameter_value = val


class TaNumericDoubleProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.NumericDoubleProcessingParameter

    def getValue(self) -> float:
        return self.linked_widget.value()

    def setValue(self):
        self.linked_widget.setValue(self.parameter_value)

    def saveValue(self, settings: TaSettings) -> None:
        settings.setValue(
            f"values/{self.parameter_name}", self.parameter_value)

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        if not isinstance(val, float):
            val = float(val)
        self.parameter_value = val


class TaProcessingParameters(QObject):
    def __init__(self, dlg=None, parent=None) -> None:
        super().__init__(parent)
        self.dlg = dlg
        self.parameters = []
        self.dlg.saveParametersButton.clicked.connect(
            self.readParametersFromDialog)
        self.settings = TaSettings("TerraAntiqua", "Terra_Antiqua")

    def createParameterObjectForWidget(self, parameter_widget) -> TaProcessingParameter:
        """Creates a processing parameter object based on the parameter widget supplied.

        :param parameter_widget: parameter widget to create a parameter object for.
        :type parameter_widget: QWidget.

        :return: S processing parameter object encapsulating the widget and the value it holds or None.
        :rtype: a subcalss of TaProcessingParameter.
        """
        param = None
        if isinstance(parameter_widget, TaMapLayerComboBox):
            param = TaMapLayerProcessingParameter()
        elif isinstance(parameter_widget, TaRasterCompilerTableWidget):
            param = TaRasterLayerListProcessingParameter()
        elif isinstance(parameter_widget, TaVectorCompilerTableWidget):
            param = TaVectorLayerListProcessingParameter()
        elif isinstance(parameter_widget, QgsFileWidget):
            param = TaOutputPathProcessingParameter()
        elif isinstance(parameter_widget, (TaCheckBox, QCheckBox)):
            param = TaCheckableProcessingParameter()
        elif isinstance(parameter_widget, QgsDoubleSpinBox):
            param = TaNumericDoubleProcessingParameter()
        elif isinstance(parameter_widget, QgsSpinBox):
            param = TaNumericIntProcessingParameter()
        return param

    def createParameterObjectForType(self, parameter_type) -> TaProcessingParameter:
        """Creates a processing parameter object based on the parameter type supplied.

        :param parameter_widget: parameter type to create a parameter object for.
        :type parameter_widget: int.

        :return: S processing parameter object encapsulating the widget and the value it holds or None.
        :rtype: a subcalss of TaProcessingParameter.
        """
        param = None
        if parameter_type == TaProcessingParameter.MapLayerProcessingParameter:
            param = TaMapLayerProcessingParameter()
        elif parameter_type == TaProcessingParameter.RasterLayerListProcessingParameter:
            param = TaRasterLayerListProcessingParameter()
        elif parameter_type == TaProcessingParameter.VectorLayerListProcessingParameter:
            param = TaVectorLayerListProcessingParameter()
        elif parameter_type == TaProcessingParameter.OutputPathProcessingParameter:
            param = TaOutputPathProcessingParameter()
        elif parameter_type == TaProcessingParameter.CheckableProcessingParameter:
            param = TaCheckableProcessingParameter()
        elif parameter_type == TaProcessingParameter.NumericDoubleProcessingParameter:
            param = TaNumericDoubleProcessingParameter()
        elif parameter_type == TaProcessingParameter.NumericIntProcessingParameter:
            param = TaNumericIntProcessingParameter()
        return param

    def readParametersFromDialog(self):
        parameters = self.dlg.getParameters()
        advanced_parameters = self.dlg.getAdvancedParameters()
        variant_parameters = self.dlg.getVariantParameters()
        for parameter_widget, p_id in parameters:
            param = self.createParameterObjectForWidget(parameter_widget)
            if param:
                param.setParameterName(p_id)
                param.setParameterGroup("main_parameter")
                param.registerLinkedWidget(parameter_widget)
                param.parameter_value = param.getValue()
                self.parameters.append(param)

        for parameter_widget, _, p_id in advanced_parameters:
            param = self.createParameterObjectForWidget(parameter_widget)
            if param:
                param.setParameterName(p_id)
                param.setParameterGroup("advanced_parameter")
                param.registerLinkedWidget(parameter_widget)
                param.parameter_value = param.getValue()
                if param.parameter_value == None:
                    continue
                self.parameters.append(param)

        for parameter_widget, _, _, p_id in variant_parameters:
            param = self.createParameterObjectForWidget(parameter_widget)
            if param:
                param.setParameterName(p_id)
                param.setParameterGroup("variant_parameter")
                param.registerLinkedWidget(parameter_widget)
                param.parameter_value = param.getValue()
                self.parameters.append(param)

        self.saveParameters()
        # self.restoreParameters()
        # self.getAllParameters()

    def saveParameters(self) -> None:
        """Stores parameters on disk via a TaSettings object"""
        group_name = self.dlg.alg_name.replace(' ', '_').replace('/', '_')
        parameters_order = self.dlg.parameters_order
        self.settings.beginGroup(group_name)
        for parameter in self.parameters:
            parameter.saveValue(self.settings)
            self.settings.setValue(
                f"types/{parameter.parameter_name}",
                parameter.parameter_type)
            self.settings.setValue(
                f"orders/{parameter.parameter_name}", parameters_order.get(parameter.parameter_name))
        self.settings.endGroup()

    def restoreParameters(self) -> None:
        """Reads stored parameters from disk."""
        group_name = self.dlg.alg_name.replace(' ', '_').replace('/', '_')
        parameters_order = self.dlg.parameters_order
        self.settings.beginGroup(group_name)
        self.settings.beginGroup("values")
        value_keys = self.settings.allKeys()
        value_keys_sorted = []
        for i in range(1, len(value_keys)+1):
            for key in value_keys:
                if parameters_order.get(key) == i:
                    value_keys_sorted.append(key)
        self.settings.endGroup()
        for p_key in value_keys_sorted:
            p_type = self.settings.value(f"types/{p_key}")
            p_type = int(p_type)
            param = self.createParameterObjectForType(p_type)
            if not param:
                print(
                    f"WARNING: failed to create a parameter object for {p_key}")
                continue
            param.restoreValue(self.settings, p_key)
            param.setParameterName(p_key)
            param.registerLinkedWidget(self.dlg.__dict__.get(p_key))
            param.setValue()
            self.parameters.append(param)
        self.settings.endGroup()
