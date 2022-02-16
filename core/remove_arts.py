# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

from PyQt5.QtCore import QObject, QVariant, Qt, pyqtSignal
from PyQt5.QtGui import QColor
import os
import tempfile
from osgeo import gdal
from qgis.core import (
    QgsVectorLayer,
    QgsField,
    QgsWkbTypes,
    QgsFields,
    QgsFeature,
    QgsProject,
    QgsMapLayer,
    QgsCoordinateReferenceSystem
)
from qgis.gui import (
    QgsMapToolEmitPoint,
    QgsRubberBand,
    QgsVertexMarker
)

import numpy as np
from numpy import *


from .utils import (
    vectorToRaster,
    fillNoDataInPolygon,
    TaVectorFileWriter)
from qgis._core import QgsRasterLayer
from .base_algorithm import TaBaseAlgorithm


class TaPolygonCreator(QgsMapToolEmitPoint):
    finished = pyqtSignal(bool)
    geom = pyqtSignal(object)

    def __init__(self, canvas, iface):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberband = QgsRubberBand(
            self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberband.setFillColor(Qt.red)
        self.rubberband.setOpacity(0.5)
        self.rubberband.setWidth(1)
        self.point = None
        self.points = []
        self.vertices = []
        self.geometry = None

    def canvasPressEvent(self, e):

        if e.button() == Qt.RightButton:
            geometry = self.rubberband.asGeometry()
            self.geometry = geometry
            self.finished.emit(True)

        if e.button() == Qt.LeftButton:
            self.point = self.toMapCoordinates(e.pos())
            m = QgsVertexMarker(self.canvas)
            m.setCenter(self.point)
            m.setColor(QColor(0, 255, 0))
            m.setIconSize(5)
            m.setIconType(QgsVertexMarker.ICON_BOX)
            m.setPenWidth(3)
            self.points.append(self.point)
            self.vertices.append(m)
            self.isEmittingPoint = True
            self.showRubberband()

    def showRubberband(self):
        self.rubberband.reset(QgsWkbTypes.PolygonGeometry)
        for point in self.points:
            self.rubberband.addPoint(point, True)
            self.rubberband.show()

    def removePolygons(self, rb, pnt, vrtx):
        for rubber, point, vertex in zip(rb, pnt, vrtx):
            point = []
            # rubber.hide()
            self.iface.mapCanvas().scene().removeItem(rubber)
            rubber = None
            for vert in vertex:
                self.iface.mapCanvas().scene().removeItem(vert)
        self.iface.mapCanvas().refresh()


class TaRemoveArtefacts(TaBaseAlgorithm):

    def __init__(self, dlg, iface):
        super().__init__(dlg)
        self.iface = iface
        self.vl = None

    def setInputLayer(self, vl):
        self.vl = vl

    def run(self):
        if not self.killed:
            try:
                topo_layer = self.getTopoLayer()
            except Exception as e:
                self.feedback.Error("{}".format(e))
                self.kill()

        if not self.killed:
            self.feedback.info(
                "Removing artefacts from the {} raster".format(topo_layer.name()))

            self.feedback.info(
                "{} polygons are found in the input layer.".format(self.vl.featureCount()))

        # Save the vector layer with mask polygons onto the disk
        if self.dlg.savePolygonsCheckBox.isChecked():
            if not self.dlg.masksOutputPath.filePath():
                outputFilePath = os.path.join(tempfile.gettempdir(),
                                              "remove_artefacts_polygons.shp")
            else:
                outputFilePath = self.dlg.masksOutputPath.filePath()
            error = TaVectorFileWriter.writeToShapeFile(self.vl,
                                                        outputFilePath,
                                                        "UTF-8",
                                                        self.crs,
                                                        "ESRI Shapefile")
            if error[0] == TaVectorFileWriter.NoError:
                self.feedback.info(f"Mask layer saved at: {outputFilePath}")
                if self.dlg.addPolLayerToCanvasCheckBox.isChecked():
                    self.layerAdded.emit(outputFilePath)
            else:
                self.feedback.warning(
                    "Failed to save mask layer onto the disk because of the following error:")
                self.feedback.warning(error[1])
        if not self.killed:
            topo_raster = gdal.Open(topo_layer.source())
            H = topo_raster.GetRasterBand(1).ReadAsArray()
        if not self.killed:
            total = 75 / self.vl.featureCount() if self.vl.featureCount() else 0
            features = self.vl.getFeatures()
            processed_successfuly = 0
            for feature in features:
                if self.killed:
                    break
                if not feature.hasGeometry():
                    continue

                if feature.isValid():

                    temp_layer = QgsVectorLayer(
                        f"Polygon?crs={self.crs.authid()}", "Temporary vector layer for rasterization", "memory")
                    temp_layer.dataProvider().addAttributes(feature.fields())
                    temp_layer.updateFields()
                    temp_layer.dataProvider().addFeatures([feature])
                    temp_layer.updateExtents()
                    mask_array = vectorToRaster(
                        temp_layer, topo_layer, topo_layer.width(), topo_layer.height())
                    temp_layer = None

                    expr = feature["Expression"]
                    self.feedback.info(
                        "The expression for feature ID {0} is: {1}.".format(feature.id(), expr))
                    try:
                        expr = self.prepareExpression(H, expr)
                    except Exception as e:
                        self.feedback.warning(
                            "Expression evaluation failed for feature ID {}.".format(feature.id()))
                        self.feedback.warning(
                            "Please use a valid python expression (e.g. H&gt;500 or H&gt;=500 or (H&gt;500)&(H&lt;700))")
                        continue
                    else:
                        try:
                            H[expr*mask_array == 1] = np.nan
                        except Exception as e:
                            self.feedback.Warning(
                                "Although the expression seems to be ok, during topography modification an exception was raised for feature id {}".format(feature.id()))
                            continue
                    processed_successfuly += 1
                else:
                    self.feedback.info(
                        "The polygon of feature ID {} is invalid.".format(feature.id()))

                self.feedback.progress += total
            if processed_successfuly == 0:
                self.kill()

        if not self.killed:
            if self.dlg.interpolateCheckBox.isChecked():
                # Create a temporary raster to store modified data for interpolation
                out_file_path = os.path.join(
                    self.temp_dir, "Raster_for_interpolation.tiff")
                raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
                    out_file_path,
                    topo_layer.width(),
                    topo_layer.height(),
                    1,  # number of bands
                    gdal.GDT_Float32  # data type
                )
                raster_for_interpolation.SetGeoTransform(
                    topo_raster.GetGeoTransform())
                raster_for_interpolation.SetProjection(
                    topo_raster.GetProjection())
                band = raster_for_interpolation.GetRasterBand(1)
                band.SetNoDataValue(np.nan)
                band.WriteArray(H)
                raster_for_interpolation = None
                H = None
                topo_raster = None

                self.feedback.progress += 10

                if not self.killed:
                    rlayer = QgsRasterLayer(
                        out_file_path, "Raster Layer for interpolation", "gdal")
                    try:
                        interpolated_raster = fillNoDataInPolygon(
                            rlayer, self.vl, self.out_file_path)
                    except Exception as e:
                        self.feedback.Error(
                            "An error occured wile interpolating values for the artefact pixels: {}".format(e))
                        self.kill()

                    self.feedback.progress = 100

                    self.finished.emit(True, interpolated_raster)
                if os.path.exists(out_file_path):
                    drv = gdal.GetDriverByName('GTIFF')
                    drv.Delete(out_file_path)
            else:

                output_raster = gdal.GetDriverByName('GTIFF').Create(
                    self.out_file_path,
                    topo_layer.width(),
                    topo_layer.height(),
                    1,  # number of bands
                    gdal.GDT_Float32  # data type
                )
                output_raster.SetGeoTransform(topo_raster.GetGeoTransform())
                output_raster.SetProjection(topo_raster.GetProjection())
                band = output_raster.GetRasterBand(1)
                band.SetNoDataValue(np.nan)
                band.WriteArray(H)
                band.FlushCache()
                output_raster = None
                H = None
                topo_raster = None

                self.feedback.progress = 100

                self.finished.emit(True, self.out_file_path)

            QgsProject.instance().layerTreeRoot().findLayer(
                topo_layer.id()).setItemVisibilityChecked(False)

        else:
            self.finished.emit(False, "")

    def getTopoLayer(self):
        topo_layer = None
        layer_found = False
        for layer in self.iface.mapCanvas().layers():
            if layer.type() == QgsMapLayer.RasterLayer:
                topo_layer = layer
                layer_found = True
                break
        if not layer_found:
            raise Exception(
                "There is no visible raster layer in the project. Please check a raster layer  with topography that you want to modify.")
        if self.crs and topo_layer.crs().authid() != self.crs.authid():
            self.feedback.warning("The layer for removing artefacts has a different Coordinate Refernce System (crs) than the\
                                  current project.")
            self.feedback.warning("For Terra Antqua to work properly the project and the layers should have the same\
                                  crs.")
        return topo_layer

    def prepareExpression(self, H, expr):
        if expr.lower() == "nodata" or expr.lower() == "no data":

            try:
                topo_layer = self.getTopoLayer()
            except Exception as e:
                self.feedback.Error(e)
                self.kill()
            topo_raster = gdal.Open(topo_layer.source())
            no_data_value = topo_raster.GetRasterBand(1).GetNoDataValue()
            topo_raster = None
            if not np.isnan(no_data_value):
                expr = "H=={}".format(no_data_value)
            else:
                expr = "np.isnan(H)"

            try:
                mask = eval(expr)
            except Exception as e:
                raise Exception(e)

        else:
            try:
                mask = eval(expr)

            except Exception as e:
                raise Exception(e)

        return mask


