#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  See core/compat.py for the note on how this port was made.

from qgis.PyQt.QtCore import QSettings, pyqtSignal  # [QGIS4 port]

class TaSettings(QSettings):
    tempValueChanged = pyqtSignal(str, object)
    def __init__(self, company_name, application_name):
        super().__init__(company_name, application_name)
        self.removeArtefactsChecked = False
        #Temporary settings that will be reset, when Qgis closes
        self.temporarySettings = {}
    def setTempValue(self, key, value):
        self.temporarySettings[key]=value
        self.tempValueChanged.emit(key, value)


