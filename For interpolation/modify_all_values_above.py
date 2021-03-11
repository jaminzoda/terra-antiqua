import numpy as np
import gdal
import sys

sys.path.insert(1, 'home/jon/dev/terra_antiqua/')
from terra_antiqua.core.utils import  modRescale

l=iface.activeLayer()
ds = gdal.Open(l.source())
array = ds.GetRasterBand(1).ReadAsArray()
array[array>500] = modRescale(array[array>500], 500,600)

driver = gdal.GetDriverByName('GTIFF')
file = '/mnt/data/Sync/Paleo-Mapping/Terra_antiqua/Qgis_Projects/Interpolation_time_steps/modified_topo.tif'
raster = driver.Create(file, array.shape[1], array.shape[0], 1, gdal.GDT_Float32)
raster.SetProjection(l.crs().toWkt())
raster.SetGeoTransform(ds.GetGeoTransform())
band = raster.GetRasterBand(1)
band.SetNoDataValue(np.nan)
band.WriteArray(array)
band.FlushCache()
band = None
raster = None
driver = None
iface.addRasterLayer(file)


