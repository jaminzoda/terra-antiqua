# -*- coding: utf-8 -*-

import tempfile
import os

import numpy as np
from plugins import processing
from PyQt5.QtGui import QColor
from osgeo import gdal, osr, ogr
from osgeo import gdalconst
from qgis.core import (
	QgsRasterLayer, 
	QgsVectorLayer, 
	QgsRasterBandStats, 
	QgsColorRampShader, 
	QgsRasterShader, 
	QgsSingleBandPseudoColorRenderer
	)



def fill_no_data(in_layer, out_file_path=None, no_data_value=None):
	"""
	Fills the missing data by interpolating from edges.
	:param in_layer: QgsRasterLayer
	:param no_data_value: NoDataValue of the input layer. These values to be set to np.nan   during the interpolation.
	:param vlayer: A vector layer with masks for interpolating only inside masks
	:return: String - the path of the output file.
	
	"""
	temp_dir = tempfile.gettempdir()
	if out_file_path is None:
		out_file_path = os.path.join(temp_dir, "Interpolated_raster.tiff")
	
	# (1) Get the input raster dataset
	if not type(in_layer) == QgsRasterLayer:
		raise TypeError("The input layer must be QgsRasterLayer")
	
	try:
		raster_ds = gdal.Open(in_layer.dataProvider().dataSourceUri())
	except FileNotFoundError:
		print("Could not open the provided raster layer.")
	else:
		in_band = raster_ds.GetRasterBand(1)
		in_array = in_band.ReadAsArray()

	if no_data_value != None:
		in_array[in_array == no_data_value] = np.nan
	else:
		no_data_value = in_band.GetNoDataValue()
		if no_data_value != np.nan:
			in_array[in_array == no_data_value] = np.nan
		
	
	# (2) Define the parameters for creating a mask raster of valid values.
	# TODO move this mask into the temporary directory of the OS
	mask_path = os.path.join(temp_dir, "Valid_data_mask_for_interpolation.tiff")
	geotransform = raster_ds.GetGeoTransform()
	width = in_layer.width()
	height = in_layer.height()


	out_array = np.ones(in_array.shape)

	out_array[np.isnan(in_array)] = np.nan
	out_array[np.isfinite(in_array)] = 1

	# Create Target - TIFF
	out_raster = gdal.GetDriverByName('GTiff').Create(mask_path, width, height, 1, gdal.GDT_Byte)
	out_raster.SetGeoTransform(geotransform)
	crs = in_layer.crs().toWkt()
	out_raster.SetProjection(crs)
	out_band = out_raster.GetRasterBand(1)
	out_band.SetNoDataValue(np.nan)
	out_band.WriteArray(out_array)
	out_band.FlushCache()
	out_raster = None

	# interpolation with the processing module
	input_layer = in_layer.dataProvider().dataSourceUri()
	
	# feedback = QgsProcessingFeedback()
	# feedback.progressChanged.connect(self.send_progress_feedback)
	# If the above two lines are uncommented, the feedback=feedback should be added to the processing algorithm below.

	fill_params = {'INPUT': input_layer,
				   'BAND': 1,
				   'DISTANCE': 100,
				   'ITERATIONS': 0,
				   'NO_MASK': False,
				   'MASK_LAYER': mask_path,
				   'OUTPUT': out_file_path}

	processing.run("gdal:fillnodata", fill_params)

	in_band.FlushCache()

	raster_ds = None

	# (4) delete the validity mask file
	driver = gdal.GetDriverByName('GTiff')
	if os.path.exists(mask_path):
		driver.Delete(mask_path)

	return out_file_path


