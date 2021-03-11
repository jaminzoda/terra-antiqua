import sys
import numpy as np
import gdal
sys.path.insert(1, '/home/jon/')
from interp import interp


l1 = QgsProject.instance().mapLayersByName('unmodified_topo')[0]
l2 = QgsProject.instance().mapLayersByName('modified_topo')[0]
ds1 = gdal.Open(l1.source())
ar1 = ds1.GetRasterBand(1).ReadAsArray()
ds2 = gdal.Open(l2.source())
ar2 = ds2.GetRasterBand(1).ReadAsArray()
res = np.empty(ar1.shape)
res[:]=np.nan
res[np.isfinite(ar2)] = interp(ar1[np.isfinite(ar2)],ar2[np.isfinite(ar2)], (0,38,10))

file = '/home/jon/raster.tif'
raster = gdal.GetDriverByName('GTIFF').Create(file, ar1.shape[1], ar1.shape[0], 1, gdal.GDT_Float32)
raster.SetGeoTransform(ds1.GetGeoTransform())
raster.SetProjection(l1.crs().toWkt())
band = raster.GetRasterBand(1)
band.SetNoDataValue(np.nan)
band.WriteArray(res)
band.FlushCache()
band=None
raster = None

iface.addRasterLayer(file, 'interpolated raster', 'gdal')
