# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

import os
try:
    from qgis.core import QgsMapLayerType
except:
    pass

from qgis.core import (
    QgsMapLayer,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsSettings
)


from . utils import setRasterSymbology, setVectorSymbology
from .remove_arts import TaRemoveArtefacts, TaPolygonCreator, TaFeatureSink
from ..gui.welcome_dialog import TaWelcomeDialog


class TaAlgorithmProvider:

    def __init__(self, dlg, thread, iface, settings, params=None):
        self.dlg = dlg()
        self.thread = thread(self.dlg)
        self.iface = iface
        self.settings = settings
        self.dlg.is_run.connect(self.start)
        self.dlg.cancelled.connect(self.stop)
        self.thread.finished.connect(self.finish)
        self.thread.progress.connect(self.dlg.setProgressValue)
        self.welcome_page = TaWelcomeDialog()
        if params:
            self.parameters = params(self.dlg)
            self.parameters.restoreParameters()

    def load(self):
        if self.settings.temporarySettings.get("first_start") != False:
            self.settings.setTempValue("first_start", False)
            if self.welcome_page.showAgain:
                result = self.welcome_page.exec_()
        self.dlg.show()

    def start(self):
        if not self.thread.isRunning():
            self.thread.startOver()
            self.thread.start()

    def stop(self):
        if self.thread.isRunning():
            self.thread.kill()
            self.thread.feedback.error(
                "The algorithm did not finish successfully, because the user canceled processing.")
            self.thread.feedback.error(
                "Or something went wrong. Please, refer to the log above for more details.")

    def finish(self, finished, output_path):
        if finished and output_path:
            self.add_result(output_path)
            self.dlg.finishEvent()
        elif finished and not output_path:
            self.dlg.finishEvent()

        else:
            if not self.dlg.isCanceled():
                self.stop()

    def add_result(self, output_path):
        file_name = os.path.splitext(os.path.basename(output_path))[0]
        ext = os.path.splitext(os.path.basename(output_path))[1]
        if ext == '.tif' or ext == '.tiff':
            try:
                layer = self.iface.addRasterLayer(
                    output_path, file_name, "gdal")
            except Exception as e:
                self.thread.feedback.warning(e)
        elif ext == '.shp':
            layer = self.iface.addVectorLayer(output_path, file_name, "ogr")

        if layer:
            # Rendering a symbology style for the resulting raster layer.
            try:
                if layer.type() == QgsMapLayerType.RasterLayer:
                    setRasterSymbology(layer)
                elif layer.type() == QgsMapLayerType.VectorLayer:
                    setVectorSymbology(layer)
            except Exception:
                if layer.type() == QgsMapLayer.LayerType.RasterLayer:
                    setRasterSymbology(layer)
                elif layer.type() == QgsMapLayer.LayerType.VectorLayer:
                    setVectorSymbology(layer)
            self.thread.feedback.info(
                "The algorithm finished processing successfully,")
            self.thread.feedback.info(
                "and added the resulting raster/vector layer to the map canvas.")
            self.thread.feedback.info(f"The ouput file path is: {output_path}")
        else:
            self.thread.feedback.info("The algorithm finished successfully,")
            self.thread.feedback.info(
                "however the resulting layer did not load. You may need to load it manually.")
            self.thread.feedback.info(f"The ouput file path is: {output_path}")


