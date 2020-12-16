from PyQt5.QtCore import QSettings, pyqtSignal

class TaSettings(QSettings):
    tempValueChanged = pyqtSignal(str, object)
    def __init__(self):
        super().__init__()
        self.removeArtefactsChecked = False
        #Temporary settings that will be reset, when Qgis closes
        self.temporarySettings = {}
    def setTempValue(self, key, value):
        self.temporarySettings[key]=value
        self.tempValueChanged.emit(key, value)


