#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
#Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6)
#  - Qt/QGIS enum names written in full (e.g. Qt.AlignmentFlag.AlignCenter), as Qt6 requires
#  - Layer filters use compat.FILTER_* (they moved to Qgis.LayerFilter in QGIS 3.34)
#  See core/compat.py for the note on how this port was made.



from qgis.PyQt import QtCore, QtWidgets  # [QGIS4 port]
from ..core.compat import FILTER_LINE, FILTER_POLYGON  # [QGIS4 port]
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from .base_dialog import TaBaseDialog
from .widgets import (
    TaTableWidget,
    TaButtonGroup
)



class TaPrepareMasksDlg(TaBaseDialog):

    def __init__(self, parent=None):
        """Constructor."""
        super(TaPrepareMasksDlg, self).__init__(parent)
        self.defineParameters()
        self.fillDialog()

    def defineParameters(self):
#        self.addLayerComboBox = self.addParameter(TaVectorLayerComboBox, "Input mask layer:", "TaMapLayerCombobox")
        self.tableWidget = self.addParameter(TaTableWidget)
        self.buttonGroup = self.addParameter(TaButtonGroup)
        self.buttonGroup.add.clicked.connect(self.addRow)
        self.buttonGroup.remove.clicked.connect(self.removeRow)
        self.buttonGroup.down.clicked.connect(self.tableWidget.moveRowDown)
        self.buttonGroup.up.clicked.connect(self.tableWidget.moveRowUp)
        self.tableWidget.insertColumn(0)
        self.tableWidget.insertColumn(1)
        self.tableWidget.setHorizontalHeaderLabels(["Input layer", "Mask category"])
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)  # [QGIS4 port]
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # [QGIS4 port]
        self.tableWidget.setMinimumHeight(250)
        self.addRow(0)

    def addRow(self, row):
        if not row:
            row = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row)
        self.tableWidget.setCellWidget(row, 0, QgsMapLayerComboBox(self))
        self.tableWidget.setCellWidget(row,1, QtWidgets.QComboBox(self))
        self.tableWidget.cellWidget(row, 1).setEditable(True)
        filter_model= QgsMapLayerProxyModel()
        filter_model.setFilters(FILTER_POLYGON|FILTER_LINE)  # [QGIS4 port]
        self.tableWidget.cellWidget(row, 0).setFilters(filter_model.filters())
        self.tableWidget.cellWidget(row,1).addItems(["Coastline", "Continental Shelf", "Shallow Sea"])
        self.tableWidget.cellWidget(row, 1).currentIndexChanged.connect(self.updateItemsInMaskCategories)
        self.tableWidget.cellWidget(row,1).repaint()

    def removeRow(self):
        selected_rows = self.tableWidget.selectionModel().selectedRows()
        rows_selected = [i.row() for i in selected_rows]
        if not len(rows_selected)>0:
            self.msgBar.pushWarning("Warning:", "No row is selected. Click on the row number to select it.")
        else:
            for index in selected_rows:
                if self.tableWidget.rowCount()>1:
                    self.tableWidget.removeRow(index.row())



    def updateItemsInMaskCategories(self, index):
        sender = QtCore.QObject().sender()
        setItem = sender.itemText(index)

        for i in range(self.tableWidget.rowCount()):
            widget = self.tableWidget.cellWidget(i, 1)
            if id(widget)==id(sender):
                continue
            items = [widget.itemText(i) for i in range(widget.count())]
            if not any([i==setItem for i in items]):
                widget.addItem(setItem)





