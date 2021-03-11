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
ds1 = gdal.Open(l1.source())
ds2 = gdal.Open(l2.source())

#gpl_fc = pygplates.FeatureCollection('/mnt/data/Sync/Paleo-Mapping/Terra_antiqua/databundle/Source_Files/Coastlines.gpml')
#rot_model = '/mnt/data/Sync/Paleo-Mapping/Terra_antiqua/databundle/Source_Files/vanHinsbergen_master.rot'
fc = pygplates.FeatureCollection('Muller_etal_AREPS_2016_StaticPolygons.gpmlz')
fc.write('initial_features.shp')
rot_model ='Matthews_etal_GPC_2016_410-0Ma_GK07.rot'
pygplates.reconstruct(fc, rot_model, 'rotated_features.shp', rot_time)
pygplates.reconstruct(fc,rot_model, 'Interpolation_features.shp', int_time )
initial_layer= QgsVectorLayer('initial_features.shp', "Initial features", "ogr")
rotated_layer= QgsVectorLayer('rotated_features.shp', "Rotated features", "ogr")
interpolation_layer = QgsVectorLayer('interpolation_features.shp', "Interpolation Features", "ogr")
initial_features = initial_layer.getFeatures()
rotated_features = rotated_layer.getFeatures()
initial_array = ds1.GetRasterBand(1).ReadAsArray()
rotated_array = ds2.GetRasterBand(1).ReadAsArray()
interpolated_array = np.empty(initial_array.shape)
interpolated_array[:] = np.nan
in_mask_array = None
rot_mask_array = None
total_feats = initial_layer.featureCount()
i=0
for in_feat, rot_feat in zip(initial_features, rotated_features):
    if in_feat.attribute('FEATURE_ID')==rot_feat.attribute('FEATURE_ID'):
        print("ok")
        print(in_feat.attribute('FEATURE_ID'))
        print(rot_feat.attribute('FEATURE_ID'))
    else:
        print("ID conflict")
        print(in_feat.attribute('FEATURE_ID'))
        print(rot_feat.attribute('FEATURE_ID'))

    i+=1
    print(f"{i}/{total_feats}")

    in_temp_layer = QgsVectorLayer(f"Polygon?crs={l1.crs().authid()}", "","memory")
    in_temp_layer.setExtent(l1.extent())
    in_temp_layer.dataProvider().addFeature(in_feat)
    in_mask_array = vectorToRaster(in_temp_layer,l1, l1.width(), l1.height())
    rot_temp_layer = QgsVectorLayer(f"Polygon?crs={l1.crs().authid()}", "","memory")
    rot_temp_layer.setExtent(l1.extent())
    rot_temp_layer.dataProvider().addFeature(rot_feat)
    rot_mask_array = vectorToRaster(rot_temp_layer,l1.extent(), l1.width(), l1.height())
    int_temp_layer = QgsVectorLayer(f"Polygon?crs={l1.crs().authid()}", "","memory")
    int_temp_layer.setExtent(l1.extent())
    int_temp_layer.dataProvider().addFeature(rot_feat)
    int_mask_array = vectorToRaster(int_temp_layer,l1.extent(), l1.width(), l1.height())
    interpolated_array[int_mask_array==1] = interp(
                                                initial_array[in_mask_array==1],
                                                rotated_array[rot_mask_array==1],
                                                (0, rot_time, int_time))



file = '/home/jon/raster.tif'
raster = gdal.GetDriverByName('GTIFF').Create(file, initial_array.shape[1], initial_array.shape[0], 1, gdal.GDT_Float32)
raster.SetGeoTransform(ds1.GetGeoTransform())
raster.SetProjection(l1.crs().toWkt())
band = raster.GetRasterBand(1)
band.SetNoDataValue(np.nan)
band.WriteArray(interpolated_array)
band.FlushCache()
band=None
raster = None
