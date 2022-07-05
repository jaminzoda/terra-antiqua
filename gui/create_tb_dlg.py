# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from PyQt5.QtWidgets import QComboBox
from .base_dialog import TaBaseDialog
from .widgets import (
    TaRasterLayerComboBox,
    TaVectorLayerComboBox,
    TaCheckBox,
    TaSpinBox,
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
                                                "Maximum ridge elevation (in m)")
        self.maxElev.spinBox.setValue(5000)
        self.minElev = self.addVariantParameter(TaSpinBox,
                                                featureTypeRandomMountain,
                                                "Minimum ridge elevation (in m)")
        self.minElev.spinBox.setValue(3000)

        self.mountRugged = self.addVariantParameter(TaSpinBox,
                                                    featureTypeRandomMountain,
                                                    "Ruggedness of the mountains (in %)")
        self.mountRugged.spinBox.setValue(30)
        self.mountRugged.setAllowedValueRange(0, 100)
        self.mountSlope = self.addVariantParameter(TaSpinBox,
                                                   featureTypeRandomMountain,
                                                   "Width of mountain slope (in km)")
        self.mountSlope.spinBox.setValue(5)
        self.mountSlope.setAllowedValueRange(0, 500)

        self.keepHighTopoCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                              label="Keep higher topography",
                                                              variant_index="Mountain range")

        # Parameters for creating mountain ranges using stream power law and fractal geometry
        self.maxElevFractal = self.addVariantParameter(TaSpinBox,
                                                       featureTypeFractalMountain,
                                                       "Maximum ridge elevation (in m)")
        self.maxElevFractal.spinBox.setValue(5000)

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
