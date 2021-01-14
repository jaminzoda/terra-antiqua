
from PyQt5 import QtWidgets
from .base_dialog import TaBaseDialog
from .widgets import (
    TaRasterLayerComboBox,
    TaVectorLayerComboBox,
    TaSpinBox,
    TaCheckBox,
    TaExpressionWidget)


class TaModifyTopoBathyDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super(TaModifyTopoBathyDlg, self).__init__(parent)
        self.defineParameters()
        self.masksBox.layerChanged.connect(self.setFieldsInLayer)
    def defineParameters(self):
        self.baseTopoBox = self.addMandatoryParameter(
            TaRasterLayerComboBox,
            "Select the topography raster for modification:",
            "TaMapLayerComboBox")
        self.masksBox = self.addMandatoryParameter(
                                    TaVectorLayerComboBox,
                                    "Select vector layer containing masks:",
                                    "TaMapLayerComboBox")
        self.selectedFeaturesBox = self.addParameter(
                                    TaCheckBox,
                                    "Selected features only",
                                   "CheckBox")
        try:
            self.selectedFeaturesBox.registerLinkedWidget(self.masksBox)
        except Exception as e:
            pass
        self.modificationModeComboBox = self.addParameter(
                                            QtWidgets.QComboBox,
                                            "Topography modification mode:")
        self.modificationModeComboBox.addItems([
                                            'Modify with formula',
                                            'Rescale with final minimum and maximum values'])
        # The formula modification parameters
        self.formulaField = self.addVariantParameter(
                                    TaExpressionWidget,
                                    "Modify with formula",
                                    "Select the formula field or type the formula:")
        self.min_maxValueCheckBox = self.addVariantParameter(
                                        TaCheckBox,
                                        "Modify with formula",
                                        "Constrain values to be modified with minimum and maximum",
                                        "CheckBox")
        self.minValueSpin= self.addVariantParameter(
                                    TaSpinBox,
                                    "Modify with formula",
                                    "Minimum:")

        self.maxValueSpin= self.addVariantParameter(
                                    TaSpinBox,
                                    "Modify with formula",
                                    "Maximum:")
        self.min_maxValueCheckBox.registerEnabledWidgets([self.minValueSpin,
                                                          self.maxValueSpin])

        # The rescaling modification parameters
        self.newMinValueSpin = self.addVariantParameter(TaSpinBox,
                                                        "Rescale with final minimum and maximum values",
                                                        "Final minimum:")
        self.newMaxValueSpin = self.addVariantParameter(TaSpinBox,
                                                        "Rescale with final minimum and maximum values",
                                                        "Final maximum:")




        self.fillDialog()
        self.showVariantWidgets(self.modificationModeComboBox.currentText())
        self.modificationModeComboBox.currentTextChanged.connect(self.showVariantWidgets)


    def setFieldsInLayer(self):
        self.formulaField.initOverrideButton("Formula", "Formula for\
                                             Topography modification",
                                             self.masksBox.currentLayer())
        self.minValueSpin.initOverrideButton("minValue",
                                              "Minimum bounding value",
                                              self.masksBox.currentLayer())
        self.maxValueSpin.initOverrideButton("maxValue",
                                              "Maximum bounding value",
                                              self.masksBox.currentLayer())
        self.newMinValueSpin.initOverrideButton("newMinValue",
                                              "Minimum value for rescaling",
                                              self.masksBox.currentLayer())
        self.newMaxValueSpin.initOverrideButton("newMaxValue",
                                              "Maximum value for rescaling",
                                              self.masksBox.currentLayer())
