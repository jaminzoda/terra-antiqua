#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
#Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py


from PyQt5 import QtCore, QtWidgets

from qgis.gui import QgsSpinBox
from qgis.core import QgsMapLayerProxyModel
from .base_dialog import TaBaseDialog
from .widgets import (
    TaRasterLayerComboBox,
    TaCheckBox,
    TaSpinBox,
    TaVectorLayerComboBox,
    TaColorSchemeWidget
)

class TaStandardProcessingDlg(TaBaseDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaStandardProcessingDlg, self).__init__(parent)
        self.defineParameters()
        self.fillingTypeBox.currentTextChanged.connect(self.reloadHelp)

    def defineParameters(self):
        self.fillingTypeBox = self.addParameter(QtWidgets.QComboBox, "How would you like to process the input DEM?")
        self.fillingTypeBox.addItems(["Fill gaps",
                                      "Copy/Paste raster",
                                      "Smooth raster",
                                      "Isostatic compensation",
                                      "Set new sea level",
                                      "Calculate bathymetry",
                                      "Change map symbology"])
        self.baseTopoBox = self.addMandatoryParameter(TaRasterLayerComboBox,
                                                      "Raster to be modified:",
                                                      "TaMapLayerComboBox")
        #Parameters for filling the gaps
        self.interpInsidePolygonCheckBox = self.addVariantParameter(TaCheckBox,
                                                                    "Fill gaps",
                                                                    "Interpolate inside polygon(s) only.")
        self.masksBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                 "Fill gaps",
                                                 "Mask layer:",
                                                 "TaMapLayerComboBox")
        self.interpInsidePolygonCheckBox.registerEnabledWidgets([self.masksBox])
        self.smoothingBox = self.addVariantParameter(TaCheckBox, "Fill gaps",
                                                     "Smooth the resulting raster")
        self.smoothingTypeBox = self.addVariantParameter(QtWidgets.QComboBox,
                                                         "Fill gaps",
                                                         "Smoothing type:")
        self.smoothingTypeBox.addItems(["Gaussian filter",
                                        "Uniform filter"])
        self.smFactorSpinBox = self.addVariantParameter(QgsSpinBox,
                                                        "Fill gaps",
                                                        "Smoothing factor (in grid cells):")
        self.smFactorSpinBox.setMinimum(1)
        self.smFactorSpinBox.setMaximum(5)

        self.smoothingBox.registerEnabledWidgets([self.smoothingTypeBox,
                                                  self.smFactorSpinBox])

        #Parameters for Copying and pasting raster data
        self.copyFromRasterBox = self.addVariantParameter(TaRasterLayerComboBox,
                                                          "Copy/Paste raster",
                                                          "Raster to copy values from:",
                                                          "TaMapLayerComboBox",
                                                          mandatory = True)
        self.copyFromMaskBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                        "Copy/Paste raster",
                                                        "Mask layer:",
                                                        "TaMapLayerComboBox",
                                                        mandatory = True)
        self.copyPasteSelectedFeaturesOnlyCheckBox = self.addVariantParameter(TaCheckBox,
                                                                              "Copy/Paste raster",
                                                                              "Selected features only")
        self.copyPasteSelectedFeaturesOnlyCheckBox.registerLinkedWidget(self.copyFromMaskBox)

        #Parameters for smothing rasters
        self.smoothInPolygonCheckBox = self.addVariantParameter(TaCheckBox,
                                                       "Smooth raster",
                                                       "Smooth inside polygon(s) only.")
        self.smoothInPolygonCheckBox.stateChanged.connect(self.onSmoothInPolygonCheckBoxStateChange)
        self.smoothingMaskBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                       "Smooth raster",
                                                       "Mask layer:",
                                                       "TaMapLayerComboBox")
        self.smoothingMaskBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.smoothingMaskBox.layerChanged.connect(self.setFieldsInLayer)
        self.smoothInPolygonCheckBox.registerEnabledWidgets([self.smoothingMaskBox])

        self.smoothingTypeBox2 = self.addVariantParameter(QtWidgets.QComboBox,
                                                          "Smooth raster",
                                                          "Smoothing type:")
        self.smFactorSpinBox2 = self.addVariantParameter(TaSpinBox,
                                                         "Smooth raster",
                                                         "Smoothing factor (in grid cells):")
        self.smoothingTypeBox2.addItems(["Gaussian filter",
                                         "Uniform filter"])
        self.smFactorSpinBox2.setAllowedValueRange(1,5)
        self.fixedPaleoShorelinesCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                      label = "Set paleoshorelines fixed.",
                                                                      variant_index = "Smooth raster")
        self.fixedPaleoShorelinesCheckBox.stateChanged.connect(self.onFixedPaleoshorelinesCheckBoxStateChange)
        self.paleoshorelinesMask = self.addAdvancedParameter(TaVectorLayerComboBox,
                                                              label = "Rotated paleoshorelines:",
                                                              widget_type = "TaMapLayerComboBox",
                                                              variant_index = "Smooth raster")
        self.paleoshorelinesMask.setLayerType("Polygon")
        self.fixedPaleoShorelinesCheckBox.registerEnabledWidgets([self.paleoshorelinesMask])

        #Parameters for Isostatic compensation
        self.selectIceTopoBox = self.addVariantParameter(TaRasterLayerComboBox,
                                                         "Isostatic compensation",
                                                         "Ice topography raster:",
                                                         mandatory = True)
        self.isostatMaskBox = self.addAdvancedParameter(TaVectorLayerComboBox,
                                                       label = "Mask layer:",
                                                       widget_type = "TaMapLayerComboBox",
                                                       variant_index = "Isostatic compensation")
        self.isostatMaskSelectedFeaturesCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                             label = "Selected features only",
                                                                             variant_index = "Isostatic compensation")
        self.isostatMaskSelectedFeaturesCheckBox.registerLinkedWidget(self.isostatMaskBox)

        self.masksFromCoastCheckBox = self.addAdvancedParameter(
                                        TaCheckBox,
                                        label = "Get polar regions automatically.",
                                        variant_index = "Isostatic compensation")
        self.isostatMaskSelectedFeaturesCheckBox.registerEnabledWidgets([self.masksFromCoastCheckBox], natural = True)



        self.iceAmountSpinBox = self.addVariantParameter(
                                        QgsSpinBox,
                                        "Isostatic compensation",
                                        "Amount of the ice to be removed (in %)"
                                        )
        self.iceAmountSpinBox.setMinimum(0)
        self.iceAmountSpinBox.setMaximum(100)
        self.iceAmountSpinBox.setValue(30)


        #Parameters for Setting sea level
        self.seaLevelShiftBox = self.addVariantParameter(QgsSpinBox,
                                                         "Set new sea level",
                                                         "Amount of sea level shift (m):")
        self.seaLevelShiftBox.setMinimum(-1000)
        self.seaLevelShiftBox.setMaximum(1000)
        self.seaLevelShiftBox.setValue(100)

        #Parameters for calculating bathymetry from ocean age
        self.ageRasterTime =  self.addVariantParameter(QgsSpinBox,
                                                          "Calculate bathymetry",
                                                          "Time of the age raster:")
        self.ageRasterTime.setValue(0)
        self.reconstructionTime = self.addVariantParameter(QgsSpinBox,
                                                          "Calculate bathymetry",
                                                          "Reconstruction time:")

        #Parameters for changing map symbology
        self.colorPalette = self.addVariantParameter(TaColorSchemeWidget, "Change map symbology", "Color palette:")

        self.fillDialog()
        self.showVariantWidgets(self.fillingTypeBox.currentText())
        self.fillingTypeBox.currentTextChanged.connect(self.showVariantWidgets)
        self.group_box.collapsedStateChanged.connect(lambda:self.showAdvancedWidgets(self.fillingTypeBox.currentText()))


    def setFieldsInLayer(self):
        self.smFactorSpinBox2.initOverrideButton("Smoothing factor","Smoothing factor for each mask",
                                             self.smoothingMaskBox.currentLayer())

    def onSmoothInPolygonCheckBoxStateChange(self, state):
        if state == QtCore.Qt.Checked:
            self.smoothingMaskBox.setLayer(self.smoothingMaskBox.layer(1))
        else:
            self.smoothingMaskBox.setLayer(self.smoothingMaskBox.layer(0))

    def onFixedPaleoshorelinesCheckBoxStateChange(self, state):
        if state == QtCore.Qt.Checked:
            self.paleoshorelinesMask.setLayer(self.smoothingMaskBox.layer(1))
        else:
            self.paleoshorelinesMask.setLayer(self.smoothingMaskBox.layer(0))

    def reloadHelp(self):
        """
        Sets the name of the chosen processing algorithm (e.g. Smooth raster) to the dialog so that it can load the help
        file properly."""
        processing_alg_names = [("Fill gaps", "TaFillGaps"),
                                ("Copy/Paste raster", "TaCopyPasteRaster"),
                                ("Smooth raster", "TaSmoothRaster"),
                                ("Isostatic compensation", "TaIsostaticCompensation"),
                                ("Set new sea level", "TaSetSeaLevel"),
                                ("Calculate bathymetry", "TaCalculateBathymetry"),
                                ("Change map symbology", "TaChangeMapSymbology")]
        for alg, name in processing_alg_names:
            if self.fillingTypeBox.currentText() == alg:
                self.setDialogName(name)
        if self.fillingTypeBox.currentText() == "Change map symbology":
            self.outputPath.hide()
            self.outputPathLabel.hide()
        else:
            self.outputPath.show()
            self.outputPathLabel.show()
        self.loadHelp()