def raster_smoothing(in_layer, factor, out_file=None, feedback=None):
	"""
	Smoothes values of pixels in a raster  by averaging  values around them
	:param in_layer: input raster layer (QgsRasterLayer) for smoothing
	:param out_file: String - output file to save the smoothed raster [Optional]. If the out_file argument is specified the smoothed raster will be written in a new raster, otherwise the old raster will be updated.
	:return:QgsRasterLayer. Smoothed raster layer.
	"""

	raster_ds = gdal.Open(in_layer.source(), gdalconst.GA_Update)
	in_band = raster_ds.GetRasterBand(1)
	in_array = in_band.ReadAsArray()
	rows = in_array.shape[0]
	cols = in_array.shape[1]

	out_array = np.zeros(in_array.shape)
	total = 100 / rows if rows else 0
	for i in range(rows - 1):
		for j in range(cols - 1):
			# Define smoothing mask; periodic boundary along date line
			x_vector = np.mod((np.arange((j - factor), (j + factor + 1))), (cols - 1))
			x_vector = x_vector.reshape(1, len(x_vector))
			y_vector = np.arange(np.maximum(0, i - factor), (np.minimum((rows - 1), i + factor) + 1), 1)
			y_vector = y_vector.reshape(len(y_vector), 1)
			out_array[i, j] = np.mean(in_array[y_vector, x_vector])
		if feedback is not None:
			feedback.emit(i * total)

	# Write the smoothed raster
	# If the out_file argument is specified the smoothed raster will written in a new raster, otherwise the old raster will be updated
	if out_file != None:
		if os.path.exists(out_file):
			driver = gdal.GetDriverByName('GTiff')
			driver.Delete(out_file)
		geotransform = raster_ds.GetGeoTransform()
		smoothed_raster = gdal.GetDriverByName('GTiff').Create(out_file, cols, rows, 1, gdal.GDT_Float32)
		smoothed_raster.SetGeoTransform(geotransform)
		crs = in_layer.crs()
		smoothed_raster.SetProjection(crs.toWkt())
		smoothed_band = smoothed_raster.GetRasterBand(1)
		smoothed_band.WriteArray(out_array)
		smoothed_band.FlushCache()

		# Close datasets
		raster_ds = None
		smoothed_raster = None

		# Get the resulting layer to return
		smoothed_layer = QgsRasterLayer(out_file, 'Smoothed paleoDEM', 'gdal')
	else:
		in_band.WriteArray(out_array)
		in_band.FlushCache()

		# Close the dataset
		raster_ds = None

		# Get the resulting layer to return
		smoothed_layer = QgsRasterLayer(in_layer.dataProvider().dataSourceUri(), 'Smoothed paleoDEM', 'gdal')

	return smoothed_layer

def set_raster_symbology(in_layer):
	"""
	Applies a color palette to a raster layer. It does not add the raster layer to the Map canvas. Before passing a layer to this function, it should be added to the map canvas.
	
	"""

	stats = in_layer.dataProvider().bandStatistics(1, QgsRasterBandStats.All)
	min_elev = stats.minimumValue
	max_elev = stats.maximumValue
	ramp_shader = QgsColorRampShader()
	ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

	lst = [ramp_shader.ColorRampItem(min_elev, QColor(0, 0, 51), str(round(min_elev))),
		   ramp_shader.ColorRampItem(-5000, QColor(0, 51, 102), '-5000'),
		   ramp_shader.ColorRampItem(-3000, QColor(24, 138, 204), '-3000'),
		   ramp_shader.ColorRampItem(-2000, QColor(25, 145, 214), '-2000'),
		   ramp_shader.ColorRampItem(-1000, QColor(25, 151, 219), '-1000'),
		   ramp_shader.ColorRampItem(-200, QColor(121, 187, 224), '-200'),
		   ramp_shader.ColorRampItem(-0.01, QColor(176, 226, 255), '0'),
		   ramp_shader.ColorRampItem(0.01, QColor(0, 97, 71), '1'),
		   ramp_shader.ColorRampItem(200, QColor(16, 123, 48), '200'),
		   ramp_shader.ColorRampItem(1000, QColor(232, 214, 125), '1000'),
		   ramp_shader.ColorRampItem(2000, QColor(163, 68, 0), '2000'),
		   ramp_shader.ColorRampItem(3000, QColor(130, 30, 30), '3000'),
		   ramp_shader.ColorRampItem(5000, QColor(189, 189, 189), '5000'),
		   ramp_shader.ColorRampItem(max_elev, QColor(255, 255, 255), str(round(max_elev)))]

	ramp_shader.setColorRampItemList(lst)

	# We’ll assign the color ramp to a QgsRasterShader
	# so it can be used to symbolize a raster layer.
	shader = QgsRasterShader()
	shader.setRasterShaderFunction(ramp_shader)

	"""Finally, we need to apply the symbology we’ve create to the raster layer. 
	First, we’ll create a renderer using our raster shader. 
	Then we’ll Assign the renderer to our raster layer."""

	renderer = QgsSingleBandPseudoColorRenderer(in_layer.dataProvider(), 1, shader)
	in_layer.setRenderer(renderer)
	in_layer.triggerRepaint()


