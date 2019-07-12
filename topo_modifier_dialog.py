#This script creates a dialog form for our second tool in the plugin
import os
from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, QgsRasterLayer
import os
import datetime
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'topo_modifier_dialog_base.ui'))
class TopoModifierDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TopoModifierDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS2.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        #Set the mode of QgsFileWidget to directory mode
        self.outputPath.setStorageMode(self.outputPath.SaveFile)
        self.outputPath.setFilter('Raster file - *.tif;;Raster file - *.tiff')
        #Base topography layer
        self.baseTopoBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.baseTopoBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens raster layers from disk
        self.selectTopoBaseButton.clicked.connect(self.addLayerToBaseTopo)
        #Input masks layer
        self.masksBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.masksBox.setLayer(None)
        # Connect the tool buttons to the file dialog that opens vector layers from disk
        self.selectMasksButton.clicked.connect(self.addLayerToMasks)
        # Enable/disable  masks field depending on the state of the checkbox associated with it.
        self.useAllMasksBox.stateChanged.connect(self.enableMaskField)
        self.masksBox.layerChanged.connect(self.setFieldsInLayer)

        #Set formula tetxt field enabled/disabled
        self.formulaField.fieldChanged.connect(self.enableFormulaText)

        self.logText.clear()
        self.logText.setReadOnly(True)
        #Set formula groupbox or minimum and maximum values group boxes enabled/disabled
        #Set intital states
        self.useAllMasksBox.setChecked(True)
        self.formulaCheckBox.setChecked(True)
        self.minMaxCheckBox.setChecked(False)
        self.minMaxGroupBox.setEnabled(False)
        self.minMaxGroupBox.setCollapsed(True)
        self.formulaGroupBox.setCollapsed(False)
        self.min_maxValueCheckBox.setChecked(True)
        
        #set the help text in the  help box (QTextBrowser)
        path_to_file = os.path.join(os.path.dirname(__file__),"help_text/help_TopographyModifier.html")
        help_file = open(path_to_file, 'r', encoding='utf-8')
        help_text = help_file.read()
        self.helpBox.setHtml(help_text)
        
        #Change the state of groupboxes, when the state of checkboxes is changed
        self.formulaCheckBox.stateChanged.connect(self.setFormulaEnabled)
        self.minMaxCheckBox.stateChanged.connect(self.setMinMaxEnabled)

        #Set the groupbox for specifying minimum and maximum elevation values that should be modified disabled/enabled
        self.min_maxValueCheckBox.stateChanged.connect(self.setBoundingValuesForModification)
        self.minMaxValuesFromAttrCheckBox.setChecked(True)
        self.setBoundingValuesFromAttrEnabled(1)
        self.minMaxValuesFromAttrCheckBox.stateChanged.connect(self.setBoundingValuesFromAttrEnabled)
        self.minMaxValuesFromSpinCheckBox.stateChanged.connect(self.setBoundingValuesFromSpinEnabled)
        #Set fields for minimum and maximum values enabled/disabled
        #If the user wants to type min and max values, the fields are disabled,
        #or the other way around.
        self.minField.setEnabled(False) # set the initial states to disabled
        self.maxField.setEnabled(False)
        self.minMaxFromAttrCheckBox.stateChanged.connect(self.setMinMaxFromAttrEnabled)
        self.runButton.setEnabled(False)
        self.masksBox.layerChanged.connect(self.enableRunButton)
        self.baseTopoBox.layerChanged.connect(self.enableRunButton)


    def enableFormulaText(self):
        if self.formulaField.currentField():
            self.formulaText.setEnabled(False)
        else:
            self.formulaText.setEnabled(True)



    def enableRunButton(self):
        if  self.baseTopoBox.currentLayer()!=None and self.masksBox.currentLayer()!=None:
            self.runButton.setEnabled(True)
            self.warningLabel.setText('')
        else:
            self.warningLabel.setText('Please, select all the mandatory fields.')
            self.warningLabel.setStyleSheet('color:red')

        # Function for enabling comboboxes for specifying a column in the attribute table
        # of the masks  layer where the names of the masks are stored. This will be used
        # to query only masks, which we need.

    def enableMaskField(self, state):
        if state > 0:
            self.maskNameField.setEnabled(False)
            self.maskNameText.setEnabled(False)

        else:
            self.maskNameField.setEnabled(True)
            self.maskNameText.setEnabled(True)

    def addLayerToBaseTopo(self):
        self.openRasterFromDisk(self.baseTopoBox)
    def addLayerToMasks(self):
        self.openVectorFromDisk(self.masksBox)
    def openVectorFromDisk(self, box):
        fd = QFileDialog()
        filter = "Vector files (*.shp)"
        fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)
        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            vlayer = QgsVectorLayer(fname, name, 'ogr')
            QgsProject.instance().addMapLayer(vlayer)
            box.setLayer(vlayer)
    def openRasterFromDisk(self, box):
        fd = QFileDialog()
        filter = "Raster files (*.jpg *.tif *.grd *.nc *.png *.tiff)"
        fname, _ = fd.getOpenFileName(caption='Select a vector layer', directory=None, filter=filter)
        if fname:
            name, _ = os.path.splitext(os.path.basename(fname))
            rlayer = QgsRasterLayer(fname, name, 'gdal')
            QgsProject.instance().addMapLayer(rlayer)
            box.setLayer(rlayer)

    # Get the fields of the masks layer displaed in the field comboboxes
    def setFieldsInLayer(self):
        self.maskNameField.setLayer(self.masksBox.currentLayer())

        self.formulaField.setLayer(self.masksBox.currentLayer())
        fields = self.masksBox.currentLayer().fields().toList()
        field_names = [i.name() for i in fields]
        for field_name in field_names:
            if field_name.lower() == "formula":
                self.formulaField.setField(field_name)

        # Final minimum and maximum values of the area to modified by initial and final min-max.
        self.minField.setLayer(self.masksBox.currentLayer())
        self.maxField.setLayer(self.masksBox.currentLayer())

        #Bounding values for selecting the range to modify with formula
        self.minValueField.setLayer(self.masksBox.currentLayer())
        #Trying to find the minimum bounding value field automatically and set it to the combobox.
        names_to_check = ["min", "min_mod", "mod_min", "min_value", "minimum"]
        for field_name in field_names:
            if not self.minValueField.currentField():
                for name in names_to_check:
                    if field_name.lower() == name:
                        self.minValueField.setField(field_name)
                        break
            else:
                break

        self.maxValueField.setLayer(self.masksBox.currentLayer())
        # Trying to find the maximum bounding value field automatically and set it to the combobox.
        names_to_check = ["max", "max_mod", "mod_max", "max_value", "maximum"]
        for field_name in field_names:
            if not self.maxValueField.currentField():
                for name in names_to_check:
                    if field_name.lower() == name:
                        self.maxValueField.setField(field_name)
                        break
            else:
                break



    # Set the groupbox for formula enabled.
    def setFormulaEnabled(self, state):
        if state > 0:
            self.formulaGroupBox.setEnabled(True)
            self.minMaxCheckBox.setChecked(False)
            self.minMaxGroupBox.setEnabled(False)
            self.minMaxGroupBox.setCollapsed(True)
            self.formulaGroupBox.setCollapsed(False)
            self.min_maxValueCheckBox.setChecked(True)

    # Set the groupbox for specifing final minimum and maximum values enabled.\
    # This is enabled if the user wants to use final minimuum and maximum values
    # for flattening and roughening instead of a formula.
    def setMinMaxEnabled(self, state):
        if state > 0:
            self.minMaxGroupBox.setEnabled(True)
            self.formulaCheckBox.setChecked(False)
            self.formulaGroupBox.setEnabled(False)
            self.formulaGroupBox.setCollapsed(True)
            self.minMaxGroupBox.setCollapsed(False)

    # Set fields for minimum and maximum values enabled. This is needed, when the user wants
    # get the minimum and maximum values from the attribute table
    def setMinMaxFromAttrEnabled(self, state):
        if state > 0:
            self.minField.setEnabled(True)
            self.maxField.setEnabled(True)
            self.minSpin.setEnabled(False)
            self.maxSpin.setEnabled(False)
        else:
            self.minField.setEnabled(False)
            self.maxField.setEnabled(False)
            self.minSpin.setEnabled(True)
            self.maxSpin.setEnabled(True)

    def setBoundingValuesForModification(self, state):
        if state > 0:
            self.minValueField.setEnabled(True)
            self.maxValueField.setEnabled(True)
            self.minValueSpin.setEnabled(True)
            self.maxValueSpin.setEnabled(True)
            self.minMaxValuesFromAttrCheckBox.setEnabled(True)
            self.minMaxValuesFromSpinCheckBox.setEnabled(True)

            self.boundingValuesGroupBox.show()
        else:
            self.minValueField.setEnabled(False)
            self.maxValueField.setEnabled(False)
            self.minValueSpin.setEnabled(False)
            self.maxValueSpin.setEnabled(False)
            self.minMaxValuesFromAttrCheckBox.setEnabled(False)
            self.minMaxValuesFromSpinCheckBox.setEnabled(False)

            self.boundingValuesGroupBox.hide()

    def setBoundingValuesFromAttrEnabled(self, state):
        if state > 0:
            self.minValueField.setEnabled(True)
            self.maxValueField.setEnabled(True)
            self.minValueSpin.setEnabled(False)
            self.maxValueSpin.setEnabled(False)
            self.minMaxValuesFromSpinCheckBox.setChecked(False)

    def setBoundingValuesFromSpinEnabled(self, state):
        if state > 0:
            self.minValueField.setEnabled(False)
            self.maxValueField.setEnabled(False)
            self.minValueSpin.setEnabled(True)
            self.maxValueSpin.setEnabled(True)
            self.minMaxValuesFromAttrCheckBox.setChecked(False)

    def set_progress_value(self, value):
        self.progressBar.setValue(value)

    def reset_progress_value(self):
        self.progressBar.setValue(0)






#     def log(self,msgs):
#         #get the current time
#         time=datetime.datetime.now()
#         time=str(time.hour)+':'+str(time.minute)+':'+str(time.second)
#         msg=' '
#         for m in msgs:
#             msg=msg+' '+m
#         # inserting log messages into the qplantextedit widget
#         self.logText.textCursor().insertText(time+' - '+msg+' \n')
# #log_handler.setFormatter(logging.Formatter('\n %(asctime)s - %(levelname)s - %(message)s'))
