layers=iface.legendInterface().layers()
            layer_list=[]
            for layer in layers:
                layer_list.append(layer.name())
                self.dlg.selectPBathy.addItems(layer_list)

# Adding loaded layers into the lilst for selection

# layers=[layer for layer in QgsProject.instance().mapLayers().values()]
# rlayer_list=[]
# vlayer_list=[]
# for layer in layers:
#     if layer.type()==1:
#         rlayer_list.append(layer.name())
#         self.dlg.selectBathy.clear()
#         self.dlg.selectBathy.addItems(rlayer_list)
#         self.dlg.selectPaleoBathy.clear()
#         self.dlg.selectPaleoBathy.addItems(rlayer_list)
#         self.dlg.selectTopo.clear()
#         self.dlg.selectTopo.addItems(rlayer_list)
#     else:
#         vlayer_list.append(layer.name())
#         self.dlg.selectMask.clear()
#         self.dlg.selectMask.addItems(vlayer_list)

""" rasterizing algorithm
"""

# 1. Define pixel_size and NoData value of new raster
NoData_value = -9999
x_res = 0.03333378 # assuming these are the cell sizes
y_res = 0.01666641 # change as appropriate
pixel_size = 1

# 2. Filenames for in- and output
_in = r"C:/Users/.../hoppla.shp"
_out = r"C:/Users/.../hoppla.tif"

# 3. Open Shapefile
source_ds = ogr.Open(_in)
source_layer = source_ds.GetLayer()
x_min, x_max, y_min, y_max = source_layer.GetExtent()

# 4. Create Target - TIFF
cols = int( (x_max - x_min) / x_res )
rows = int( (y_max - y_min) / y_res )

_raster = gdal.GetDriverByName('GTiff').Create(_out, cols, rows, 1, gdal.GDT_Byte)
_raster.SetGeoTransform((x_min, x_res, 0, y_max, 0, -y_res))
_band = _raster.GetRasterBand(1)
_band.SetNoDataValue(NoData_value)


# 5. Rasterize why is the burn value 0... isn't that the same as the background?
gdal.RasterizeLayer(_raster, [1], source_layer, burn_values=[0])