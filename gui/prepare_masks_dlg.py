
import os

from PyQt5 import QtWidgets, QtCore, uic, QtGui
from PyQt5.QtWidgets import QFileDialog, QTableWidgetItem
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
from qgis.gui import QgsMapLayerComboBox, QgsMessageBar
import os
from .base_dialog import TaBaseDialog
from .widgets import (
    TaVectorLayerComboBox,
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
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
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
        filter_model.setFilters(QgsMapLayerProxyModel.PolygonLayer|QgsMapLayerProxyModel.LineLayer)
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





