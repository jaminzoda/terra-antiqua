#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - Python built-ins abs, bool, max, min, pow and round restored after "from numpy import *",
#    because NumPy 2 (bundled with QGIS 4) would otherwise replace them
#  - Raster files are deleted with compat.delete_raster_file, so a failed deletion
#    (Windows "Permission denied") no longer stops the tool
#  - modifyWithFormula: formula check uses core/expressions.evaluate instead of eval()
#  See core/compat.py for the note on how this port was made.

import os
from osgeo import (
    gdal,
    osr
)

from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    NULL,
    QgsExpressionContext,
    QgsExpressionContextUtils
)
import shutil

import numpy as np
from numpy import * #This is to import math functions to use in formula
# NumPy 2.x (bundled with QGIS 4) also exports abs, bool, max, min, pow and round, which would
# replace Python's built-ins in this module. Restore them so behaviour matches NumPy 1.x.
from builtins import abs, bool, max, min, pow, round  # noqa: E402,F811  # [QGIS4 port]

from .utils import (
     vectorToRaster,
     modFormula,
     modRescale,
     polygonOverlapCheck
     )
from .base_algorithm import TaBaseAlgorithm
from .compat import delete_raster_file  # [QGIS4 port]
from .expressions import evaluate  # [QGIS4 port]


