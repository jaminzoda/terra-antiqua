from osgeo import gdal
import numpy as np
layer=iface.activeLayer()
ds = gdal.Open(layer.dataProvider().dataSourceUri())
array=ds.GetRasterBand(1).ReadAsArray()
array[np.isnan(array)]=1
print("max: ",array.max())
print("min: ", array.min())
