# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - Python built-ins abs, bool, max, min, pow and round restored after "from numpy import *",
#    because NumPy 2 (bundled with QGIS 4) would otherwise replace them
#  - Qt/QGIS enum names written in full, as Qt6 requires (file widget mode)
#  - formulaValidation: uses core/expressions.evaluate instead of eval()
#  See core/compat.py for the note on how this port was made.


import os
import tempfile
from qgis.PyQt.QtWidgets import QComboBox, QPushButton  # [QGIS4 port]

from qgis.gui import QgsFileWidget
from .base_dialog import TaBaseDialog
from .widgets import TaExpressionWidget, TaCheckBox, TaColorSchemeWidget
from numpy import *
# NumPy 2.x (bundled with QGIS 4) also exports abs, bool, max, min, pow and round, which would
# replace Python's built-ins in this module. Restore them so behaviour matches NumPy 1.x.
from builtins import abs, bool, max, min, pow, round  # noqa: E402,F811  # [QGIS4 port]
from ..core.expressions import evaluate  # noqa: E402  # [QGIS4 port]


class TaRemoveArtefactsDlg(TaBaseDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(TaRemoveArtefactsDlg, self).__init__(parent)
        self.defineParameters()

    def defineParameters(self):
        self.comparisonTypeBox = self.addParameter(QComboBox,
                                                   "Choose a comparison operator")
        # List comparison operators

        options = ['More than', 'Less than', 'Equal', 'Between']
        self.comparisonTypeBox.addItems(options)
        self.comparisonTypeBox.setCurrentIndex(0)

        self.exprLineEdit = self.addMandatoryParameter(TaExpressionWidget,
                                                       "Enter your expression:")
        self.exprLineEdit.lineEdit.editingFinished.connect(
            self.formulaValidation)
        self.interpolateCheckBox = self.addParameter(TaCheckBox,
                                                     "Interpolate values for removed cells")
        self.addButton = self.addParameter(QPushButton, "Add more polygons")
        # Elements of dialog are changed appropriately, when a filling type is selected
        self.comparisonTypeBox.currentIndexChanged.connect(
            self.typeOfComparison)

        # Add advanced parameters
        self.savePolygonsCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                              label="Save mask layer.")
        self.addPolLayerToCanvasCheckBox = self.addAdvancedParameter(TaCheckBox,
                                                                     label="Add mask layer to the map canvas.")
        self.addPolLayerToCanvasCheckBox.setDefaultCheckedState(True)

        self.masksOutputPath = self.addAdvancedParameter(QgsFileWidget,
                                                         label="Output file path:")
        self.masksOutputPath.setStorageMode(QgsFileWidget.StorageMode.SaveFile)  # [QGIS4 port]
        self.masksOutputPath.setFilter('*.shp')
        default_file_path = os.path.join(tempfile.gettempdir(),
                                         "remove_artefacts_polygons.shp")
        if len(default_file_path) > 68:
            d_path, f_path = os.path.split(default_file_path)
            for i in range(30):
                d_path, last_item = os.path.split(d_path)
                if len(os.path.join(last_item, f_path)) < 68:
                    if not last_item:
                        break
                    f_path = os.path.join(last_item, f_path)
                else:
                    default_file_path = os.path.join('...', f_path)
                    break
        self.masksOutputPath.lineEdit().setPlaceholderText(
            f"{default_file_path}")

        self.savePolygonsCheckBox.registerEnabledWidgets(
            [self.masksOutputPath, self.addPolLayerToCanvasCheckBox])

        self.typeOfComparison()
        self.fillDialog()

    def typeOfComparison(self):
        current_index = self.comparisonTypeBox.currentIndex()
        if current_index == 0:
            self.exprLineEdit.lineEdit.setValue("H>")
        elif current_index == 1:
            self.exprLineEdit.lineEdit.setValue("H<")

        elif current_index == 2:
            self.exprLineEdit.lineEdit.setValue("H==")

        elif current_index == 3:
            self.exprLineEdit.lineEdit.setValue("(H> )&(H< )")

    def formulaValidation(self):
        expression = self.exprLineEdit.lineEdit.value().lower()
        if expression == 'nodata' or expression == 'no data':
            return
        H = random.random((1800, 3600))
        try:
            evaluate(self.exprLineEdit.lineEdit.value(), {"H": H})  # [QGIS4 port]
        except Exception as e:
            self.msgBar.pushWarning(
                "Warning:", f"The entered expression is invalid: {e}.")