def vector_to_raster(in_layer, geotransform, width, height, field_to_burn=None, no_data=None, burn_value=None):
	"""
	Rasterizes a vector layer and returns a numpy array.

	:param field_to_burn: A specific field from attributes table to get values to burn. This can be a field with
	depth or elevation values.
	:param no_data: No data value. It can be NAN, zero or any other value.
	:param burn_value: A fixed value to burn in the raster.
	:param geotransform: geotransform for the resulting raster layer. Can accept geotransform (raster_ds.GetGeotransform())
	extent (raster_layer.extent()) and QgsRasterLayer.
	:param width: number of columns in the raster. Should be consistent with the raster that the masks will deployed on.
	:param height: number of rows in the raster. Should be consistent with the raster that the masks will deployed on.
	:return: Numpy array.
	"""

	# Convert geotransform to extent if the geotransform is supplied
	if type(geotransform) == tuple and len(geotransform) == 6:
		upx, xres, xskew, upy, yskew, yres = geotransform
		cols = width
		rows = height

		xmin = upx + 0 * xres + rows * xskew  # Lower left x and y coordinates
		ymin = upy + 0 * yskew + rows * yres

		xmax = upx + cols * xres + 0 * xskew  # Upper right x and y coordinates
		ymax = upy + cols * yskew + 0 * yres

		raster_extent = "{},{},{},{}".format(xmin, xmax, ymin, ymax)
	else:
		raster_extent = geotransform

	field_to_burn = field_to_burn if field_to_burn is not None else None

	nodata = no_data if no_data is not None else 0
	burn_value = burn_value if burn_value is not None else 1

	input_layer = in_layer
	r_params = {
		'INPUT': input_layer,
		'FIELD': field_to_burn,
		'BURN': burn_value,
		'UNITS': 0,
		'WIDTH': width,  # Width of the input layer will be used
		'HEIGHT': height,  # Height of the input layer will be used
		'EXTENT': raster_extent,
		'NODATA': nodata,
		'OPTIONS': '',
		'DATA_TYPE': 5,  # Float32 is used
		'INIT': None,
		'INVERT': False,
		'OUTPUT': 'TEMPORARY_OUTPUT'
	}
	points_raster = processing.run("gdal:rasterize", r_params)["OUTPUT"]
	points_raster_ds = gdal.Open(points_raster)
	points_array = points_raster_ds.GetRasterBand(1).ReadAsArray()

	return points_array

def vector_to_raster_old(in_layer, geotransform, ncols, nrows):
	"""
	Rasterizes a vector layer and returns a numpy array.

	:param geotransform: geotransform for the resulting raster layer.
	:param ncols: number of columns in the raster. Should be consistent with the raster that the masks will deployed on.
	:param nrows: number of rows in the raster. Should be consistent with the raster that the masks will deployed on.
	:return: Numpy array.
	"""

	# Opening the shapefile of the input layer
	try:
		in_shapefile = ogr.Open(in_layer.source())

		if in_shapefile:  # checks to see if shapefile was successfully defined
			v_layer = in_shapefile.GetLayer()
		else:  # if it's not successfully defined
			print("Couldn't load shapefile")

	except:  # Seems redundant, but if an exception is raised in the Open() call, you get a message
		print("Exception raised during shapefile loading")

	NoData_value = 0
	# Create a temporary raster file to save the raster mask in. Define spatial referece system, and get the raster band for writing the mask.
	mask_raster = gdal.GetDriverByName('MEM').Create('', ncols, nrows, 1, gdal.GDT_Int32)
	mask_raster.SetGeoTransform(geotransform)
	crs = osr.SpatialReference()
	crs.ImportFromEPSG(4326)
	mask_raster.SetProjection(crs.ExportToWkt())
	band = mask_raster.GetRasterBand(1)
	band.SetNoDataValue(NoData_value)

	# Rasterize mask layer
	gdal.RasterizeLayer(mask_raster, [1], v_layer, burn_values=[1])
	band.FlushCache()
	raster_array = band.ReadAsArray()
	in_shapefile = None
	v_layer = None
	mask_raster = None

	return raster_array

def polygons_to_polylines(in_layer, out_layer_path: str):
	"""
	Converts polygons to polylines.

	:param out_layer_path: the path to store the layer with polylines.
	:return: QgsVectorLayer.
	"""
	polygons_layer = in_layer
	fixed_polygons = processing.run('native:fixgeometries',
									{'INPUT': polygons_layer, 'OUTPUT': 'memory:' + "fixed_pshoreline_polygons"})[
		'OUTPUT']
	processing.run("qgis:polygonstolines", {'INPUT': fixed_polygons, 'OUTPUT': out_layer_path})
	polylines_layer = QgsVectorLayer(out_layer_path, "Polylines_from_polygons", "ogr")

	return polylines_layer