class TaRemoveArtefactsAlgProvider:

    def __init__(self, tltp, dlg, iface, actions, settings, params=None):
        self.dlg = dlg()
        self.tooltip = tltp()
        self.actions = actions
        self.settings = settings
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.nFeatures = None
        self.rbCollection = None
        self.pointCollection = None
        self.vertexCollection = None

        self.thread = TaRemoveArtefacts(self.dlg, self.iface)
        self.thread.progress.connect(self.dlg.setProgressValue)
        self.thread.finished.connect(self.addResult)
        self.thread.layerAdded.connect(self.addSecondaryOutputToProject)

        self.dlg.is_run.connect(self.start)
        self.dlg.cancelled.connect(self.stop)
        self.dlg.addButton.clicked.connect(self.createPolygon)
        self.dlg.closeButton.clicked.connect(self.clean)
        if params:
            self.parameters = params(self.dlg)

    def initiate(self):
        if self.tooltip.showAgain:
            self.tooltip.show()
            self.tooltip.accepted.connect(self.drawPolygon)
        else:
            self.drawPolygon()

    def drawPolygon(self):
        if self.tooltip.showAgain:
            if self.tooltip.showAgainCheckBox.isChecked():
                self.tooltip.setShowable(False)
        if not self.nFeatures:
            self.nFeatures = 0
        self.toolPoly = TaPolygonCreator(self.canvas, self.iface)
        self.toolPoly.finished.connect(self.load)
        self.canvas.setMapTool(self.toolPoly)
        for action in self.actions:
            if action.text() == "Remove Artefacts":
                self.toolPoly.setAction(action)

    def load(self):
        self.storeRubberbands(self.toolPoly.rubberband,
                              self.toolPoly.vertices, self.toolPoly.points)
        self.dlg.show()
        if self.nFeatures == 0:
            context = QgsExpressionContext()
            context.appendScope(
                QgsExpressionContextUtils.projectScope(QgsProject.instance()))
            crs = context.variable("project_crs")
            crs = QgsCoordinateReferenceSystem(crs)
            self.feature_sink = TaFeatureSink(crs)

    def createPolygon(self):
        self.nFeatures += 1
        expr = self.dlg.exprLineEdit.lineEdit.value()
        geom = self.toolPoly.geometry
        self.feature_sink.createFeature(geom, expr)
        self.dlg.hide()
        self.drawPolygon()

    def start(self):
        if self.toolPoly.geometry:
            expr = self.dlg.exprLineEdit.lineEdit.value()
            geom = self.toolPoly.geometry
            self.feature_sink.createFeature(geom, expr)
        self.vl = self.feature_sink.getVectorLayer()
        if self.vl.featureCount() != 0:
            self.thread.setInputLayer(self.vl)
            self.thread.start()
            self.nFeatures = 0
            self.toolPoly.geometry = None
        else:
            self.thread.feedback.warning(
                "There are no polygons drawn. Please draw new polygons and try again.")
            self.finish()

    def stop(self):
        if 'thread' in self.__dict__:
            self.thread.kill()
        self.thread.feedback.error(
            "The algorithm did not finish successfully, because the user canceled processing.")
        self.thread.feedback.error(
            "Or something went wrong. Please, refer to the log above for more details.")
        self.nFeatures = 0
        self.clean()

    def storeRubberbands(self, rb, vrtx, pnt):
        if not self.rbCollection:
            self.rbCollection = []
        if not self.pointCollection:
            self.pointCollection = []
        if not self.vertexCollection:
            self.vertexCollection = []

        self.rbCollection.append(rb)
        self.pointCollection.append(pnt)
        self.vertexCollection.append(vrtx)

    def addResult(self, finished, output_path):
        if finished is True:
            file_name = os.path.splitext(os.path.basename(output_path))[0]
            rlayer = self.iface.addRasterLayer(output_path, file_name, "gdal")
            if rlayer:
                setRasterSymbology(rlayer)
                self.thread.feedback.info(
                    "The artefacts were removed successfully,")
                self.thread.feedback.info(
                    "and the resulting layer is added to the map canvas with the following name: {}.".format(file_name))
            else:
                self.thread.feedback.info(
                    "The algorithm has removed artefacts successfully,")
                self.thread.feedback.info(
                    "however the resulting layer did not load. You may need to load it manually.")
                self.thread.feedback.info(
                    "The modified raster is saved at: {}".format(output_path))
            self.finish()
        else:
            self.dlg.cancelEvent()

    def addSecondaryOutputToProject(self, path_to_output):
        file_name = os.path.splitext(os.path.basename(path_to_output))[0]
        ext = os.path.splitext(os.path.basename(path_to_output))[1]
        if ext == '.tif' or ext == '.tiff':
            try:
                layer = self.iface.addRasterLayer(
                    path_to_output, file_name, "gdal")
            except Exception as e:
                self.thread.feedback.warning(e)
        elif ext == '.shp':
            layer = self.iface.addVectorLayer(path_to_output, file_name, "ogr")

        if layer:
            # Rendering a symbology style for the resulting raster layer.
            try:
                if layer.type() == QgsMapLayerType.RasterLayer:
                    setRasterSymbology(layer)
                elif layer.type() == QgsMapLayerType.VectorLayer:
                    setVectorSymbology(layer)
            except Exception:
                if layer.type() == QgsMapLayer.LayerType.RasterLayer:
                    setRasterSymbology(layer)
                elif layer.type() == QgsMapLayer.LayerType.VectorLayer:
                    setVectorSymbology(layer)
            self.thread.feedback.info(
                f"A secondary output layer is added to the project: {path_to_output}")
        else:
            self.thread.feedback.info(
                f"Failed to add a secondary output layer to the project: {path_to_output}")

    def finish(self):
        self.dlg.finishEvent()
        self.clean()

    def clean(self):
        self.iface.actionPan().trigger()
        try:
            self.toolPoly.removePolygons(
                self.rbCollection, self.pointCollection, self.vertexCollection)
            self.nFeatures = 0
        except Exception:
            pass
        try:
            self.feature_sink.cleanFeatureSink()
        except:
            pass

        self.settings.removeArtefactsChecked = False
#        self.dlg.close()
