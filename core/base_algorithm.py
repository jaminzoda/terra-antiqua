# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

import os
import tempfile

from PyQt5.QtCore import (
    QThread,
    pyqtSignal
)
from PyQt5.QtWidgets import QMessageBox
from qgis.core import (QgsExpressionContext,
                       QgsCoordinateReferenceSystem,
                       QgsProject,
                       QgsExpressionContextUtils,
                       QgsVectorLayer,
                       QgsSettings)

from .utils import isPathValid


class TaBaseAlgorithm(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, object)
    log = pyqtSignal(object)
    layerAdded = pyqtSignal(str)

    def __init__(self, dlg):
        super().__init__()
        self.__name__ = self.__class__.__name__
        self.killed = False
        self.progress_count = 0
        self.started.connect(self.onRun)
        self.dlg = dlg
        self.context = self.getExpressionContext()
        self.qgis_version = self.context.variable("qgis_short_version")
        self.crs = QgsProject.instance().crs()
        self.temp_dir = tempfile.gettempdir()
        self.out_file_path = self.getOutFilePath()
        self.dlg.setDefaultOutFilePath(self.out_file_path)
        self.decisionMessageBox = QMessageBox()
        self.decisionMessageBox.setIcon(QMessageBox.Warning)
        self.decisionMessageBox.setWindowTitle('Terra Antiqua - Warning')
        self.decisionMessageBox.setStandardButtons(
            QMessageBox.Yes | QMessageBox.No)
        self.processing_output = self.getProcessingOutput()
        self.informationMessageBox = QMessageBox()
        self.informationMessageBox.setIcon(QMessageBox.Warning)
        self.informationMessageBox.setWindowTitle('Terra Antiqua - Warning')
        self.informationMessageBox.setStandardButtons(QMessageBox.Ok)
        try:
            self.feedback = self.dlg.createFeedback()
        except Exception as e:
            raise e
        self.checkProjectCrs()
        self.checkLayersCrs()
        self.isProcessingPluginEnabled(QgsSettings())

    def setName(self, name):
        self.__name__ = name
        self.out_file_path = self.getOutFilePath()
        self.dlg.setDefaultOutFilePath(self.out_file_path)

    def checkProjectCrs(self):
        if not self.crs.isValid():
            msg = 'Your project does not have a Coordinate Reference System.\n Do you want to set WGS84 Coordinate Reference System to your project?'
            self.decisionMessageBox.setText(msg)
            retval = self.decisionMessageBox.exec_()
            if retval == QMessageBox.Yes:
                self.crs = self.setProjectCrs()
            else:
                self.dlg.reject()

    def checkLayersCrs(self):
        unmaching_crs = []
        for key, layer in QgsProject.instance().mapLayers().items():
            if layer.crs() != self.crs:
                unmaching_crs.append(layer.name())
        if len(unmaching_crs) > 0:
            msg = f"""{len(unmaching_crs)} layers in your project have a different Coordinate Reference System (crs) from the current project. For Terra Antiqua to work properly all the layers must have the same crs  as the project. Consider reprojecting your layer to the project crs before using Terra Antiqua."""
            self.informationMessageBox.setText(msg)
            retval = self.informationMessageBox.exec_()

    def setProjectCrs(self, crs: QgsCoordinateReferenceSystem = None) -> QgsCoordinateReferenceSystem:
        if not crs:
            crs = QgsCoordinateReferenceSystem('EPSG:4326')
        project = QgsProject.instance()
        project.setCrs(crs)
        return crs

    def getProjectCrs(self):
        return self.crs

    def isProcessingPluginEnabled(self, settings):
        value = settings.value("PythonPlugins/processing")
        if value == 'false' or not value:
            msg = """The processing plugin, which is essential for Terra Antiqua to function properly, seems to be deactivated in your QGIS installation. Activate it before using Terra Antiqua. It can be activated in the Plugin manager window by following these steps: Plugins -> Manage and install plugins ... -> Installed -> check the checkbox for <i>Processing</i> plugin."""
            self.informationMessageBox.setText(msg)
            retval = self.informationMessageBox.exec_()

    def getOutFilePath(self):
        file_type = None
        algs = [
            ('TaCreateTopoBathy', 'PaleoDEM_withCreatedFeatures.tif', 'raster'),
            ('TaCompileTopoBathy', 'Compiled_DEM_Topo+Bathy.tif', 'raster'),
            ('TaModifyTopoBathy', 'PaleoDEM_modified_topography.tif', 'raster'),
            ('TaPrepareMasks', 'Extracted_general_masks.shp', 'vector'),
            ('TaRemoveArtefacts', 'PaleoDEM_withArtefactsRemoved.tif', 'raster'),
            ('TaSetPaleoshorelines', 'PaleoDEM_Paleoshorelines_set.tif', 'raster'),
            ('TaFillGaps', 'PaleoDEM_interpolated.tif', 'raster'),
            ('TaCopyPasteRaster', 'PaleoDEM_with_copied_values.tif', 'raster'),
            ('TaSmoothRaster', 'PaleoDEM_smoothed.tif', 'raster'),
            ('TaIsostaticCompensation', 'PaleoDEM_isostat_compensated.tif', 'raster'),
            ('TaSetSeaLevel', 'PaleoDEM_with_Sea_Level_changed.tif', 'raster'),
            ('TaCalculateBathymetry', 'PaleoDEM_with_calculated_bathymetry.tif', 'raster')
        ]

        temp_file_name = None
        for alg_name, out_file, f_type in algs:
            if self.__name__ == alg_name:
                temp_file_name = out_file
                file_type = f_type

        if not temp_file_name:
            temp_file_name = 'PaleoDEM_modified.tif'

        # Get the output path
        if not self.dlg.outputPath.filePath():
            out_file_path = os.path.join(self.temp_dir, temp_file_name)
        else:
            out_file_path = self.dlg.outputPath.filePath()

        # check if the provided path for the output path is valid
        ret = isPathValid(out_file_path, file_type if file_type else 'raster')
        if not ret[0]:
            self.feedback.error(ret[1])
            self.kill()
        return out_file_path

    def getProcessingOutput(self):
        # The processing algorithms in Qgis starting from version 3.8
        # use a notation of 'TEMPORARY_OUTPUT' for memory outputs
        # while in versions below 3.8 the 'memory:' notation is used.
        # Here we set the appropriate processing output for relevant qgis versions.

        if float(self.qgis_version) >= 3.8:
            processing_output = 'TEMPORARY_OUTPUT'
        elif self.qgis_version == '3.10':  # conversion of 3.10 to float gives 3.1 therefore we do not convert it
            processing_output = 'TEMPORARY_OUTPUT'
        elif float(self.qgis_version) < 3.8:
            processing_output = 'memory:'
        else:
            processing_output = 'TEMPORARY_OUTPUT'
            try:
                self.feedback.warning(
                    "TEMPORARY_OUTPUT is used for intermediate files but your Qgis version is different from what is expected. Check if you get correct results.")
            except:
                pass

        return processing_output

    def getExpressionContext(self, layer: QgsVectorLayer = None):
        context = QgsExpressionContext()
        if not layer:
            context.appendScope(QgsExpressionContextUtils.globalScope())
        else:
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        return context

    @property
    def set_progress(self):
        return self.progress_count

    @set_progress.setter
    def set_progress(self, value):
        self.progress_count = value
        self.emit_progress(self.progress_count)

    def emit_progress(self, progress_count):
        self.progress.emit(progress_count)

    def kill(self):
        self.killed = True
        self.feedback.setCanceled(True)
        self.progress_count = 0

    def startOver(self):
        self.killed = False
        self.feedback.setCanceled(False)

    def onRun(self):
        self.out_file_path = self.getOutFilePath()
