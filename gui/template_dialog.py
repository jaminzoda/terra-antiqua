# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

import os
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore
from .widgets import TaHelpBrowser


class TaTemplateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TaTemplateDialog, self).__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)

        self.setGeometry(200, 200, 900, 600)
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.paramsScrollArea = QtWidgets.QScrollArea()
        self.paramsScrollArea.setAlignment(QtCore.Qt.AlignTop)
        self.paramsScrollArea.setWidgetResizable(True)
        self.paramsWidget = QtWidgets.QWidget()
        self.paramsLayout = QtWidgets.QVBoxLayout()
        self.paramsWidget.setLayout(self.paramsLayout)
        self.paramsScrollArea.setWidget(self.paramsWidget)

        self.tabWidget.addTab(self.paramsScrollArea, 'Parameters')
        self.logBrowser = QtWidgets.QTextBrowser(self)
        self.logBrowser.setOpenExternalLinks(True)
        self.tabWidget.addTab(self.logBrowser, 'Log')
        self.helpTextBox = TaHelpBrowser(self)
        self.helpTextBox.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        try:
            self.helpTextBox.placeholderText = "Your log will be shown here."
        except:
            pass
        self.iconRight = QtGui.QIcon(':/arrow_right.png')
        self.iconLeft = QtGui.QIcon(':/arrow_left.png')
        self.collapseButton = QtWidgets.QToolButton(self)
        self.collapseButton.setIcon(self.iconRight)
        self.collapseButton.setIconSize(QtCore.QSize(8, 8))
        self.collapseButton.setAutoRaise(True)
        self.tabWidget.setCornerWidget(
            self.collapseButton, QtCore.Qt.TopRightCorner)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.addWidget(self.tabWidget)
        self.splitter.addWidget(self.helpTextBox)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([480, 300])
        self.splitter.setCollapsible(0, False)
        self.progressBar = QtWidgets.QProgressBar()
        self.cancelButton = QtWidgets.QPushButton()
        self.cancelButton.setText('Cancel')
        self.progressLayout = QtWidgets.QHBoxLayout()
        self.progressLayout.addWidget(self.progressBar)
        self.progressLayout.addWidget(self.cancelButton)
        self.warnLabel = QtWidgets.QLabel()
        self.closeButton = QtWidgets.QPushButton()
        self.closeButton.setText('Close')
        self.runButton = QtWidgets.QPushButton()
        self.runButton.setText('Run')
        self.helpButton = QtWidgets.QPushButton()
        self.helpButton.setText('Help')
        self.helpButton.setToolTip("Open user manual")
        self.saveParametersButton = QtWidgets.QPushButton()
        self.saveParametersButton.setText("Save parameters")
        self.saveParametersButton.setToolTip("Save parameters for later use")
        self.runLayout = QtWidgets.QHBoxLayout()
        self.runLayout.addWidget(self.helpButton)
        self.runLayout.addWidget(self.saveParametersButton)
        self.runLayout.addWidget(self.warnLabel)
        self.runLayout.addStretch()
        self.runLayout.addWidget(self.closeButton)
        self.runLayout.addWidget(self.runButton)

        self.dialogLayout = QtWidgets.QVBoxLayout()
        self.dialogLayout.setSpacing(5)
        self.dialogLayout.addWidget(self.splitter)
        self.dialogLayout.addLayout(self.progressLayout)
        self.dialogLayout.addLayout(self.runLayout)
        self.setLayout(self.dialogLayout)

        # Signals Connection
        self.collapseButton.pressed.connect(self.hideHelpTextBox)
        self.tabWidget.currentChanged.connect(self.onSwitchTab)
        self.helpTextBox.visibilityChanged.connect(
            self.changeCollapseButtonIcon)
        self.splitter.splitterMoved.connect(self.splitterCollapsed)

    def onSwitchTab(self, tab):
        max_size = sum(self.splitter.sizes())
        min_size = round(max_size*0.62)
        if tab == 0:
            if self.helpTextBox.collapsed:
                self.splitter.moveSplitter(min_size, 1)
        else:
            if not self.helpTextBox.collapsed:
                self.splitter.moveSplitter(max_size, 1)

    def hideHelpTextBox(self):
        max_size = sum(self.splitter.sizes())
        min_size = round(max_size*0.62)
        if self.helpTextBox.collapsed:
            self.splitter.moveSplitter(min_size, 1)
            self.helpTextBox.collapsed = False
        else:
            self.splitter.moveSplitter(max_size, 1)
            self.helpTextBox.collapsed = True

    def changeCollapseButtonIcon(self, state):
        if state:
            self.collapseButton.setIcon(self.iconRight)
        else:
            self.collapseButton.setIcon(self.iconLeft)

    def splitterCollapsed(self, pos, index):
        max_size = sum(self.splitter.sizes())
        if pos >= max_size:
            self.changeCollapseButtonIcon(False)
            self.helpTextBox.collapsed = True
        else:
            self.changeCollapseButtonIcon(True)
            self.helpTextBox.collapsed = False


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    dlg = TaTemplateDialog()
    dlg.show()
    app.exec_()
