#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py

from PyQt5.QtCore import QSettings, pyqtSignal

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


