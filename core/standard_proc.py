import os
from osgeo import gdal

from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsExpression,
    QgsFeatureRequest
    )
import shutil

import numpy as np


from.utils import (
    vectorToRaster,
    fillNoData,
    fillNoDataInPolygon,
    TaProgressImitation
    )
from .utils import rasterSmoothing
from .base_algorithm import TaBaseAlgorithm


class TaStandardProcessing(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)

    def getParameters(self):
        self.processing_type = self.dlg.fillingTypeBox.currentText()

        processing_alg_names = [("Fill gaps", "TaFillGaps"),
                                ("Copy/Paste raster", "TaCopyPasteRaster"),
                                ("Smooth raster", "TaSmoothRaster"),
                                ("Isostatic compensation", "TaIsostaticCompensation"),
                                ("Set new sea level", "TaSetSeaLevel"),
                                ("Calculate bathymetry", "TaCalculateBathymetry")]
        for alg, name in processing_alg_names:
            if alg == self.processing_type:
                self.setName(name)

    def run(self):
        self.getParameters()
        if self.processing_type == "Fill gaps":
            self.fillGaps()
        elif self.processing_type == "Copy/Paste raster":
            self.copyPasteRaster()
        elif self.processing_type == "Smooth raster":
            self.smoothRaster()
        elif self.processing_type == "Isostatic compensation":
            self.isostaticCompensation()
        elif self.processing_type == "Set new sea level":
            self.setSeaLevel()
        elif self.processing_type == "Calculate bathymetry":
            self.calculateBathymetry()





    def fillGaps(self):
        if not self.killed:
            base_raster_layer = self.dlg.baseTopoBox.currentLayer()
            self.feedback.info("Filling the gaps in {}".format(base_raster_layer.name()))
            self.feedback.info("Inverse Distance Weighting Interpolation method is used.")
            if self.dlg.interpInsidePolygonCheckBox.isChecked():
                mask_layer = self.dlg.masksBox.currentLayer()
                interpolated_raster = fillNoDataInPolygon(base_raster_layer, mask_layer, self.out_file_path)
            else:
                interpolated_raster = fillNoData(base_raster_layer, self.out_file_path)
            self.feedback.info("Interpolation finished.")

            if self.dlg.smoothingBox.isChecked():
                self.feedback.progress+= 20
            else:
                self.feedback.progress+= 40


        if not self.killed:

            if self.dlg.smoothingBox.isChecked():
                self.feedback.info("Smoothing the interpolated raster.")
                # Get the layer for smoothing
                interpolated_raster_layer = QgsRasterLayer(interpolated_raster, 'Interpolated DEM', 'gdal')

                # Get smoothing factor
                sm_factor = self.dlg.smFactorSpinBox.value()
                sm_type = self.dlg.smoothingTypeBox.currentText()

                # Smooth the raster
                rasterSmoothing(interpolated_raster_layer, sm_type, sm_factor, feedback=self.feedback,
                                runtime_percentage=68)

                self.feedback.info("Smoothing has finished.")


                self.feedback.progress= 100
                self.finished.emit(True, self.out_file_path)

            else:
                self.feedback.progress= 100
                self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")



    def copyPasteRaster(self):
        if not self.killed:
            # Get a raster layer to copy the elevation values FROM
            from_raster_layer = self.dlg.copyFromRasterBox.currentLayer()
            from_raster = gdal.Open(from_raster_layer.dataProvider().dataSourceUri())
            from_array = from_raster.GetRasterBand(1).ReadAsArray()
        if not self.killed:
            # Get a raster layer to copy the elevation values TO
            to_raster_layer = self.dlg.baseTopoBox.currentLayer()
            to_raster = gdal.Open(to_raster_layer.dataProvider().dataSourceUri())
            to_array = to_raster.GetRasterBand(1).ReadAsArray()
        self.feedback.progress +=20

        if not self.killed:
            self.feedback.info("Copying elevation/bathymetry values from {0} to {1}.".format(from_raster_layer.name(),
                                                                                             to_raster_layer.name()))
        if not self.killed:
            # Get a vector containing masks
            mask_vector_layer = self.dlg.copyFromMaskBox.currentLayer()
            self.feedback.info("{} layer is used for masking the pixels to be copied.".format(mask_vector_layer.name()))

            self.feedback.info("Rasterizing the masks from the vector layer.")
            # Rasterize masks
            geotransform = to_raster.GetGeoTransform()
            nrows, ncols = to_array.shape
            mask_array = vectorToRaster(
                mask_vector_layer,
                geotransform,
                ncols,
                nrows,
                field_to_burn=None,
                no_data=0
                )

            self.feedback.info("The masks are rasterized.")
            self.feedback.progress += 40
        if not self.killed:
            self.feedback.info("Copying the elevation values.")
            # Fill the raster
            to_array[mask_array == 1] = from_array[mask_array == 1]
            self.feedback.progress+= 20

        if not self.killed:
            self.feedback.info("Saving the resulting raster.")
            # Create a new raster for the result
            output_raster = gdal.GetDriverByName('GTiff').Create(self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
            output_raster.SetGeoTransform(geotransform)
            crs = to_raster_layer.crs()
            output_raster.SetProjection(crs.toWkt())
            output_band = output_raster.GetRasterBand(1)
            output_band.SetNoDataValue(np.nan)
            output_band.WriteArray(to_array)
            output_band.FlushCache()
            output_raster = None

            self.feedback.progress= 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")


    def smoothRaster(self):
        if not self.killed:
            raster_to_smooth_layer = self.dlg.baseTopoBox.currentLayer()
            self.feedback.info("Smoothing toporaphy in the {} raster layer.".format(raster_to_smooth_layer))
            smoothing_factor = self.dlg.smFactorSpinBox2.value()
            smoothing_type = self.dlg.smoothingTypeBox.currentText()
            self.feedback.info("Using {} for smoothing the elevation/bathymetry values.".format(smoothing_type))
            self.feedback.info("Smoothing factor: {}.".format(smoothing_factor))

        if not self.killed:
            try:
                smoothed_raster_layer = rasterSmoothing(raster_to_smooth_layer, smoothing_type, smoothing_factor,
                                                        out_file=self.out_file_path, feedback = self.feedback)
            except Exception as e:
                self.feedback.warning(e)

            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def isostaticCompensation(self):
            self.feedback.info("Correcting topography for ice load in Greenland and Antarctic...")
            # Get the bedrock topography raster
            if not self.killed:
                try:
                    topo_br_layer = self.dlg.baseTopoBox.currentLayer()
                    topo_br_ds = gdal.Open(topo_br_layer.dataProvider().dataSourceUri())
                    topo_br_data = topo_br_ds.GetRasterBand(1).ReadAsArray()
                    assert topo_br_layer, "The Berock topography raster layer is not loaded properly."
                    assert topo_br_layer.isValid(), "The Bedrock topography raster layer is not valid."
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()

                if not self.killed:
                    self.feedback.info("Bedrock topography raster layer: {}.".format(topo_br_layer.name()))
                    self.feedback.progress += 5

            if not self.killed:
                # Get the ice surface topography raster
                try:
                    topo_ice_layer = self.dlg.selectIceTopoBox.currentLayer()
                    topo_ice_ds = gdal.Open(topo_ice_layer.dataProvider().dataSourceUri())
                    topo_ice_data = topo_ice_ds.GetRasterBand(1).ReadAsArray()
                    assert topo_ice_layer, "The Ice topography raster layer is not loaded properly."
                    assert topo_ice_layer.isValid(), "The Ice topography raster layer is not valid."
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()

                if not self.killed:
                    self.feedback.info("Ice topography raster layer: {}.".format(topo_ice_layer.name()))
                    self.feedback.progress += 5

            if not self.killed:
                # Get the masks
                try:
                    vlayer = self.dlg.isostatMaskBox.currentLayer()
                    assert vlayer is not None, "The Mask vector layer is not loaded properly."
                    assert vlayer.isValid(), "The Mask vector layer is not valid."
                    assert vlayer.featureCount() >0, "The selected mask vector layer is empty."
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()

                if not self.killed:
                    self.feedback.info("Mask vector layer: {}.".format(vlayer.name()))
                    self.feedback.progress += 5

            if self.dlg.masksFromCoastCheckBox.isChecked():
                if not self.killed:
                    self.feedback.info("Retrieving the masks with the following names (case insensitive): ")
                    for i in [ "<i>Greeanland",
                                  "<i>Antarctic (Including East Antarctic and Antarctic peninsula)",
                                  "<i>Matie Byrd Land",
                                  "<i>Ronne Ice Shelf",
                                  "<i>Thurston Island",
                                  "<i>Admundsen Terrane."
                              ]:
                        self.feedback.info(i)
                    # Get features from the masks layer
                    try:
                        expr = QgsExpression(
                            "lower(\"NAME\") LIKE '%greenland%' OR lower(\"NAME\") LIKE '%antarctic%' OR lower(\"NAME\") LIKE '%marie byrd%' OR lower(\"NAME\") LIKE '%ronne ice%' OR lower(\"NAME\") LIKE '%thurston%' OR lower(\"NAME\") LIKE '%admundsen%'")

                        features = vlayer.getFeatures(QgsFeatureRequest(expr))
                        assert any(True for _ in features), "No features with the above names are found in the input mask layer"
                        temp_layer = QgsVectorLayer('Polygon?crs=epsg:4326', 'extracted_masks', 'memory')
                        temp_prov = temp_layer.dataProvider()
                        temp_prov.addFeatures(features)

                        self.feedback.progress += 5

                        if not self.killed:

                            path = os.path.join(os.path.dirname(self.out_file_path), 'vector_masks')
                            self.feedback.info(
                                "Creating a temporary folder to save extracted masks for rasterization at: {}.".format(path))
                            if not os.path.exists(path):
                                try:
                                    os.mkdir(path)
                                except OSError:
                                    self.feedback.error("Creation of the directory %s failed" % path)
                                else:
                                    self.feedback.info("Successfully created the directory %s " % path)

                            out_file = os.path.join(path, 'isostat_comp_masks.shp')
                            self.feedback.warning(
                                "The shapefile {} already exists in the {} folder, therefore it will be deleted.".format(out_file,
                                                                                                                       path))
                            if os.path.exists(out_file):
                                # function deleteShapeFile return bool True iif deleted False if not
                                deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
                                if deleted:
                                    self.feedback.info(out_file + "has been deleted.")
                                else:
                                    self.feedback.warning(out_file + "is not deleted.")

                            self.feedback.progress += 5

                            error = QgsVectorFileWriter.writeAsVectorFormat(temp_layer, out_file, "UTF-8", vlayer.crs(),
                                                                            "ESRI Shapefile")
                            if error[0] == QgsVectorFileWriter.NoError:
                                self.feedback.info(
                                    "The  {} shapefile is created successfully.".format(os.path.basename(out_file)))
                            else:
                                self.feedback.warning(
                                    "Failed to create the {} shapefile because {}.".format(
                                        os.path.basename(out_file), error[1]))

                            v_layer = QgsVectorLayer(out_file, 'extracted_masks', 'ogr')
                            self.feedback.progress += 5
                    except AssertionError as e:
                        self.feedback.warning(e)
                        self.feedback.warning(
                            "All the polygons inside the input mask layer will be used for topography correction.")
                        v_layer = vlayer

                if not self.killed:
                    self.feedback.info("Rasterizing exrtacted masks.")
                    # Rasterize extracted masks
                    geotransform = topo_br_ds.GetGeoTransform()
                    nrows, ncols = np.shape(topo_br_data)
                    r_masks = vectorToRaster(
                        v_layer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                        )

                    self.feedback.progress += 10

                    # Close  the temporary vector layer
                    v_layer = None

                    # Remove the shapefile of the temporary vector layer from the disk. Also remove the temporary folder created for it.
                    try:
                        if os.path.exists(out_file):
                            deleted = QgsVectorFileWriter.deleteShapeFile(out_file)
                            if deleted:
                                if os.path.exists(path):
                                    shutil.rmtree(path)
                                else:
                                    self.feedback.warning('Created a temporary folder with a shapefile at: ' + os.path.join(path))
                                    self.feedback.warning('But could not delete it. You may need delete it manually.')
                    except UnboundLocalError:
                        pass

                    self.feedback.progress += 5

            else:
                if not self.killed:
                    geotransform = topo_br_ds.GetGeoTransform()
                    nrows, ncols = np.shape(topo_br_data)
                    self.feedback.info("Rasterizing the masks.")
                    r_masks = vectorToRaster(
                        vlayer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                        )

                    self.feedback.progress += 30
            if not self.killed:
                # Compensate for ice load
                self.feedback.info("Compensating for ice load.")
                rem_amount = self.dlg.iceAmountSpinBox.value()  # the amount of ice that needs to be removed.
                comp_factor = 0.3 * (topo_ice_data[r_masks == 1] - topo_br_data[r_masks == 1]) * rem_amount / 100
                comp_factor[np.isnan(comp_factor)] = 0
                comp_factor[comp_factor < 0] = 0
                topo_br_data[r_masks == 1] = topo_br_data[r_masks == 1] + comp_factor
                self.feedback.progress += 30
            if not self.killed:
                # Create a new raster for the result
                self.feedback.info("Saving the resulting layer.")
                output_raster = gdal.GetDriverByName('GTiff').Create(self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                output_raster.SetGeoTransform(geotransform)
                crs = topo_br_layer.crs()
                output_raster.SetProjection(crs.toWkt())
                output_band = output_raster.GetRasterBand(1)
                output_band.SetNoDataValue(np.nan)
                output_band.WriteArray(topo_br_data)
                output_band.FlushCache()
                output_raster = None

                self.feedback.progress = 100
                self.finished.emit(True, self.out_file_path)
            else:
                self.finished.emit(False, "")
    def setSeaLevel(self):
        progress = TaProgressImitation(100,100, self, self.feedback)
        progress.start()
        if not self.killed:
            topo_layer = self.dlg.baseTopoBox.currentLayer()
            shiftAmount = self.dlg.seaLevelShiftBox.value()
            self.feedback.info("Setting new sea level...")
            self.feedback.info("The sea level will be "
                               f"{'raised' if shiftAmount>=0 else 'lowered'}"
                               f" by  {np.abs(shiftAmount)} meters.")
            try:
                topo_ds = gdal.Open(topo_layer.source())
                input_topo_array = topo_ds.GetRasterBand(1).ReadAsArray()
            except Exception as e:
                self.feedback.error(f"Could not load the input raster layer {topo_layer.name()} properly.")
                self.feedback.error(f"Following error occured: {e}.")
                self.kill()
        if not self.killed:
            try:
                modified_topo_array = np.empty(input_topo_array.shape)
                modified_topo_array[:] = np.nan
                modified_topo_array[np.isfinite(input_topo_array)] = input_topo_array[np.isfinite(input_topo_array)] - shiftAmount
            except Exception as e:
                self.feedback.warning(e)
        if not self.killed:
            nrows, ncols = input_topo_array.shape
            geotransform = topo_ds.GetGeoTransform()

            try:
                raster = gdal.GetDriverByName('GTiff').Create(self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(geotransform)
                raster.SetProjection(topo_layer.crs().toWkt())
                raster.GetRasterBand(1).WriteArray(modified_topo_array)
                raster.GetRasterBand(1).SetNoDataValue(np.nan)
                raster = None
            except Exception as e:
                self.feedback.error("Could not write the result to the output file.")
                self.feedback.error(f"Following error occured: {e}.")
                self.kill()

        if not self.killed:
            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, '')

    def calculateBathymetry(self):
        """Calculates ocean depth from its age."""
        if not self.killed:
            age_layer = self.dlg.baseTopoBox.currentLayer()

            age_raster = gdal.Open(age_layer.dataProvider().dataSourceUri())
            ocean_age = age_raster.GetRasterBand(1).ReadAsArray()
            reconstruction_time = self.dlg.reconstructionTime.value()
            self.feedback.info("Calculating ocean depth from its age.")
            self.feedback.info(f"Input layer: {age_layer.name()}.")
            self.feedback.info(f"Reconstruction time: {reconstruction_time} Ma.")
            self.feedback.progress +=10

        if not self.killed:
            # create an empty array to store calculated ocean depth from age.
            ocean_depth = np.empty(ocean_age.shape)
            ocean_depth[:] = np.nan
            # calculate ocean age
            ocean_age[ocean_age > 0] = ocean_age[ocean_age > 0] - reconstruction_time
            ocean_depth[ocean_age > 0] = -2620 - 330 * (np.sqrt(ocean_age[ocean_age > 0]))
            ocean_depth[ocean_age > 90] = -5750
            self.feedback.progress +=50
        if not self.killed:
            nrows, ncols = ocean_depth.shape
            geotransform = age_raster.GetGeoTransform()

            try:
                raster = gdal.GetDriverByName('GTiff').Create(self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(geotransform)
                raster.SetProjection(age_layer.crs().toWkt())
                raster.GetRasterBand(1).WriteArray(ocean_depth)
                raster.GetRasterBand(1).SetNoDataValue(np.nan)
                raster.GetRasterBand(1).FlushCache()
                raster = None
                self.feedback.progress +=30
            except Exception as e:
                self.feedback.error("Could not write the result to the output file.")
                self.feedback.error(f"Following error occured: {e}.")
                self.kill()

        if not self.killed:
            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, '')
