# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


# -*- coding: utf-8 -*-
import os
from PyQt5 import QtWidgets, QtCore, Qt
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsRasterLayer
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsDoubleSpinBox
)
from .base_dialog import TaBaseDialog
from .widgets import (
    TaVectorLayerComboBox,
    TaRasterCompilerTableWidget,
    TaCheckBox,
    TaColorSchemeWidget
)


class TaCompileTopoBathyDlg(TaBaseDialog):

    def __init__(self, parent=None):
        super(TaCompileTopoBathyDlg, self).__init__(parent)
        self.defineParameters()
        # fill the parameters tab of the dialog with widgets appropriate to defined parameters
        self.fillDialog()

    def defineParameters(self):
        """ Adds parameters to a list object that is used by the TaBaseDialog
        class to create widgets and place them in parameters tab.
        """
        self.compileRasterLayers = self.addParameter(TaRasterCompilerTableWidget,
                                                     param_id="compileRasterLayers")
        self.compileRasterLayers.registerMsgBar(self.msgBar)

        self.compileRasterLayers.table.insertColumn(0)
        self.compileRasterLayers.table.insertColumn(1)
        self.compileRasterLayers.table.setHorizontalHeaderLabels(
            ["Input layer", ""])
        header = self.compileRasterLayers.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.compileRasterLayers.table.setMinimumHeight(200)
        self.compileRasterLayers.addRow(0)

        # Add advanced parameters
        self.removeOverlapBathyCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                    label='Remove overlapping bathymetry',
                                                                    widget_type='CheckBox',
                                                                    param_id="removeOverlapBathyCheckBox")
        self.maskComboBox = self.addAdvancedParameter(TaVectorLayerComboBox,
                                                      label="Mask layer:",
                                                      widget_type="TaMapLayerComboBox",
                                                      param_id="maskComboBox")
        self.selectedFeaturesCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                  label="Selected features only",
                                                                  widget_type="CheckBox",
                                                                  param_id="selectedFeaturesCheckBox")
        self.bufferDistanceForRemoveOverlapBath = self.addAdvancedParameter(
            QgsDoubleSpinBox,
            label="Buffer distance (In map units):",
            param_id="bufferDistanceForRemoveOverlapBath")

        self.maskComboBox.layerChanged.connect(self.onLayerChange)
        self.maskComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.removeOverlapBathyCheckBox.registerEnabledWidgets([self.maskComboBox,
                                                                self.bufferDistanceForRemoveOverlapBath])
        self.removeOverlapBathyCheckBox.stateChanged.connect(
            self.onRemoveOverlapCheckBoxStateChange)
        self.selectedFeaturesCheckBox.registerLinkedWidget(self.maskComboBox)
        self.bufferDistanceForRemoveOverlapBath.setValue(0.5)

    def onLayerChange(self, layer):
        if layer and not self.compileRasterLayers.table.columnCount() > 2:
            self.compileRasterLayers.addColumn()
        elif not layer and self.compileRasterLayers.table.columnCount() > 2:
            self.compileRasterLayers.table.removeColumn(2)
            header = self.compileRasterLayers.table.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

    def onRemoveOverlapCheckBoxStateChange(self, state):
        if state == QtCore.Qt.Checked:
            self.maskComboBox.setLayer(self.maskComboBox.layer(1))
        else:
            self.maskComboBox.setLayer(self.maskComboBox.layer(0))
