# -*- coding: utf-8 -*-

import os
import os.path

import numpy as np
from osgeo import gdal, osr, ogr, gdalconst
from qgis.core import QgsVectorLayer, QgsRasterLayer
from .topo_modifier_dialog import TopoModifierDialog


# Import the code for the dialog


class RasterTools(QgsRasterLayer):
	def __init__(self):
		super.__init__(self)


	def fill_no_data(self, no_data_value=None):
		"""
		Fils the missing data by interpolating from edges.
		:param in_layer: QgsRasterLayer
		:param no_data_value: NoDataValue of the input layer
		:param vlayer: A vector layer with masks for interpolating only inside masks
		:return: Boolean
		"""
		#Get the input raster dataset
		rlayer=self
		raster_ds = gdal.Open(rlayer.dataProvider().dataSourceUri(), gdalconst.GA_Update)
		in_band = raster_ds.GetRasterBand(1)
		in_array = in_band.ReadAsArray()

		if no_data_value == None:
			in_band.SetNoDataValue(np.nan)
		else:
			in_band.SetNoDataValue(no_data_value)

		if no_data_value != None:
			in_array[in_array == no_data_value] = np.nan

		#Define the parameters for creating a mask raster of valid values.
		path=os.path.split(rlayer.dataProvider().dataSourceUri())[0]
		mask_name="mask_"+os.path.split(rlayer.dataProvider().dataSourceUri())[1]
		mask_file=os.path.join(path,mask_name)
		geotransform = raster_ds.GetGeoTransform()
		cols = in_array.shape[1]
		rows = in_array.shape[0]

		out_array = np.ones(in_array.shape)

		out_array[np.isnan(in_array)] = np.nan
		out_array[np.isfinite(in_array)] = 1

		#Create Target - TIFF
		out_raster = gdal.GetDriverByName('GTiff').Create(mask_file, cols, rows, 1, gdal.GDT_Byte)
		out_raster.SetGeoTransform(geotransform)
		out_band = out_raster.GetRasterBand(1)
		out_band.SetNoDataValue(np.nan)
		out_band.WriteArray(out_array)

		result = gdal.FillNodata(targetBand = in_band, maskBand = out_band,
								 maxSearchDist = 100, smoothingIterations = 0)
		in_band.FlushCache()

		raster_ds = None
		out_raster = None
		return result

	def raster_smoothing(self, factor):
		"""
		Smoothes values of pixels in a raster  by averaging  values around them
		:param self, in_layer: input raster layer for smoothing
		:return:Boolean
		"""

		rlayer = self
		raster_ds = gdal.Open(rlayer.dataProvider().dataSourceUri(), gdalconst.GA_Update)
		in_band = raster_ds.GetRasterBand(1)
		in_array = in_band.ReadAsArray()
		rows=in_array.shape[0]
		cols=in_array.shape[1]

		out_array=np.zeros(in_array.shape)


		for i in range(rows-1):
			for j in range(cols-1):
				# Define smoothing mask; periodic boundary along date line
				x_vector = np.mod((np.arange((j - factor), (j + factor + 1))), (cols-1))
				x_vector = x_vector.reshape(1, len(x_vector))
				y_vector = np.arange(np.maximum(0, i - factor), (np.minimum((rows-1), i + factor) + 1), 1)
				y_vector = y_vector.reshape(len(y_vector), 1)
				out_array[i, j] = np.mean(in_array[y_vector, x_vector])



		in_band.WriteArray(out_array)
		in_band.FlushCache()
		return True
class VectorTools(QgsVectorLayer):
	def __init__(self):
		super.__init__(self)

	def vector_to_raster(self, out_path, geotransform, ncols, nrows, name_of_mask):

		v_layer=self
		# if the folder for storing the rasters is created. If not it will be created
		path = os.path.join(out_path, "raster_masks")

		if not os.path.exists(path):
			try:
				os.mkdir(path)
			except OSError:
				print("Creation of the directory %s failed" % path)
			else:
				print("Successfully created the directory %s " % path)
		else:
			print("The folder raster_masks is already created.")

		# In and out files
		out_raster_file = os.path.join(path, name_of_mask + ".tif")

		# Opening the shapefile of the layer specified in the user dialog combobox selectSsMask
		try:
			in_shapefile = ogr.Open(v_layer.source())

			if in_shapefile:  # checks to see if shapefile was successfully defined
				v_layer = in_shapefile.GetLayer()
			else:  # if it's not successfully defined
				print("Couldn't load shapefile")

		except:  # Seems redundant, but if an exception is raised in the Open() call, you get a message
			print("Exception raised during shapefile loading")

		NoData_value = 0
		# getting the real work done
		mask_raster = gdal.GetDriverByName('GTiff').Create(out_raster_file, ncols, nrows, 1, gdal.GDT_Int32)
		mask_raster.SetGeoTransform(geotransform)
		crs = osr.SpatialReference()
		crs.ImportFromEPSG(4326)
		mask_raster.SetProjection(crs.ExportToWkt())
		band = mask_raster.GetRasterBand(1)
		band.SetNoDataValue(NoData_value)

		gdal.RasterizeLayer(mask_raster, [1], v_layer, burn_values = [1])
		mask_raster = None
		band = None
		raster = gdal.Open(out_raster_file)
		raster_array = raster.GetRasterBand(1).ReadAsArray()
		return raster_array


class ArrayTools(np.ndarray):
	def __init__(self):
		super.__init__(self)
	def mod_min_max(self, fmin:int, fmax:int):
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
		in_array=self
		#Define the initial minimum and maximum values of the array
		#imin = in_array.min()
		imax = in_array[np.isfinite(in_array)].max()
		out_array=in_array

		ratio=(imax-fmin)/(fmax-fmin)
		out_array[out_array>=fmin]=fmin+(in_array[in_array>=fmin]-fmin)/ratio
		return out_array

	def mod_rescale(self, min:int, max:int):
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
		in_array=self
		#Define the initial minimum and maximum values of the array
		#imin = in_array.min()
		imax = in_array[np.isfinite(in_array)].max()
		imin=in_array[np.isfinite(in_array)].min()
		out_array=in_array
		out_array[:]=(max-min)*(out_array[:]-imin)/(imax-imin)+min

		return out_array

	def mod_formula(self, formula, min=None, max=None):
		"""
		:input self (numpy array): an input array that contains elevation values.
		:param formula: the formula to be used for topography modification.

		:param mask_array: mask that will be used to subset area of the raster (input array) for modification.
		:return: numpy array of modified elevation values.
		"""

		topo=self

		x=np.empty(topo.shape)
		x.fill(np.nan)
		if min!=None and max!=None:
			index='x[(x>min)*(x<max)==1]'
			x[(topo>min)*(topo<max)==1]=topo[(topo>min)*(topo<max)==1]
			new_formula = formula.replace('x', index)
			x[(topo>min)*(topo<max)==1] = eval(new_formula)

		elif min!=None and max==None:
			index = 'x[x>min]'
			x[topo>min] = topo[topo>min]
			new_formula = formula.replace('x', index)
			x[topo>min]= eval(new_formula)
		elif min==None and max!=None:
			index = 'x[x<max]'
			x[topo<max]= topo[topo<max]
			new_formula = formula.replace('x', index)
			x[topo<max]=eval(new_formula)
		else:
			x= topo
			new_formula = formula
			x[:]=eval(new_formula)



		topo[np.isfinite(x)]=x[np.isfinite(x)]

		return topo


