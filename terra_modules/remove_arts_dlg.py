
import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog
from qgis.core import (
    QgsMapLayerProxyModel, 
    QgsProject, 
    QgsVectorLayer, 
    QgsRasterLayer
    )

from .utils import loadHelp

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '../ui/remove_arts.ui'))

class TaRemoveArtefactsDlg(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaRemoveArtefactsDlg, self).__init__(parent)
        self.setupUi(self)

        # List comparison operators.TypeBox
       
        options = ['More than', 'Less than', 'Equal','Between']
        self.comparisonTypeBox.addItems(options)
        self.comparisonTypeBox.setCurrentIndex(0)
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.comparisonTypeBox.currentIndexChanged.connect(self.typeOfComparison)
        self.typeOfComparison()

        # Set the mode of QgsFileWidget to directory mode
        self.outputPath.setStorageMode(self.outputPath.SaveFile)
        self.outputPath.setFilter('*.tif;;*.tiff')

        #Set the run button enabled only when the user selected input layers.
        self.runButton.setEnabled(False)
        self.addButton.setEnabled(False)
        self.exprLineEdit.valueChanged.connect(self.enableRunButton)
        
        
        
        loadHelp(self)


    def typeOfComparison(self):
        current_index = self.comparisonTypeBox.currentIndex()
        if current_index == 0:
            self.exprLineEdit.setValue("H>")      
        elif current_index == 1:
            self.exprLineEdit.setValue("H<") 
           
        elif current_index==2:
            self.exprLineEdit.setValue("H==") 

        elif current_index==3:
            self.exprLineEdit.setValue("(H> )&(H< )") 
 
    def enableRunButton(self):
        val = self.exprLineEdit.value()
        if  val and "H" in val and (">" in val or "<" in val or "==" in val) and any(char.isdigit() for char in val) or val.lower()=="nodata" or val.lower()=="no data":
            self.runButton.setEnabled(True)
            self.addButton.setEnabled(True)
            self.warningLabel.setText('')
        else:
            self.warningLabel.setText('Please, provide a valid expression.')
            self.warningLabel.setStyleSheet('color:red')

   

    def setProgressValue(self, value):
        self.progressBar.setValue(value)

    def resetProgressValue(self):
        self.progressBar.setValue(0)






