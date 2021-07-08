#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
#Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py

import os
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore


class TaWelcomeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TaWelcomeDialog, self).__init__(parent)
        self.setGeometry(200, 200, 700, 300)
        self.logo = QtGui.QIcon(':/logo.png')
        self.toolButton = QtWidgets.QToolButton(self)
        self.toolButton.setIcon(self.logo)
        self.toolButton.setIconSize(QtCore.QSize(150,150))
        self.toolButton.setAutoRaise(False)
        self.introBrowser = QtWidgets.QTextBrowser(self)
        self.introBrowser.setOpenExternalLinks(True)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.toolButton, alignment = QtCore.Qt.AlignTop)
        self.layout.addWidget(self.introBrowser)
        self.hlayout = QtWidgets.QHBoxLayout()
        self.doNotShowCheckBox = QtWidgets.QCheckBox("Do not show this again")
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        self.hlayout.addStretch()
        self.hlayout.addWidget(self.doNotShowCheckBox)
        self.hlayout.addWidget(self.buttonBox,QtCore.Qt.AlignRight)
        self.vlayout = QtWidgets.QVBoxLayout()
        self.vlayout.addLayout(self.layout)
        self.vlayout.addLayout(self.hlayout)
        self.setLayout(self.vlayout)
        self.setWindowTitle("Welcome to Terra Antiqua!")
        path_to_file = os.path.join(os.path.dirname(__file__),'../help_text/welcome.html')
        with open(path_to_file, 'r', encoding='utf-8') as help_file:
            help_text = help_file.read()
        self.introBrowser.setHtml(help_text)
        self.buttonBox.accepted.connect(self.accept)
        self.showAgain = None
        self.isShowable()

    def accept(self):
        if self.doNotShowCheckBox.isChecked():
            self.setShowable(False)
        self.close()

    def isShowable(self):
        settings_file = os.path.join(os.path.dirname(__file__), '../resources/settings.txt')
        with open(settings_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for current,line in enumerate(lines):
            line = line.strip()
            if line == 'WELCOME_PAGE':
                settings_line = lines[current+1].strip()
                setting = settings_line.split(':')[1]
                if setting == 'hide':
                    self.showAgain = False
                else:
                    self.showAgain = True

    def setShowable(self, value):
        data_out = None
        settings_file = os.path.join(os.path.dirname(__file__), '../resources/settings.txt')
        if value:
            with  open(settings_file, 'r', encoding='utf-8') as f:
                data = f.read()
                if not self.showAgain:
                    data_out = data.replace('show_again:hide','show_again:show')
        else:
            with  open(settings_file, 'r', encoding='utf-8') as f:
                data = f.read()
                if self.showAgain:
                    data_out = data.replace('show_again:show', 'show_again:hide')

        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(data_out)



if __name__=='__main__':
    app = QtWidgets.QApplication([])
    dlg = TaWelcomeDialog()
    dlg.show()
    app.exec_()
