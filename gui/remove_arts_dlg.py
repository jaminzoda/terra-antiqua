#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
#Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py


import os
import tempfile
from PyQt5.QtWidgets import QComboBox, QPushButton

from qgis.gui import QgsFileWidget
from .base_dialog import TaBaseDialog
from .widgets import TaExpressionWidget, TaCheckBox, TaColorSchemeWidget
from numpy import *


class TaRemoveArtefactsDlg(TaBaseDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaRemoveArtefactsDlg, self).__init__(parent)
        self.defineParameters()

    def defineParameters(self):
        self.comparisonTypeBox = self.addParameter(QComboBox,
                                                   "Choose a comparison operator")
        # List comparison operators

        options = ['More than', 'Less than', 'Equal','Between']
        self.comparisonTypeBox.addItems(options)
        self.comparisonTypeBox.setCurrentIndex(0)


        self.exprLineEdit = self.addMandatoryParameter(TaExpressionWidget,
                                                       "Enter your expression:")
        self.exprLineEdit.lineEdit.editingFinished.connect(self.formulaValidation)
        self.interpolateCheckBox = self.addParameter(TaCheckBox,
                                                     "Interpolate values for removed cells")
        self.addButton = self.addParameter(QPushButton, "Add more polygons")
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.comparisonTypeBox.currentIndexChanged.connect(self.typeOfComparison)

        #Add advanced parameters
        self.savePolygonsCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                              label = "Save mask layer.")

        self.masksOutputPath = self.addAdvancedParameter(QgsFileWidget,
                                                    label = "Output file path:")
        self.masksOutputPath.setStorageMode(self.masksOutputPath.SaveFile)
        self.masksOutputPath.setFilter('*.shp')
        default_file_path = os.path.join(tempfile.gettempdir(),
                                            "remove_artefacts_polygons.shp")
        if len(default_file_path)>68:
            d_path, f_path = os.path.split(default_file_path)
            for i in range(30):
                d_path, last_item = os.path.split(d_path)
                if len(os.path.join(last_item, f_path))<68:
                    if not last_item:
                        break
                    f_path = os.path.join(last_item, f_path)
                else:
                    default_file_path = os.path.join('...', f_path)
                    break
        self.masksOutputPath.lineEdit().setPlaceholderText(f"{default_file_path}")

        self.savePolygonsCheckBox.registerEnabledWidgets([self.masksOutputPath])

        self.typeOfComparison()
        self.fillDialog()


    def typeOfComparison(self):
        current_index = self.comparisonTypeBox.currentIndex()
        if current_index == 0:
            self.exprLineEdit.lineEdit.setValue("H>")
        elif current_index == 1:
            self.exprLineEdit.lineEdit.setValue("H<")

        elif current_index==2:
            self.exprLineEdit.lineEdit.setValue("H==")

        elif current_index==3:
            self.exprLineEdit.lineEdit.setValue("(H> )&(H< )")

    def formulaValidation(self):
        expression = self.exprLineEdit.lineEdit.value().lower()
        if expression == 'nodata' or expression == 'no data':
            return
        H = random.random((1800,3600))
        try:
            eval(self.exprLineEdit.lineEdit.value())
        except Exception as e:
            self.msgBar.pushWarning("Warning:", f"The entered expression is invalid: {e}.")
