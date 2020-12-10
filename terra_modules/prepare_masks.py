
from PyQt5.QtCore import QVariant
import os
from qgis.core import (
    QgsVectorLayer,
    QgsWkbTypes,
    QgsField
    )
try:
    from plugins import processing
except Exception:
    import processing

from .utils import (
    refactorFields,
    polylinesToPolygons,
    TaVectorFileWriter
)
from .base_algorithm import TaBaseAlgorithm

class TaPrepareMasks(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)

    def getParameters(self):
        items=[]
        for i in range(self.dlg.tableWidget.rowCount()):
            category = self.dlg.tableWidget.cellWidget(i, 1).currentText()
            layer = self.dlg.tableWidget.cellWidget(i,0).currentLayer()
            items.append((i, category, layer))
        rowsAdded = []
        self.items = []
        order =1
        for rowNumber, category, layer in items:
            if rowNumber in rowsAdded:
                continue
            catDict = {
                        "Order":order,
                        "Category": category,
                        "Layers":[layer]
                        }
            for row, cat, layer in items:
                if row == rowNumber: continue
                if cat == category:
                    catDict.get("Layers").append(layer)
                    rowsAdded.append(row)
            rowsAdded.append(rowNumber)
            self.items.append(catDict)
            order+=1
        del items




    def run(self):
        self.getParameters()
        merged_layers = 0
        item_progress = 70/len(self.items)
        for item in self.items:
            if self.killed:
                break
            layers_to_merge = []
            for layer in item.get("Layers"):
                if self.killed:
                    break
                self.feedback.progress+=item_progress/len(item.get('Layers'))
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    try:
                        self.feedback.info("Layer {} contains {} polyline features.".format(layer.name(),
                                                                                                layer.featureCount()))
                        layer = polylinesToPolygons(layer, self.feedback)
                        assert type(layer)==QgsVectorLayer, "Something went wrong while converting polylines to polygons"
                        self.feedback.info("Converted line geometries in layer {} to polygons.".format(layer.name()))
                    except Exception as e:
                        self.feedback.warning("Failed to convert line geometries to polygons in layer\
                                              {}.".format(layer.name()))
                        self.feedback.warning("This layer will be ignored.")
                        self.feedback.debug(e)
                        continue

                else:
                    try:
                        self.feedback.info("Layer {} contains {} polygon features.".format(layer.name(),
                                                                                           layer.featureCount()))
                        layer = processing.run('native:fixgeometries', {'INPUT': layer, 'OUTPUT': 'memory:'+layer.name()})['OUTPUT']
                        self.feedback.info("Fixed invalid geometries in layer {}.".format(layer.name()))
                    except Exception as e:
                        self.feedback.warning("Failed to fix invalid geometries in layer {}.".format(layer.name))
                        self.feedback.warning("This layer will be ignored. Try fixing invalid geometries manually.")
                        self.feedback.debug(e)
                        continue

                if len(layers_to_merge)>0:
                    try:
                        layer, fields_refactored = refactorFields(layer,layers_to_merge[-1], layer.name())
                        if len(fields_refactored)>0:
                            self.feedback.info("Refactored {} fields in layer {}: {}.".format(len(fields_refactored),
                                                                                              layer.name(),
                                                                                              fields_refactored))
                    except Exception as e:
                        self.feedback.warning("Failed to refactor fields in layer {}.".format(layer.name()))
                        self.feedback.debug(e)



                layers_to_merge.append(layer)

            if len(layers_to_merge)==0:
                self.feedback.warning("There are no valid layers to merge in {} category.".format(item.get("Category")))
                self.feedback.warning("This category will be ignored.")
                continue
            elif len(layers_to_merge)==1:
                item['Merged_Layer'] = layers_to_merge[0]
                item['Merged_Layer'].setName(item.get('Category'))
                merged_layers +=1
                self.feedback.info("Category {} has only 1 valid layer.".format(layers_to_merge[0].name()))
            else:
                self.feedback.info("Number of features in layers to merge:")
                for l in layers_to_merge:
                    self.feedback.info("{}:{}".format(l.name(), l.featureCount()))
                params_merge = {'LAYERS': layers_to_merge, 'OUTPUT': 'memory:'}
                merged_layer = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
                merged_layer.setName(item.get("Category"))
                if merged_layer.isValid():
                    item['Merged_Layer'] = merged_layer
                    merged_layers +=1
                    self.feedback.info("Merged layers in category {}: {}.".format(item.get("Category"),
                                                                              [l.name() for l in layers_to_merge]))

            if not 'Category' in item['Merged_Layer'].fields().names():
                cat_field = QgsField('Category', QVariant.String, 'Text', 80)
                item['Merged_Layer'].startEditing()
                item['Merged_Layer'].addAttribute(cat_field)
                item['Merged_Layer'].commitChanges()
            field_index = item['Merged_Layer'].fields().indexOf('Category')
            item['Merged_Layer'].startEditing()
            for feat in item['Merged_Layer'].getFeatures():
                item['Merged_Layer'].changeAttributeValue(
                    feat.id(),
                    field_index,
                    item.get('Category'))
            item['Merged_Layer'].commitChanges()
        if not self.killed:
            if merged_layers ==0:
                self.feedback.error("No valid layers to merge.")
                self.kill()
            elif merged_layers==1:
                for item in self.items:
                    if "Merged_Layer" in item:
                        final_layer = item.get("Merged_Layer")
            else:
                #remove any item that does not contain Merged_Layer
                for i in range(len(self.items)):
                    if not "Merged_Layer" in self.items[i]:
                        del self.items[i]
                #sort items by order
                self.items = sorted(self.items, key=lambda k: k['Order'], reverse=True)
                #remove overlapping parts of polygons
                #Parts of polygons in the input layer that overlap with parts of polygons in the overlay layer will be
                #removed.
                i = 0
                j=1
                item_progress = 20/len(self.items)
                while True:
                    if j>len(self.items)-1:
                        break
                    self.feedback.progress += item_progress

                    if i ==0:
                        in_lr = self.items[i].get('Merged_Layer')

                    ov_lr = self.items[j].get('Merged_Layer')

                    self.feedback.debug("Number of features in layer {} before difference:\
                                   {}".format(in_lr.name(),in_lr.featureCount()))

                    params = {'INPUT': in_lr, 'OVERLAY':ov_lr, 'OUTPUT': 'memory:'}
                    intermediate_layer = processing.run('native:difference', params)["OUTPUT"]
                    intermediate_layer.setName(in_lr.name())

                    self.feedback.debug("Number of features after difference:\
                                    {}.".format(intermediate_layer.featureCount()))

                    params_merge = {'LAYERS': [intermediate_layer, ov_lr], 'OUTPUT': 'memory:'}
                    merged_layer = processing.run('native:mergevectorlayers', params_merge)['OUTPUT']
                    merged_layer.setName(intermediate_layer.name()+ov_lr.name())

                    in_lr = merged_layer
                    i=i+1
                    j=j+1
                final_layer = merged_layer



        if not self.killed:
            error = TaVectorFileWriter.writeToShapeFile(final_layer, self.out_file_path, "UTF-8", final_layer.crs(), "ESRI Shapefile")
            if error[0] == TaVectorFileWriter.NoError:
                self.feedback.info("All the layers were merged. \
                                   The resulting layer is saved at: {}".format(self.out_file_path))
            else:
                self.feedback.error("Failed to write the resulting layer onto the disk at\
                                    {}.".format(self.out_file_path))
                self.feedback.error(error[1])
                self.kill()
        if not self.killed:
            self.feedback.progress =100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, '')


