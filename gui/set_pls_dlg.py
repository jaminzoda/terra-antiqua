# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from cProfile import label
from PyQt5 import QtWidgets
from qgis.gui import QgsSpinBox
from .base_dialog import TaBaseDialog
from .widgets import TaRasterLayerComboBox, TaVectorLayerComboBox, TaColorSchemeWidget


class TaSetPaleoshorelinesDlg(TaBaseDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaSetPaleoshorelinesDlg, self).__init__(parent)
        self.defineParameters()

    def defineParameters(self):
        """ Adds parameters to a list object that is used by the TaBaseDialog
        class to create widgets and place them parameters tab.
        """

        self.baseTopoBox = self.addMandatoryParameter(
            TaRasterLayerComboBox,
            label="Raster to be modifiied (input):",
            widget_type="TaMapLayerComboBox",
            param_id="baseTopoBox")
        self.masksBox = self.addMandatoryParameter(
            TaVectorLayerComboBox,
            label="Rotated paleoshorelines:",
            widget_type="TaMapLayerComboBox",
            param_id="masksBox")

        self.modeLabel = self.addParameter(
            QtWidgets.QLabel,
            label="Modification mode:",
            widget_type="GroupLabel",
            param_id="modeLabel")
        self.interpolateCheckBox = self.addParameter(
            QtWidgets.QCheckBox,
            label="Interpolation",
            widget_type="CheckBox",
            param_id="interpolateCheckBox")
        self.rescaleCheckBox = self.addParameter(
            QtWidgets.QCheckBox,
            label="Rescaling",
            widget_type="CheckBox",
            param_id="rescaleCheckBox")
        self.maxElevSpinBox = self.addParameter(
            QgsSpinBox,
            label="Maximum elevation of the emerged area (in m):",
            widget_type="QgsSpinBox",
            param_id="maxElevSpinBox")
        self.maxDepthSpinBox = self.addParameter(
            QgsSpinBox,
            label="Maximum depth of the submerged area (in m):",
            widget_type="QgsSpinBox",
            param_id="maxDepthSpinBox")
        self.maxElevSpinBox.setMaximum(2000)
        self.maxElevSpinBox.setMinimum(-1)
        self.maxElevSpinBox.setValue(2)
        self.maxDepthSpinBox.setMaximum(1)
        self.maxDepthSpinBox.setMinimum(-1000)
        self.maxDepthSpinBox.setValue(-5)
        # Select modification mode
        self.selectModificationModeInterpolate(1)
        self.interpolateCheckBox.stateChanged.connect(
            self.selectModificationModeInterpolate)
        self.rescaleCheckBox.stateChanged.connect(
            self.selectModificationModeRescale)

        # Add advanced parameters

        # Fill the parameters' tab of the Dialog with the defined parameters
        self.fillDialog()

    def selectModificationModeInterpolate(self, state):
        if state > 0:
            self.rescaleCheckBox.setChecked(False)
            self.maxElevSpinBox.setEnabled(False)
            self.maxDepthSpinBox.setEnabled(False)
            self.interpolateCheckBox.setChecked(True)
        else:
            self.rescaleCheckBox.setChecked(True)
            self.maxElevSpinBox.setEnabled(True)
            self.maxDepthSpinBox.setEnabled(True)
            self.interpolateCheckBox.setChecked(False)

    def selectModificationModeRescale(self, state):
        if state > 0:
            self.rescaleCheckBox.setChecked(True)
            self.maxElevSpinBox.setEnabled(True)
            self.maxDepthSpinBox.setEnabled(True)
            self.interpolateCheckBox.setChecked(False)
        else:
            self.rescaleCheckBox.setChecked(False)
            self.maxElevSpinBox.setEnabled(False)
            self.maxDepthSpinBox.setEnabled(False)
            self.interpolateCheckBox.setChecked(True)
