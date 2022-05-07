# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
from typing import Tuple
from ..gui.widgets import TaMapLayerComboBox, TaRasterCompilerTableWidget, TaVectorCompilerTableWidget
from .settings import TaSettings
from qgis.core import (
    QgsMapLayer,
    QgsProject
)
from qgis.gui import QgsFileWidget
from PyQt5.QtCore import QVariant, QObject
from PyQt5.QtWidgets import QWidget


class TaProcessingParameter(QObject):
    MapLayerProcessingParameter = 0
    VectorLayerListProcessingParameter = 1
    RasterLayerListProcessingParameter = 2
    OutputPathProcessingParameter = 3

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

    def parameterName(self):
        return self.parameter_name

    def parameterType(self):
        return self.parameter_type

    def parameterGroup(self):
        return self.parameter_group

    def setParameterName(self, p_name: str):
        self.parameter_name = p_name

    def setParameterType(self, p_type: str):
        self.parameter_type = p_type

    def setParameterGroup(self, p_group: str):
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
    # TODO handle empty list from QgsProject.mapLayersByName()

    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        assert(isinstance(val, str))
        val = self.project.mapLayersByName(val)[0]
        self.parameter_value = val
        self.parameter_name = p_key


class TaVectorLayerListProcessingParameter(TaProcessingParameter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parameter_type = self.VectorLayerListProcessingParameter

    def getValue(self) -> Tuple[QgsMapLayer, str]:
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

    # TODO handle empty list from QgsProject.mapLayersByName()
    def restoreValue(self, settings: TaSettings, p_key: str) -> None:
        val = settings.value(f"values/{p_key}")
        if isinstance(val, QVariant):
            val = val.value()
        assert(isinstance(val, list))
        self.parameter_value = [(self.project.mapLayersByName(ln)[0],
                                str(cat)) for ln, cat in val]


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


class TaProcessingParameters(QObject):
    def __init__(self, dlg=None, parent=None) -> None:
        super().__init__(parent)
        self.dlg = dlg
        self.parameters = []
        self.dlg.saveParametersButton.clicked.connect(
            self.readParametersFromDialog)
        self.settings = TaSettings("TerraAntiqua", "Terra_Antiqua")
        # self.restoreParameters()

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
        self.settings.beginGroup(group_name)
        for parameter in self.parameters:
            parameter.saveValue(self.settings)
            self.settings.setValue(
                f"types/{parameter.parameter_name}",
                parameter.parameter_type)
        self.settings.endGroup()

    def restoreParameters(self) -> None:
        """Reads stored parameters from disk."""
        group_name = self.dlg.alg_name.replace(' ', '_').replace('/', '_')
        self.settings.beginGroup(group_name)
        self.settings.beginGroup("values")
        value_keys = self.settings.allKeys()
        self.settings.endGroup()
        for p_key in value_keys:
            p_type = self.settings.value(f"types/{p_key}")
            param = self.createParameterObjectForType(p_type)
            param.restoreValue(self.settings, p_key)
            param.setParameterName(p_key)
            param.registerLinkedWidget(self.dlg.__dict__.get(p_key))
            param.setValue()
            self.parameters.append(param)
        self.settings.endGroup()
