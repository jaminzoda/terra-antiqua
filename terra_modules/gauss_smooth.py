import  gdal, gdalconst
import numpy as np
import os
from qgis.core import QgsRasterLayer
from scipy.ndimage.filters import gaussian_filter
import time
from .utils import TaProgressImitation, TaFeedback
from PyQt5.QtCore import pyqtSignal


def rasterSmoothing_slow(in_layer, factor, out_file=None, feedback=None, runtime_percentage=None):
	"""
	Smoothes values of pixels in a raster  by averaging  values around them
	:param in_layer: input raster layer (QgsRasterLayer) for smoothing
	:param out_file: String - output file to save the smoothed raster [Optional]. If the out_file argument is specified the smoothed raster will be written in a new raster, otherwise the old raster will be updated.
	:return:QgsRasterLayer. Smoothed raster layer.
	"""
	extent = in_layer.extent()
	x_max = extent.xMaximum()
	x_min = extent.xMinimum()
	feedback.log.emit("Gaussian filter is being applied for smoothing the raster")
	raster_ds = gdal.Open(in_layer.source(), gdalconst.GA_Update)
	in_band = raster_ds.GetRasterBand(1)
	in_array = in_band.ReadAsArray()
	rows = in_array.shape[0]
	cols = in_array.shape[1]

	out_array = np.zeros(in_array.shape)
	if runtime_percentage:
		total = runtime_percentage / rows if rows else 0
	else:
		total = 100 / rows if rows else 0

	x_dir = np.arange(cols)
	y_dir = np.arange(rows)
	x2d, y2d = np.meshgrid(x_dir, y_dir)
	factor = 10
	sigma = factor / np.sqrt(8 * np.log(2))
	feedback.log.emit("size of out_array: {}".format(out_array.shape))
	for i in range(rows):
		for j in range(cols):
			
			#Check if the raster covers the globe. To smooth across the date line.
			if x_max>=180 and x_min<=-180:
				# Define smoothing mask; periodic boundary along date line
				x_vector = np.mod((np.arange((j - factor), (j + factor + 1))), (cols - 1))
			else:
				x_vector = np.arange(np.maximum(0, j-factor), (np.minimum((cols-1), j+factor)+1),1)
			x_vector = x_vector.reshape(1, len(x_vector))
			y_vector = np.arange(np.maximum(0, i - factor), (np.minimum((rows - 1), i + factor) + 1), 1)
			y_vector = y_vector.reshape(len(y_vector), 1)
			kernel = np.exp(-((x_vector-j)**2+(y_vector-i)**2)/(2*sigma**2))
			kernel = kernel/(2*sigma**2)
			out_array[i,j]=np.sum(in_array[y_vector, x_vector]*kernel)
		if feedback:
			feedback.progress.emit(feedback.progress_count + (i * total))

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





def rasterSmoothing(in_layer, factor, out_file=None, feedback=None, runtime_percentage=None):
	"""
	Smoothes values of pixels in a raster  by averaging  values around them
	:param in_layer: input raster layer (QgsRasterLayer) for smoothing
	:param out_file: String - output file to save the smoothed raster [Optional]. If the out_file argument is specified the smoothed raster will be written in a new raster, otherwise the old raster will be updated.
	:return:QgsRasterLayer. Smoothed raster layer.
	"""
	
	

	

	raster_ds = gdal.Open(in_layer.source(), gdalconst.GA_Update)
	in_band = raster_ds.GetRasterBand(1)
	in_array = in_band.ReadAsArray()
	
	if runtime_percentage:
		total = runtime_percentage
	else:
		total = 100
	total_time = (in_array.size * 0.32/6485401)*factor
	fdbck = TaFeedback() 
	imit_progress = TaProgressImitation(total, total_time, fdbck, feedback)	
	imit_progress.start()
	
	rows = in_array.shape[0]
	cols = in_array.shape[1]
		
	extent = in_layer.extent()
	x_max = extent.xMaximum()
	x_min = extent.xMinimum()

	out_array = gaussian_filter(in_array, factor/2)

	
	
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
		
	fdbck.finished.emit(True)
	return smoothed_layer

