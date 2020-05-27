from PyQt5.QtCore import (
    QThread,
    pyqtSignal
)
import logging
from PyQt5 import QtWidgets
from .logger import TaLogger

class TaAlgorithmProvider(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, object)
    log = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self.killed = False
        self.progress_count = 0
#        self.logTextBox = TaLogger(self.dlg)
#        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
#        logging.getLogger().addHandler(self.logTextBox)
#
#        # You can control the logging level
#        logging.getLogger().setLevel(logging.DEBUG)
#        self.log_tab = QtWidgets.QWidget()
#        self.dlg.Tabs.addTab(self.log_tab, "Logging")
#        self.log_tab.layout = QtWidgets.QVBoxLayout(self.dlg)
#        self.log_tab.layout.addWidget(self.logTextBox.widget)
#        self.log_tab.setLayout(self.log_tab.layout)
#
    @property
    def set_progress(self):
        return self.progress_count

    @set_progress.setter
    def set_progress(self, value):
        self.progress_count = value
        self.emit_progress(self.progress_count)

    def emit_progress(self, progress_count):
        self.progress.emit(progress_count)

    def kill(self):
        self.killed = True


