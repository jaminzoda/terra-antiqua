import os
from osgeo import (
    gdal
)
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
    TaVectorFileWriter
)
from .base_algorithm import TaBaseAlgorithm


class TaCompileTopoBathy(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)
        self.crs = None
        self.remove_overlap = None


    def getParameters(self):
        self.items=[]
        if not self.killed:
            self.mask_layer = self.dlg.maskComboBox.currentLayer()
            self.remove_overlap = self.dlg.removeOverlapBathyCheckBox.isChecked()
        self.feedback.info(f"{self.dlg.tableWidget.rowCount()} layers will be merged in the following order:")

        for i in range(self.dlg.tableWidget.rowCount()):
            if self.killed:
                break
            layer = self.dlg.tableWidget.cellWidget(i,0).currentLayer()
            if self.dlg.maskComboBox.currentLayer():
                category = self.dlg.tableWidget.cellWidget(i, 2).currentText()
            else:
                category = None
            item = {
                        "Order":i+1,
                        "Category": category,
                        "Layer":layer
                        }
            self.items.append(item)
            self.feedback.info(f"{i+1}: {layer.name()}")
        self.feedback.info("Note that the overlaping data of a higher order layer will be removed.")


        self.feedback.info(f"The following Coordinate Reference System will be used for the resuling layer:")
        if  self.mask_layer:
            self.crs = self.mask_layer.crs()
            self.feedback.info(f"{self.crs.authid()} (Taken from {self.mask_layer.name()})")
        else:
            for item in self.items:
                if item.get("Layer").crs().isValid():
                    self.crs = item.get("Layer").crs()
                    self.feedback.info(f"{self.crs.authid()} (Taken from {item.get('Layer').name()})")
                    break


    def run(self):
        self.getParameters()
        raster_size = (self.items[0].get('Layer').dataProvider().ySize(),
                      self.items[0].get('Layer').dataProvider().xSize())
        compiled_array = np.empty(raster_size)
        compiled_array[:] = np.nan
        unit_progress = 90/len(self.items)
        for i in range(len(self.items), 0, -1):
            item = self.items[i-1]
            self.feedback.info(f"Compiling {item.get('Layer').name()} raster layer.")

            ds = gdal.Open(item.get("Layer").source())
            data_array = ds.GetRasterBand(1).ReadAsArray()
            # Set nodata values to np.nan
            no_data_value = ds.GetRasterBand(1).GetNoDataValue()
            data_array[data_array==no_data_value] = np.nan
            if item.get("Category") and item.get("Category") != "All":
                self.feedback.info(f"Using {item.get('Category')} vector masks to comile raster.")
                expression = QgsExpression(f"\"Category\"='{item.get('Category')}'")
                features = self.mask_layer.getFeatures(QgsFeatureRequest(expression))
                temp_layer = QgsVectorLayer("Polygon?crs={}".format(self.crs.authid()), "Layer to rasterize", "memory")
                temp_layer_dp = temp_layer.dataProvider()
                feats_added = temp_layer_dp.addFeatures(list(features))
                res = temp_layer_dp.flushBuffer()
                if not res:
                    self.feedback.debug(f"Masking features in {item.get('Layer').name()} \
                                          were not added to a temporary layer for rasterization.")
                del temp_layer_dp
            elif item.get("Category") and item.get("Category") =="All":
                temp_layer = self.mask_layer


            if not self.killed:
                if item.get("Category"):
                    try:
                        mask_array = vectorToRaster(temp_layer,
                                                ds.GetGeoTransform(),
                                                raster_size[1],
                                                raster_size[0],
                                                field_to_burn=None,
                                                no_data = 0)
                        compiled_array[mask_array==1] = data_array[mask_array == 1]
                    except Exception as e:
                        self.feedback.warning("Could not rasterize vector layer containing masks because of the \
                                              following error:")
                        self.feedback.warning(e)
                        self.feedback.warning(f"All the data from the {item.get('Layer').name()} \
                                              raster layer will be compiled.")
                        compiled_array[np.isfinite(data_array)] = data_array[np.isfinite(data_array)]

                else:
                    compiled_array[np.isfinite(data_array)] = data_array[np.isfinite(data_array)]


                self.feedback.progress += unit_progress

        if not self.killed:
            geotransform = gdal.Open(self.items[0].get("Layer").source()).GetGeoTransform()
            if self.remove_overlap:
                item = self.items[0]
                self.feedback.info(f"Creating buffer around polygon \
                                   geometries of the {item.get('Category')} category.")
                expression = QgsExpression(f"\"Category\"='{item.get('Category')}'")
                features = self.mask_layer.getFeatures(QgsFeatureRequest(expression))
                buffer_layer= QgsVectorLayer(f"Polygon?crs={self.crs.authid()}", "Temporary ss", "memory")
                buffer_layer.dataProvider().addFeatures(features)
                buffer_layer.dataProvider().flushBuffer()
                buffer_layer = bufferAroundGeometries(buffer_layer, 0.5, 100, self.feedback, 10)
                buffer_array = vectorToRaster(
                    buffer_layer,
                    geotransform,
                    raster_size[1],
                    raster_size[0],
                    field_to_burn = None,
                    no_data = 0
                    )

                #Remove negative values inside the buffered regions
                self.feedback.info("Removing bathymetry values from the gaps between continental blocks." )
                compiled_array[(buffer_array == 1)*(compiled_array< -1000)==1] = np.nan


        if not self.killed:
            output_raster = gdal.GetDriverByName("GTiff").Create(self.out_file_path,
                                                                 raster_size[1],
                                                                 raster_size[0],
                                                                 1,
                                                                 gdal.GDT_Float32)
            output_raster.SetGeoTransform(geotransform)
            output_raster.SetProjection(self.crs.toWkt())
            output_raster.GetRasterBand(1).WriteArray(compiled_array)
            output_raster.GetRasterBand(1).SetNoDataValue(np.nan)
            output_raster = None

            self.feedback.progress = 100

            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

