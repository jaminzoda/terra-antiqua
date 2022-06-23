# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py


import imp
import os
from tkinter import W, Spinbox
from typing import Any, Dict
import webbrowser as wb
from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QShortcut,
    QSizePolicy,
    QCheckBox,
    QComboBox
)
from numpy import isin
from qgis.gui import (
    QgsFileWidget,
    QgsMessageBar,
    QgsCollapsibleGroupBox,
    QgsSpinBox,
    QgsDoubleSpinBox
)
from qgis.core import (QgsMapLayerProxyModel, QgsProperty)

from ..core.proc_params import TaProcessingParameters

from .widgets import (
    TaAbstractMapLayerComboBox,
    TaCheckBox,
    TaExpressionWidget,
    TaMapLayerComboBox,
    TaRasterCompilerTableWidget,
    TaSpinBox,
    TaTableWidget
)
from ..core.logger import TaFeedback
from .template_dialog import TaTemplateDialog


class TaBaseDialog(TaTemplateDialog):
    is_run = QtCore.pyqtSignal(bool)
    cancelled = QtCore.pyqtSignal(bool)
    dialog_name_changed = QtCore.pyqtSignal()
    RUNNING = False
    CANCELED = False

    def __init__(self, parent=None):
        super(TaBaseDialog, self).__init__(parent)
        self.alg_name = self.getAlgName()
        self.dlg_name = self.__class__.__name__
        self.parameters = []
        self.mandatory_parameters = []
        self.variant_parameters = []
        self.advanced_parameters = []
        self.parameters_order = {}
        self.parameters_added = 0
        self.var_index = None
        self.runButton.clicked.connect(self.runEvent)
        self.closeButton.clicked.connect(self.close)
        self.cancelButton.clicked.connect(self.cancelEvent)
        self.helpButton.clicked.connect(self.openManual)
        self.msgBar = QgsMessageBar(self)
        self.msgBar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.layout().insertWidget(0, self.msgBar)
        self.setKeyboardShortcuts()

        self.setDialogTitle()
        self.loadHelp()

    def setDialogTitle(self):
        self.setWindowTitle("Terra Antiqua - {}".format(self.alg_name))

    def setDialogName(self, name):
        self.dlg_name = name
        self.dialog_name_changed.emit()

    def createFeedback(self):
        feedback = TaFeedback(self)
        return feedback

    def addMandatoryParameter(self,
                              param: str,
                              label: str = None,
                              widget_type: str = None,
                              param_id: str = None) -> QWidget:
        """Adds parameter widget to the list of parameters and marks it as mandatory.
        :param param: The parameter widget to be added.
        :type param: QWidget.
        :param label: Label for the parameter to be added.
        :type label: str.
        :param widget_type: Widget type. Currently supports only TaAbstractMapLayerComboBox.
        If the parameter to be added is of TaAbstractMapLayerComboBox type, the maplayer combobox
        will be returned by calling parameter.getMainWidget()
        :type widget_type: str.
        :param param_id: parameter id that will be used from within the algorithm to access the
        value of the parameter.
        :type patam_id: str.

        :return: the added parameter widget.
        :rtype: QWidget."""
        if label:
            label = f"{label} *"
        mandatory_param = self.addParameter(param,
                                            label=label,
                                            widget_type=widget_type,
                                            param_id=param_id)
        self.mandatory_parameters.append(mandatory_param)
        try:
            mandatory_param.setAllowEmptyLayer(False)
        except Exception:
            pass
        return mandatory_param

    def addParameter(self,
                     param: str,
                     label: str = None,
                     widget_type: str = None,
                     param_id: str = None) -> QWidget:
        """Adds parameter widget to the list of parameters to be able to show it on the dialog.
        :param param: The parameter widget to be added.
        :type param: QWidget.
        :param label: Label for the parameter to be added.
        :type label: str.
        :param widget_type: Widget type. Currently supports only TaAbstractMapLayerComboBox.
        If the parameter to be added is of TaAbstractMapLayerComboBox type, the maplayer combobox
        will be returned by calling parameter.getMainWidget()
        :type widget_type: str.
        :param param_id: parameter id that will be used from within the algorithm to access the
        value of the parameter.
        :type patam_id: str.

        :return: the added parameter widget.
        :rtype: QWidget."""
        if label:
            try:
                param = param(label)
            except Exception:
                label = QLabel(label)
                self.parameters.append((label, param_id))
                param = param()
        else:
            param = param()
        self.parameters.append((param, param_id))
        self.parameters_added += 1
        self.parameters_order[param_id] = self.parameters_added
        if widget_type == 'TaMapLayerComboBox':
            return param.getMainWidget()
        else:
            return param

    def addVariantParameter(self,
                            param: QWidget,
                            variant_index: str,
                            label: str = None,
                            widget_type: str = None,
                            mandatory: bool = False,
                            param_id: str = None) -> QWidget:
        """Adds a variant parameter widget to the list of parameters to be able to show it on the dialog.
        :param param: The parameter widget to be added.
        :type param: QWidget.
        :param label: Label for the parameter to be added.
        :type label: str.
        :param widget_type: Widget type. Currently supports only TaAbstractMapLayerComboBox.
        If the parameter to be added is of TaAbstractMapLayerComboBox type, the maplayer combobox
        will be returned by calling parameter.getMainWidget()
        :type widget_type: str.
        :param variant_index: In a dialog with multiple algorithms this specifies index  (name) of that algorithm
        the parameter is shown only, if that index is chosen in the appropriate combobox.
        :type variant_index: str.
        :param param_id: parameter id that will be used from within the algorithm to access the
        value of the parameter.
        :type patam_id: str

        :return: the added parameter widget.
        :rtype: QWidget."""
        if label and mandatory:
            label = f"{label} *"
        if label:
            try:
                param = param(label)
            except Exception:
                label = QLabel(label)
                self.variant_parameters.append(
                    (label, variant_index, False, param_id))
                param = param()
        else:
            param = param()
        if mandatory:
            self.variant_parameters.append(
                (param, variant_index, True, param_id))
            try:
                param.getMainWidget().setAllowEmptyLayer(False)
            except Exception:
                pass
        else:
            self.variant_parameters.append(
                (param, variant_index, False, param_id))
        self.parameters_added += 1
        self.parameters_order[param_id] = self.parameters_added

        if widget_type == 'TaMapLayerComboBox':
            return param.getMainWidget()
        else:
            return param

    def addAdvancedParameter(self,
                             param: QWidget,
                             label: str = None,
                             widget_type: str = None,
                             variant_index: str = None,
                             param_id: str = None) -> QWidget:
        """Adds advanced parameters to the dialog.
        :param param: A parameter widget to be added.
        :type param: QWidget.
        :param label: Label for the parameter to be added.
        :type label: str.
        :param widget_type: Widget type. Currently supports only TaAbstractMapLayerComboBox.
        If the parameter to be added is of TaAbstractMapLayerComboBox type, the maplayer combobox
        will be returned by calling parameter.getMainWidget()
        :type widget_type: str.
        :param variant_index: If this keyword argument is specified the parameter will be shown only case
        a specified combobox containt the string as the variant_index ->  to be signal connected in the tools dialog
        i.e. TaStandardProcessingDlg.
        :type variant_index: str.

        :return: Handle to the newly added widget.
        :rtype: QWidget
        """
        if label:
            try:
                param = param(label)
            except Exception:
                label = QLabel(label)
                self.advanced_parameters.append(
                    (label, variant_index, param_id))
                param = param()
        else:
            param = param()
        self.advanced_parameters.append((param, variant_index, param_id))
        self.parameters_added += 1
        self.parameters_order[param_id] = self.parameters_added
        if widget_type == 'TaMapLayerComboBox':
            return param.getMainWidget()
        else:
            return param

    def getParameters(self) -> list:
        """Returns a list of main paramaters."""
        return self.parameters

    def getAdvancedParameters(self) -> list:
        """Returns a list of advanced parameters. """
        return self.advanced_parameters

    def getVariantParameters(self) -> list:
        """Returns a list of variant parameters."""
        return self.variant_parameters

    def fillDialog(self, add_output_path=True):
        parameters, _ = zip(*self.parameters)
        for parameter in parameters:
            self.paramsLayout.addWidget(parameter)

        if len(self.variant_parameters) > 0:
            self.appendVariantWidgets()

        if len(self.advanced_parameters) > 0:
            self.appendAdvancedWidgets()

        if add_output_path:
            self.outputPath = QgsFileWidget()
            self.outputPathLabel = QLabel('Output file path:')
            self.outputPath.setStorageMode(self.outputPath.SaveFile)
            self.outputPath.setFilter('*.tif;;*.tiff')
            self.paramsLayout.addWidget(self.outputPathLabel)
            self.paramsLayout.addWidget(self.outputPath)
            self.parameters.append((self.outputPath, "outputPath"))
            self.parameters_added += 1
            self.parameters_order["outputPath"] = self.parameters_added
        self.paramsLayout.addStretch()

        for parameter in self.mandatory_parameters:
            if type(parameter).__name__ == 'TaAbstractMapLayerComboBox':
                parameter.layerChanged.connect(self.checkMandatoryParameters)

    def appendVariantWidgets(self):
        for param, variant_index, mandatory, param_id in self.variant_parameters:
            self.paramsLayout.addWidget(param)

    def showVariantWidgets(self, index):
        self.var_index = index
        for param, variant_index, mandatory, param_id in self.variant_parameters:
            if variant_index != index:
                param.hide()
            else:
                param.show()
        if len(self.advanced_parameters) > 0:
            self.showAdvancedWidgets(index)

    def appendAdvancedWidgets(self):
        """Appends advanced parameters' widgets to the dialog."""
        self.group_box = QgsCollapsibleGroupBox(self)
        self.group_box.setTitle("Advanced parameters")
        self.group_box.setCollapsed(True)
        self.group_box.collapsedStateChanged.connect(
            lambda state: self.showAdvancedWidgets(self.var_index) if not state else None)
        layout = QVBoxLayout()
        for widget, variant_index, param_id in self.advanced_parameters:
            layout.addWidget(widget)
        self.group_box.setLayout(layout)
        self.paramsLayout.addWidget(self.group_box)

    def showAdvancedWidgets(self, index):
        widgets_to_show = 0
        for param, variant_index, param_id in self.advanced_parameters:
            if variant_index and variant_index != index:
                param.hide()
            else:
                param.show()
                widgets_to_show += 1
        if widgets_to_show == 0:
            self.group_box.hide()
        else:
            self.group_box.show()

    def checkMandatoryParameters(self):
        param_checks = []
        for parameter in self.mandatory_parameters:
            # TODO if other widget types are added as mandatory parameter
            # a new elif checks should be added
            if type(parameter).__name__ == 'TaAbstractMapLayerComboBox':
                param_checks.append(bool(parameter.currentLayer()))

        for parameter, variant_index, mandatory, param_id in self.variant_parameters:
            if variant_index == self.var_index and mandatory:
                if type(parameter.getMainWidget()).__name__ == 'TaAbstractMapLayerComboBox':
                    param_checks.append(
                        bool(parameter.getMainWidget().currentLayer()))

        if all(param_checks):
            return True
        else:
            return False

    def setProgressValue(self, value):
        self.progressBar.setValue(value)

    def resetProgressValue(self):
        self.progressBar.setValue(0)

    def getAlgName(self):
        class_names = {
            'TaCompileTopoBathyDlg': 'Compile Topo/Bathymetry',
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
        # set the help text in the  help box (QTextBrowser)
        files = [
            ('TaCompileTopoBathyDlg', 'compile_tb'),
            ('TaSetPaleoshorelinesDlg', 'set_pls'),
            ('TaModifyTopoBathyDlg', 'modify_tb'),
            ('TaCreateTopoBathyDlg', 'create_tb'),
            ('TaRemoveArtefactsDlg', 'remove_arts'),
            ('TaPrepareMasksDlg', 'prepare_masks'),
            ('TaRemoveArtefactsTooltip', 'remove_arts_tooltip'),
            ('TaStandardProcessingDlg', 'fill_gaps'),
            ('TaFillGaps', 'fill_gaps'),
            ('TaCopyPasteRaster', 'copy_paste'),
            ('TaSmoothRaster', 'smoothing'),
            ('TaIsostaticCompensation', 'isostat_cp'),
            ('TaSetSeaLevel', 'set_sl'),
            ('TaCalculateBathymetry', 'calc_bathy'),
            ('TaChangeMapSymbology', 'change_symbology')
        ]
        for class_name, file_name in files:
            if class_name == self.dlg_name:
                path_to_file = os.path.join(os.path.dirname(
                    __file__), '../help_text/{}.html'.format(file_name))

        with open(path_to_file, 'r', encoding='utf-8') as help_file:
            help_text = help_file.read()
        self.helpTextBox.setHtml(help_text)

    def openManual(self):
        path_to_manual = 'https://jaminzoda.github.io/terra-antiqua-documentation/'
        wb.open(path_to_manual)

    def setDefaultOutFilePath(self, outFilePath):
        """Sets the default output file path for each tool. For now the default folder for storing
        the output files is the OS's temporary folder.
        :param outFilePath: default ouput file path. An absolute file path for stroting the results of the tools.
        :type outFilePath: str
        """
        if len(outFilePath) > 68:
            d_path, f_path = os.path.split(outFilePath)
            for i in range(30):
                d_path, last_item = os.path.split(d_path)
                if len(os.path.join(last_item, f_path)) < 68:
                    if not last_item:
                        break
                    f_path = os.path.join(last_item, f_path)
                else:
                    outFilePath = os.path.join('...', f_path)
                    break

        self.outputPath.lineEdit().setPlaceholderText(f"{outFilePath}")

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
