#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - Qt/QGIS enum names written in full (e.g. Qt.AlignmentFlag.AlignCenter), as Qt6 requires (window flags)
#  See core/compat.py for the note on how this port was made.

import os
from qgis.PyQt.QtCore import Qt  # [QGIS4 port]
from qgis.PyQt import QtWidgets  # [QGIS4 port]
from qgis.PyQt import uic  # [QGIS4 port]
from .utils import loadHelp

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '../gui/remove_arts_tooltip.ui'))

class TaRemoveArtefactsTooltip(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaRemoveArtefactsTooltip, self).__init__(parent)
        self.setupUi(self)
        # enable custom window hint
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.CustomizeWindowHint)  # [QGIS4 port]

        # disable (but not hide) close button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)  # [QGIS4 port]

        #self.setWindowFlags(Qt.CustomizeWindowHint)
        #self.setWindowFlags(Qt.WindowCloseButtonHint, False)

        # List comparison operators.TypeBox

        self.showAgain = None
        self.isShowable()

        loadHelp(self)


    def isShowable(self):
        settings_file = os.path.join(os.path.dirname(__file__), '../resources/settings.txt')
        with open(settings_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for current,line in enumerate(lines):
            line = line.strip()
            if line == 'REMOVE_ARTEFACTS':
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
            pass
        else:
            with  open(settings_file, 'r', encoding='utf-8') as f:
                data = f.read()
                data_out = data.replace('first_help:show', 'first_help:hide')

            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write(data_out)
