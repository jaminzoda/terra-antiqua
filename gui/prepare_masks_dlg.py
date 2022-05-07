# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from PyQt5 import QtCore, QtWidgets
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from .base_dialog import TaBaseDialog
from .widgets import (
    TaVectorCompilerTableWidget
)


class TaPrepareMasksDlg(TaBaseDialog):

    def __init__(self, parent=None):
        """Constructor."""
        super(TaPrepareMasksDlg, self).__init__(parent)
        self.defineParameters()
        self.fillDialog()

    def defineParameters(self):
        #        self.addLayerComboBox = self.addParameter(TaVectorLayerComboBox, "Input mask layer:", "TaMapLayerCombobox")
        self.compileVectorLayers = self.addParameter(TaVectorCompilerTableWidget,
                                                     param_id="compileVectorLayers")
        self.compileVectorLayers.registerMsgBar(self.msgBar)
        self.compileVectorLayers.table.insertColumn(0)
        self.compileVectorLayers.table.insertColumn(1)
        self.compileVectorLayers.table.setHorizontalHeaderLabels(
            ["Input layer", "Mask category"])
        header = self.compileVectorLayers.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.compileVectorLayers.table.setMinimumHeight(250)
        self.compileVectorLayers.addRow(0)
