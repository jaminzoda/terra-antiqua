
import os
from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets
from PyQt5 import uic
from .utils import loadHelp

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '../ui/remove_arts_tooltip.ui'))

class TaRemoveArtefactsTooltip(QtWidgets.QDialog, FORM_CLASS):
	def __init__(self, parent=None):
		"""Constructor."""
		super(TaRemoveArtefactsTooltip, self).__init__(parent)
		self.setupUi(self)
		# enable custom window hint
		self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)

		# disable (but not hide) close button
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
		
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
		settings_file2 = os.path.join(os.path.dirname(__file__), '../resources/settings2.txt')
		if value:
			pass
		else:
			with  open(settings_file, 'r', encoding='utf-8') as f:
				data = f.read()
				data_out = data.replace('first_help:show', 'first_help:hide')
			
			with open(settings_file, 'w', encoding='utf-8') as f:
				f.write(data_out) 
