# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import pyqtSlot
from .base_dialog import TaBaseDialog
from .widgets import (
    TaRasterLayerComboBox,
    TaVectorLayerComboBox,
    TaCheckBox,
    TaSpinBox,
    TaDoubleSpinBox,
    TaColorSchemeWidget
)


class TaCreateTopoBathyDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super(TaCreateTopoBathyDlg, self).__init__(parent)
        self.defineParameters()
        self.masksBox.layerChanged.connect(self.setFieldsInLayer)

    def defineParameters(self):
        featureTypeSea = "Sea"
        featureTypeRandomMountain = "Mountain range (random)"
        featureTypeFractalMountain = "Mountain range (fractal)"
        self.baseTopoBox = self.addMandatoryParameter(
            TaRasterLayerComboBox, "Raster to be modified:", "TaMapLayerComboBox")
        self.masksBox = self.addMandatoryParameter(
            TaVectorLayerComboBox, "Layer with feature polygons:", "TaMapLayerComboBox")
        self.selectedFeaturesBox = self.addParameter(
            TaCheckBox, "Selected features only")
        self.selectedFeaturesBox.registerLinkedWidget(self.masksBox)
        self.featureTypeBox = self.addParameter(
            QComboBox, "Geographic feature type:")
        self.featureTypeBox.addItems(
            [featureTypeSea, featureTypeRandomMountain, featureTypeFractalMountain])

        # Parameters for sea creation
        self.maxDepth = self.addVariantParameter(TaSpinBox, featureTypeSea,
                                                 "Maximum sea depth (in m):")
        self.maxDepth.spinBox.setValue(-5750)
        self.minDepth = self.addVariantParameter(TaSpinBox, featureTypeSea,
                                                 "Minimum sea depth (in m):")
        self.minDepth.spinBox.setValue(-4000)
        self.shelfDepth = self.addVariantParameter(TaSpinBox, featureTypeSea,
                                                   "Maximum shelf depth (in m):")
        self.shelfDepth.spinBox.setValue(-200)
        self.shelfWidth = self.addVariantParameter(TaSpinBox, featureTypeSea,
                                                   "Shelf width (in km):")
        self.shelfWidth.spinBox.setValue(150)
        self.shelfWidth.setAllowedValueRange(0, 1000)
        self.contSlopeWidth = self.addVariantParameter(TaSpinBox, featureTypeSea,
                                                       "Width of continental slope (in km):")
        self.contSlopeWidth.spinBox.setValue(100)
        self.contSlopeWidth.setAllowedValueRange(0, 1000)

        self.keepDeepBathyCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                               label="Keep deeper bathymetry",
                                                               variant_index=featureTypeSea)

        # Parameters for mountain range creation
        self.maxElev = self.addVariantParameter(TaSpinBox,
                                                featureTypeRandomMountain,
                                                "Maximum ridge elevation (in m):")
        self.maxElev.spinBox.setValue(5000)
        self.minElev = self.addVariantParameter(TaSpinBox,
                                                featureTypeRandomMountain,
                                                "Minimum ridge elevation (in m):")
        self.minElev.spinBox.setValue(3000)

        self.mountRugged = self.addVariantParameter(TaSpinBox,
                                                    featureTypeRandomMountain,
                                                    "Ruggedness of the mountains (in %):")
        self.mountRugged.spinBox.setValue(30)
        self.mountRugged.setAllowedValueRange(0, 100)
        self.mountSlope = self.addVariantParameter(TaSpinBox,
                                                   featureTypeRandomMountain,
                                                   "Width of mountain slope (in km):")
        self.mountSlope.spinBox.setValue(5)
        self.mountSlope.setAllowedValueRange(0, 500)

        self.keepHighTopoCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                              label="Keep higher topography",
                                                              variant_index="Mountain range")

        # Parameters for creating mountain ranges using stream power law and fractal geometry
        self.maxElevFractal = self.addVariantParameter(TaSpinBox,
                                                       featureTypeFractalMountain,
                                                       "Maximum ridge elevation (in m):")
        self.maxElevFractal.spinBox.setValue(5000)
        self.maxElevFractal.setDataType("double")

        self.mExponentFractal = self.addVariantParameter(TaDoubleSpinBox,
                                                         featureTypeFractalMountain,
                                                         "m exponent of the Stream power law:")
        self.mExponentFractal.spinBox.setObjectName("mExponent")
        self.mExponentFractal.setAllowedValueRange(0.1, 10000.0)
        self.mExponentFractal.setValue(0.45)
        self.mExponentFractal.setDataType("double")
        self.mExponentFractal.spinBox.setClearValue(
            self.mExponentFractal.spinBox.minimum())
        self.mExponentFractal.spinBox.valueChanged.connect(
            self.synchronizeMAndNExponents)

        self.nExponentFractal = self.addVariantParameter(TaDoubleSpinBox,
                                                         featureTypeFractalMountain,
                                                         "n exponent of the Stream power law:")
        self.nExponentFractal.spinBox.setObjectName("nExponent")
        self.nExponentFractal.setAllowedValueRange(0.1, 10000.0)
        self.nExponentFractal.setValue(1)
        self.nExponentFractal.setDataType("double")
        self.nExponentFractal.spinBox.setClearValue(
            self.nExponentFractal.spinBox.minimum())
        self.nExponentFractal.spinBox.valueChanged.connect(
            self.synchronizeMAndNExponents)

        self.rockErodabilityFractal = self.addVariantParameter(TaDoubleSpinBox,
                                                               featureTypeFractalMountain,
                                                               "Rock erodability (K):")
        self.rockErodabilityFractal.spinBox.setDecimals(13)
        self.rockErodabilityFractal.setAllowedValueRange(1e-13, 1e-2)
        self.rockErodabilityFractal.setValue(2e-5)
        self.rockErodabilityFractal.setDataType("double")
        self.rockErodabilityFractal.spinBox.setClearValue(
            self.rockErodabilityFractal.spinBox.minimum())

        self.drainageAreaFractal = self.addVariantParameter(TaDoubleSpinBox,
                                                            featureTypeFractalMountain,
                                                            "Upstream drainage area (A):")
        self.drainageAreaFractal.setAllowedValueRange(1.0, 100000.0)
        self.drainageAreaFractal.setValue(2e4)
        self.drainageAreaFractal.setDataType("double")
        self.drainageAreaFractal.spinBox.setClearValue(
            self.drainageAreaFractal.spinBox.minimum())

        self.channelSlopeFractal = self.addVariantParameter(TaDoubleSpinBox,
                                                            featureTypeFractalMountain,
                                                            "Channel slope (S):")
        self.channelSlopeFractal.setAllowedValueRange(0.0, 10000.0)
        self.channelSlopeFractal.setValue(0.6)
        self.channelSlopeFractal.setDataType("double")
        self.channelSlopeFractal.spinBox.setClearValue(
            self.channelSlopeFractal.spinBox.minimum())

        self.fillDialog()
        self.showVariantWidgets(self.featureTypeBox.currentText())
        self.featureTypeBox.currentTextChanged.connect(self.showVariantWidgets)

    def setFieldsInLayer(self):
        self.maxDepth.initOverrideButton("maxDepthValue",
                                         "Maximum sea depth",
                                         self.masksBox.currentLayer())
        self.minDepth.initOverrideButton("minDepthValue",
                                         "Minimum sea depth",
                                         self.masksBox.currentLayer())
        self.shelfDepth.initOverrideButton("shelfDepthValue",
                                           "The shelf depth",
                                           self.masksBox.currentLayer())
        self.shelfWidth.initOverrideButton("shelfWidthValue",
                                           "The shelf width",
                                           self.masksBox.currentLayer())

        self.contSlopeWidth.initOverrideButton("slopeWidthValue",
                                               "The width of continental slope",
                                               self.masksBox.currentLayer())
        self.maxElev.initOverrideButton("maxElevValue",
                                        "Maximum elevation of mountain",
                                        self.masksBox.currentLayer())
        self.minElev.initOverrideButton("minElevValue",
                                        "Minimum elevation of mountain",
                                        self.masksBox.currentLayer())
        self.mountRugged.initOverrideButton("mountRuggedValue",
                                            "Ruggedness of mountain",
                                            self.masksBox.currentLayer())
        self.mountSlope.initOverrideButton("mountSlopeValue",
                                           "Width of mountain slope",
                                           self.masksBox.currentLayer())
        self.maxElevFractal.initOverrideButton("maxElevValueFractal",
                                               "Maximum ridge elevation",
                                               self.masksBox.currentLayer())
        self.mExponentFractal.initOverrideButton("mExponentFractal",
                                                 "m Exponent of SPL",
                                                 self.masksBox.currentLayer())
        self.nExponentFractal.initOverrideButton("nExponentFractal",
                                                 "n Exponent of SPL",
                                                 self.masksBox.currentLayer())
        self.rockErodabilityFractal.initOverrideButton("rockErodabilityFractal",
                                                       "Rock erodability",
                                                       self.masksBox.currentLayer())
        self.drainageAreaFractal.initOverrideButton("drainageAreaFractal",
                                                    "Upstream drainage area",
                                                    self.masksBox.currentLayer())
        self.channelSlopeFractal.initOverrideButton("channelSlopeFractal",
                                                    "Channel slope",
                                                    self.masksBox.currentLayer())

    @pyqtSlot()
    def synchronizeMAndNExponents(self):
        """The ration of m/n in stream power law equation (E=KA^mS^n)
        should range between 0.2 and 0.8. This function makes sure
        that it doesn't go beyond this range."""
        ratio = self.mExponentFractal.value()/self.nExponentFractal.value()
        if self.sender().objectName() == "mExponent":
            if ratio > 0.8:
                self.nExponentFractal.setValue(
                    self.mExponentFractal.value()/0.8)
            elif ratio < 0.2:
                self.nExponentFractal.setValue(
                    self.mExponentFractal.value()/0.2)
        elif self.sender().objectName() == "nExponent":
            if ratio > 0.8:
                self.mExponentFractal.setValue(
                    self.nExponentFractal.value()*0.8)
            elif ratio < 0.2:
                self.mExponentFractal.setValue(
                    self.nExponentFractal.value()*0.2)
