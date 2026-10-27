#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
#Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - Qt/QGIS enum names written in full (e.g. Qt.AlignmentFlag.AlignCenter), as Qt6 requires
#  - exec_() replaced by exec()
#  - Logo loaded from the resources/ folder through compat.icon_path (resources.py removed)
#  See core/compat.py for the note on how this port was made.

import os
from qgis.PyQt import QtWidgets  # [QGIS4 port]
from qgis.PyQt import QtGui  # [QGIS4 port]
from qgis.PyQt import QtCore  # [QGIS4 port]
from ..core.compat import icon_path  # [QGIS4 port]


class TaWelcomeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TaWelcomeDialog, self).__init__(parent)
        self.setGeometry(200, 200, 700, 300)
        self.logo = QtGui.QIcon(icon_path('logo.png'))  # [QGIS4 port]
        self.toolButton = QtWidgets.QToolButton(self)
        self.toolButton.setIcon(self.logo)
        self.toolButton.setIconSize(QtCore.QSize(150,150))
        self.toolButton.setAutoRaise(False)
        self.introBrowser = QtWidgets.QTextBrowser(self)
        self.introBrowser.setOpenExternalLinks(True)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.toolButton, alignment = QtCore.Qt.AlignmentFlag.AlignTop)  # [QGIS4 port]
        self.layout.addWidget(self.introBrowser)
        self.hlayout = QtWidgets.QHBoxLayout()
        self.doNotShowCheckBox = QtWidgets.QCheckBox("Do not show this again")
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)  # [QGIS4 port]
        self.hlayout.addStretch()
        self.hlayout.addWidget(self.doNotShowCheckBox)
        self.hlayout.addWidget(self.buttonBox,QtCore.Qt.AlignmentFlag.AlignRight)  # [QGIS4 port]
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
    app.exec()  # [QGIS4 port]
