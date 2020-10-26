from PyQt5.QtCore import (
    QThread,
    pyqtSignal
)
import os
from osgeo import (
    gdal,
    osr
)

try:
    from plugins import processing
except Exception:
    import processing

from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsExpression,
    NULL,
    QgsFeatureRequest,
    QgsExpressionContext,
    QgsExpressionContextUtils
)
import shutil
import tempfile

import numpy as np

from .utils import (
     vectorToRaster,
     modFormula,
     modMinMax,
     modRescale,
    polygonOverlapCheck
     )
from .base_algorithm import TaBaseAlgorithm


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
            self.path = self.createTemporaryFolder()
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

        self.cleanUp()

        if not self.killed:
            # Check if raster was modified. If the x matrix was assigned.
            if ok:
                # Write the resulting raster array to a raster file
                driver = gdal.GetDriverByName('GTiff')
                if os.path.exists(self.out_file_path):
                    driver.Delete(self.out_file_path)

                raster = driver.Create(self.out_file_path, self.ncols, self.nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(self.geotransform)
                crs = osr.SpatialReference()
                crs.ImportFromEPSG(4326)
                raster.SetProjection(crs.ExportToWkt())
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

        for feat in self.features:
            if self.killed:
                break
            mask_number += 1
            self.context.setFeature(feat)
            formula, ok = self.dlg.formulaField.overrideButton.toProperty().value(self.context)
            if not ok:
                formula = self.dlg.formulaField.lineEdit.value()

            # Check if the formula field contains the formula
            if formula == NULL or ('x' in formula) is False:
                self.feedback.warning("Mask {} does not contain any formula.".format(mask_number))
                self.feedback.warning("You might want to check if the field\
                                   for formula is specified correctly in the plugin dialog.")
                continue
            else:
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
            temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
            temp_dp = temp_layer.dataProvider()
            temp_dp.addAttributes(self.fields)
            temp_layer.updateFields()

            temp_dp.addFeature(feat)

            # Create a temporary shapefile to store extracted masks before rasterizing them
            self.out_file = os.path.join(self.path, 'masks_for_topo_modification.shp')

            if os.path.exists(self.out_file):
                deleted = QgsVectorFileWriter.deleteShapeFile(self.out_file)

            error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, self.out_file, "UTF-8",
                                                            temp_layer.crs(), "ESRI Shapefile")
            if error[0] == QgsVectorFileWriter.NoError:
                self.feedback.debug("The  {} shapefile is created\
                                    successfully.".format(os.path.basename(self.out_file)))
            else:
                self.feedback.error("Failed to create the {0} shapefile because\
                                    {1}.".format(os.path.basename(self.out_file), error[1]))
                self.kill()

            if not self.killed:
                # Rasterize extracted masks
                v_layer = QgsVectorLayer(self.out_file, 'extracted_masks', 'ogr')
                r_masks = vectorToRaster(
                    v_layer,
                    self.geotransform,
                    self.ncols,
                    self.nrows,
                    field_to_burn=None,
                    no_data=0
                    )
                v_layer = None

                # Modify the topography
                x = self.topo
                in_array = x[r_masks == 1]
                x[r_masks == 1] = modFormula(in_array, formula, min_value, max_value)

            # Send progress feedback
            self.feedback.progress += total/ self.feats_count
        if 'x' in locals():
            return (x, True)
        else:
            return (None, False)

    def modifyWithMinAndMax(self, run_time = None):
        if run_time:
            total = run_time
        else:
            total = 100
        mask_number = 0
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
            temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
            temp_dp = temp_layer.dataProvider()
            temp_dp.addAttributes(self.fields)
            temp_layer.updateFields()

            temp_dp.addFeature(feat)

            # Create a temporary shapefile to store extracted masks before rasterizing them
            self.out_file = os.path.join(self.path, 'masks_for_topo_modification.shp')

            if os.path.exists(self.out_file):
                deleted = QgsVectorFileWriter.deleteShapeFile(self.out_file)
            error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer,
                                                            self.out_file, "UTF-8",
                                                            temp_layer.crs(), "ESRI Shapefile")
            if error[0] == QgsVectorFileWriter.NoError:
                self.feedback.debug(
                    "The  {} shapefile is created\
                    successfully.".format(os.path.basename(self.out_file)))
            else:
                self.feedback.error(
                    "Failed to create the {0} shapefile because\
                    {1}.".format(os.path.basename(self.out_file), error[1]))
                self.kill()

            # Rasterize extracted masks
            v_layer = QgsVectorLayer(self.out_file, 'extracted_masks', 'ogr')
            r_masks = vectorToRaster(
                v_layer,
                self.geotransform,
                self.ncols,
                self.nrows,
                field_to_burn=None,
                no_data=0
                )
            v_layer = None

            # Modify the topography
            x = self.topo
            in_array = x[r_masks == 1]
            x[r_masks == 1] = modRescale(in_array, fmin, fmax)

            # Send progress feedback
            self.feedback.progress += total/ self.feats_count

        if 'x' in locals():
            return (x, True)
        else:
            return (None, False)

    def createTemporaryFolder(self):
        if not self.killed:
            # Create a directory for temporary vector files
            path = os.path.join(os.path.dirname(self.out_file_path), "vector_masks")
            if not os.path.exists(path):
                try:
                    os.mkdir(path)
                except OSError:
                    self.feedback.error("Creation of the directory {}\
                                       failed".format(path))
                    return None
                else:
                    self.feedback.info("Successfully created the  directory\
                                       {}".format(path))
                    return path
            else:
                self.feedback.info("The folder vector_masks is already created.")
                return path

    def cleanUp(self):
        # Delete temporary files and folders
        self.feedback.info('Trying to delete the temporary files and folders.')

        try:
            if os.path.exists(self.out_file):
                deleted = QgsVectorFileWriter.deleteShapeFile(self.out_file)
                if deleted:
                    self.feedback.info(
                        "The {} shapefile is deleted\
                        successfully.".format(os.path.basename(self.out_file)))
                else:
                    self.feedback.warning("The {} shapefile is NOT\
                                          deleted.".format(os.path.basename(self.out_file)))
        except Exception:
            pass
        try:
            if os.path.exists(self.path):
                try:
                    shutil.rmtree(self.path)
                except OSError:
                    self.feedback.warning("The directory {} is not\
                                       deleted.".format(self.path))
                else:
                    self.feedback.info("The directory {} is successfully\
                                       deleted".format(self.path))
        except:
            pass

