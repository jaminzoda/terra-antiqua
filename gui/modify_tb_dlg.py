# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from re import L
from PyQt5 import QtWidgets
from .base_dialog import TaBaseDialog
from .widgets import (
    TaRasterLayerComboBox,
    TaVectorLayerComboBox,
    TaSpinBox,
    TaCheckBox,
    TaExpressionWidget,
    TaColorSchemeWidget
)
from numpy import *  # This is to use math functions for formula validation


class TaModifyTopoBathyDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super(TaModifyTopoBathyDlg, self).__init__(parent)
        self.defineParameters()
        self.masksBox.layerChanged.connect(self.setFieldsInLayer)

    def defineParameters(self):
        self.baseTopoBox = self.addMandatoryParameter(
            TaRasterLayerComboBox,
            label="Select the topography raster for modification:",
            widget_type="TaMapLayerComboBox",
            param_id="baseTopoBox")
        self.masksBox = self.addMandatoryParameter(
            TaVectorLayerComboBox,
            label="Select vector layer containing masks:",
            widget_type="TaMapLayerComboBox",
            param_id="masksBox")
        self.selectedFeaturesBox = self.addParameter(
            TaCheckBox,
            label="Selected features only",
            widget_type="CheckBox",
            param_id="selectedFeaturesBox")
        try:
            self.selectedFeaturesBox.registerLinkedWidget(self.masksBox)
        except Exception as e:
            pass
        self.modificationModeComboBox = self.addParameter(
            QtWidgets.QComboBox,
            label="Topography modification mode:",
            widget_type="QComboBox",
            param_id="modificationModeComboBox")
        self.modificationModeComboBox.addItems(['Modify with formula',
                                                'Rescale with final minimum and maximum values'])
        # The formula modification parameters
        self.formulaField = self.addVariantParameter(
            TaExpressionWidget,
            variant_index="Modify with formula",
            label="Select the formula field or type the formula:",
            param_id="formulaField")
        self.formulaField.lineEdit.editingFinished.connect(
            self.formulaValidation)
        self.min_maxValueCheckBox = self.addVariantParameter(
            TaCheckBox,
            variant_index="Modify with formula",
            label="Constrain values to be modified with minimum and maximum",
            widget_type="CheckBox",
            param_id="min_maxValueCheckBox")
        self.minValueSpin = self.addVariantParameter(
            TaSpinBox,
            variant_index="Modify with formula",
            label="Minimum:",
            param_id="minValueSpin")

        self.maxValueSpin = self.addVariantParameter(
            TaSpinBox,
            variant_index="Modify with formula",
            label="Maximum:",
            param_id="maxValueSpin")
        self.min_maxValueCheckBox.registerEnabledWidgets([self.minValueSpin,
                                                          self.maxValueSpin])

        # The rescaling modification parameters
        self.newMinValueSpin = self.addVariantParameter(TaSpinBox,
                                                        variant_index="Rescale with final minimum and maximum values",
                                                        label="Final minimum:",
                                                        param_id="newMinValueSpin")
        self.newMaxValueSpin = self.addVariantParameter(TaSpinBox,
                                                        variant_index="Rescale with final minimum and maximum values",
                                                        label="Final maximum:",
                                                        param_id="newMaxValueSpin")

        # Add advanced parameters

        self.fillDialog()
        self.showVariantWidgets(self.modificationModeComboBox.currentText())
        self.modificationModeComboBox.currentTextChanged.connect(
            self.showVariantWidgets)

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

    def formulaValidation(self):
        H = random.random((1800, 3600))
        try:
            eval(self.formulaField.lineEdit.value())
        except Exception as e:
            self.msgBar.pushWarning(
                "Warning:", f"The entered formula is invalid: {e}.")
