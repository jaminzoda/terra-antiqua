# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

from .base_algorithm import TaBaseAlgorithm
from .utils import rasterSmoothing, rasterSmoothingInPolygon
import os
from osgeo import gdal, gdalconst

from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsExpression,
    QgsFeatureRequest,
    QgsProject,
    NULL
)
import shutil

import numpy as np


from.utils import (
    vectorToRaster,
    fillNoData,
    fillNoDataInPolygon,
    setRasterSymbology,
    TaProgressImitation,
    smoothArrayWithWrapping,
    polygonsToPolylines,
    modRescale,
    fillNoDataWithAFixedValue
)


class TaStandardProcessing(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)
        self.getParameters()
        self.dlg.dialog_name_changed.connect(self.getParameters)

    def getParameters(self):
        self.processing_type = self.dlg.processingTypeBox.currentText()

        processing_alg_names = [("Fill gaps", "TaFillGaps"),
                                ("Copy/Paste raster", "TaCopyPasteRaster"),
                                ("Smooth raster", "TaSmoothRaster"),
                                ("Isostatic compensation",
                                 "TaIsostaticCompensation"),
                                ("Set new sea level", "TaSetSeaLevel"),
                                ("Calculate bathymetry", "TaCalculateBathymetry"),
                                ("Change map symbology", "TaChangeMapSymbology")]
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
        elif self.processing_type == "Change map symbology":
            self.changeMapSymbology()

    def fillGaps(self):
        if not self.killed:
            base_raster_layer = self.dlg.baseTopoBox.currentLayer()
            self.feedback.info("Filling the gaps in {}".format(
                base_raster_layer.name()))
            if self.dlg.fillingTypeBox.currentText() == "Interpolation":
                self.feedback.info(
                    "Inverse Distance Weighting Interpolation method is used.")
                if all([self.dlg.interpInsidePolygonCheckBox.isChecked(),
                        self.dlg.masksBox.currentLayer()]):
                    mask_layer = self.dlg.masksBox.currentLayer()
                    interpolated_raster = fillNoDataInPolygon(
                        base_raster_layer, mask_layer, self.out_file_path)
                else:
                    interpolated_raster = fillNoData(
                        base_raster_layer, self.out_file_path)
                self.feedback.info("Interpolation finished.")
            elif self.dlg.fillingTypeBox.currentText() == "Fixed value":
                mask_layer = None
                value_to_fill = self.dlg.fillingValueSpinBox.value()
                if all([self.dlg.interpInsidePolygonCheckBox.isChecked(),
                        self.dlg.masksBox.currentLayer()]):
                    mask_layer = self.dlg.masksBox.currentLayer()
                try:
                    interpolated_raster = fillNoDataWithAFixedValue(base_raster_layer,
                                                                    value_to_fill,
                                                                    mask_layer,
                                                                    self.out_file_path
                                                                    )
                except Exception as e:
                    self.feedback.warning(
                        "Filling gaps failed due to the following error:")
                    self.feedback.warning(f"{e}")

            if self.dlg.smoothingBox.isChecked():
                self.feedback.progress += 20
            else:
                self.feedback.progress += 40

        if not self.killed:

            if self.dlg.smoothingBox.isChecked():
                self.feedback.info("Smoothing the interpolated raster.")
                # Get the layer for smoothing
                interpolated_raster_layer = QgsRasterLayer(
                    interpolated_raster, 'Interpolated DEM', 'gdal')

                # Get smoothing factor
                sm_factor = self.dlg.smFactorSpinBox.value()
                sm_type = self.dlg.smoothingTypeBox.currentText()

                # Smooth the raster
                if self.dlg.interpInsidePolygonCheckBox.isChecked():
                    rasterSmoothing(interpolated_raster_layer, sm_type, sm_factor, mask_layer, feedback=self.feedback,
                                    runtime_percentage=68)
                else:
                    rasterSmoothing(interpolated_raster_layer, sm_type, sm_factor, feedback=self.feedback,
                                    runtime_percentage=68)

                self.feedback.info("Smoothing has finished.")

                self.feedback.progress = 100
                self.finished.emit(True, self.out_file_path)

            else:
                self.feedback.progress = 100
                self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def copyPasteRaster(self):
        if not self.killed:
            # Get a raster layer to copy the elevation values FROM
            from_raster_layer = self.dlg.copyFromRasterBox.currentLayer()
            from_raster = gdal.Open(
                from_raster_layer.dataProvider().dataSourceUri())
            from_array = from_raster.GetRasterBand(1).ReadAsArray()
        if not self.killed:
            # Get a raster layer to copy the elevation values TO
            to_raster_layer = self.dlg.baseTopoBox.currentLayer()
            to_raster = gdal.Open(
                to_raster_layer.dataProvider().dataSourceUri())
            to_array = to_raster.GetRasterBand(1).ReadAsArray()
        self.feedback.progress += 20

        if not self.killed:
            self.feedback.info("Copying elevation/bathymetry values from {0} to {1}.".format(from_raster_layer.name(),
                                                                                             to_raster_layer.name()))
        if not self.killed:
            # Get a vector containing masks
            if self.dlg.copyPasteSelectedFeaturesOnlyCheckBox.isChecked():
                features = self.dlg.copyFromMaskBox.currentLayer().getSelectedFeatures()
                fields = self.dlg.copyFromMaskBox.currentLayer().fields().toList()
                layer_name = self.dlg.copyFromMaskBox.currentLayer().name()
                mask_vector_layer = QgsVectorLayer(
                    f"Polygon?crs={self.crs.authid()}", layer_name, "memory")
                mask_vector_layer.dataProvider().addAttributes(fields)
                mask_vector_layer.updateFields()
                mask_vector_layer.dataProvider().addFeatures(features)
            else:
                mask_vector_layer = self.dlg.copyFromMaskBox.currentLayer()

            self.feedback.info("{} layer is used for masking the pixels to be copied.".format(
                mask_vector_layer.name()))

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
            self.feedback.progress += 20

        if not self.killed:
            self.feedback.info("Saving the resulting raster.")
            # Create a new raster for the result
            output_raster = gdal.GetDriverByName('GTiff').Create(
                self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
            output_raster.SetGeoTransform(geotransform)
            output_raster.SetProjection(self.crs.toWkt())
            output_band = output_raster.GetRasterBand(1)
            output_band.SetNoDataValue(np.nan)
            output_band.WriteArray(to_array)
            output_band.FlushCache()
            output_raster = None

            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def smoothRaster(self):
        if not self.killed:
            raster_to_smooth_layer = self.dlg.baseTopoBox.currentLayer()
            raster_to_smooth_ds = gdal.Open(raster_to_smooth_layer.source())
            self.feedback.info(
                "Smoothing toporaphy in the {} raster layer.".format(raster_to_smooth_layer))
            smoothing_type = self.dlg.smoothingTypeBox2.currentText()
            self.feedback.info(
                "Using {} for smoothing the elevation/bathymetry values.".format(smoothing_type))

        if not self.killed:
            in_array = raster_to_smooth_ds.GetRasterBand(1).ReadAsArray()

            # Check if data contains NaN values. If it contains, interpolate values for them first
            # If the pixels with NaN values are left empty they will cause part of the smoothed raster to get empty.
            # Gaussian filter removes all values under the kernel, which contain at least one NaN ValueError
            nan_mask = np.zeros(in_array.shape)
            no_data_value = raster_to_smooth_ds.GetRasterBand(
                1).GetNoDataValue()
            # if the no_data_value is np.nan, band.GetNoDataValue returns nan,
            # which is !=np.nan but np.isnan(no_data_value) returns True
            if in_array[in_array == no_data_value].size == 0:
                in_array[np.isnan(in_array)] = np.nan
            else:
                in_array[in_array == no_data_value] = np.nan

            if np.isnan(in_array).any():
                nan_mask[np.isnan(in_array)] = 1
                filled_raster = fillNoData(raster_to_smooth_layer)
                raster_to_smooth_ds = gdal.Open(
                    filled_raster, gdalconst.GA_ReadOnly)
                in_array = raster_to_smooth_ds.GetRasterBand(1).ReadAsArray()

        if not self.killed:
            in_raster_extent = raster_to_smooth_layer.extent()
            xres = raster_to_smooth_layer.rasterUnitsPerPixelX()
            yres = raster_to_smooth_layer.rasterUnitsPerPixelY()
        if not self.killed:
            if self.dlg.smoothInPolygonCheckBox.isChecked():
                mask_layer = self.dlg.smoothingMaskBox.currentLayer()
                self.context = self.getExpressionContext(mask_layer)
                if self.dlg.smoothInSelectedFeaturesOnlyCheckBox.isChecked():
                    features = mask_layer.getSelectedFeatures()
                    progress_unit = 100/mask_layer.selectedFeatureCount()
                else:
                    features = mask_layer.getFeatures()
                    progress_unit = 100/mask_layer.featureCount()

                for feature in features:
                    if self.killed:
                        break
                    try:
                        self.feedback.info(
                            f"<b><i> Smoothing raster with \
                            {feature.attribute('name') if feature.attribute('name')!=NULL else 'NoName'}\
                            polygon")
                    except Exception as e:
                        self.feedback.info(
                            f"<b><i>Smoothing raster with polygon {feature.id()}")
                        self.feedback.debug(e)

                    # Set feature to context to be able to retrieve smoothing factor for each feature
                    self.context.setFeature(feature)

                    # Retrieve the smoothing factor for the feature
                    smoothing_factor, ok = self.dlg.smFactorSpinBox2.overrideButton.toProperty(
                    ).valueAsInt(self.context)
                    if not ok:
                        smoothing_factor = self.dlg.smFactorSpinBox2.spinBox.value()
                        self.feedback.warning(
                            f"Mask polygon {feature.id()} has no smoothing factor.")
                        self.feedback.warning(
                            "Therefore default smoothing value will be used.")
                    self.feedback.info(
                        f"Smoothing factor: {smoothing_factor}.")

                    # Define the area of the subset array
                    bounding_box = feature.geometry().boundingBox()
                    feat_xmin = bounding_box.xMinimum()
                    feat_xmax = bounding_box.xMaximum()
                    feat_ymin = bounding_box.yMinimum()
                    feat_ymax = bounding_box.yMaximum()
                    rl_xmin = in_raster_extent.xMinimum()
                    rl_xmax = in_raster_extent.xMaximum()
                    rl_ymin = in_raster_extent.yMinimum()
                    rl_ymax = in_raster_extent.yMaximum()

                    # Find the distances` between the edges of the raster layer and the extent of the mask polygon
                    if feat_xmin < rl_xmin:
                        xdistance = 0
                    else:
                        xdistance = np.sqrt(pow((feat_xmin - rl_xmin), 2))

                    if feat_ymax > rl_ymax:
                        ydistance = 0
                    else:
                        ydistance = np.sqrt(pow((feat_ymax - rl_ymax), 2))

                    # Column number for the upper left corner of the polygon mask extent
                    xoff = int(round(xdistance/xres))
                    # Row number for the upper left corner of the polygon mask extent
                    yoff = int(round(ydistance/yres))

                    # Check if the extent of the polygon mask does not go beyond the extent of the raster layer
                    # and calculate the size of the subset array to be smoothed (<=polygon extent size)
                    # TODO handle the negative values
                    if feat_xmax > rl_xmax and feat_xmin < rl_xmin:
                        win_xsize = round((rl_xmax-rl_xmin)/xres)
                    elif feat_xmax > rl_xmax and not feat_xmin < rl_xmin:
                        win_xsize = round((rl_xmax-feat_xmin)/xres)
                    elif not feat_xmax > rl_xmax and feat_xmin < rl_xmin:
                        win_xsize = int(
                            round(np.sqrt(pow((rl_xmin-feat_xmax), 2))/xres))
                    else:
                        win_xsize = round((feat_xmax-feat_xmin)/xres)

                    if feat_ymin < rl_ymin and feat_ymax > rl_ymax:
                        win_ysize = round((rl_ymax-rl_ymin)/yres)
                    elif feat_ymin < rl_ymin and not feat_ymax > rl_ymax:
                        win_ysize = round((feat_ymax-rl_ymin)/yres)
                    elif not feat_ymin < rl_ymin and feat_ymax > rl_ymax:
                        win_ysize = int(
                            round(np.sqrt(pow((feat_ymin-rl_ymax), 2))/yres))
                    else:
                        win_ysize = round((feat_ymax-feat_ymin)/yres)

                    # extend the subset array for smoothing pixel at its edges
                    if yoff-smoothing_factor >= 0:
                        yoff = yoff-smoothing_factor
                        win_ysize += smoothing_factor

                    if yoff+win_ysize+smoothing_factor <= in_array.shape[0]:
                        ymax = yoff+win_ysize+smoothing_factor
                        win_ysize += smoothing_factor
                    else:
                        ymax = yoff+win_ysize

                    if xoff-smoothing_factor >= 0:
                        xoff = xoff-smoothing_factor
                        win_xsize += smoothing_factor

                    if xoff+win_xsize+smoothing_factor <= in_array.shape[1]:
                        xmax = xoff+win_xsize+smoothing_factor
                        win_xsize += smoothing_factor
                    else:
                        xmax = xoff+win_xsize

                    # convert mask feature polygon into an array mask
                    geotransform = (xoff*xres-180-(xres/2), xres,
                                    0, 90-(yoff*yres)+(yres/2), 0, (yres*-1))
                    feature_layer = QgsVectorLayer(
                        "Polygon?crs={self.crs.authid()}", "Smoothing mask layer", "memory")
                    feature_layer.dataProvider().addAttributes(mask_layer.fields())
                    feature_layer.updateFields()
                    feature_layer.dataProvider().addFeature(feature)
                    mask_array = vectorToRaster(
                        feature_layer, geotransform, win_xsize, win_ysize, feedback=self.feedback)

                    # Check if the subset array lies at the left or right edges and that the raster is a global one
                    # If so, the subset raster will be extended by wrapping around the edges
                    if xoff <= 0 or xmax >= in_array.shape[1]:
                        if in_raster_extent.xMinimum() < (-179.95) and in_raster_extent.xMaximum() >= 179.95:
                            try:
                                smoothed_array = smoothArrayWithWrapping(in_array,
                                                                         [(yoff, ymax),
                                                                          (xoff, xmax)],
                                                                         "W" if xoff <= 0 else "E",
                                                                         smoothing_factor,
                                                                         smoothing_type,
                                                                         smoothing_factor,
                                                                         mask_array,
                                                                         self.feedback,
                                                                         progress_unit)
                            except Exception as e:
                                self.feedback.warning(
                                    f"Smoothing failed for the mask polygon with id {feature.id()}")
                                self.feedback.error(f"Error: {e}")
                    else:
                        array_to_smooth = in_array[yoff:ymax, xoff:xmax]
                        try:
                            smoothed_array = rasterSmoothingInPolygon(array_to_smooth,
                                                                      smoothing_type,
                                                                      smoothing_factor,
                                                                      mask_array=mask_array,
                                                                      smoothing_mode='reflect',
                                                                      feedback=self.feedback,
                                                                      runtime_percentage=progress_unit)
                        except Exception as e:
                            self.feedback.warning(
                                f"Smoothing failed for the mask polygon with id {feature.id()}")
                            self.feedback.error(f"Error: {e}")

                    in_array[yoff:ymax, xoff:xmax] = smoothed_array

                # set initial nan values back to nan
                in_array[nan_mask == 1] = np.nan

                # Write the smoothed raster
                # If the out_file argument is specified the smoothed raster will written in a new raster, otherwise the old raster will be updated
                try:
                    if os.path.exists(self.out_file_path):
                        driver = gdal.GetDriverByName('GTiff')
                        driver.Delete(self.out_file_path)
                except Exception as e:
                    self.feedback.error(e)

                smoothed_raster = gdal.GetDriverByName('GTiff').Create(self.out_file_path, in_array.shape[1],
                                                                       in_array.shape[0], 1, gdal.GDT_Float32)
                smoothed_raster.SetGeoTransform(
                    raster_to_smooth_ds.GetGeoTransform())
                smoothed_raster.SetProjection(self.crs.toWkt())
                smoothed_band = smoothed_raster.GetRasterBand(1)
                smoothed_band.WriteArray(in_array)
                smoothed_band.FlushCache()

                # Close datasets
                smoothed_band = None
                smoothed_raster = None
                in_array = None

            else:
                try:
                    smoothing_factor = self.dlg.smFactorSpinBox2.spinBox.value()
                    # check if the raster is global
                    if in_raster_extent.xMinimum() < (-179.95) and in_raster_extent.xMaximum() >= 179.95:
                        smoothing_mode = 'wrap'
                    else:
                        smoothing_mode = 'reflect'

                    smoothed_raster_layer = rasterSmoothing(raster_to_smooth_layer, smoothing_type, smoothing_factor,
                                                            smoothing_mode=smoothing_mode, out_file=self.out_file_path,
                                                            feedback=self.feedback)
                except Exception as e:
                    self.feedback.warning(e)

            if not self.killed:
                # Set paleoshorelines fixed
                if self.dlg.fixedPaleoShorelinesCheckBox.isChecked() and self.dlg.paleoshorelinesMask.currentLayer():
                    pls_vlayer = self.dlg.paleoshorelinesMask.currentLayer()
                    shorelines = polygonsToPolylines(pls_vlayer)
                    shorelines_array = vectorToRaster(shorelines,
                                                      raster_to_smooth_ds.GetGeoTransform(),
                                                      raster_to_smooth_ds.RasterXSize,
                                                      raster_to_smooth_ds.RasterYSize)
                    shorelines_mask_array = vectorToRaster(pls_vlayer,
                                                           raster_to_smooth_ds.GetGeoTransform(),
                                                           raster_to_smooth_ds.RasterXSize,
                                                           raster_to_smooth_ds.RasterYSize)
                    smoothed_raster = gdal.Open(
                        self.out_file_path, gdalconst.GA_Update)
                    smoothed_array = smoothed_raster.GetRasterBand(
                        1).ReadAsArray()
                    # map NoData values to reset them after interpolation
                    nan_mask = np.zeros(smoothed_array.shape, dtype=np.int8)
                    nan_mask[np.isnan(smoothed_array)] = 1
                    # set paleoshorelines
                    smoothed_array[shorelines_array == 1] = 0
                    smoothed_array[(shorelines_mask_array == 1)
                                   * (smoothed_array < 0) == 1] = np.nan
                    smoothed_array[(shorelines_mask_array != 1)
                                   * (smoothed_array > 0) == 1] = np.nan
                    smoothed_raster.GetRasterBand(1).WriteArray(smoothed_array)
                    smoothed_array = None
                    shorelines_array = None
                    smoothed_raster = None
                    # fill the resulting gaps
                    layer_to_fill = QgsRasterLayer(
                        self.out_file_path, "Smoothed raster", "gdal")
                    self.out_file_path = fillNoData(
                        layer_to_fill, self.out_file_path)
                    # Make sure that values close to the shorelnes are interpolated correctly
                    # Pixels in touch with the shorelines can get wrong value if they diagonally touch
                    # any pixel on the other side of the shoreline
                    final_raster = gdal.Open(
                        self.out_file_path, gdalconst.GA_Update)
                    final_array = final_raster.GetRasterBand(1).ReadAsArray()
                    array_to_rescale_asl = final_array[(
                        shorelines_mask_array == 1)*(final_array < 0) == 1]
                    rescaled = modRescale(array_to_rescale_asl, 0.1, 5)
                    final_array[(shorelines_mask_array == 1) *
                                (final_array < 0) == 1] = rescaled
                    array_to_rescale_bsl = final_array[(
                        shorelines_mask_array != 1)*(final_array >= 0) == 1]
                    rescaled = modRescale(array_to_rescale_bsl, -5, -0.1)
                    final_array[(shorelines_mask_array != 1) *
                                (final_array >= 0) == 1] = rescaled
                    final_array[nan_mask == 1] = np.nan
                    final_raster.GetRasterBand(1).WriteArray(final_array)
                    final_array = None
                    shorelines_mask_array = None
            else:
                self.finished.emit(False, "")

            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def isostaticCompensation(self):

        self.feedback.info(
            "Correcting topography for ice load in Greenland and Antarctic...")
        # Get the bedrock topography raster
        if not self.killed:
            try:
                topo_br_layer = self.dlg.baseTopoBox.currentLayer()
                topo_br_ds = gdal.Open(
                    topo_br_layer.dataProvider().dataSourceUri())
                topo_br_data = topo_br_ds.GetRasterBand(1).ReadAsArray()
                assert topo_br_layer, "The Berock topography raster layer is not loaded properly."
                assert topo_br_layer.isValid(), "The Bedrock topography raster layer is not valid."
            except Exception as e:
                self.feedback.error(e)
                self.kill()

            if not self.killed:
                self.feedback.info(
                    "Bedrock topography raster layer: {}.".format(topo_br_layer.name()))
                self.feedback.progress += 5

        if not self.killed:
            # Get the ice surface topography raster
            try:
                topo_ice_layer = self.dlg.selectIceTopoBox.currentLayer()
                topo_ice_ds = gdal.Open(
                    topo_ice_layer.dataProvider().dataSourceUri())
                topo_ice_data = topo_ice_ds.GetRasterBand(1).ReadAsArray()
                assert topo_ice_layer, "The Ice topography raster layer is not loaded properly."
                assert topo_ice_layer.isValid(), "The Ice topography raster layer is not valid."
            except Exception as e:
                self.feedback.error(e)
                self.kill()

            if not self.killed:
                self.feedback.info(
                    "Ice topography raster layer: {}.".format(topo_ice_layer.name()))
                self.feedback.progress += 5

        if self.dlg.isostatMaskBox.currentLayer():
            if not self.killed:
                # Get the masks
                try:
                    vlayer = self.dlg.isostatMaskBox.currentLayer()
                    assert vlayer is not None, "The Mask vector layer is not loaded properly."
                    assert vlayer.isValid(), "The Mask vector layer is not valid."
                    assert vlayer.featureCount() > 0, "The selected mask vector layer is empty."
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()

                if not self.killed:
                    self.feedback.info(
                        "Mask vector layer: {}.".format(vlayer.name()))
                    self.feedback.progress += 5

            if self.dlg.masksFromCoastCheckBox.isChecked():
                if not self.killed:
                    self.feedback.info(
                        "Retrieving the masks with the following names (case insensitive): ")
                    for i in ["Greenland",
                              "Antarctic or antarctica (Including East Antarctica and Antarctic peninsula)",
                              "Marie Byrd Land",
                              "Rone Ice Shelf",
                              "Thurston Island",
                              "Berkner Island",
                              "Whitmore Mountains",
                              "Filchner Block",
                              "Ross Terrane",
                              "Ellsworth Mountains",
                              "Dronning or Queen Maud Land",
                              "Lutzow-Holm or Luetzow-Holm Bay",
                              "Raynor Province",
                              "Haag Mountains o Nunataks",
                              "Admundsen Terrane"
                              ]:
                        self.feedback.info(f"<i>{i}")
                    # Get features from the masks layer
                    # build expression string
                    names_to_look_for = ["greenland",
                                         "antarctic",
                                         "antarctica",
                                         "eastantarctic",
                                         "eastantarctica",
                                         "marie",
                                         "byrd",
                                         "rone",
                                         "thurston",
                                         "berkner",
                                         "whitmore",
                                         "filchner",
                                         "ross",
                                         "ellsworth",
                                         "dronning",
                                         "queen",
                                         "maud",
                                         "lutzow",
                                         "luetzow",
                                         "raynor",
                                         "haag",
                                         "admundsen"]
                    expression_string = ""
                    self.feedback.progress = 10
                    for i in names_to_look_for:
                        if len(expression_string) != 0:
                            expression_string += " OR "
                        expression_string += f"lower(\"NAME\") LIKE '%{i}%'"
                    try:
                        expr = QgsExpression(expression_string)

                        features = list(vlayer.getFeatures(
                            QgsFeatureRequest(expr)))
                        assert any(
                            True for _ in features), "No features with the above names are found in the input mask layer"
                        temp_layer = QgsVectorLayer(
                            f'Polygon?crs={self.crs.authid()}', 'extracted_masks', 'memory')
                        temp_prov = temp_layer.dataProvider()
                        temp_prov.addAttributes(
                            vlayer.dataProvider().fields().toList())
                        temp_layer.updateFields()
                        temp_prov.addFeatures(features)
                        temp_prov = None

                        self.feedback.progress += 10

                    except AssertionError as e:
                        self.feedback.warning(e)
                        self.feedback.warning(
                            "All the polygons inside the input mask layer will be used for topography correction.")
                        temp_layer = vlayer

                if not self.killed:
                    self.feedback.info("Rasterizing exrtacted masks.")
                    # Rasterize extracted masks
                    geotransform = topo_br_ds.GetGeoTransform()
                    nrows, ncols = np.shape(topo_br_data)
                    r_masks = vectorToRaster(
                        temp_layer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                    )

                    self.feedback.progress += 10

            elif self.dlg.isostatMaskSelectedFeaturesCheckBox.isChecked():
                features = list(vlayer.getSelectedFeatures())
                assert any(
                    True for _ in features), "No features with the above names are found in the input mask layer"
                temp_layer = QgsVectorLayer(
                    f'Polygon?crs={self.crs.authid()}', 'extracted_masks', 'memory')
                temp_prov = temp_layer.dataProvider()
                temp_prov.addAttributes(
                    vlayer.dataProvider().fields().toList())
                temp_layer.updateFields()
                temp_prov.addFeatures(features)
                temp_prov = None
                if not self.killed:
                    geotransform = topo_br_ds.GetGeoTransform()
                    nrows, ncols = np.shape(topo_br_data)
                    self.feedback.info("Rasterizing the masks.")
                    r_masks = vectorToRaster(
                        temp_layer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                    )
                    self.feedback.progress += 30

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
        else:
            r_masks = None

        if not self.killed:
            # Compensate for ice load
            self.feedback.info("Compensating for ice load.")
            # the amount of ice that needs to be removed.
            rem_amount = self.dlg.iceAmountSpinBox.value()
            if r_masks is not None:
                comp_factor = 0.3 * \
                    (topo_ice_data[r_masks == 1] -
                     topo_br_data[r_masks == 1]) * rem_amount / 100
                comp_factor[np.isnan(comp_factor)] = 0
                comp_factor[comp_factor < 0] = 0
                topo_br_data[r_masks ==
                             1] = topo_br_data[r_masks == 1] + comp_factor
            else:
                comp_factor = 0.3 * \
                    (topo_ice_data - topo_br_data) * rem_amount / 100
                comp_factor[np.isnan(comp_factor)] = 0
                comp_factor[comp_factor < 0] = 0
                topo_br_data = topo_br_data + comp_factor

            self.feedback.progress += 30
        if not self.killed:
            # Create a new raster for the result
            self.feedback.info("Saving the resulting layer.")
            geotransform = topo_br_ds.GetGeoTransform()
            nrows, ncols = np.shape(topo_br_data)
            output_raster = gdal.GetDriverByName('GTiff').Create(
                self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
            output_raster.SetGeoTransform(geotransform)
            output_raster.SetProjection(self.crs.toWkt())
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
        progress = TaProgressImitation(100, 100, self.feedback)
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
                self.feedback.error(
                    f"Could not load the input raster layer {topo_layer.name()} properly.")
                self.feedback.error(f"Following error occured: {e}.")
                self.kill()
        if not self.killed:
            try:
                modified_topo_array = np.empty(input_topo_array.shape)
                modified_topo_array[:] = np.nan
                modified_topo_array[np.isfinite(input_topo_array)] = input_topo_array[np.isfinite(
                    input_topo_array)] - shiftAmount
            except Exception as e:
                self.feedback.warning(e)
        if not self.killed:
            nrows, ncols = input_topo_array.shape
            geotransform = topo_ds.GetGeoTransform()

            try:
                raster = gdal.GetDriverByName('GTiff').Create(
                    self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(geotransform)
                raster.SetProjection(self.crs.toWkt())
                raster.GetRasterBand(1).WriteArray(modified_topo_array)
                raster.GetRasterBand(1).SetNoDataValue(np.nan)
                raster = None
            except Exception as e:
                self.feedback.error(
                    "Could not write the result to the output file.")
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
            age_raster_time = self.dlg.ageRasterTime.value()
            self.feedback.info("Calculating ocean depth from its age.")
            self.feedback.info(f"Input layer: {age_layer.name()}.")
            self.feedback.info(
                f"Reconstruction time: {reconstruction_time} Ma.")
            self.feedback.progress += 10

        if not self.killed:
            # create an empty array to store calculated ocean depth from age.
            ocean_depth = np.empty(ocean_age.shape)
            ocean_depth[:] = np.nan
            # calculate ocean age
            time_difference = reconstruction_time - age_raster_time

            ocean_age[ocean_age > 0] = ocean_age[ocean_age > 0] - \
                time_difference
            ocean_depth[ocean_age > 0] = -2620 - 330 * \
                (np.sqrt(ocean_age[ocean_age > 0]))
            ocean_depth[ocean_age > 90] = -5750
            self.feedback.progress += 50
        if not self.killed:
            nrows, ncols = ocean_depth.shape
            geotransform = age_raster.GetGeoTransform()

            try:
                raster = gdal.GetDriverByName('GTiff').Create(
                    self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                raster.SetGeoTransform(geotransform)
                raster.SetProjection(self.crs.toWkt())
                raster.GetRasterBand(1).WriteArray(ocean_depth)
                raster.GetRasterBand(1).SetNoDataValue(np.nan)
                raster.GetRasterBand(1).FlushCache()
                raster = None
                self.feedback.progress += 30
            except Exception as e:
                self.feedback.error(
                    "Could not write the result to the output file.")
                self.feedback.error(f"Following error occured: {e}.")
                self.kill()

        if not self.killed:
            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, '')

    def changeMapSymbology(self):
        layer = self.dlg.baseTopoBox.currentLayer()
        self.feedback.info(f"Changing map symbology for layer {layer.name()}.")
        color_ramp_name = self.dlg.colorPalette.currentText()

        self.feedback.info(f"Color ramp selected: {color_ramp_name}")
        try:
            setRasterSymbology(layer, color_ramp_name)
            self.feedback.info("Map symbology changed successfully.")
            self.finished.emit(True, '')
            # This is not a proper algorithm that processes much data
            # Therefore we can close it after it is finished
            # But closing it will delete a refernce to it and the finish event triggered above
            # will not able to run properly. Therefore we hide it.
            # self.dlg.hide()
        except Exception as e:
            self.feedback.warning(
                f"Changing map symbology failed due to the following exception: {e}")
            self.finished.emit(False, '')
