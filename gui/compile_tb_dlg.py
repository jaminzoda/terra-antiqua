# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QUrl, QFile, QFileInfo
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
from qgis.gui import QgsSpinBox
from .base_dialog import TaBaseDialog
from .widgets import TaRasterLayerComboBox, TaVectorLayerComboBox

class TaCompileTopoBathyDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super(TaCompileTopoBathyDlg, self).__init__(parent)
        self.defineParameters()

    def defineParameters(self):
       """ Adds parameters to a list object that is used by the TaBaseDialog
       class to create widgets and place them parameters tab.
       """
                                    #Widget class to be created, Label (is put on top, or beside), Type of Widget
       self.selectMasks = self.addMandatoryParameter(TaVectorLayerComboBox,
                                                     'Continental blocks',
                                                     'TaMapLayerComboBox')
       self.selectBrTopo = self.addMandatoryParameter(TaRasterLayerComboBox,
                                                      'Bedrock topography',
                                                      'TaMapLayerComboBox')
       self.selectPaleoBathy = self.addMandatoryParameter(TaRasterLayerComboBox,
                                                          'Reconstructed paleobathymetry',
                                                          'TaMapLayerComboBox')
       self.selectOceanAge = self.addParameter(TaRasterLayerComboBox, 'Ocean age','TaMapLayerComboBox')
       self.selectSbathy = self.addParameter(TaRasterLayerComboBox, 'Shallow sea bathymetry', 'TaMapLayerComboBox')
       self.shelfDepthBox = self.addParameter(QgsSpinBox, 'Maximum depth of the continental shelf (in m)')
       self.ageBox = self.addParameter(QgsSpinBox, 'Age of reconstructiton (Ma)')
       self.removeOverlapBathyCheckBox = self.addParameter(QtWidgets.QCheckBox,
                                                           'Remove overlapping bathymetry',
                                                           'CheckBox')

       self.shelfDepthBox.setMinimum(-12000)
       self.shelfDepthBox.setMaximum(0)
       self.shelfDepthBox.setValue(-100)
       self.ageBox.setMaximum(4500)
       self.ageBox.setMinimum(0)
       self.ageBox.setValue(0)
       # fill the parameters tab of the dialog with widgets appropriate to
       # defined parameters
       self.fillDialog()

