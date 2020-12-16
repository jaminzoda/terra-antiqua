
import os

from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QFileDialog, QComboBox, QPushButton
from qgis.core import (
    QgsMapLayerProxyModel,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer
    )

from .base_dialog import TaBaseDialog
from .widgets import TaExpressionWidget, TaCheckBox


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
        self.interpolateCheckBox = self.addParameter(TaCheckBox,
                                                     "Interpolate values for removed cells")
        self.addButton = self.addParameter(QPushButton, "Add more polygons")
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.comparisonTypeBox.currentIndexChanged.connect(self.typeOfComparison)
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







