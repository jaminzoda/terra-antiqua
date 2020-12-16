

import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog, QComboBox
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
from .base_dialog import TaBaseDialog
from .widgets import (
                        TaRasterLayerComboBox,
                        TaVectorLayerComboBox,
                        TaCheckBox,
                        TaSpinBox
                    )

class TaCreateTopoBathyDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super(TaCreateTopoBathyDlg, self).__init__(parent)
        self.defineParameters()
        self.masksBox.layerChanged.connect(self.setFieldsInLayer)

    def defineParameters(self):
        self.baseTopoBox = self.addMandatoryParameter(TaRasterLayerComboBox, "Raster to be modified", "TaMapLayerComboBox")
        self.masksBox = self.addMandatoryParameter(TaVectorLayerComboBox, "Layer with feature polygons", "TaMapLayerComboBox")
        self.selectedFeaturesBox = self.addParameter(TaCheckBox, "Selected features only")
        self.selectedFeaturesBox.registerLinkedWidget(self.masksBox)
        self.featureTypeBox = self.addParameter(QComboBox, "Geographic feature type")
        self.featureTypeBox.addItems(["Sea", "Mountain range"])

        #Parameters for sea creation
        self.maxDepth= self.addVariantParameter(TaSpinBox, "Sea",
                                                "Maximum sea depth (in m)")
        self.maxDepth.spinBox.setValue(-5750)
        self.minDepth= self.addVariantParameter(TaSpinBox, "Sea",
                                                    "Minimum sea depth (in m)")
        self.minDepth.spinBox.setValue(-4000)
        self.shelfDepth= self.addVariantParameter(TaSpinBox, "Sea",
                                                "Maximum shelf depth (in m)")
        self.shelfDepth.spinBox.setValue(-200)
        self.shelfWidth= self.addVariantParameter(TaSpinBox, "Sea",
                                                "Shelf width (in km)")
        self.shelfWidth.spinBox.setValue(150)
        self.shelfWidth.setAllowedValueRange(0, 1000)
        self.contSlopeWidth= self.addVariantParameter(TaSpinBox, "Sea",
                                        "Width of continental slope (in km)")
        self.contSlopeWidth.spinBox.setValue(100)
        self.contSlopeWidth.setAllowedValueRange(0, 1000)

        #Parameters for mountain range creation
        self.maxElev = self.addVariantParameter(TaSpinBox,
                                                "Mountain range",
                                                "Maximum ridge elevation (in m)")
        self.maxElev.spinBox.setValue(5000)
        self.minElev = self.addVariantParameter(TaSpinBox,
                                                "Mountain range",
                                                "Minimum ridge elevation (in m)")
        self.minElev.spinBox.setValue(3000)

        self.mountRugged = self.addVariantParameter(TaSpinBox,
                                                "Mountain range",
                                                "Ruggedness of the mountains (in %)")
        self.mountRugged.spinBox.setValue(30)
        self.mountRugged.setAllowedValueRange(0, 100)
        self.mountSlope = self.addVariantParameter(TaSpinBox,
                                                   "Mountain range",
                                                   "Width of mountain slope (in km)")
        self.mountSlope.spinBox.setValue(5)
        self.mountSlope.setAllowedValueRange(0, 500)

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


