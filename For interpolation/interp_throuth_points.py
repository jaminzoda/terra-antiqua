
import sys
import numpy as np
sys.path.insert(1, '/home/jon/')
sys.path.insert(1, '/home/jon/dev/terra_antiqua/')
import pygplates
from terra_antiqua.core.utils import vectorToRaster
from interp import interp
import gdal
#from PyQt5.QtWidgets import QApplication
#app = QApplication([])
from qgis.core import QgsProject

rot_time = 10
int_time =5
l1= QgsProject.instance().mapLayersByName('unmodified_topo')[0]
l2= QgsProject.instance().mapLayersByName('modified_topo')[0]
params = {'INPUT_RASTER':l1.source(),'RASTER_BAND':1,'FIELD_NAME':'VALUE','OUTPUT':'/home/jon/points.shp'}
points1 = processing.run("native:pixelstopoints", params)['OUTPUT']
fc = pygplates.FeatureCollection(points1)
print(type(fc))
