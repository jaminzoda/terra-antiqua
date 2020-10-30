import sys
import os
from PyQt5 import uic
from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QLabel,
    QShortcut
)
import logging
from qgis.gui import QgsFileWidget
from .logger import TaLogHandler, TaLogStream, TaFeedback
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
        self.variant_parameters = []
        self.runButton.clicked.connect(self.runEvent)
        self.closeButton.clicked.connect(self.close)
        self.cancelButton.clicked.connect(self.cancelEvent)
        self.setKeyboardShortcuts()

        self.setDialogTitle()
        self.loadHelp()

    def setDialogTitle(self):
        self.setWindowTitle("Terra Antiqua - {}".format(self.alg_name))


    def createFeedback(self):
        feedback = TaFeedback(self)
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
        if label:
            try:
                param = param(label)
            except Exception:
                label = QLabel(label)
                self.parameters.append(label)
                param = param()
        else:
            param = param()
        self.parameters.append(param)
        if widget_type == 'TaMapLayerComboBox':
            return param.getMainWidget()
        else:
            return param

    def addVariantParameter(self, param, variant_index, label = None, widget_type = None):
        if label:
            try:
                param = param(label)
            except Exception:
                label = QLabel(label)
                self.variant_parameters.append((label, variant_index))
                param = param()
        else:
            param = param()
        self.variant_parameters.append((param,variant_index))
        if widget_type == 'TaMapLayerComboBox':
            return param.getMainWidget()
        else:
            return param
    def getParameters(self):
        pass

    def fillDialog(self, add_output_path=True):
        for parameter in self.parameters:
            self.paramsLayout.addWidget(parameter)

        if len(self.variant_parameters)>0:
            self.appendVariantWidgets()

        if add_output_path:
            self.outputPath = QgsFileWidget()
            self.outputPath.setStorageMode(self.outputPath.SaveFile)
            self.outputPath.setFilter('*.tif;;*.tiff')
            self.outputPath.lineEdit().setPlaceholderText("[Create temporary layer]")
            self.paramsLayout.addWidget(QLabel('Output file path'))
            self.paramsLayout.addWidget(self.outputPath)
        self.paramsLayout.addStretch()


        for parameter in self.mandatory_parameters:
            if type(parameter).__name__ == 'QgsMapLayerComboBox':
                parameter.layerChanged.connect(self.checkMandatoryParameters)
    def appendVariantWidgets(self):
        for param, variant_index in self.variant_parameters:
            self.paramsLayout.addWidget(param)
    def showVariantWidgets(self, index):
        for param, variant_index in self.variant_parameters:
            if variant_index != index:
                param.hide()
            else:
                param.show()


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
        with open("log.txt", "a") as log_file:
            log_file.write("On ProgressBar: {}\n".format(value))

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
            self.RUNNING = True
            self.logBrowser.clear()
            self.is_run.emit(True)
            self.warnLabel.setText('')
            self.resetProgressValue()

            try:
                self.tabWidget.setCurrentIndex(1)
            except Exception:
                pass
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

    def setKeyboardShortcuts(self):
        self.shortcuts = {}
        self.shortcuts["Run"] = QShortcut(self)
        self.shortcuts["Run"].setContext(QtCore.Qt.ApplicationShortcut)
        self.shortcuts["Run"].setKey(QtCore.Qt.Key_Enter)
        self.shortcuts["Run"].activated.connect(self.runButton.click)
