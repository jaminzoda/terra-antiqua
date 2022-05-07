# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from cProfile import label
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
        self.baseTopoBox = self.addMandatoryParameter(TaRasterLayerComboBox,
                                                      label="Raster to be modified:",
                                                      widget_type="TaMapLayerComboBox",
                                                      param_id="baseTopoBox")
        self.masksBox = self.addMandatoryParameter(TaVectorLayerComboBox,
                                                   label="Layer with feature polygons:",
                                                   widget_type="TaMapLayerComboBox",
                                                   param_id="masksBox")
        self.selectedFeaturesBox = self.addParameter(TaCheckBox,
                                                     label="Selected features only",
                                                     param_id="selectedFeaturesBox")
        self.selectedFeaturesBox.registerLinkedWidget(self.masksBox)
        self.featureTypeBox = self.addParameter(QComboBox,
                                                label="Geographic feature type:",
                                                param_id="featureTypeBox")
        self.featureTypeBox.addItems(["Sea", "Mountain range"])

        # Parameters for sea creation
        self.maxDepth = self.addVariantParameter(TaSpinBox,
                                                 variant_index="Sea",
                                                 label="Maximum sea depth (in m):",
                                                 param_id="maxDepth")
        self.maxDepth.spinBox.setValue(-5750)
        self.minDepth = self.addVariantParameter(TaSpinBox,
                                                 variant_index="Sea",
                                                 label="Minimum sea depth (in m):",
                                                 param_id="minDepth")
        self.minDepth.spinBox.setValue(-4000)
        self.shelfDepth = self.addVariantParameter(TaSpinBox,
                                                   variant_index="Sea",
                                                   label="Maximum shelf depth (in m):",
                                                   param_id="shelfDepth")
        self.shelfDepth.spinBox.setValue(-200)
        self.shelfWidth = self.addVariantParameter(TaSpinBox,
                                                   variant_index="Sea",
                                                   label="Shelf width (in km):",
                                                   param_id="shelfWidth")
        self.shelfWidth.spinBox.setValue(150)
        self.shelfWidth.setAllowedValueRange(0, 1000)
        self.contSlopeWidth = self.addVariantParameter(TaSpinBox,
                                                       variant_index="Sea",
                                                       label="Width of continental slope (in km):",
                                                       param_id="contSlopeWidth")
        self.contSlopeWidth.spinBox.setValue(100)
        self.contSlopeWidth.setAllowedValueRange(0, 1000)

        self.keepDeepBathyCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                               label="Keep deeper bathymetry",
                                                               variant_index="Sea",
                                                               param_id="keepDeepBathyCheckBox")

        # Parameters for mountain range creation
        self.maxElev = self.addVariantParameter(TaSpinBox,
                                                variant_index="Mountain range",
                                                label="Maximum ridge elevation (in m)",
                                                param_id="maxElev")
        self.maxElev.spinBox.setValue(5000)
        self.minElev = self.addVariantParameter(TaSpinBox,
                                                variant_index="Mountain range",
                                                label="Minimum ridge elevation (in m)",
                                                param_id="minElev")
        self.minElev.spinBox.setValue(3000)

        self.mountRugged = self.addVariantParameter(TaSpinBox,
                                                    variant_index="Mountain range",
                                                    label="Ruggedness of the mountains (in %)",
                                                    param_id="mountRugged")
        self.mountRugged.spinBox.setValue(30)
        self.mountRugged.setAllowedValueRange(0, 100)
        self.mountSlope = self.addVariantParameter(TaSpinBox,
                                                   variant_index="Mountain range",
                                                   label="Width of mountain slope (in km)",
                                                   param_id="mountSlope")
        self.mountSlope.spinBox.setValue(5)
        self.mountSlope.setAllowedValueRange(0, 500)

        self.keepHighTopoCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                              label="Keep higher topography",
                                                              variant_index="Mountain range",
                                                              param_id="keepHighTopoCheckBox")
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
