import sys
import os
from PyQt5 import uic
from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog, QPushButton, QLabel
import logging
from qgis.gui import QgsFileWidget
from .logger import TaLogHandler, TaLogStream
from .template_dialog import TaTemplateDialog

class TaBaseDialog(TaTemplateDialog):
    is_run = QtCore.pyqtSignal(bool)
    cancelled = QtCore.pyqtSignal(bool)
    RUNNING = False
    CANCELED = False
    def __init__(self, parent=None):
        super(TaBaseDialog, self).__init__(parent)
        self.alg_name = self.getAlgName()
        self.parameters = []
        self.mandatory_parameters = []
        self.runButton.clicked.connect(self.runEvent)
        self.closeButton.clicked.connect(self.close)
        self.cancelButton.clicked.connect(self.cancelEvent)

        TaLogStream.stdout().messageWritten.connect( self.logBrowser.textCursor().insertHtml )
        #TaLogStream.stderr().messageWritten.connect( self.logText.insertPlainText )
        self.setDialogTitle()
        self.loadHelp()

    def setDialogTitle(self):
        self.setWindowTitle("Terra Antiqua - {}".format(self.alg_name))


    def createFeedback(self):
        feedback = logging.getLogger(self.alg_name)
        if len(feedback.handlers):
            for handler in feedback.handlers:
                feedback.removeHandler(handler)

        handler = TaLogHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt='%Y-%m-%d %I:%M:%S'))
        feedback.addHandler(handler)
        feedback.setLevel(logging.DEBUG)
        return feedback



    def addMandatoryParameter(self, param, label=None, widget_type=None):
        if label:
            label = f"{label} *"
        mandatory_param = self.addParameter(param, label, widget_type)
        self.mandatory_parameters.append(mandatory_param)
        try:
            mandatory_param.setAllowEmptyLayer(False)
        except Exception:
            pass
        return mandatory_param

    def addParameter(self, param, label=None, widget_type=None):
        if widget_type == 'TaMapLayerComboBox':
            if label:
                self.param = param(label)
            else:
                self.param = param()
        elif widget_type == 'CheckBox':
            try:
                self.param = param(label)
            except:
                self.param()
        elif widget_type == "GroupLabel":
            self.param = param(label)
        else:
            if label:
                label = QLabel(label)
                self.parameters.append(label)
                self.param = param()
            else:
                self.param = param()
        self.parameters.append(self.param)
        if widget_type == 'TaMapLayerComboBox':
            return self.param.getMainWidget()
        else:
            return self.param


    def getParameters(self):
        pass

    def fillDialog(self, add_output_path=True):
        for parameter in self.parameters:
            self.paramsLayout.addWidget(parameter)

        if add_output_path:
            self.outputPath = QgsFileWidget()
            self.outputPath.setStorageMode(self.outputPath.SaveFile)
            self.outputPath.setFilter('*.tif;;*.tiff')
            self.paramsLayout.addWidget(QLabel('Output file path'))
            self.paramsLayout.addWidget(self.outputPath)
        self.paramsLayout.addStretch()

        for parameter in self.mandatory_parameters:
            if type(parameter).__name__ == 'QgsMapLayerComboBox':
                parameter.layerChanged.connect(self.checkMandatoryParameters)

    def checkMandatoryParameters(self):
        param_checks = []
        for parameter in self.mandatory_parameters:
            #TODO if other widget types are added as mandatory parameter
            # a new elif checks should be added
            if type(parameter).__name__ == 'QgsMapLayerComboBox':
                param_checks.append(bool(parameter.currentLayer()))

        if all(param_checks):
            self.warnLabel.setText('')
            return True
        else:
            self.warnLabel.setText('Please, select all the mandatory fields.')
            self.warnLabel.setStyleSheet('color:red')
            return False

    def setProgressValue(self, value):
        self.progressBar.setValue(value)

    def resetProgressValue(self):
        self.progressBar.setValue(0)

    def getAlgName(self):
        class_names = {
            'TaCompileTopoBathyDlg':'Compile Topo/Bathymetry',
            'TaSetPaleoshorelinesDlg': 'Set Paleoshorelines',
            'TaModifyTopoBathyDlg': 'Modify Topo/Bathymetry',
            'TaCreateTopoBathyDlg': 'Create Topo/Bathymetry',
            'TaRemoveArtefactsDlg': 'Remove Artefacts',
            'TaPrepareMasksDlg': 'Prepare Masks',
            'TaStandardProcessingDlg': 'Standard Processing'
            }

        alg_name = None
        for class_name in class_names:
            if class_name == self.__class__.__name__:
                alg_name = class_names.get(class_name)

        if not alg_name:
            alg_name = 'NoName'

        return alg_name

    def loadHelp(self):
        #set the help text in the  help box (QTextBrowser)
        files = [
                ('TaCompileTopoBathyDlg', 'compile_tb'),
                ('TaSetPaleoshorelinesDlg', 'set_pls'),
                ('TaModifyTopoBathyDlg', 'modify_tb'),
                ('TaCreateTopoBathyDlg', 'create_tb'),
                ('TaRemoveArtefactsDlg', 'remove_arts'),
                ('TaPrepareMasksDlg', 'prepare_masks'),
                ('TaRemoveArtefactsTooltip', 'remove_arts_tooltip')
                ]
        for class_name, file_name in files:
            if class_name    == type(self).__name__:
                path_to_file = os.path.join(os.path.dirname(__file__),'../help_text/{}.html'.format(file_name))

        with open(path_to_file, 'r', encoding='utf-8') as help_file:
            help_text = help_file.read()
        self.helpTextBox.setHtml(help_text)

    def runEvent(self):
        if self.checkMandatoryParameters() and not self.RUNNING:
            self.logBrowser.clear()
            self.is_run.emit(True)
            self.warnLabel.setText('')
            self.resetProgressValue()

            try:
                self.tabWidget.setCurrentIndex(1)
            except Exception:
                pass
            self.RUNNING = True
        elif not self.RUNNING and not self.checkMandatoryParameters():
            self.warnLabel.setText('Please, select all the mandatory fields.')
            self.warnLabel.setStyleSheet('color:red')
        elif self.checkMandatoryParameters() and self.RUNNING:
            self.warnLabel.setText('The algorithm is running.')
            self.warnLabel.setStyleSheet('color:red')

    def showEvent(self, event):
        self.tabWidget.setCurrentIndex(0)

    def closeEvent(self, event):
        self.logBrowser.clear()
        self.deleteLater()
        self = None

    def cancelEvent(self):
        if self.RUNNING:
            self.cancelled.emit(True)
            self.resetProgressValue()
            self.warnLabel.setText('Error!')
            self.warnLabel.setStyleSheet('color:red')
            self.RUNNING = False
            self.CANCELED = True

    def finishEvent(self):
        self.warnLabel.setText('Done!')
        self.warnLabel.setStyleSheet('color:green')
        self.RUNNING = False
    def isCanceled(self):
        return self.CANCELED
