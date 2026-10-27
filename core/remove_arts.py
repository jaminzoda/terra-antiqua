# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6);
#    "qgis._core" (private) replaced by "qgis.core"
#  - Python built-ins abs, bool, max, min, pow and round restored after "from numpy import *",
#    because NumPy 2 (bundled with QGIS 4) would otherwise replace them
#  - TaPolygonCreator: rubber band uses compat.GEOMETRY_POLYGON; mouse buttons, colour and vertex
#    marker use full enum names
#  - TaFeatureSink: ID and Expression fields use compat.FIELD_INT / FIELD_STRING
#  - run: the temporary raster for interpolation is released before it is deleted
#  - Raster files are deleted with compat.delete_raster_file, so a failed deletion
#    (Windows "Permission denied") no longer stops the tool
#  - Saved mask layer checked against compat.VECTOR_WRITER_NO_ERROR
#  - feedback.Error / feedback.Warning written as feedback.error / feedback.warning
#  - prepareExpression: expressions are evaluated with core/expressions.evaluate instead of eval()
#  See core/compat.py for the note on how this port was made.

from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal  # [QGIS4 port]
from qgis.PyQt.QtGui import QColor  # [QGIS4 port]
import os
import tempfile
from osgeo import gdal
from qgis.core import (
    QgsVectorLayer,
    QgsField,
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
# NumPy 2.x (bundled with QGIS 4) also exports abs, bool, max, min, pow and round, which would
# replace Python's built-ins in this module. Restore them so behaviour matches NumPy 1.x.
from builtins import abs, bool, max, min, pow, round  # noqa: E402,F811  # [QGIS4 port]


from .utils import (
    vectorToRaster,
    fillNoDataInPolygon,
    TaVectorFileWriter)
from .compat import FIELD_INT, FIELD_STRING, GEOMETRY_POLYGON, VECTOR_WRITER_NO_ERROR, delete_raster_file  # [QGIS4 port]
from qgis.core import QgsRasterLayer  # [QGIS4 port]
from .base_algorithm import TaBaseAlgorithm
from .expressions import evaluate  # [QGIS4 port]


class TaPolygonCreator(QgsMapToolEmitPoint):
    finished = pyqtSignal(bool)
    geom = pyqtSignal(object)

    def __init__(self, canvas, iface):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberband = QgsRubberBand(
            self.canvas, GEOMETRY_POLYGON)  # [QGIS4 port]
        self.rubberband.setFillColor(Qt.GlobalColor.red)  # [QGIS4 port]
        self.rubberband.setOpacity(0.5)
        self.rubberband.setWidth(1)
        self.point = None
        self.points = []
        self.vertices = []
        self.geometry = None

    def canvasPressEvent(self, e):

        if e.button() == Qt.MouseButton.RightButton:  # [QGIS4 port]
            geometry = self.rubberband.asGeometry()
            self.geometry = geometry
            self.finished.emit(True)

        if e.button() == Qt.MouseButton.LeftButton:  # [QGIS4 port]
            self.point = self.toMapCoordinates(e.pos())
            m = QgsVertexMarker(self.canvas)
            m.setCenter(self.point)
            m.setColor(QColor(0, 255, 0))
            m.setIconSize(5)
            m.setIconType(QgsVertexMarker.IconType.ICON_BOX)  # [QGIS4 port]
            m.setPenWidth(3)
            self.points.append(self.point)
            self.vertices.append(m)
            self.isEmittingPoint = True
            self.showRubberband()

    def showRubberband(self):
        self.rubberband.reset(GEOMETRY_POLYGON)  # [QGIS4 port]
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
                self.feedback.error("{}".format(e))  # [QGIS4 port]
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
            if error[0] == VECTOR_WRITER_NO_ERROR:  # [QGIS4 port]
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
                            self.feedback.warning(  # [QGIS4 port]
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
                        self.feedback.error(  # [QGIS4 port]
                            "An error occured wile interpolating values for the artefact pixels: {}".format(e))
                        self.kill()

                    self.feedback.progress = 100

                    self.finished.emit(True, interpolated_raster)
                # Release the temporary layer before deleting its file (Windows)
                rlayer = None  # [QGIS4 port]
                delete_raster_file(out_file_path, self.feedback)  # [QGIS4 port]
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
            if layer.type() == QgsMapLayer.LayerType.RasterLayer:  # [QGIS4 port]
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
                self.feedback.error(e)  # [QGIS4 port]
                self.kill()
            topo_raster = gdal.Open(topo_layer.source())
            no_data_value = topo_raster.GetRasterBand(1).GetNoDataValue()
            topo_raster = None
            if not np.isnan(no_data_value):
                expr = "H=={}".format(no_data_value)
            else:
                expr = "np.isnan(H)"

            try:
                mask = evaluate(expr, {"H": H})  # [QGIS4 port]
            except Exception as e:
                raise Exception(e)

        else:
            try:
                mask = evaluate(expr, {"H": H})  # [QGIS4 port]

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
        id_field = QgsField("ID", FIELD_INT, "integer")  # [QGIS4 port]
        expr_field = QgsField("Expression", FIELD_STRING, "text")  # [QGIS4 port]
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
        id_field = QgsField("ID", FIELD_INT, "integer")  # [QGIS4 port]
        expr_field = QgsField("Expression", FIELD_STRING, "text")  # [QGIS4 port]
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
