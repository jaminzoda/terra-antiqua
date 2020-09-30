import os
try:
    from qgis.core import QgsMapLayerType
except:
    pass

from qgis.core import QgsMapLayer

from . utils import setRasterSymbology

class TaAlgorithmProviderNew:

    def __init__(self, dlg, thread, iface):
        self.dlg = dlg()
        self.thread = thread(self.dlg)
        self.iface = iface
        self.dlg.is_run.connect(self.start)
        self.dlg.cancelled.connect(self.stop)


    def load(self):
        self.dlg.show()

    def start(self):
        if not self.thread.isRunning():
            self.thread.startOver()
            self.thread.progress.connect(self.dlg.setProgressValue)
            self.thread.progress.connect(lambda:print("Legacy progress"))
            self.thread.start()
            self.thread.finished.connect(self.add_result)

    def stop(self):
        if self.thread.isRunning():
            self.thread.kill()
            self.thread.feedback.error("The algorithm did not finish successfully, because the user canceled processing.")
            self.thread.feedback.error("Or something went wrong. Please, refer to the log above for more details.")


    def finish(self):
        self.dlg.finishEvent()


    def add_result(self, finished, output_path):
        if finished is True:
            file_name = os.path.splitext(os.path.basename(output_path))[0]
            ext = os.path.splitext(os.path.basename(output_path))[1]
            if ext == '.tif' or ext == '.tiff':
                layer = self.iface.addRasterLayer(output_path, file_name, "gdal")
            elif ext == '.shp':
                layer = self.iface.addVectorLayer(output_path, file_name, "ogr")
            if layer:
                # Rendering a symbology style for the resulting raster layer.
                try:
                    if layer.type() == QgsMapLayerType.RasterLayer:
                        setRasterSymbology(layer)
                except Exception:
                    if layer.type() == QgsMapLayer.LayerType.RasterLayer:
                        setRasterSymbology(layer)
                else:
                    pass
                self.thread.feedback.info("The algorithm finished processing successfully,")
                self.thread.feedback.info("and added the resulting raster/vector layer to the map canvas.")
            else:
                self.thread.feedback.info("The algorithm finished successfully,")
                self.thread.feedback.info("however the resulting layer did not load. You may need to load it manually.")

            self.finish()
        else:
            if  not self.dlg.isCanceled():
                self.stop()


