# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


from PyQt5 import QtCore, QtWidgets

import os
import shutil
from PyQt5.QtWidgets import (
    QComboBox,
    QPushButton,
    QFileDialog
)

from qgis.gui import QgsSpinBox, QgsDoubleSpinBox
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
        self.processingTypeBox.currentTextChanged.connect(self.reloadHelp)

    def defineParameters(self):
        self.processingTypeBox = self.addParameter(QComboBox,
                                                   label="How would you like to process the input DEM?",
                                                   param_id="processingTypeBox")
        self.processingTypeBox.addItems(["Fill gaps",
                                         "Copy/Paste raster",
                                         "Smooth raster",
                                         "Isostatic compensation",
                                         "Set new sea level",
                                         "Calculate bathymetry",
                                         "Change map symbology"])
        self.baseTopoBox = self.addMandatoryParameter(TaRasterLayerComboBox,
                                                      label="Raster to be modified:",
                                                      widget_type="TaMapLayerComboBox",
                                                      param_id="baseTopoBox")
        # Parameters for filling the gaps
        self.fillingTypeBox = self.addVariantParameter(QComboBox,
                                                       variant_index="Fill gaps",
                                                       label="Filling type:",
                                                       param_id="fillingTypeBox")
        self.fillingTypeBox.addItems(["Interpolation",
                                      "Fixed value"])
        self.fillingValueSpinBox = self.addVariantParameter(QgsDoubleSpinBox,
                                                            variant_index="Fill gaps",
                                                            label="Filling value:",
                                                            param_id="fillingValueSpinBox")
        self.fillingValueSpinBox.setMaximum(99999)
        self.fillingValueSpinBox.setMinimum(-99999)
        self.fillingValueSpinBox.setValue(9999)
        self.interpInsidePolygonCheckBox = self.addVariantParameter(TaCheckBox,
                                                                    variant_index="Fill gaps",
                                                                    label="Fill inside polygon(s) only.",
                                                                    param_id="interpInsidePolygonCheckBox")
        self.masksBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                 variant_index="Fill gaps",
                                                 label="Mask layer:",
                                                 widget_type="TaMapLayerComboBox",
                                                 param_id="masksBox")
        self.interpInsidePolygonCheckBox.registerEnabledWidgets([
                                                                self.masksBox])
        self.smoothingBox = self.addVariantParameter(TaCheckBox,
                                                     variant_index="Fill gaps",
                                                     label="Smooth the resulting raster",
                                                     param_id="smoothingBox")
        self.smoothingTypeBox = self.addVariantParameter(QtWidgets.QComboBox,
                                                         variant_index="Fill gaps",
                                                         label="Smoothing type:",
                                                         param_id="smoothingTypeBox")
        self.smoothingTypeBox.addItems(["Gaussian filter",
                                        "Uniform filter"])
        self.smFactorSpinBox = self.addVariantParameter(QgsSpinBox,
                                                        variant_index="Fill gaps",
                                                        label="Smoothing factor (in grid cells):",
                                                        param_id="smFactorSpinBox")
        self.smFactorSpinBox.setMinimum(1)
        self.smFactorSpinBox.setMaximum(5)

        self.smoothingBox.registerEnabledWidgets([self.smoothingTypeBox,
                                                  self.smFactorSpinBox])

        # Parameters for Copying and pasting raster data
        self.copyFromRasterBox = self.addVariantParameter(TaRasterLayerComboBox,
                                                          variant_index="Copy/Paste raster",
                                                          label="Raster to copy values from:",
                                                          widget_type="TaMapLayerComboBox",
                                                          mandatory=True,
                                                          param_id="copyFromRasterBox")
        self.copyFromMaskBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                        variant_index="Copy/Paste raster",
                                                        label="Mask layer:",
                                                        widget_type="TaMapLayerComboBox",
                                                        mandatory=True,
                                                        param_id="copyFromMaskBox")
        self.copyPasteSelectedFeaturesOnlyCheckBox = self.addVariantParameter(TaCheckBox,
                                                                              variant_index="Copy/Paste raster",
                                                                              label="Selected features only",
                                                                              param_id="copyPasteSelectedFeaturesOnlyCheckBox")
        self.copyPasteSelectedFeaturesOnlyCheckBox.registerLinkedWidget(
            self.copyFromMaskBox)

        # Parameters for smothing rasters
        self.smoothInPolygonCheckBox = self.addVariantParameter(TaCheckBox,
                                                                variant_index="Smooth raster",
                                                                label="Smooth inside polygon(s) only.",
                                                                param_id="smoothInPolygonCheckBox")
        self.smoothInPolygonCheckBox.stateChanged.connect(
            self.onSmoothInPolygonCheckBoxStateChange)
        self.smoothingMaskBox = self.addVariantParameter(TaVectorLayerComboBox,
                                                         variant_index="Smooth raster",
                                                         label="Mask layer:",
                                                         widget_type="TaMapLayerComboBox",
                                                         param_id="smoothingMaskBox")
        self.smoothingMaskBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.smoothingMaskBox.layerChanged.connect(self.setFieldsInLayer)
        self.smoothInPolygonCheckBox.registerEnabledWidgets(
            [self.smoothingMaskBox])
        self.smoothInSelectedFeaturesOnlyCheckBox = self.addVariantParameter(TaCheckBox,
                                                                             variant_index="Smooth raster",
                                                                             label="Selected features only.",
                                                                             param_id="smoothInSelectedFeaturesOnlyCheckBox")
        self.smoothInSelectedFeaturesOnlyCheckBox.registerLinkedWidget(
            self.smoothingMaskBox)

        self.smoothingTypeBox2 = self.addVariantParameter(QtWidgets.QComboBox,
                                                          variant_index="Smooth raster",
                                                          label="Smoothing type:",
                                                          param_id="smoothingTypeBox2")
        self.smFactorSpinBox2 = self.addVariantParameter(TaSpinBox,
                                                         variant_index="Smooth raster",
                                                         label="Smoothing factor (in grid cells):",
                                                         param_id="smFactorSpinBox2")
        self.smoothingTypeBox2.addItems(["Gaussian filter",
                                         "Uniform filter"])
        self.smFactorSpinBox2.setAllowedValueRange(1, 5)
        self.fixedPaleoShorelinesCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                      label="Set paleoshorelines fixed.",
                                                                      variant_index="Smooth raster",
                                                                      param_id="fixedPaleoShorelinesCheckBox")
        self.fixedPaleoShorelinesCheckBox.stateChanged.connect(
            self.onFixedPaleoshorelinesCheckBoxStateChange)
        self.paleoshorelinesMask = self.addAdvancedParameter(TaVectorLayerComboBox,
                                                             label="Rotated paleoshorelines:",
                                                             widget_type="TaMapLayerComboBox",
                                                             variant_index="Smooth raster",
                                                             param_id="paleoshorelinesMask")
        self.paleoshorelinesMask.setLayerType("Polygon")
        self.fixedPaleoShorelinesCheckBox.registerEnabledWidgets(
            [self.paleoshorelinesMask])

        # Parameters for Isostatic compensation
        self.selectIceTopoBox = self.addVariantParameter(TaRasterLayerComboBox,
                                                         "Isostatic compensation",
                                                         "Ice topography raster:",
                                                         mandatory=True,
                                                         param_id="selectIceTopoBox")
        self.isostatMaskBox = self.addAdvancedParameter(TaVectorLayerComboBox,
                                                        label="Mask layer:",
                                                        widget_type="TaMapLayerComboBox",
                                                        variant_index="Isostatic compensation",
                                                        param_id="isostatMaskBox")
        self.isostatMaskSelectedFeaturesCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                             label="Selected features only",
                                                                             variant_index="Isostatic compensation",
                                                                             param_id="isostatMaskSelectedFeaturesCheckBox")
        self.isostatMaskSelectedFeaturesCheckBox.registerLinkedWidget(
            self.isostatMaskBox)

        self.masksFromCoastCheckBox = self.addAdvancedParameter(
            TaCheckBox,
            label="Get polar regions automatically.",
            variant_index="Isostatic compensation",
            param_id="masksFromCoastCheckBox")
        self.isostatMaskSelectedFeaturesCheckBox.registerEnabledWidgets(
            [self.masksFromCoastCheckBox], natural=True)

        self.iceAmountSpinBox = self.addVariantParameter(
            QgsSpinBox,
            variant_index="Isostatic compensation",
            label="Amount of the ice to be removed (in %)",
            param_id="iceAmountSpinBox"
        )
        self.iceAmountSpinBox.setMinimum(0)
        self.iceAmountSpinBox.setMaximum(100)
        self.iceAmountSpinBox.setValue(30)

        # Parameters for Setting sea level
        self.seaLevelShiftBox = self.addVariantParameter(QgsSpinBox,
                                                         variant_index="Set new sea level",
                                                         label="Amount of sea level shift (m):",
                                                         param_id="seaLevelShiftBox")
        self.seaLevelShiftBox.setMinimum(-1000)
        self.seaLevelShiftBox.setMaximum(1000)
        self.seaLevelShiftBox.setValue(100)

        # Parameters for calculating bathymetry from ocean age
        self.ageRasterTime = self.addVariantParameter(QgsSpinBox,
                                                      variant_index="Calculate bathymetry",
                                                      label="Time of the age raster:",
                                                      param_id="ageRasterTime")
        self.ageRasterTime.setValue(0)
        self.reconstructionTime = self.addVariantParameter(QgsSpinBox,
                                                           variant_index="Calculate bathymetry",
                                                           label="Reconstruction time:",
                                                           param_id="reconstructionTime")

        # Parameters for changing map symbology
        self.colorPalette = self.addVariantParameter(TaColorSchemeWidget,
                                                     variant_index="Change map symbology",
                                                     label="Color palette:",
                                                     param_id="colorPalette")
        self.addColorPaletteButton = self.addVariantParameter(QPushButton,
                                                              variant_index="Change map symbology",
                                                              label="Add custom color palette",
                                                              param_id="addColorPaletteButton")
        self.addColorPaletteButton.pressed.connect(self.addColorPalette)

        self.fillDialog()
        self.showVariantWidgets(self.processingTypeBox.currentText())
        self.processingTypeBox.currentTextChanged.connect(
            self.showVariantWidgets)
        self.group_box.collapsedStateChanged.connect(
            lambda: self.showAdvancedWidgets(self.processingTypeBox.currentText()))

    def setFieldsInLayer(self):
        self.smFactorSpinBox2.initOverrideButton("Smoothing factor", "Smoothing factor for each mask",
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

    def addColorPalette(self) -> bool:
        """Adds a custom color palette to TA resources folder and to displays its name in the color palettes' combobox.

        :return: True if added successfully, otherwise False.
        :rtype: bool.
        """
        fd = QFileDialog()
        filter = "Color palette files (*.cpt)"
        fname, _ = fd.getOpenFileName(
            caption='Select color palette', directory=None, filter=filter)
        if fname:
            ext = os.path.splitext(fname)[1]
        else:
            return False
        if ext != '.cpt':
            return False

        color_lines = []
        comment_lines = []
        bottom_lines = []
        color_model = None
        with open(fname) as file:
            lines = file.readlines()
            color_scheme_name = lines[0].strip()
            color_scheme_name = color_scheme_name.replace("#", "")
            for line_no, line in enumerate(lines):
                new_line = line.strip()
                if new_line and not any([new_line[0] == '#',
                                         new_line[0] == 'B',
                                         new_line[0] == 'F',
                                         new_line[0] == 'N']):
                    new_line = new_line.split()
                    new_line = [i for i in new_line if i]
                    color_lines.append(new_line)
                elif new_line and new_line[0] == '#':
                    if "COLOR_MODEL" in new_line:
                        color_model = new_line.split('=')[1].strip()
                    comment_lines.append(new_line)
                elif new_line and any([
                        new_line[0] == 'B',
                        new_line[0] == 'F',
                        new_line[0] == 'N']):
                    bottom_lines.append(new_line)
        if color_model == 'HSV':
            self.msgBar.pushWarning("Warning:",
                                    "The selected color palette has an HSV color model, which is currently not supported.")
            return False

        if len(color_lines[0]) > 4:
            new_color_lines = []
            for line in color_lines:
                new_line = []
                new_line.append(line[0])
                new_line.append(str(line[1])+'/'+str(line[2])+'/'+str(line[3]))
                new_line.append(line[4])
                new_line.append(str(line[5])+'/'+str(line[6])+'/'+str(line[7]))
                new_color_lines.append(new_line)
            color_lines = new_color_lines

            new_file_name = os.path.join(self.colorPalette.path_to_color_schemes,
                                         os.path.basename(fname))
            with open(new_file_name, mode='w') as f:
                for line in comment_lines:
                    f.write(line)
                    f.write("\n")
                for line in color_lines:
                    for no, i in enumerate(line):
                        f.write(i)
                        if not no == len(line):
                            f.write("\t")
                    f.write("\n")
                for no, line in enumerate(bottom_lines):
                    f.write(line)
                    if not no == len(bottom_lines):
                        f.write("\n")

        else:
            try:
                shutil.copy(fname, self.colorPalette.path_to_color_schemes)
            except Exception as e:
                return False

        if self.colorPalette.findText(color_scheme_name) == -1:
            self.colorPalette.addItem(color_scheme_name)
        else:
            self.msgBar.pushWarning("Warning:",
                                    "A color palette with this name is already added.")
        self.colorPalette.setCurrentText(color_scheme_name)
        return True

    def reloadHelp(self):
        """
        Sets the name of the chosen processing algorithm (e.g. Smooth raster) to the dialog so that it can load the help
        file properly."""
        processing_alg_names = [("Fill gaps", "TaFillGaps"),
                                ("Copy/Paste raster", "TaCopyPasteRaster"),
                                ("Smooth raster", "TaSmoothRaster"),
                                ("Isostatic compensation",
                                 "TaIsostaticCompensation"),
                                ("Set new sea level", "TaSetSeaLevel"),
                                ("Calculate bathymetry", "TaCalculateBathymetry"),
                                ("Change map symbology", "TaChangeMapSymbology")]
        for alg, name in processing_alg_names:
            if self.processingTypeBox.currentText() == alg:
                self.setDialogName(name)
        if self.processingTypeBox.currentText() == "Change map symbology":
            self.outputPath.hide()
            self.outputPathLabel.hide()
        else:
            self.outputPath.show()
            self.outputPathLabel.show()
        self.loadHelp()
