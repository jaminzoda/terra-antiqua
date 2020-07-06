import  gdal, gdalconst
import numpy as np
import os
from qgis.core import QgsRasterLayer

from .utils import TaProgressImitation, TaFeedbackOld, install_package, fillNoData
try:
    from scipy.ndimage.filters import gaussian_filter, uniform_filter
except Exception:
    install_package('scipy')
    from scipy.ndimage.filters import gaussian_filter, uniform_filter

import time

from PyQt5.QtCore import pyqtSignal


def rasterSmoothing(in_layer, filter_type, factor, out_file=None, feedback=None, runtime_percentage=None):
    """
    Smoothes values of pixels in a raster  by implementing a low-pass filter  such as gaussian or uniform (mean filter)
    :param in_layer: input raster layer (QgsRasterLayer) for smoothing
    :param factor: factor that is used define the size of a kernel used (e.g. 3x3, 5x5 etc).
    :param out_file: String - output file to save the smoothed raster [Optional]. If the out_file argument is specified the smoothed raster will be written in a new raster, otherwise the old raster will be updated.
    :return:QgsRasterLayer. Smoothed raster layer.
    """

    raster_ds = gdal.Open(in_layer.source(), gdalconst.GA_Update)
    in_band = raster_ds.GetRasterBand(1)
    no_data_value = in_band.GetNoDataValue()
    in_array = in_band.ReadAsArray()
    in_array[in_array == no_data_value] = np.nan
    nan_mask = np.isnan(in_array)
    # Check if data contains NaN values. If it contains, interpolate values for them first
    # If the pixels with NaN values are left empty they will cause part of the smoothed raster to get empty.
    # Gaussian filter removes all values under the kernel, which contain at least one NaN value
    if np.isnan(in_array).any():
        in_array = None
        filled_raster = fillNoData(in_layer)
        raster_ds_filled = gdal.Open(filled_raster, gdalconst.GA_ReadOnly)
        in_band_filled = raster_ds_filled.GetRasterBand(1)
        in_array = in_band_filled.ReadAsArray()
        raster_ds_filled = None
        in_band_filled = None

    if runtime_percentage:
        total = runtime_percentage
    else:
        total = 100
    total_time = (in_array.size * 0.32 / 6485401) * factor
    fdbck = TaFeedbackOld()
    imit_progress = TaProgressImitation(total, total_time, fdbck, feedback)
    imit_progress.start()

    rows = in_array.shape[0]
    cols = in_array.shape[1]
    if filter_type == 'Gaussian filter':
        out_array = gaussian_filter(in_array, factor / 2)
    elif filter_type == 'Uniform filter':
        out_array = uniform_filter(in_array, factor*3-(factor-1))


    #set the initial nan values back to nan
    out_array[nan_mask]=np.nan

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
    while not imit_progress.isFinished():
        time.sleep(2)

    return smoothed_layer


