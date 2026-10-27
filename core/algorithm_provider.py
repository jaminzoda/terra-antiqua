# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - exec_() replaced by exec()
#  - add_result / addSecondaryOutputToProject: raster or vector results are recognised with
#    isinstance() instead of QgsMapLayerType (removed: the try/except import of QgsMapLayerType)
#  - releaseDefaultOutput / restoreReleasedOutput: when a tool writes to its DEFAULT output file while the
#    previous result is open on the map, the old layer is pointed at a temporary copy during the run and
#    pointed back afterwards, so the file can be overwritten on Windows as the help text describes
#    (on macOS/Linux the end result is the same as before). Output paths chosen by the user are never touched.
#  See core/compat.py for the note on how this port was made.

import glob  # [QGIS4 port]
import os
import shutil  # [QGIS4 port]
import tempfile  # [QGIS4 port]
from qgis.core import (
    QgsDataProvider,  # [QGIS4 port]
    QgsMapLayer,
    QgsRasterLayer,  # [QGIS4 port]
    QgsVectorLayer,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsSettings
)


from . utils import setRasterSymbology, setVectorSymbology
from .remove_arts import TaRemoveArtefacts, TaPolygonCreator, TaFeatureSink
from ..gui.welcome_dialog import TaWelcomeDialog


def _same_file(path_a, path_b):  # [QGIS4 port]
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def releaseDefaultOutput(thread):  # [QGIS4 port]
    """Releases the tool's default output file if the previous result is open on the map.

    Windows cannot overwrite a file that QGIS has open. If the user did not choose an output
    path (so the default file is used, which the help text says is overwritten on every run)
    and that file is loaded as a layer, the layer is pointed at a temporary copy of it while
    the tool runs. The layer keeps its place and style. Must be called from the main thread.
    Returns the information needed by restoreReleasedOutput, or None.
    """
    try:
        thread.prepareOutputName()
        if thread.dlg.outputPath.filePath():
            return None  # an output path chosen by the user is never touched
        path = thread.getOutFilePath()
        if not path or not os.path.exists(path):
            return None
        layers = [layer for layer in QgsProject.instance().mapLayers().values()
                  if layer.source().split("|")[0] and _same_file(layer.source().split("|")[0], path)]
        if not layers:
            return None
        copy_dir = tempfile.mkdtemp(prefix="terra_antiqua_previous_result_")
        base = os.path.splitext(path)[0]
        for file_path in glob.glob(glob.escape(base) + ".*"):  # the file and its side files
            if os.path.isfile(file_path):
                shutil.copy2(file_path, copy_dir)
        copy_path = os.path.join(copy_dir, os.path.basename(path))
        released = []
        for layer in layers:
            source = layer.source()
            layer.setDataSource(copy_path + source[len(source.split("|")[0]):], layer.name(),
                                layer.providerType(), QgsDataProvider.ProviderOptions())
            released.append((layer.id(), source))
        return {"path": path, "copy_dir": copy_dir, "layers": released}
    except Exception:
        return None


def restoreReleasedOutput(released):  # [QGIS4 port]
    """Points layers released by releaseDefaultOutput back at the output file and deletes the copy."""
    if not released:
        return
    keep_copy = False
    for layer_id, source in released["layers"]:
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            continue
        if os.path.exists(released["path"]):
            layer.setDataSource(source, layer.name(), layer.providerType(),
                                QgsDataProvider.ProviderOptions())
            layer.triggerRepaint()
        else:
            keep_copy = True  # the output was not written: the layer keeps showing the copy
    if not keep_copy:
        shutil.rmtree(released["copy_dir"], ignore_errors=True)


class TaAlgorithmProvider:

    def __init__(self, dlg, thread, iface, settings):
        self.dlg = dlg()
        self.thread = thread(self.dlg)
        self.iface = iface
        self.settings = settings
        self.dlg.is_run.connect(self.start)
        self.dlg.cancelled.connect(self.stop)
        self.thread.finished.connect(self.finish)
        self.thread.progress.connect(self.dlg.setProgressValue)
        self.welcome_page = TaWelcomeDialog()
        self.released_output = None  # [QGIS4 port]

    def load(self):
        if self.settings.temporarySettings.get("first_start") != False:
            self.settings.setTempValue("first_start", False)
            if self.welcome_page.showAgain:
                result = self.welcome_page.exec()  # [QGIS4 port]
        self.dlg.show()

    def start(self):
        if not self.thread.isRunning():
            restoreReleasedOutput(self.released_output)  # [QGIS4 port]
            self.released_output = releaseDefaultOutput(self.thread)  # [QGIS4 port]
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
        restoreReleasedOutput(self.released_output)  # [QGIS4 port]
        self.released_output = None  # [QGIS4 port]
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
            if isinstance(layer, QgsRasterLayer):  # [QGIS4 port]
                setRasterSymbology(layer)  # [QGIS4 port]
            elif isinstance(layer, QgsVectorLayer):  # [QGIS4 port]
                setVectorSymbology(layer)  # [QGIS4 port]
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

    def __init__(self, tltp, dlg, iface, actions, settings):
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
        self.released_output = None  # [QGIS4 port]

        self.thread = TaRemoveArtefacts(self.dlg, self.iface)
        self.thread.progress.connect(self.dlg.setProgressValue)
        self.thread.finished.connect(self.addResult)
        self.thread.layerAdded.connect(self.addSecondaryOutputToProject)

        self.dlg.is_run.connect(self.start)
        self.dlg.cancelled.connect(self.stop)
        self.dlg.addButton.clicked.connect(self.createPolygon)
        self.dlg.closeButton.clicked.connect(self.clean)

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
            restoreReleasedOutput(self.released_output)  # [QGIS4 port]
            self.released_output = releaseDefaultOutput(self.thread)  # [QGIS4 port]
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
        restoreReleasedOutput(self.released_output)  # [QGIS4 port]
        self.released_output = None  # [QGIS4 port]
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
            if isinstance(layer, QgsRasterLayer):  # [QGIS4 port]
                setRasterSymbology(layer)  # [QGIS4 port]
            elif isinstance(layer, QgsVectorLayer):  # [QGIS4 port]
                setVectorSymbology(layer)  # [QGIS4 port]
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