def refactor_fields(in_layer, layer2):
	layer1 = in_layer
	fields1 = layer1.fields()
	fields2 = layer2.fields()

	field_mapping = []
	names_matching = []
	fields_refactored = []
	for field1 in fields1:
		for field2 in fields2:
			if field1.name() == field2.name():
				if field1.type() == field2.type():
					refact_params = {'name': field1.name(),
									 'type': field1.type(),
									 'length': field1.length(),
									 'precision': field1.precision(),
									 'expression': field1.name()
									 }
					field_mapping.append(refact_params)
				else:
					refact_params = {'name': field1.name(),
									 'type': field2.type(),
									 'length': field2.length(),
									 'precision': field2.precision(),
									 'expression': field1.name()
									 }
					field_mapping.append(refact_params)
					fields_refactored.append(field1.name())
				names_matching.append(field1.name())

	for field1 in fields1:
		name_match = False
		for name in names_matching:
			if field1.name() == name:
				name_match = True
		if not name_match:
			refact_params = {'name': field1.name(),
							 'type': field1.type(),
							 'length': field1.length(),
							 'precision': field1.precision(),
							 'expression': field1.name()
							 }
			field_mapping.append(refact_params)

	params = {'INPUT': layer1, 'FIELDS_MAPPING': field_mapping, 'OUTPUT': 'memory:Refactored_layer'}
	refactored_layer = processing.run("qgis:refactorfields", params)['OUTPUT']

	return refactored_layer, fields_refactored


def mod_min_max(in_array, fmin: int, fmax: int):
	"""
	Modifies the elevation/bathimetry
	values based on the current and provided
	minimum and maximum values.
	This is basically flattening and roughening.
	:param in_array: input numpy array for modification.
	:param fmin: final minimum value of elevation/bathymetry.
	:param fmax: final maximum value of elevation/bathymetry.
	:return: modified array of eleveation/bathymetry values.
	"""
	
	# Define the initial minimum and maximum values of the array
	# imin = in_array.min()
	imax = in_array[np.isfinite(in_array)].max()
	out_array = in_array

	ratio = (imax - fmin) / (fmax - fmin)
	out_array[out_array >= fmin] = fmin + (in_array[in_array >= fmin] - fmin) / ratio
	return out_array

def mod_rescale(in_array, min: int, max: int):
	"""
	Modifies the elevation/bathimetry
	values based on the current and provided
	minimum and maximum values.
	This is basically flattening and roughening.
	:param in_array: input numpy array for modification.
	:param fmin: final minimum value of elevation/bathymetry.
	:param fmax: final maximum value of elevation/bathymetry.
	:return: modified array of eleveation/bathymetry values.
	"""
	
	# Define the initial minimum and maximum values of the array

	imax = in_array[np.isfinite(in_array)].max()
	imin = in_array[np.isfinite(in_array)].min()
	out_array = in_array
	out_array[:] = (max - min) * (out_array[:] - imin) / (imax - imin) + min

	return out_array

def mod_formula(in_array, formula, min=None, max=None):
		"""
		:input in_array (numpy array): an input array that contains elevation values.
		:param formula: the formula to be used for topography modification.

		:param mask_array: mask that will be used to subset area of the raster (input array) for modification.
		:return: numpy array of modified elevation values.
		"""

		topo = in_array

		x = np.empty(topo.shape)
		x.fill(np.nan)
		if min != None and max != None:
			index = 'x[(x>min)*(x<max)==1]'
			x[(topo > min) * (topo < max) == 1] = topo[(topo > min) * (topo < max) == 1]
			new_formula = formula.replace('x', index)
			x[(topo > min) * (topo < max) == 1] = eval(new_formula)

		elif min != None and max == None:
			index = 'x[x>min]'
			x[topo > min] = topo[topo > min]
			new_formula = formula.replace('x', index)
			x[topo > min] = eval(new_formula)
		elif min == None and max != None:
			index = 'x[x<max]'
			x[topo < max] = topo[topo < max]
			new_formula = formula.replace('x', index)
			x[topo < max] = eval(new_formula)
		else:
			x = topo
			new_formula = formula
			x[:] = eval(new_formula)

		topo[np.isfinite(x)] = x[np.isfinite(x)]

		return topo
def is_path_valid(path: str)-> tuple: # for now is used for output paths. Modify the raise texts to fit in other contexts. 
	"""
	Checks if the specified output path is valid and accessible. Returns True, if the path is a file path and writable. False otherwise. 
	"""
	# Check if the path is empty
	file_check = False
	path_check = False
	file_name = os.path.split(path)[1]
	file_ext = os.path.splitext(file_name)[1]
	if file_name and file_ext:
		if file_ext == ".tiff" or file_ext == ".tif":
			file_check = True
		
			
	dir_path = os.path.split(path)[0]
	if dir_path:
		if os.access(dir_path, os.W_OK):
			path_check = True
	
	if path_check and file_check:
		return (True,"")
	else:
		if not file_check:
			return(False, "Error: The file output file name is incorrect. Please provide a proper file name for the output. The file name should have a 'tif' or 'tiff' extension.")
		elif not path_check:
			return(False, "Error: The output path does not exist or you do not have write permissions.")
		else:
			return(False, "Error: The provided path for the output is not correct. Example: {}".format(r'C:\\Users\user_name\Documents\file.tiff'))
	
	