class TaModifyTopoBathy(TaBaseAlgorithm):


    def __init__(self, dlg):
        super().__init__(dlg)
        self.vlayer = None
        self.topo = None
        self.fields = None
        self.features = None
        self.feats_count = None
        self.geotransform = None
        self.ncols = None
        self.nrows = None
        self.path = None
        self.out_file = None
        self.context = None

    def getParameters(self):
        self.feedback.info('The processing algorithm has started.')

        # Get the topography as an array
        self.feedback.info('Getting the raster layer')
        topo_layer = self.dlg.baseTopoBox.currentLayer()
        topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
        self.topo = topo_ds.GetRasterBand(1).ReadAsArray()
        self.geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
        self.nrows, self.ncols = np.shape(self.topo)

        if self.topo is not None:
            self.feedback.info('Size of the Topography raster: {}'.format(self.topo.shape))
        else:
            self.feedback.info('There is a problem with reading the Topography raster')

        # Get the vector masks
        self.feedback.info('Getting the vector layer')
        self.vlayer = self.dlg.masksBox.currentLayer()

        if self.vlayer.isValid():
            self.feedback.info('The mask layer is loaded properly')
        else:
            self.feedback.error('There is a problem with the mask layer - not loaded properly')
            self.kill()
        if not self.killed:
            self.fields = self.vlayer.fields().toList()

            #Check if the input layer contains overlapping features
            if self.dlg.selectedFeaturesBox.isChecked():
                overlaps = polygonOverlapCheck(self.vlayer, selected_only=True,
                                               feedback=self.feedback,
                                               run_time=10)
            else:
                overlaps = polygonOverlapCheck(self.vlayer, selected_only=False,
                                               feedback=self.feedback,
                                               run_time=10)
            if overlaps>0:
                self.feedback.warning("Some polygons in the input vector layer overlap each other")
                self.feedback.warning("The topography of overlapping areas\
                                      will be modified multiple times.")
        if not self.killed:
            if self.dlg.selectedFeaturesBox.isChecked():
                self.features = self.vlayer.getSelectedFeatures()
                self.feats_count = self.vlayer.selectedFeatureCount()
                if self.feats_count == 0:
                    self.feedback.error("You did not select any feature.")
                    self.kill()
            else:
                self.features = self.vlayer.getFeatures()
                self.feats_count = self.vlayer.featureCount()
                if self.feats_count ==0:
                    self.feedback.error("The layer you selected as an input\
                                        layer is empty.")
                    self.kill()

            self.context = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.vlayer))
            return True
        else:
            return False

    def run(self):
        if not self.killed:
            retrieved = self.getParameters()
            if retrieved:
                # Check if the formula mode of topography modification is checked
                # Otherwise minimum and maximum values will be used to calculate the formula
                mode = self.dlg.modificationModeComboBox.currentText()
                if mode == 'Modify with formula':
                    modified_array, ok = self.modifyWithFormula(80)
                else:
                    modified_array, ok = self.modifyWithMinAndMax(80)


        if not self.killed:
            if ok:
                # Write the resulting raster array to a raster file
                driver = gdal.GetDriverByName('GTiff')
                delete_raster_file(self.out_file_path, self.feedback)  # [QGIS4 port]

                raster = driver.Create(self.out_file_path, self.ncols, self.nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(self.geotransform)
                raster.SetProjection(self.crs.toWkt())
                raster.GetRasterBand(1).WriteArray(modified_array)
                raster = None
                self.finished.emit(True, self.out_file_path)
                self.feedback.progress = 100

            else:
                self.feedback.error("The plugin did not succeed because one or more parameters were set incorrectly.")
                self.feedback.error("Please, check the log above.")
                self.finished.emit(False, "")
        else:
            self.finished.emit(False, "")

    def modifyWithFormula(self, run_time = None):
        if run_time:
            total = run_time
        else:
            total = 100
        mask_number = 0

        H = self.topo
        for feat in self.features:
            if self.killed:
                break
            mask_number += 1
            self.context.setFeature(feat)
            formula, ok = self.dlg.formulaField.overrideButton.toProperty().value(self.context)
            if not ok:
                formula = self.dlg.formulaField.lineEdit.value()

            # Check if the formula field contains the formula
            if formula == NULL or ('H' in formula) is False:
                self.feedback.warning("Mask {} does not contain any formula.".format(mask_number))
                self.feedback.warning("You might want to check if the field\
                                   for formula is specified correctly in the plugin dialog.")
                continue
            else:
                try:
                    evaluate(formula, {"H": H})  # [QGIS4 port]
                except Exception as e:
                    self.feedback.warning(f"Formula for mask {mask_number} \
                                          is invalid: {formula}.")
                    self.feedback.debug(f"Raised exception: {e}.")
                    continue
                self.feedback.debug("Formula for mask number {} is:\
                                    {}".format(mask_number, formula))

            if self.dlg.min_maxValueCheckBox.isChecked():
                min_value, ok = self.dlg.minValueSpin.overrideButton.toProperty().value(self.context)
                if not ok and not self.dlg.maxValueSpin.spinBox.value() - self.dlg.minValueSpin.spinBox.value()==0:
                    min_value = self.dlg.minValueSpin.spinBox.value()
                else:
                    min_value = None
                max_value, ok = self.dlg.maxValueSpin.overrideButton.toProperty().value(self.context)
                if not ok and not self.dlg.maxValueSpin.spinBox.value() - self.dlg.minValueSpin.spinBox.value()==0:
                    max_value = self.dlg.maxValueSpin.spinBox.value()
                else:
                    max_value = None
            else:
                min_value = None
                max_value = None

            # Create a temporary layer to store the extracted masks
            temp_layer = QgsVectorLayer(f'Polygon?crs={self.crs.authid()}', 'extracted_masks', 'memory')
            temp_dp = temp_layer.dataProvider()
            temp_dp.addAttributes(self.fields)
            temp_layer.updateFields()

            temp_dp.addFeature(feat)
            temp_dp = None


            if not self.killed:
                # Rasterize extracted masks
                r_masks = vectorToRaster(
                    temp_layer,
                    self.geotransform,
                    self.ncols,
                    self.nrows,
                    field_to_burn=None,
                    no_data=0
                    )
                v_layer = None

                # Modify the topography
                in_array = H[r_masks == 1]
                H[r_masks == 1] = modFormula(in_array, formula, min_value, max_value)

            # Send progress feedback
            self.feedback.progress += total/ self.feats_count
        if 'H' in locals():
            return (H, True)
        else:
            return (None, False)

    def modifyWithMinAndMax(self, run_time = None):
        if run_time:
            total = run_time
        else:
            total = 100
        mask_number = 0
        H = self.topo
        for feat in self.features:
            if self.killed:
                break
            mask_number += 1
            self.context.setFeature(feat)
            fmin, ok = self.dlg.newMinValueSpin.overrideButton.toProperty().value(self.context)
            if not ok:
                fmin = self.dlg.newMinValueSpin.spinBox.value()
            fmax, ok = self.dlg.newMaxValueSpin.overrideButton.toProperty().value(self.context)
            if not ok:
                fmax = self.dlg.newMaxValueSpin.spinBox.value()

            # Check if the min and max fields contain any value
            if fmin == NULL or fmax == NULL:
                self.feedback.warning("Mask {} does not contain final\
                                      maximum or/and minimum values \
                                      specified in the attributes table.". format(mask_number))
                self.feedback.warning("You might want to check if the fields for minimum and "
                              "maximum values are specified correctly in the plugin dialog.")
                continue

            # Create a temporary layer to store the extracted masks
            temp_layer = QgsVectorLayer(f'Polygon?crs={self.crs.authid()}', 'extracted_masks', 'memory')
            temp_dp = temp_layer.dataProvider()
            temp_dp.addAttributes(self.fields)
            temp_layer.updateFields()

            temp_dp.addFeature(feat)
            temp_dp = None


            # Rasterize extracted masks
            r_masks = vectorToRaster(
                temp_layer,
                self.geotransform,
                self.ncols,
                self.nrows,
                field_to_burn=None,
                no_data=0
                )
            v_layer = None

            # Modify the topography
            in_array = H[r_masks == 1]
            H[r_masks == 1] = modRescale(in_array, fmin, fmax)

            # Send progress feedback
            self.feedback.progress += total/ self.feats_count

        if 'H' in locals():
            return (H, True)
        else:
            return (None, False)


