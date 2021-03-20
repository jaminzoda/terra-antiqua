import os
from osgeo import gdal, osr, gdalconst
from qgis.core import QgsRasterLayer

import numpy as np

from .utils import (
    polygonsToPolylines,
    vectorToRaster,
    fillNoData,
    modRescale
    )
from .base_algorithm import TaBaseAlgorithm


class TaSetPaleoshorelines(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)

    def run(self):
        self.feedback.info('Starting')

        self.feedback.info('Getting the raster layer')
        topo_layer = self.dlg.baseTopoBox.currentLayer()
        topo_extent = topo_layer.extent()
        topo_ds = gdal.Open(topo_layer.dataProvider().dataSourceUri())
        topo = topo_ds.GetRasterBand(1).ReadAsArray()
        geotransform = topo_ds.GetGeoTransform()  # this geotransform is used to rasterize extracted masks below
        nrows, ncols = np.shape(topo)

        # Get the elevation and depth constrains
        max_elev = self.dlg.maxElevSpinBox.value()
        max_depth = self.dlg.maxDepthSpinBox.value()

        self.set_progress += 10

        if topo is not None:
            self.feedback.info(('Size of the Topography raster: {}'.format(topo.shape)))
        else:
            self.feedback.info('There is a problem with reading the Topography raster')
            self.kill()

        # Get the vector masks
        self.feedback.info('Getting the vector layer')
        vlayer = self.dlg.masksBox.currentLayer()

        if vlayer.isValid() and vlayer.featureCount()>0:
            self.feedback.info('The mask layer is loaded properly')
        elif vlayer.isValid() and vlayer.featureCount()==0:
            self.feedback.error("The mask layer has no features. Please add polygon features to it and try again.")
            self.kill()
        else:
            self.feedback.error('There is a problem with the mask layer - not loaded properly')
            self.kill()

        self.set_progress += 10

        # Check which type of modification is chosen

        if self.dlg.interpolateCheckBox.isChecked():
            if not self.killed:
                self.feedback.info('The interpolation mode is selected.')
                self.feedback.info('In this mode the areas to emerge or submerge')
                self.feedback.info('will be set to NAN values, after which the values of these cells will be interpolated from adjacent cells.')

            if not self.killed:
                # Converting polygons to polylines in order to set the shoreline values to 0
                path_to_polylines = os.path.join(os.path.dirname(self.out_file_path), "polylines_from_polygons.shp")
                try:
                    pshoreline = polygonsToPolylines(vlayer, path_to_polylines)
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()
            if not self.killed:
                try:
                    pshoreline_rmask = vectorToRaster(
                        pshoreline,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                        )
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()
            if not self.killed:
                # Setting shorelines to 0 m
                topo[pshoreline_rmask == 1] = 0

            self.set_progress += 10

            if not self.killed:
                # Getting the raster masks of the land and sea area
                try:
                    r_masks = vectorToRaster(
                        vlayer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                        )
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()


            if not self.killed:
                # Setting the inland values that are below sea level, and in-sea values that are above sea level to
                # NAN (empty cell)
                # Creating an empty matrix to copy values from topo before setting them to NaN
                topo_values_copied = np.empty(topo.shape)
                topo_values_copied[:] = np.nan
                topo_values_copied[(r_masks == 1) * (topo < 0) == 1] = topo[(r_masks == 1) * (topo < 0) == 1]
                topo_values_copied[(r_masks == 0) * (topo > 0) == 1] = topo[(r_masks == 0) * (topo > 0) == 1]
                topo[(r_masks == 1) * (topo < 0) == 1] = np.nan
                topo[(r_masks == 0) * (topo > 0) == 1] = np.nan

            self.set_progress += 10

            if not self.killed:
                # Check if raster was modified. If the x matrix was assigned.
                if 'topo' in locals():

                    temp_out_file = os.path.join(os.path.dirname(self.out_file_path),
                                                 "PaleoShorelines_without_theGaps_filled.tiff")
                    driver = gdal.GetDriverByName('GTiff')
                    if os.path.exists(temp_out_file):
                        driver.Delete(temp_out_file)

                    raster = driver.Create(temp_out_file, ncols, nrows, 1, gdal.GDT_Float32)
                    raster.SetGeoTransform(geotransform)
                    crs = topo_layer.crs().toWkt()
                    raster.SetProjection(crs)
                    raster.GetRasterBand(1).SetNoDataValue(np.nan)
                    raster.GetRasterBand(1).WriteArray(topo)
                    raster = None

                    self.set_progress += 5

                    raster_layer = QgsRasterLayer(temp_out_file, "PaleoShorelines_without_theGaps_filled", "gdal")

                    ret = fillNoData(raster_layer, self.out_file_path)

                    #Delete the temporary layer stored before filling the gaps
                    if os.path.exists(temp_out_file):
                        driver.Delete(temp_out_file)
                        driver = None

                    self.set_progress += 10

                    # Read the resulting raster to check if the interpolation was done correctly.
                    # If some areas are interpolated between to zero values of shorelines (i.e. large areas were
                    # assigned zero values), the old values will used and rescaled below/above sea level
                    raster_layer_ds = gdal.Open(self.out_file_path, gdalconst.GA_Update)
                    topo_modified = raster_layer_ds.GetRasterBand(1).ReadAsArray()

                    array_to_rescale_bsl = topo_values_copied[np.isfinite(topo_values_copied) * (topo_modified == 0)
                                                              * (r_masks == 0) == 1]

                    array_to_rescale_asl = topo_values_copied[np.isfinite(topo_values_copied) * (topo_modified == 0)
                                                              * (r_masks == 1) == 1]
                    if array_to_rescale_bsl.size>0 and np.isfinite(array_to_rescale_bsl).size>0:
                        topo_modified[np.isfinite(topo_values_copied) * (topo_modified == 0) * (r_masks == 0) == 1] = \
                            modRescale(array_to_rescale_bsl, -5, -0.1)

                    if array_to_rescale_asl.size>0 and np.isfinite(array_to_rescale_asl).size>0:
                        topo_modified[np.isfinite(topo_values_copied) * (topo_modified == 0) * (r_masks == 1) == 1] = \
                            modRescale(array_to_rescale_asl, 0.1, 5)

                    self.set_progress += 5

                    # Removing final artefacts from the sea and land. Some pixels that are close to the shoreline
                    # touch pixels on the other side of the shoreline and get wrong value during the interpolation

                    # Pixel values of the sea that are asl
                    data_to_fill_bsl = topo_values_copied[(r_masks == 0) * (topo_modified > 0) *
                                                          (np.isfinite(topo_values_copied)) == 1]
                    if data_to_fill_bsl.size>0 and np.isfinite(data_to_fill_bsl).size>0:
                        topo_modified[(r_masks == 0) * (topo_modified > 0) * np.isfinite(topo_values_copied) == 1] \
                            = modRescale(data_to_fill_bsl, -5, -0.1)

                    self.set_progress += 5

                    # Pixel values of land that are bsl
                    data_to_fill_asl = topo_values_copied[(r_masks == 1) * (topo_modified < 0) *
                                                          np.isfinite(topo_values_copied) == 1]
                    if data_to_fill_asl.size>0 and np.isfinite(data_to_fill_asl).size>0:
                        topo_modified[(r_masks == 1) * (topo_modified < 0) * np.isfinite(topo_values_copied) == 1] \
                            = modRescale(data_to_fill_asl, 0.1, 5)

                    self.set_progress += 5

                    # Still removing artifacts
                    topo_modified[(r_masks == 0) * (topo_modified > 0)] = np.nan
                    topo_modified[(r_masks == 1) * (topo_modified < 0)] = np.nan

                    self.set_progress += 5

                    # Updating the raster with the modified values
                    raster_layer_ds.GetRasterBand(1).WriteArray(topo_modified)
                    raster_layer_ds = None

                    self.set_progress += 5

                    self.feedback.info(
                        "The raster was modified successfully and saved at: <a href='file://{}'>{}</a>.".format(
                            os.path.dirname(self.out_file_path), self.out_file_path))

                    self.finished.emit(True, self.out_file_path)

                    self.set_progress = 100

                else:
                    self.feedback.info("The plugin did not succeed because one or more parameters were set incorrectly.")
                    self.feedback.info("Please, check the log above.")
                    self.finished.emit(False, "")
            else:
                self.finished.emit(False, "")



        elif self.dlg.rescaleCheckBox.isChecked():
            if not self.killed:
                try:
                    r_masks = vectorToRaster(
                        vlayer,
                        geotransform,
                        ncols,
                        nrows,
                        field_to_burn=None,
                        no_data=0
                        )
                except Exception as e:
                    self.feedback.error(e)
                    self.kill()
                # The bathymetry values that are above sea level are taken down below sea level
                in_array = topo[(r_masks == 0) * (topo > 0) == 1]
                topo[(r_masks == 0) * (topo > 0) == 1] = modRescale(in_array, max_depth, -0.1)

                self.set_progress += 30

            if not self.killed:
                # The topography values that are below sea level are taken up above sea level
                in_array = topo[(r_masks == 1) * (topo < 0) == 1]
                topo[(r_masks == 1) * (topo < 0) == 1] = modRescale(in_array, 0.1, max_elev)

                self.set_progress += 30

            if not self.killed:
                # Check if raster was modified. If the x matrix was assigned.
                if 'topo' in locals():

                    driver = gdal.GetDriverByName('GTiff')
                    if os.path.exists(self.out_file_path):
                        driver.Delete(self.out_file_path)

                    raster = driver.Create(self.out_file_path, ncols, nrows, 1, gdal.GDT_Float32)
                    raster.SetGeoTransform(geotransform)
                    crs = osr.SpatialReference()
                    crs.ImportFromEPSG(4326)
                    raster.SetProjection(crs.ExportToWkt())
                    raster.GetRasterBand(1).WriteArray(topo)
                    raster = None

                    self.set_progress += 10

                    self.feedback.info(
                        "The raster was modified successfully and saved at: <a\
                        href='file://{}/'>{}</a>.".format(
                            os.path.dirname(self.out_file_path), self.out_file_path))

                    self.finished.emit(True, self.out_file_path)

                    self.set_progress = 100

                else:
                    self.feedback.info("The plugin did not succeed because one or more parameters were set incorrectly.")
                    self.feedback.info("Please, check the log above.")
                    self.finished.emit(False, "")
            else:
                self.finished.emit(False, "")