class TaFeatureSink(QObject):

    def __init__(self, crs):
        super().__init__()
        self.crs = crs
        self.vl = self.createVectorLayer()
        self.feat_id = 0

    def createVectorLayer(self):
        vl = QgsVectorLayer(
            f"Polygon?crs={self.crs.authid()}", "Polygons created", "memory")
        id_field = QgsField("ID", QVariant.Int, "integer")
        expr_field = QgsField("Expression", QVariant.String, "text")
        fields = QgsFields()
        fields.append(id_field)
        fields.append(expr_field)
        vl.dataProvider().addAttributes(fields)
        vl.updateFields()
        return vl

    def createFeature(self, geom, expr):
        self.feat_id += 1
        feature = QgsFeature()
        feature.setGeometry(geom)
        fields = QgsFields()
        id_field = QgsField("ID", QVariant.Int, "integer")
        expr_field = QgsField("Expression", QVariant.String, "text")
        fields.append(id_field)
        fields.append(expr_field)
        feature.setFields(fields)
        feature["ID"] = self.feat_id
        feature["Expression"] = expr
        self.vl.dataProvider().addFeature(feature)
        self.vl.updateExtents()

    def getVectorLayer(self):
        return self.vl

    def cleanFeatureSink(self):
        self.vl = self.createVectorLayer()
