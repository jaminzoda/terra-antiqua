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
                       QgsExpressionContextUtils)

from .utils import isPathValid


class TaBaseAlgorithm(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, object)
    log = pyqtSignal(object)

    def __init__(self, dlg):
        super().__init__()
        self.killed = False
        self.progress_count = 0
        self.started.connect(self.onRun)
        self.dlg = dlg
        self.context = self.getExpressionContext()
        self.qgis_version = self.context.variable("qgis_short_version")
        self.crs = QgsProject.instance().crs()
        self.temp_dir = tempfile.gettempdir()
        self.out_file_path = None
        self.processing_output = self.getProcessingOutput()
        try:
            self.feedback = self.dlg.createFeedback()
        #TODO raise e when all the algorithms are based on the unified base dialog
        except Exception as e:
            pass
        self.checkCrs()
    def checkCrs(self):
        if not self.crs.isValid():
            msg = 'Your project does not have a Coordinate Refernce System.\n Do you want to set WGS84 Coordinate Refernce System to your project?'
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(msg)
            msg_box.setWindowTitle('Terra Antiqua - Warning')
            msg_box.setStandardButtons(QMessageBox.Yes|QMessageBox.No)
            retval = msg_box.exec_()
            if retval == QMessageBox.Yes:
                self.crs = self.setProjectCrs()
            else:
                self.dlg.reject()
    def setProjectCrs(self):
        crs = QgsCoordinateReferenceSystem('EPSG:4326')
        project = QgsProject.instance()
        project.setCrs(crs)
        return crs

    def getOutFilePath(self):
        file_type = None
        algs = [
            ('TaCreateTopoBathy', 'PaleoDEM_withCreatedFeatures.tif', 'raster'),
            ('TaCompileTopoBathy', 'Compiled_DEM_Topo+Bathy.tif', 'raster'),
            ('TaModifyTopoBathy', 'PaleoDEM_modified_topography.tif', 'raster'),
            ('TaPrepareMasks', 'Extracted_general_masks.shp', 'vector'),
            ('TaRemoveArtefacts', 'PaleoDEM_withArtefactsRemoved.tif', 'raster'),
            ('TaSetPaleoshorelines', 'PaleoDEM_Paleoshorelines_set.tif', 'raster')
        ]

        temp_file_name = None
        for i in algs:
            if self.__class__.__name__ == i[0]:
                temp_file_name = i[1]
                file_type = i[2]
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
            try:
                self.feedback.error(ret[1])
            except:
                self.log.emit(ret[1])
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

    @staticmethod
    def getExpressionContext():
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())
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

    def startOver(self):
        self.killed = False

    def onRun(self):
        self.out_file_path = self.getOutFilePath()
