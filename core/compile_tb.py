#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
import os
from osgeo import (
    gdal
)
from PyQt5 import QtWidgets
from qgis.core import (
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsExpression,
    QgsFeatureRequest
)
import shutil

import numpy as np

from .utils import (
    vectorToRaster,
    modRescale,
    bufferAroundGeometries,
    TaVectorFileWriter,
    reprojectVectorLayer,
    polygonsToPolylines
)
from .base_algorithm import TaBaseAlgorithm


class TaCompileTopoBathy(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)
        self.remove_overlap = None


    def getParameters(self):
        self.items=[]
        self.feedback.info(f"{self.dlg.tableWidget.rowCount()} layers will be merged in the following order:")

        self.remove_overlap = self.dlg.removeOverlapBathyCheckBox.isChecked()
        if self.remove_overlap:
            self.mask_layer = self.dlg.maskComboBox.currentLayer()
        else:
            self.mask_layer = None
        for i in range(self.dlg.tableWidget.rowCount()):
            if self.killed:
                break
            layer = self.dlg.tableWidget.cellWidget(i,0).currentLayer()
            if self.remove_overlap and self.mask_layer:
                mask_applied = self.dlg.tableWidget.cellWidget(i, 2).findChild(QtWidgets.QWidget,
                                                                               name = "apply_mask_checkbox").isChecked()
            else:
                mask_applied = False
            item = {
                        "Order":i+1,
                        "Mask_Applied": mask_applied,
                        "Layer":layer
                        }
            self.items.append(item)
            self.feedback.info(f"{i+1}: {layer.name()}")
        self.feedback.info("Note that the overlaping data of a higher order layer will be removed.")


        #Check crs of layers
        if not self.killed:
            for item in self.items:
                layer = item.get("Layer")
                if layer.crs() != self.crs:
                    self.feedback.warning(f"Layer {layer.name()} has a different Coordinate Reference System than the \
                                          current project.")
                    self.feedback.warning(f"For the input raster layers to be properly compiled, they should have the \
                                          same crs as the current project crs ({self.crs.authid()})")
                    self.feedback.warning("Consider reprojecting your layers to the project crs using the \
                                          reprojecting tool of QGIS (Raster -> Projections -> Warp(Reproject)...)")

            if self.mask_layer and self.mask_layer.crs() != self.crs:
                try:
                    self.mask_layer = reprojectVectorLayer(self.mask_layer,
                                                           target_crs = self.crs,
                                                           feedback = self.feedback)
                except Exception as e:
                    self.feedback.warning(f"Layer {self.mask_layer.name()} has a Coordinate Reference System (crs)\
                    that is  different from your project crs.")
                    self.feedback.warning("Terra Antiqua tried to reproject it, but did not succeed. You may need to \
                                          reproject it manually.")
                    self.feedback.warning(f"Exception raised by reprojecting algorithm: {e}.")

        #Check if all input raster layers have the same size
        raster_sizes = []
        for item in self.items:
            width = item.get("Layer").width()
            height = item.get("Layer").height()
            name = item.get("Layer").name()
            raster_sizes.append((name, width, height))
        current_width = raster_sizes[0][1]
        current_height= raster_sizes[0][2]
        for name, width, height in raster_sizes:
            if current_width == width and current_height == height:
                continue
            else:
                self.feedback.error("The input raster layers have differing sizes.")
                self.feedback.error("For the layers to be properly compiled, they should be of the same size.")
                for i in raster_sizes:
                    self.feedback.error(f"Layer: {i[0]}, width: {i[1]}, height: {i[2]}")
                self.kill()
                break

    def run(self):
        self.getParameters()
        raster_size = (self.items[0].get('Layer').dataProvider().ySize(),
                      self.items[0].get('Layer').dataProvider().xSize())
        compiled_array = np.empty(raster_size)
        compiled_array[:] = np.nan
        unit_progress = 90/len(self.items)
        for i in range(len(self.items), 0, -1):
            if self.killed:
                break
            item = self.items[i-1]
            self.feedback.info(f"Compiling {item.get('Layer').name()} raster layer.")

            try:
                ds = gdal.Open(item.get("Layer").source())
                data_array = ds.GetRasterBand(1).ReadAsArray()
            except Exception as e:
                self.feedback.error(f"Compiling {item.get('Layer').name()} failed.")
                self.feedback.error("You need to check, if you have access to this layer's storage location (should not\
                                    be stored on the cloud.")
                self.kill()
                continue
            # Set nodata values to np.nan
            no_data_value = ds.GetRasterBand(1).GetNoDataValue()
            if no_data_value != np.nan:
                data_array[data_array==no_data_value] = np.nan
            compiled_array[np.isfinite(data_array)] = data_array[np.isfinite(data_array)]

            if self.remove_overlap and item.get("Mask_Applied"):
                geotransform = ds.GetGeoTransform()
                self.feedback.info(f"Creating buffer around polygon \
                                   geometries for removing overlapping bathymetry, to be applied to \
                                   {item.get('Layer').name()} layer.")
                buffer_distance = self.dlg.bufferDistanceForRemoveOverlapBath.value()
                if self.dlg.selectedFeaturesCheckBox.isChecked():
                    features = list(self.mask_layer.getSelectedFeatures())
                    temp_layer = QgsVectorLayer(f"Polygon?crs={self.crs.authid()}",
                                                "Selected mask features", "memory")
                    dp = temp_layer.dataProvider()
                    dp.addAttributes(self.mask_layer.dataProvider().fields().toList())
                    temp_layer.updateFields()
                    dp.addFeatures(features)
                    dp = None
                    try:
                        buffer_layer = bufferAroundGeometries(temp_layer, buffer_distance, 100, self.feedback, 10)
                    except Exception as e:
                        self.feedback.error("Something went wrong while creating buffer around polygon \
                                            geometries in the mask layer")
                        self.feedback.error("You might want to check if the mask layer contains any invalid geometry")
                        self.feedback.error("The following exception was raised:")
                        self.feedback.error(e)
                        self.kill()
                        continue

                    #Get polygon borders for removing artefats beneath them
                    polyline_layer = polygonsToPolylines(temp_layer)

                else:
                    try:
                        buffer_layer = bufferAroundGeometries(self.mask_layer, buffer_distance, 100, self.feedback, 10)
                    except Exception as e:
                        self.feedback.error("Something went wrong while creating buffer around polygon \
                                            geometries in the mask layer")
                        self.feedback.error("You might want to check if the mask layer contains any invalid geometry")
                        self.feedback.error("The following exception was raised:")
                        self.feedback.error(e)
                        self.kill()
                        continue
                    #Get polygon borders for removing artefats beneath them
                    polyline_layer = polygonsToPolylines(self.mask_layer)

                buffer_array = vectorToRaster(
                    buffer_layer,
                    geotransform,
                    raster_size[1],
                    raster_size[0],
                    field_to_burn = None,
                    no_data = 0
                    )

                #Rasterize polygon borders for removing negative (artefact) values beneath them.
                masks_border_array = vectorToRaster(
                    polyline_layer,
                    geotransform,
                    raster_size[1],
                    raster_size[0],
                    field_to_burn=None,
                    no_data = 0
                    )


                #Remove negative values inside the buffered regions
                self.feedback.info("Removing bathymetry values from the gaps between continental blocks." )
                compiled_array[(buffer_array == 1)*(compiled_array< -1000)==1] = np.nan
                compiled_array[(masks_border_array== 1)*(compiled_array< -1000)==1] = np.nan

            self.feedback.progress += unit_progress



        if not self.killed:
            output_raster = gdal.GetDriverByName("GTiff").Create(self.out_file_path,
                                                                 raster_size[1],
                                                                 raster_size[0],
                                                                 1,
                                                                 gdal.GDT_Float32)

            ds = gdal.Open(self.items[0].get("Layer").source())
            geotransform = ds.GetGeoTransform()
            ds = None
            output_raster.SetGeoTransform(geotransform)
            output_raster.SetProjection(self.crs.toWkt())
            output_raster.GetRasterBand(1).WriteArray(compiled_array)
            output_raster.GetRasterBand(1).SetNoDataValue(np.nan)
            output_raster = None

            self.feedback.progress = 100

            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

