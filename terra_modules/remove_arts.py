from PyQt5.QtCore import QVariant, Qt, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsItem
import os
from osgeo import gdal
from random import randrange
from qgis.core import (
    QgsVectorLayer,
    QgsField,
    QgsWkbTypes,
    QgsFields,
    QgsFeature,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsProject,
    QgsMapLayer,
    Qgis,
    edit,
    QgsCoordinateReferenceSystem
    )
from qgis.gui import (
    QgsMapToolEmitPoint,
    QgsRubberBand,
    QgsVertexMarker,
    QgsAttributeDialog,
    QgsAttributeEditorContext
    )
import tempfile

import numpy as np


from .utils import (
    vectorToRaster,
    fillNoDataInPolygon,
    setVectorSymbology)
from qgis._core import QgsRasterLayer
from psycopg2.errorcodes import NO_DATA
from .base_algorithm import TaBaseAlgorithm

class TaPolygonCreator(QgsMapToolEmitPoint):
    finished = pyqtSignal(bool)
    geom = pyqtSignal(object)


    def __init__(self, canvas, iface):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberband = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberband.setFillColor(Qt.red)
        self.rubberband.setOpacity(0.5)
        self.rubberband.setWidth(1)
        self.point = None
        self.points = []
        self.vertices=[]
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
            m.setColor(QColor(0,255,0))
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
            #rubber.hide()
            self.iface.mapCanvas().scene().removeItem(rubber)
            rubber = None
            for vert in vertex:
                self.iface.mapCanvas().scene().removeItem(vert)
        self.iface.mapCanvas().refresh()


class TaRemoveArtefacts(TaBaseAlgorithm):

    def __init__(self, vl, dlg, iface):
        super().__init__(dlg)
        self.iface = iface
        self.vl = vl


    def run(self):
        if not self.killed:
            try:
                topo_layer = self.getTopoLayer()
            except Exception as e:
                self.log.emit("Error: {}".format(e))
                self.kill()

        if not self.killed:
            self.log.emit("Removing artefacts from the {} raster".format(topo_layer.name()))

            self.log.emit("{} polygons are found in the input layer.".format(self.vl.featureCount()))


        if not self.killed:
            topo_raster = gdal.Open(topo_layer.source())
            H=topo_raster.GetRasterBand(1).ReadAsArray()
        if not self.killed:
            total = 75 / self.vl.featureCount() if self.vl.featureCount() else 0
            features= self.vl.getFeatures()
            for feature in features:
                if self.killed:
                    break
                if not feature.hasGeometry():
                    continue

                if feature.isValid():

                    temp_layer = QgsVectorLayer("Polygon?crs={}".format(self.vl.crs().toWkt()), "Temporary vector layer for rasterization", "memory")
                    temp_layer.dataProvider().addAttributes(feature.fields())
                    temp_layer.updateFields()
                    temp_layer.dataProvider().addFeatures([feature])
                    temp_layer.updateExtents()
                    mask_array = vectorToRaster(temp_layer, topo_layer, topo_layer.width(), topo_layer.height())
                    temp_layer = None

                    expr = feature["Expression"]
                    self.log.emit("The expression for feature ID {0} is: {1}.".format(feature.id(), expr))
                    try:
                        expr = self.prepareExpression(H, expr)
                    except Exception as e:
                        self.log.emit("Warning: Expression evaluation failed for feature ID {}.".format(feature.id()))
                        self.log.emit("Warning: Please use a valid python expression (e.g. H&gt;500 or H&gt;=500 or (H&gt;500)&(H&lt;700))")
                        continue
                    else:
                        try:
                            H[expr*mask_array==1] = np.nan
                        except Exception as e:
                            self.log.emit("Warning: Although the expression seems to be ok, during topography modification an exception was raised for feature id {}".format(feature.id()))
                            continue
                else:
                    self.log.emit("The polygon of feature ID {} is invalid.".format(feature.id()))

                self.set_progress += total



        if not self.killed:
            if self.dlg.interpolateCheckBox.isChecked():
                # Create a temporary raster to store modified data for interpolation
                out_file_path = os.path.join(self.temp_dir, "Raster_for_interpolation.tiff")
                raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
                out_file_path,
                topo_layer.width(),
                topo_layer.height(),
                1, #number of bands
                gdal.GDT_Float32 #data type
            )
                raster_for_interpolation.SetGeoTransform(topo_raster.GetGeoTransform())
                raster_for_interpolation.SetProjection(topo_raster.GetProjection())
                band = raster_for_interpolation.GetRasterBand(1)
                band.SetNoDataValue(np.nan)
                band.WriteArray(H)
                raster_for_interpolation = None
                H = None
                topo_raster = None

                self.set_progress+=10


                if not self.killed:
                    rlayer = QgsRasterLayer(out_file_path, "Raster Layer for interpolation", "gdal")
                    try:
                        interpolated_raster = fillNoDataInPolygon(rlayer, self.vl, self.out_file_path)
                    except Exception as e:
                        self.log.emit("Error: An error occured wile interpolating values for the artefact pixels: {}".format(e))
                        self.kill()

                    self.set_progress=100


                    self.finished.emit(True, interpolated_raster)
                if os.path.exists(out_file_path):
                    drv = gdal.GetDriverByName('GTIFF')
                    drv.Delete(out_file_path)
            else:

                output_raster = gdal.GetDriverByName('GTIFF').Create(
                self.out_file_path,
                topo_layer.width(),
                topo_layer.height(),
                1, #number of bands
                gdal.GDT_Float32 #data type
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

                self.set_progress=100


                self.finished.emit(True, self.out_file_path)

            QgsProject.instance().layerTreeRoot().findLayer(topo_layer.id()).setItemVisibilityChecked(False)

        else:
            self.finished.emit(False, "")



    def getTopoLayer(self):
        topo_layer = None
        layer_found = False
        for layer in self.iface.mapCanvas().layers():
            if layer.type() == QgsMapLayer.RasterLayer:
                topo_layer = layer
                layer_found=True
                break
        if not layer_found:
            raise Exception("There is no visible raster layer in the project. Please check a raster layer  with topography that you want to modify.")
        if not topo_layer.crs().authid() == self.crs and self.crs:
            new_crs = QgsCoordinateReferenceSystem(self.crs)
            topo_layer.setCrs(new_crs)

        return topo_layer

    def prepareExpression(self, H, expr):
        if expr.lower() == "nodata" or expr.lower() == "no data":

            try:
                topo_layer = self.getTopoLayer()
            except Exception as e:
                self.log.emit(e)
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

        self.vl = QgsVectorLayer("Polygon?crs={}".format(crs), "Polygons created", "memory")
        expr_field = QgsField("Expression", QVariant.String, "text")
        fields=QgsFields()
        fields.append(expr_field)
        self.vl.dataProvider().addAttributes(fields)
        self.vl.updateFields()


    def createFeature(self, geom, expr):
        feature = QgsFeature()
        feature.setGeometry(geom)
        fields = QgsFields()
        field = QgsField("Expression", QVariant.String, "text")
        fields.append(field)
        feature.setFields(fields)
        feature["Expression"]=expr
        self.vl.dataProvider().addFeature(feature)
        self.vl.updateExtents()

    def getVectorLayer(self):
        return self.vl
