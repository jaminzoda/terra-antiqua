from PyQt5 import QtWidgets
from qgis.gui import QgsSpinBox
from .base_dialog import TaBaseDialog
from .widgets import TaRasterLayerComboBox, TaVectorLayerComboBox

class TaSetPaleoshorelinesDlg(TaBaseDialog):
    def __init__(self, parent = None):
        """Constructor."""
        super(TaSetPaleoshorelinesDlg, self).__init__(parent)
        self.defineParameters()

    def defineParameters(self):
        """ Adds parameters to a list object that is used by the TaBaseDialog
        class to create widgets and place them parameters tab.
        """

        self.baseTopoBox = self.addMandatoryParameter(
            TaRasterLayerComboBox,
            "Raster to be modifiied (input):",
            "TaMapLayerComboBox")
        self.masksBox = self.addMandatoryParameter(
            TaVectorLayerComboBox,
            "Rotated paleoshorelines:",
            "TaMapLayerComboBox")

        self.modeLabel = self.addParameter(
            QtWidgets.QLabel,
            "Modification mode:",
            "GroupLabel")
        self.interpolateCheckBox = self.addParameter(
            QtWidgets.QCheckBox,
            "Interpolation",
            "CheckBox")
        self.rescaleCheckBox = self.addParameter(
            QtWidgets.QCheckBox,
            "Rescaling",
            "CheckBox")
        self.maxElevSpinBox = self.addParameter(
            QgsSpinBox,
            "Maximum elevation of the emerged area (in m):")
        self.maxDepthSpinBox = self.addParameter(
            QgsSpinBox,
            "Maximum depth of the submerged area (in m):")
        self.maxElevSpinBox.setMaximum(2000)
        self.maxElevSpinBox.setMinimum(-1)
        self.maxElevSpinBox.setValue(2)
        self.maxDepthSpinBox.setMaximum(1)
        self.maxDepthSpinBox.setMinimum(-1000)
        self.maxDepthSpinBox.setValue(-5)
        # Select modification mode
        self.selectModificationModeInterpolate(1)
        self.interpolateCheckBox.stateChanged.connect(self.selectModificationModeInterpolate)
        self.rescaleCheckBox.stateChanged.connect(self.selectModificationModeRescale)

        #Fill the parameters' tab of the Dialog with the defined parameters
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

