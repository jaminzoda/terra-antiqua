# -*- coding: utf-8 -*-
import os
from PyQt5 import QtWidgets, QtCore
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsRasterLayer
from qgis.gui import (
    QgsMapLayerComboBox)
from .base_dialog import TaBaseDialog
from .widgets import (
    TaVectorLayerComboBox,
    TaTableWidget,
    TaButtonGroup,
    TaCheckBox,
    TaColorSchemeWidget
)

class TaCompileTopoBathyDlg(TaBaseDialog):
    openRasterButtonSignal=QtCore.pyqtSignal(QtWidgets.QWidget)
    def __init__(self, parent=None):
        super(TaCompileTopoBathyDlg, self).__init__(parent)
        self.openRasterButtonSignal.connect(self.openRasterFromDisk)
        self.defineParameters()
        # fill the parameters tab of the dialog with widgets appropriate to defined parameters
        self.fillDialog()

    def defineParameters(self):
       """ Adds parameters to a list object that is used by the TaBaseDialog
       class to create widgets and place them in parameters tab.
       """
       self.maskComboBox = self.addParameter(TaVectorLayerComboBox, "Mask layer:", "TaMapLayerComboBox")
       self.maskComboBox.layerChanged.connect(self.onLayerChange)
       self.maskComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
       self.removeOverlapBathyCheckBox = self.addParameter(TaCheckBox,
                                                           'Remove overlapping bathymetry',
                                                           'CheckBox')
       self.maskComboBox.layerChanged.connect(self.enableOverlapRemoveCheckBox)
       self.removeOverlapBathyCheckBox.setEnabled(False)
       self.tableWidget = self.addParameter(TaTableWidget)
       self.itemControlButtons = self.addParameter(TaButtonGroup)
       self.itemControlButtons.add.clicked.connect(self.addRow)
       self.itemControlButtons.remove.clicked.connect(self.removeRow)
       self.itemControlButtons.down.clicked.connect(self.tableWidget.moveRowDown)
       self.itemControlButtons.up.clicked.connect(self.tableWidget.moveRowUp)
       self.tableWidget.insertColumn(0)
       self.tableWidget.insertColumn(1)
       self.tableWidget.setHorizontalHeaderLabels(["Input layer", ""])
       header = self.tableWidget.horizontalHeader()
       header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
       header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
       self.tableWidget.setMinimumHeight(200)
       self.addRow(0)

       #Add advanced parameters
       self.colorPalette = self.addAdvancedParameter(TaColorSchemeWidget, "Color palette:")


    def addRow(self, row):
        if not row:
            row = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row)
        self.tableWidget.setCellWidget(row, 0, QgsMapLayerComboBox(self))
        self.tableWidget.setCellWidget(row,1, QtWidgets.QToolButton(self))
        if self.tableWidget.columnCount()>2:
            self.tableWidget.setCellWidget(row, 2, QtWidgets.QComboBox(self))
            self.tableWidget.cellWidget(row,2).addItems(self.getCategories(self.maskComboBox.currentLayer()))
        btn = self.tableWidget.cellWidget(row, 1)
        btn.setText('...')
        btn.setIconSize(QtCore.QSize(10,10))
        filter_model= QgsMapLayerProxyModel()
        filter_model.setFilters(QgsMapLayerProxyModel.RasterLayer)
        cmb = self.tableWidget.cellWidget(row, 0)
        cmb.setFilters(filter_model.filters())
        btn.clicked.connect(lambda: self.openRasterButtonSignal.emit(cmb))
        self.tableWidget.setCurrentCell(row,0)

    def removeRow(self):
        selected_rows = self.tableWidget.selectionModel().selectedRows()
        rows_selected = [i.row() for i in selected_rows]
        if not len(rows_selected)>0:
            self.msgBar.pushWarning("Warning:", "No row is selected. Click on the row number to select it.")
        else:
            for index in selected_rows:
                self.tableWidget.removeRow(index.row())


    def openRasterFromDisk(self, cmb):
        fd = QtWidgets.QFileDialog()
        filter = "Raster files (*.jpg *.tif *.grd *.nc *.png *.tiff)"
        fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)

        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            rlayer = QgsRasterLayer(fname, name, 'gdal')
            QgsProject.instance().addMapLayer(rlayer)
            cmb.setLayer(rlayer)

    def getCategories(self, layer):
        """Gets category names stored in the attribute table
        of the input layer. """
        field_names = layer.fields().names()
        field_name = None
        for name in field_names:
            if name.lower() == 'category':
                field_name = name
                break
        if not field_name:
            self.msgBar.pushWarning("Warning:",
                                    "The selected mask layer does not contain a field with name 'category'.")
            categories = set()
        else:
            field_index = layer.fields().indexOf(field_name)
            categories = layer.uniqueValues(field_index)

        categories.add('')
        categories.add('All')
        return categories

    def addColumn(self, layer):
        self.tableWidget.insertColumn(2)
        self.tableWidget.setHorizontalHeaderLabels(["Input layer", "", "Mask Category"])
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        for i in range(self.tableWidget.rowCount()):
            self.tableWidget.setCellWidget(i, 2, QtWidgets.QComboBox(self))
            self.tableWidget.cellWidget(i, 2).addItems(self.getCategories(layer))

    def onLayerChange(self, layer):
        if layer and not self.tableWidget.columnCount()>2:
            self.addColumn(layer)
        elif not layer and self.tableWidget.columnCount()>2:
            self.tableWidget.removeColumn(2)
            header = self.tableWidget.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

    def enableOverlapRemoveCheckBox(self, layer):
        if layer and layer.featureCount()>0:
            self.removeOverlapBathyCheckBox.setEnabled(True)
        else:
            self.removeOverlapBathyCheckBox.setEnabled(False)

