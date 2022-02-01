
# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

# -*- coding: utf-8 -*-
from .logger import TaFeedback
from qgis.gui import QgsMessageBar
from qgis.core import (
    QgsRasterLayer,
    QgsVectorLayer,
    QgsRasterBandStats,
    QgsColorRampShader,
    QgsGradientColorRamp,
    QgsGradientStop,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsProject,
    QgsField,
    QgsDistanceArea,
    QgsProcessingContext,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
    QgsFeature,
    QgsFeatureIterator,
    QgsFields,
    NULL,
    QgsMapLayer,
    QgsMapLayerType,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
    QgsRendererCategory,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsCoordinateReferenceSystem,
    QgsSimpleFillSymbolLayer,
    QgsProcessingException

)
from osgeo import gdal, osr, ogr, gdalconst
from PyQt5.QtCore import QVariant, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QColor
import sys
import tempfile
import os
import time


import numpy as np
# This to import math functions to be used in formula (modFormula)
from numpy import *
import subprocess
import random
from random import randrange
from typing import Tuple, Union


def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


try:
    from scipy.ndimage.filters import gaussian_filter, uniform_filter
except Exception:
    install_package('scipy')
    from scipy.ndimage.filters import gaussian_filter, uniform_filter


try:
    from plugins import processing
    from plugins.processing.tools import vector
except Exception:
    import processing
    from processing.tools import vector


def fillNoData(in_layer: QgsRasterLayer,
               out_file_path: str = None,
               no_data_value: Union[float, int] = None) -> str:
    """
    Fills the missing data by interpolating from edges.

    :param in_layer: A raster layer to fill gaps in.
    :type in_layer: QgsRasterLayer.
    :param no_data_value: NoDataValue of the input layer. These values to be set to np.nan   during the interpolation.
    :type no_data_value: float|int
    :param vlayer: A vector layer with masks for interpolating only inside masks

    :return: The path of the output file.
    :rtype: str.

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
    mask_path = os.path.join(
        temp_dir, "Valid_data_mask_for_interpolation.tiff")
    geotransform = raster_ds.GetGeoTransform()
    width = in_layer.width()
    height = in_layer.height()

    raster_ds = None

    out_array = np.ones(in_array.shape)

    out_array[np.isnan(in_array)] = np.nan
    out_array[np.isfinite(in_array)] = 1

    # Create Target - TIFF
    out_raster = gdal.GetDriverByName('GTiff').Create(
        mask_path, width, height, 1, gdal.GDT_Byte)
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

    # (4) delete the validity mask file
    driver = gdal.GetDriverByName('GTiff')
    if os.path.exists(mask_path):
        driver.Delete(mask_path)

    return out_file_path


def fillNoDataInPolygon(in_layer, poly_layer, out_file_path=None, no_data_value=None):
    """
    Fills the missing data by interpolating from edges.

    :param in_layer: Input raster layer in which the empty cells are filled with interpolation (IDW). Type: QgsRasterLayer.
    :param poly_layer: A vector layer with polygon masks that are used to interpolate values inside them. Type: QgsVectorLayer.
    :param out_file_path: A path for the output raster layer, filled. Type: str.
    :param no_data_value: NoDataValue of the input layer. These values to be set to np.nan   during the interpolation. Type: Number (Double, Int, Float...) or numpy.nan.
    :return: String - the path of the output file.

    """
    temp_dir = tempfile.gettempdir()
    if out_file_path is None:
        out_file_path = os.path.join(temp_dir, "Interpolated_raster.tiff")

    # (1) Get the input raster dataset
    if not type(in_layer) == QgsRasterLayer:
        raise TypeError("The input layer must be QgsRasterLayer")

    try:
        raster_ds = gdal.Open(
            in_layer.dataProvider().dataSourceUri(), gdal.GA_Update)
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

    # Get geotransform and raster size for rasterization
    geotransform = raster_ds.GetGeoTransform()
    width = in_layer.width()
    height = in_layer.height()

    # (2) Define the parameters for creating a mask raster of valid values.

    mask_path = os.path.join(
        temp_dir, "Valid_data_mask_for_interpolation.tiff")

    out_array = np.ones(in_array.shape)

    out_array[np.isnan(in_array)] = np.nan
    out_array[np.isfinite(in_array)] = 1

    # Create Target - TIFF
    out_raster = gdal.GetDriverByName('GTiff').Create(
        mask_path, width, height, 1, gdal.GDT_Byte)
    out_raster.SetGeoTransform(geotransform)
    crs = in_layer.crs().toWkt()
    out_raster.SetProjection(crs)
    out_band = out_raster.GetRasterBand(1)
    out_band.SetNoDataValue(np.nan)
    out_band.WriteArray(out_array)
    out_band.FlushCache()
    out_raster = None

    # Set the no_data values outside the polygon to -99999
    # Rasterize the input vector layer with polygon masks
    poly_array = vectorToRaster(poly_layer, geotransform, width, height)
    mapped_array = np.zeros((height, width))
    mapped_array[np.isnan(in_array)*(poly_array != 1) == 1] = 1
    raster_ds = None
    in_array = None

    # interpolation with the processing module
    input_layer = in_layer.dataProvider().dataSourceUri()

    fill_params = {'INPUT': input_layer,
                   'BAND': 1,
                   'DISTANCE': 100,
                   'ITERATIONS': 0,
                   'NO_MASK': False,
                   'MASK_LAYER': mask_path,
                   'OUTPUT': out_file_path}

    processing.run("gdal:fillnodata", fill_params)

    # Output raster
    raster_ds = gdal.Open(out_file_path, gdal.GA_Update)
    raster_array = raster_ds.GetRasterBand(1).ReadAsArray()
    raster_array[mapped_array == 1] = np.nan
    raster_ds.GetRasterBand(1).WriteArray(raster_array)
    raster_ds.GetRasterBand(1).FlushCache()
    raster_ds = None
    raster_array = None
    mapped_array = None
    poly_array = None

    # (4) delete the validity mask file
    driver = gdal.GetDriverByName('GTiff')
    if os.path.exists(mask_path):
        driver.Delete(mask_path)

    return out_file_path

def fillNoDataWithAFixedValue(in_layer:QgsRasterLayer,
                              value_to_fill:float,
                              mask_layer:QgsVectorLayer = None,
                              out_file_path:str = None) -> str:
    """Fills gaps in a raster layer with a specific fixed value.
    :param in_layer: A raster layer to fill gaps in.
    :type in_layer: QgsRasterLayer.
    :param value_to_fill: Fixed value that need to be assigned to NoData values pixels (gaps).
    :type value_to_fill: float.
    :param mask_layer: A mask layer to constrain filling within mask polygons.
    :type mask_layer: QgsVectorLayer.
    :param out_file_path: A path to save the ouput file at.
    :type out_file_path: str.

    :return: Path to the output file.
    :rtype: str.
    """
    if out_file_path is None:
        temp_dir = tempfile.gettempdir()
        out_file_path = os.path.join(temp_dir, "PaleoDEM_with_gaps_filled.tiff")
    ds = gdal.Open(in_layer.source())
    in_array = ds.GetRasterBand(1).ReadAsArray()
    no_data_value = ds.GetRasterBand(1).GetNoDataValue()
    geotransform = ds.GetGeoTransform()
    width = in_layer.width()
    height = in_layer.height()
    if not np.isnan(no_data_value):
        in_array[in_array==no_data_value] = np.nan
    if mask_layer and mask_layer.isValid():
       assert mask_layer.featureCount() >0, "The selected mask vector layer is empty."
       mask_array = vectorToRaster(mask_layer,
                                    geotransform,
                                    width,
                                    height)
       in_array[(mask_array==1)*np.isnan(in_array) == 1] = value_to_fill
    else:
        in_array[np.isnan(in_array)] = value_to_fill

    # Create Target - TIFF
    out_raster = gdal.GetDriverByName('GTiff').Create(out_file_path, width, height, 1, gdal.GDT_Float32)
    out_raster.SetGeoTransform(geotransform)
    crs = in_layer.crs().toWkt()
    out_raster.SetProjection(crs)
    out_band = out_raster.GetRasterBand(1)
    out_band.SetNoDataValue(np.nan)
    out_band.WriteArray(in_array)
    out_band.FlushCache()
    out_raster = None

    return out_file_path

def rasterSmoothing(in_layer, filter_type,
                    factor,
                    mask_layer=None,
                    smoothing_mode='reflect',
                    out_file=None,
                    feedback=None,
                    runtime_percentage=None):
    """
    Smoothes values of pixels in a raster  by implementing a low-pass filter  such as gaussian or uniform (mean filter)

    :param in_layer: input raster layer for smoothing
    :type in_layer: QgsRasterLayer
    :param factor: factor that is used define the size of a kernel used (e.g. 3x3, 5x5 etc).
    :type factor: int
    :param out_file: output file path to save the smoothed raster. If the out_file argument is specified the smoothed raster will be written in a new raster, otherwise the old raster will be updated.
    :type out_file_path: str
    :param mask_layer: a vector layer containing mask for smoothing only inside polygons.
    :type mask_layer: QgsVectorLayer.

    :return: Smoothed raster layer.
    :rtype: QgsRasterLayer
    """
    assert factor > 0, "The smoothing factor cannot be 0 or negative."
    assert factor <= 5, "In this version of Terra Antiqua the smoothing factor cannot be higher than 5."
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
    imit_progress = TaProgressImitation(total, total_time, feedback)
    imit_progress.start()

    rows = in_array.shape[0]
    cols = in_array.shape[1]
    geotransform = raster_ds.GetGeoTransform()
    if filter_type == 'Gaussian filter':
        out_array = gaussian_filter(in_array, factor / 2, mode=smoothing_mode)
    elif filter_type == 'Uniform filter':
        out_array = uniform_filter(
            in_array, factor*3-(factor-1), mode=smoothing_mode)

    # Rasterize mask layer and restore the initial values outside poligons if the smoothing is
    # set to be done only inside  polygons
    if mask_layer:
        mask_array = vectorToRaster(mask_layer, geotransform, cols, rows)
        out_array[mask_array != 1] = in_array[mask_array != 1]

    # set the initial nan values back to nan
    out_array[nan_mask] = np.nan

    # Write the smoothed raster
    # If the out_file argument is specified the smoothed raster will written in a new raster, otherwise the old raster will be updated
    if out_file != None:
        try:
            if os.path.exists(out_file):
                driver = gdal.GetDriverByName('GTiff')
                driver.Delete(out_file)
        except Exception as e:
            raise e
        smoothed_raster = gdal.GetDriverByName('GTiff').Create(
            out_file, cols, rows, 1, gdal.GDT_Float32)
        smoothed_raster.SetGeoTransform(geotransform)
        crs = in_layer.crs()
        smoothed_raster.SetProjection(crs.toWkt())
        smoothed_band = smoothed_raster.GetRasterBand(1)
        smoothed_band.WriteArray(out_array)
        smoothed_band.FlushCache()

        # Close datasets
        raster_ds = None
        smoothed_band = None
        smoothed_raster = None

        # Get the resulting layer to return
        smoothed_layer = QgsRasterLayer(out_file, 'Smoothed paleoDEM', 'gdal')
    else:
        in_band.WriteArray(out_array)
        in_band.FlushCache()

        # Close the dataset
        raster_ds = None

        # Get the resulting layer to return
        smoothed_layer = QgsRasterLayer(
            in_layer.dataProvider().dataSourceUri(), 'Smoothed paleoDEM', 'gdal')

    imit_progress.processingFinished.emit(True)
    while not imit_progress.isFinished():
        time.sleep(2)

    return smoothed_layer


def rasterSmoothingInPolygon(in_array: np.ndarray,
                             filter_type: str,
                             factor: int,
                             mask_array: np.ndarray = None,
                             smoothing_mode: str = 'reflect',
                             feedback: TaFeedback = None,
                             runtime_percentage: int = None) -> np.ndarray:
    """
    Smoothes values of an array by implementing a low-pass filter  such as gaussian or uniform (mean filter)

    :param in_array: input array or smoothing
    :type in_array: Numpy n-dimensional array
    :param filter_type: Smoothing filter type (for now accepts only "Uniform" and "Gaussian").
    :type filter_type: str.
    :param factor: factor that is used to define the size of a kernel used (e.g. 3x3, 5x5 etc).
    :type factor: int
    :param mask_array: an array containing mask for smoothing only inside polygons.
    :type mask_array: np.ndarray.
    :param feedback: A feedback object to report progress and log info.
    :type feedback: TaFeedback.
    :param runtime_percentage: Percentage of the total algorithm run time that smoothing takes.
    :type runtime_percentage: int.

    :return: Smoothed raster array.
    :rtype: np.ndarray
    """

    assert factor > 0, "The smoothing factor cannot be 0 or negative."
    assert factor <= 5, "In this version of Terra Antiqua the smoothing factor cannot be higher than 5."
    if runtime_percentage:
        total = runtime_percentage
    else:
        total = 100
    total_time = (in_array.size * 0.32 / 6485401) * factor
    imit_progress = TaProgressImitation(total, total_time, feedback)
    imit_progress.start()

    if filter_type == 'Gaussian filter':
        out_array = gaussian_filter(in_array, factor / 2, mode=smoothing_mode)
    elif filter_type == 'Uniform filter':
        out_array = uniform_filter(
            in_array, factor*3-(factor-1), mode=smoothing_mode)

    if mask_array is not None:
        out_array[mask_array != 1] = in_array[mask_array != 1]

    imit_progress.processingFinished.emit(True)
    while not imit_progress.isFinished():
        time.sleep(2)

    return out_array


def setRasterSymbology(in_layer, color_ramp_name=None):
    """
    Applies a color palette to a raster layer. It does not add the raster layer to the Map canvas. Before passing a layer to this function, it should be added to the map canvas.

    :param in_layer: A raster layer to apply a new color palette to.
    :type in_layer: QgsRasterLayer
    :param color_ramp_name: name of the color ramp to apply to in_layer.
    :type color_ramp_name: str

    """
    path_to_color_schemes = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "../resources/color_schemes"))
    if color_ramp_name:
        file_names = []
        for (dirpath, dirnames, filenames) in os.walk(path_to_color_schemes):
            file_names.extend(filenames)
        for file in file_names:
            with open(os.path.join(path_to_color_schemes, file)) as f:
                lines = f.readlines()
                color_scheme_name = lines[0].strip()
                color_scheme_name = color_scheme_name.replace("#", "")
                if color_scheme_name == color_ramp_name:
                    color_palette_file = os.path.join(
                        path_to_color_schemes, file)
    else:
        color_palette_file = os.path.join(
            path_to_color_schemes, "TerraAntiqua_color_ramp.cpt")

    def readCpt(file_name):
        color_lines = []
        with open(file_name) as file:
            lines = file.readlines()
            for line_no, line in enumerate(lines):
                new_line = line.strip()
                if new_line and not any([new_line[0] == '#',
                                         new_line[0] == 'B',
                                         new_line[0] == 'F',
                                         new_line[0] == 'N']):
                    new_line = new_line.split('\t')
                    new_line = [i for i in new_line if i]
                    color_lines.append(new_line)
        return color_lines

    def getColorRampItems(ramp_shader: QgsColorRampShader, color_lines, minimum, maximum):
        color_items_list = []
        for line_no, line in enumerate(color_lines):
            r, g, b = line[1].split('/')
            if line_no == 0:
                color_item = ramp_shader.ColorRampItem(
                    minimum, QColor(int(r), int(g), int(b)), str(round(minimum)))
            elif line_no == len(color_lines)-1:
                r_last, g_last, b_last = line[3].split('/')
                color_item = ramp_shader.ColorRampItem(float(line[0]), QColor(int(r), int(g), int(b)),
                                                       str(round(float(line[0]))))
                color_items_list.append(color_item)
                if not maximum <= float(line[0]):
                    color_item1 = ramp_shader.ColorRampItem(maximum, QColor(
                        int(r_last), int(g_last), int(b_last)), str(round(maximum)))
                    color_items_list.append(color_item1)
                continue
            else:
                color_item = ramp_shader.ColorRampItem(float(line[0]), QColor(
                    int(r), int(g), int(b)), str(round(float(line[0]))))
            color_items_list.append(color_item)
        return color_items_list

    def createColorRamp(color_ramp_items: list) -> QgsGradientColorRamp:
        """Creates a QgsGradient color ramp from ColorRampItem list.
        :param color_ramp_items: A list of color ramp items.
        :type color_ramp_items: QgsColorRampShader.ColorRampItem.

        :return: Color ramp.
        :rtype: QgsGradientColorRamp
        """
        color_ramp = QgsGradientColorRamp()
        color1 = color_ramp_items[0].color
        color2 = color_ramp_items[-1].color
        color_ramp.setColor1(color1)
        color_ramp.setColor2(color2)
        stops = []
        maximum_value = color_ramp_items[-1].value
        minimum_value = color_ramp_items[0].value
        for item in color_ramp_items[1:len(color_ramp_items)-1]:
            max_min_distance = np.sqrt(pow(maximum_value-minimum_value, 2))
            stop_distance = np.sqrt(pow(item.value - minimum_value, 2))
            stop = stop_distance/max_min_distance
            stops.append(QgsGradientStop(stop, item.color))
        color_ramp.setStops(stops)
        return color_ramp

    stats = in_layer.dataProvider().bandStatistics(1, QgsRasterBandStats.All)
    min_elev = stats.minimumValue
    max_elev = stats.maximumValue
    ramp_shader = QgsColorRampShader()
    ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

    cpt_data = readCpt(color_palette_file)
    lst = getColorRampItems(ramp_shader, cpt_data, min_elev, max_elev)
    ramp_shader.setColorRampItemList(lst)
    ramp_shader.setSourceColorRamp(createColorRamp(lst))
    # ramp_shader.classifyColorRamp()

    # We’ll assign the color ramp to a QgsRasterShader
    # so it can be used to symbolize a raster layer.
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp_shader)

    # Finally, we need to apply the symbology we’ve created to the raster layer.
    # First, we’ll create a renderer using our raster shader.
    # Then we’ll Assign the renderer to our raster layer.

    renderer = QgsSingleBandPseudoColorRenderer(
        in_layer.dataProvider(), 1, shader)
    renderer.setClassificationMax(max_elev)
    renderer.setClassificationMin(min_elev)
    in_layer.setRenderer(renderer)
    in_layer.triggerRepaint()


def setVectorSymbology(in_layer):
    """
    Renders symbology for the input vector layer.

    :param in_layer: input vector layer for rendering symbology.
    :type in_layer: QgsVectorLayer.
    """
    # provide file name index and field's unique values

    layer = in_layer
    assert layer.type() == QgsMapLayerType.VectorLayer, "The input layer must be of type QgsVectorLayer."
    if not layer.isValid():
        raise Exception("The input vector layer is not valid.")
    list_of_fields = ['Category', 'Id', 'ID', 'iD', 'id', 'Fid', 'FID', 'fid']
    fni = -1
    for f in list_of_fields:
        if not fni == -1:
            break
        fni = layer.fields().indexFromName(f)
    unique_values = layer.uniqueValues(fni)

    # fill categories
    categories = []
    for unique_value in unique_values:
        # initialize the default symbol for this geometry type
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())

        # configure a symbol layer
        layer_style = {}
        layer_style['color'] = '%d, %d, %d' % (
            randrange(0, 256), randrange(0, 256), randrange(0, 256))
        layer_style['outline'] = '#000000'
        symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)

        # replace default symbol layer with the configured one
        if symbol_layer is not None:
            symbol.changeSymbolLayer(0, symbol_layer)

        # create renderer object
        category = QgsRendererCategory(unique_value, symbol, str(unique_value))
        # entry for the list of category items
        categories.append(category)

    # create renderer object
    renderer = QgsCategorizedSymbolRenderer(
        layer.fields().field(fni).name(), categories)

    # assign the created renderer to the layer
    if renderer is not None:
        layer.setRenderer(renderer)

    layer.triggerRepaint()


def vectorToRaster(in_layer, geotransform, width, height, feedback=None, field_to_burn=None, no_data=None, burn_value=None, output_path=None):
    """
    Rasterizes a vector layer and returns a numpy array.
    :param in_layer: Accepted data types:
                - str: layer ID
                - str: layer name
                - str: layer source
                - QgsProcessingFeatureSourceDefinition
                - QgsProperty
                - QgsVectorLayer

    :param field_to_burn: A specific field from attributes table to get values to burn. This can be a field with depth or elevation values.
    :param no_data: No data value. It can be NAN, zero or any other value.
    :param burn_value: A fixed value to burn in the raster.
    :param geotransform: geotransform for the resulting raster layer. Can accept geotransform (raster_ds.GetGeotransform()) extent (raster_layer.extent()) and QgsRasterLayer.
    :param width: number of columns in the raster. Should be consistent with the raster that the masks will deployed on.
    :param height: number of rows in the raster. Should be consistent with the raster that the masks will deployed on.
    :return: Numpy array.
    """

    # define the output path for the resulting raster file
    output = os.path.join(tempfile.gettempdir(
    ), "Rasterized_vector_layer.tiff") if output_path is None else output_path
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

    # Burn values from a field in the attribute table if the field is supplied
    field_to_burn = field_to_burn if field_to_burn is not None else None

    # Specify NODATA value
    nodata = no_data if no_data is not None else np.nan
    # If a fixed value should be burned, specify the value to burn
    burn_value = burn_value if burn_value is not None else 1

    # Check if the input vector layer contains any feature
    assert (in_layer.featureCount(
    ) > 0), "The Input vector layer does not contain any feature (polygon, polyline or point)."

    r_params = {
        'INPUT': in_layer,
        'FIELD': field_to_burn,
        'BURN': burn_value,  # 1 - if no fixed value is burned
        'UNITS': 0,  # 0- Pixels; 1 - Georeferenced units
        'WIDTH': width,  # Width of the input layer will be used
        'HEIGHT': height,  # Height of the input layer will be used
        'EXTENT': raster_extent,
        'NODATA': nodata,
        'OPTIONS': '',
        'DATA_TYPE': 5,  # Float32 is used
        'INIT': None,
        'INVERT': False,
        'OUTPUT': output
    }
    try:
        points_raster = processing.run("gdal:rasterize", r_params)["OUTPUT"]
    except QgsProcessingException as e:
        if feedback:
            feedback.Error(e)
        else:
            raise e

    points_raster_ds = gdal.Open(points_raster)
    points_array = points_raster_ds.GetRasterBand(1).ReadAsArray()

    drv = gdal.GetDriverByName('GTIFF')
    drv.Delete(output)

    return points_array


def vectorToRasterOld(in_layer, geotransform, ncols, nrows):
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
    mask_raster = gdal.GetDriverByName('MEM').Create(
        '', ncols, nrows, 1, gdal.GDT_Int32)
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


def polygonsToPolylines(in_layer):
    """
    Converts polygons to polylines.

    :param in_layer: Vector layer with polygons to be converted into polylines.
    :type in_layer: QgsVectorLayer

    :return: Vector layer containing polylines
    :rtype: QgsVectorLayer
    """

    polygons_layer = in_layer
    try:
        fixed_polygons = processing.run('native:fixgeometries',
                                        {'INPUT': polygons_layer,
                                         'OUTPUT': 'memory:' + "fixed_pshoreline_polygons"
                                         })['OUTPUT']
    except Exception as e:
        raise e
    try:
        polylines = processing.run("qgis:polygonstolines",
                                   {'INPUT': fixed_polygons,
                                    'OUTPUT': 'memory:polylines_from_prolygons'})
    except Exception as e:
        raise e

    return polylines['OUTPUT']


def polylinesToPolygons(in_layer: QgsVectorLayer, feedback: TaFeedback) -> QgsVectorLayer:
    """Creates polygon feature from the points of line features.

    :param in_layer: Input vector layer.
    :type in_layer: QgsVectorLayer
    :param feedback: A feedback object to show progress and log info.
    :type feedback: TaFeedback

    :return: Vector layer containing polygonized polylines.
    :rtype: QgsVectorLayer
    """
    features = in_layer.getFeatures()
    assert in_layer.featureCount() > 0, "The input layer is empty."
    polygonFeatures = []
    for feature in features:
        if feedback.canceled:
            break
        # get the geometry of a feature
        geometry = feature.geometry()
        attributes = feature.attributes()

        # checking if the geometry is polyline or multipolyline
        if geometry.wkbType() == QgsWkbTypes.LineString:
            coordinates = geometry.asPolyline()
        elif geometry.wkbType() == QgsWkbTypes.MultiLineString:
            coordinates = geometry.asMultiPolyline()
        else:
            feedback.info(
                "The geometry is neither polyline nor multipolyline.")
        polygonGeometry = QgsGeometry.fromPolygonXY(coordinates)
        feature = QgsFeature()
        feature.setGeometry(polygonGeometry)
        feature.setAttributes(attributes)
        polygonFeatures.append(feature)

    if not feedback.canceled:
        out_layer = QgsVectorLayer(
            'Polygon?crs='+in_layer.crs().authid(), in_layer.name(), 'memory')
        out_layer.dataProvider().addFeatures(polygonFeatures)
        del polygonFeatures

        # Fix invalid geometries
        output_layer = processing.run('native:fixgeometries',
                                      {'INPUT': out_layer, 'OUTPUT': 'memory:'})['OUTPUT']
        output_layer.setName(in_layer.name())
        feedback.info(
            "Fixed invalid geometries in layer {}.".format(in_layer.name()))
        return output_layer
    else:
        return None


def refactorFields(in_layer, layer2, out_layer_name):
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

    params = {'INPUT': layer1, 'FIELDS_MAPPING': field_mapping,
              'OUTPUT': 'memory:{}'.format(out_layer_name)}
    refactored_layer = processing.run("qgis:refactorfields", params)['OUTPUT']

    return refactored_layer, fields_refactored


def modMinMax(in_array, fmin: int, fmax: int):
    """
    Modifies the elevation/bathimetry values based on the current and provided
    minimum and maximum values.  This is basically flattening and roughening.

    :param in_array: input numpy array for modification.
    :param fmin: final minimum value of elevation/bathymetry.
    :param fmax: final maximum value of elevation/bathymetry.
    :return: numpy.array
    """

    # Define the initial minimum and maximum values of the array
    # imin = in_array.min()
    imax = in_array[np.isfinite(in_array)].max()
    out_array = in_array

    ratio = (imax - fmin) / (fmax - fmin)
    out_array[out_array >= fmin] = fmin + \
        (in_array[in_array >= fmin] - fmin) / ratio
    return out_array


def modRescale(in_array: np.ndarray, min: int, max: int) -> np.ndarray:
    """
    Modifies the elevation/bathimetry
    values based on the current and provided
    minimum and maximum values.
    This is basically flattening and roughening.

    :param in_array: input numpy array for modification.
    :type in_array: np.ndarray.
    :param fmin: final minimum value of elevation/bathymetry.
    :type fmin: int.
    :param fmax: final maximum value of elevation/bathymetry.
    :type fmax: int.

    :return:rescaled array.
    :rtype:np.ndarray.
    """

    # Define the initial minimum and maximum values of the array
    if in_array.size > 0 and np.isfinite(in_array).size > 0:
        imax = in_array[np.isfinite(in_array)].max()
        imin = in_array[np.isfinite(in_array)].min()
    else:
        raise ValueError("The input Array is empty.")
    out_array = in_array
    out_array[:] = (max - min) * (out_array[:] - imin) / (imax - imin) + min

    return out_array


def modFormula(in_array, formula, min=None, max=None):
    """
    Modifies elevation values given a formula.

    :param in_array (numpy array): an input array that contains elevation values.
    :param formula: the formula to be used for topography modification.

    :param mask_array: mask that will be used to subset area of the raster (input array) for modification.
    :return: numpy array of modified elevation values.
    """

    topo = in_array

    H = np.empty(topo.shape)
    H.fill(np.nan)
    if min != None and max != None:
        index = 'H[(H>min)*(H<max)==1]'
        H[(topo > min) * (topo < max) == 1] = topo[(topo > min) * (topo < max) == 1]
        new_formula = formula.replace('H', index)
        H[(topo > min) * (topo < max) == 1] = eval(new_formula)

    elif min != None and max == None:
        index = 'H[H>min]'
        H[topo > min] = topo[topo > min]
        new_formula = formula.replace('H', index)
        H[topo > min] = eval(new_formula)
    elif min == None and max != None:
        index = 'H[H<max]'
        H[topo < max] = topo[topo < max]
        new_formula = formula.replace('H', index)
        H[topo < max] = eval(new_formula)
    else:
        H = topo
        new_formula = formula
        H[:] = eval(new_formula)

    topo[np.isfinite(H)] = H[np.isfinite(H)]

    return topo


# for now is used for output paths. Modify the raise texts to fit in other contexts.
def isPathValid(path: str, output_type: str) -> tuple:
    """
    Checks if the specified output path is valid and accessible. Returns True, if the path is a file path and writable. False otherwise.
    """
    # Check if the path is empty
    file_check = False
    path_check = False
    file_name = os.path.split(path)[1]
    file_ext = os.path.splitext(file_name)[1]

    if file_name and file_ext:
        if output_type == 'raster':
            if file_ext == ".tiff" or file_ext == ".tif":
                file_check = True
        elif output_type == 'vector':
            if file_ext == ".shp":
                file_check = True

    dir_path = os.path.split(path)[0]
    if dir_path:
        if os.access(dir_path, os.W_OK):
            path_check = True

    if path_check and file_check:
        return (True, "")
    else:
        if not file_check and output_type == 'raster':
            return(False, "Error: The file output file name is incorrect. Please provide a proper file name for the output. The file name should have a '.tif' or '.tiff' extension.")
        elif not file_check and output_type == 'vector':
            return(False, "Error: The file output file name is incorrect. Please provide a proper file name for the output. The file name should have a '.shp' extension.")
        elif not path_check:
            return(False, "Error: The output path does not exist or you do not have write permissions.")
        else:
            return(False, "Error: The provided path for the output is not correct. Example: {} or {}".format(r'C:\\Users\user_name\Documents\file.tiff', r'C:\\Users\user_name\Documents\file.shp'))


def reprojectVectorLayer(input_layer: QgsVectorLayer,
                         target_crs: QgsCoordinateReferenceSystem = QgsCoordinateReferenceSystem(
                             'EPSG:4326'),
                         output_path: str = 'TEMPORARY_OUTPUT',
                         feedback: TaFeedback = None) -> QgsVectorLayer:
    """
    Reprojects input vector layers into a different coordinate reference system.
    :param input_layer: Input layer to be reprojected.
    :type input_layer: QgsVectorLayer.
    :param target_crs: The crs of the ouput layer. Defaults to epsg:4326 - WGS84
    :type target_crs: QgsCoordinateReferenceSystem.
    :param output_path: Path to save ouput file. Defaults to "TEMPORARY_OUTPUT" and saves the output in the memory.
    :type output_path: str.
    """
    reprojecting_params = {"INPUT": input_layer,
                           "TARGET_CRS": target_crs.authid(),
                           "OUTPUT": output_path}
    if feedback:
        feedback.info(
            f"Reprojecting {input_layer.name()} layer from {input_layer.crs().authid()} to {target_crs.authid()}.")
    try:
        reprojected_layer = processing.run(
            "native:reprojectlayer", reprojecting_params)['OUTPUT']
    except Exception as e:
        if feedback:
            feedback.warning(
                f"Reprojection of {input_layer.name()} layer failed due to the following exception:")
            feedback.warning(f"{e}")
            return input_layer
        else:
            raise e
    reprojected_layer.setName(input_layer.name())
    return reprojected_layer


def generateUniqueIds(vlayer, id_field) -> QgsVectorLayer:
    id_found = False
    fields = vlayer.fields().toList()
    for field in fields:
        if field.name().lower == id_field:
            id_found = True
            id_field = field
        else:
            pass

    if not id_found:
        id_field = QgsField("id", QVariant.Int, "integer")
        vlayer.startEditing()
        vlayer.addAttribute(id_field)
        vlayer.commitChanges()

    features = vlayer.getFeatures()
    vlayer.startEditing()
    for current, feature in enumerate(features):
        feature[id_field.name()] = current
        vlayer.updateFeature(feature)

    return vlayer


def randomPointsInPolygon(source, point_density, min_distance, feedback, runtime_percentage):
    """
    Creates random points inside polygons.

    :param source: input vector layer with polygon features, inside which the random points will be created.
    :param point_density: the density of points to be created inside polygons. Number of points to be created will be calculated with the following formula: Pnumber = Pdensity * PolygonArea.
    :param min_distance: Minimum distance that will be kept between created points.
    :param feedback: a feedback object to provide progress and other info to user. For now a Qthread object is passed to use its pyqtsignals, functions and attributes for feedback purposes.
    :param runtime_percentage: time that this part of the algorithm will take (this function is run inside an algorithm e.g. Feature Creator) in percent (e.g. 10%)
    """
    progress_count = feedback.progress

    context = QgsProcessingContext()
    context.setProject(QgsProject.instance())

    da = QgsDistanceArea()
    da.setSourceCrs(source.crs(), context.transformContext())
    da.setEllipsoid(context.project().ellipsoid())

    fields = QgsFields()
    fields.append(QgsField('id', QVariant.Int, '', 10, 0))
    crs = source.crs().toWkt()
    points_layer = QgsVectorLayer("Point?" + crs, "Depth layer", "memory")
    points_layer_dp = points_layer.dataProvider()
    points_layer_dp.addAttributes(fields)
    points_layer.updateFields()

    total = runtime_percentage / source.featureCount() if source.featureCount() else 0

    pointId = 0
    created_features = []
    for current, f in enumerate(source.getFeatures()):
        if feedback.canceled:
            break

        if not f.hasGeometry():
            continue

        fGeom = f.geometry()
        engine = QgsGeometry.createGeometryEngine(fGeom.constGet())
        engine.prepareGeometry()

        bbox = fGeom.boundingBox()
        area = da.measureArea(fGeom)
        if da.areaUnits() != 8:
            area = da.convertAreaMeasurement(area, 8)

        pointCount = int(round(point_density * area))

        if pointCount == 0:
            feedback.warning(
                "Warning: Skip feature {} while creating random points as number of points for it is 0.".format(f.id()))
            continue

        index = None
        if min_distance:
            index = QgsSpatialIndex()
        points = dict()

        nPoints = 0
        nIterations = 0
        maxIterations = pointCount * 200
        feature_total = total / pointCount if pointCount else 1

        random.seed()
        try:
            feedback.info(
                "{0} random points being created inside feature <b>{1}</b>.".format(
                    pointCount,
                    f['name'] if f['name'] != NULL else "NoName"
                )
            )
        except KeyError:
            feedback.info("{0} random points being created inside feature ID {1}.".format(
                pointCount, f.id()))

        while nIterations < maxIterations and nPoints < pointCount:
            if feedback.canceled:
                break

            rx = bbox.xMinimum() + bbox.width() * random.random()
            ry = bbox.yMinimum() + bbox.height() * random.random()

            p = QgsPointXY(rx, ry)
            geom = QgsGeometry.fromPointXY(p)
            if engine.contains(geom.constGet()) and \
                    (not min_distance or vector.checkMinDistance(p, index, min_distance, points)):
                f = QgsFeature(nPoints)
                f.initAttributes(1)
                f.setFields(fields)
                f.setAttribute('id', pointId)
                f.setGeometry(geom)
                created_features.append(f)
                if min_distance:
                    index.addFeature(f)
                points[nPoints] = p
                nPoints += 1
                pointId += 1
                if int(progress_count) < int(nPoints*feature_total):
                    progress_count += int(nPoints*feature_total)
                    feedback.progress = progress_count
            nIterations += 1

        if nPoints < pointCount:
            feedback.info(
                'Could not generate requested number of random points. Maximum number of attempts exceeded.')

    points_layer_dp.addFeatures(created_features)
    points_layer_dp = None
    nPolygons = source.featureCount()
    feedback.info(
        "Created random points inside {} polygons.".format(nPolygons))

    return points_layer


def bufferAroundGeometries(in_layer: Union[QgsVectorLayer, QgsFeatureIterator],
                           buf_dist: int,
                           num_segments: int,
                           feedback: TaFeedback,
                           runtime_percentage: int) -> QgsVectorLayer:
    """Creates buffer around polygon geometries.

    :param in_layer: Input vector layer
    :type in_layer: QgsVectorLayer or QgsFeatureIterator
    :param buf_dist: Buffer distance in map units.
    :type buf_dist: float
    :param num_segments: Number of segments (int) used to approximate curves
    :type num_segments: int
    :param feedback: A feedback object to report feedback into log tab.
    :type feedback: TaFeedback
    :param runtime_percentage: Percentage of runtime (int) to report progress
    :type runtime_percentage: int

    :return: Vector layer that contain created buffer polygons.
    :rtype: QgsVectorLayer
    """

    feats = in_layer.getFeatures()

    buffer_layer = QgsVectorLayer('Polygon?crs={}'.format(
        in_layer.crs().authid()), '', 'memory')
    fixed_layer = QgsVectorLayer('Polygon?crs={}'.format(
        in_layer.crs().authid()), '', 'memory')
    dp = buffer_layer.dataProvider()
    dp_fixed = fixed_layer.dataProvider()
    total = runtime_percentage/in_layer.featureCount() if in_layer.featureCount() else 0
    progress = 0
    for current, feat in enumerate(feats):
        if feedback.canceled:
            break
        geom_in = feat.geometry()
        fixed_geom = geom_in.makeValid()
        buf = fixed_geom.buffer(buf_dist, num_segments)
        feat.setGeometry(fixed_geom)
        buf_feat = QgsFeature()
        buf_feat.setGeometry(buf)
        dp.addFeature(buf_feat)
        dp_fixed.addFeature(feat)
        progress += total
        if progress >= 1:
            feedback.progress += int(progress)
            progress = 0
    dp = None
    dp_fixed = None
    params = {
        'INPUT': buffer_layer,
        'OVERLAY': fixed_layer,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    }
    out_layer = processing.run("native:difference", params)['OUTPUT']
    return out_layer


def polygonOverlapCheck(vlayer, selected_only=False, feedback=None,
                        run_time=None):

    if selected_only:
        features = vlayer.getSelectedFeatures()
    else:
        features = vlayer.getFeatures()
    features = list(features)
    if run_time:
        total = run_time
    else:
        total = 100
    overlaps_number = 0
    for i in range(0, len(features)):
        if feedback and feedback.canceled:
            break
        for j in range(0, len(features)):
            if feedback and feedback.canceled:
                break
            if i == j:
                continue
            if features[i].geometry().overlaps(features[j].geometry()):
                overlaps_number += 1
        if feedback:
            feedback.progress += total/len(features)

    return overlaps_number


def assignUniqueIds(vlayer, feedback, run_time):
    progress_count = feedback.progress
    id_found = False
    fields = vlayer.fields().toList()
    if run_time:
        total = run_time
    else:
        total = 100
    for field in fields:
        if feedback and feedback.canceled:
            break
        if field.name().lower() == "id":
            id_found = True
            id_field = field
            break
        progress_count += total*0.3/len(fields)
        if not int(feedback.progress) == int(progress_count):
            feedback.progress = int(progress_count)

    if not id_found:
        id_field = QgsField("id", QVariant.Int, "integer")
        vlayer.startEditing()
        vlayer.addAttribute(id_field)
        vlayer.commitChanges()

    features = vlayer.getFeatures()
    vlayer.startEditing()
    for current, feature in enumerate(features):
        if feedback and feedback.canceled:
            break
        feature[id_field.name()] = current
        vlayer.updateFeature(feature)
        progress_count += total*0.7/vlayer.featureCount()
        if not int(feedback.progress) == int(progress_count):
            feedback.progress = int(progress_count)

    ret_code = vlayer.commitChanges()

    if ret_code:
        return (vlayer, True)
    else:
        return (None, False)


def smoothArrayWithWrapping(input_array: np.ndarray,
                            index: list,
                            side: str,
                            wrapping_size: tuple,
                            filter_type: str,
                            smoothing_factor: int,
                            mask_array: np.ndarray,
                            feedback: TaFeedback = None,
                            runtime_percentage: int = None) -> np.ndarray:
    """ Reads a subset of a 2-dimensional numpy array, wrapping it around the edges to opposite side.

    :prarm input_array: Input numpy array to read a subset from.
    :type input_array: np.ndarray.
    :param index: A list of tuples with indices for reading the input array. Each tuple in the list contains two
    addresses - from and to for each axis (rows, columns).
    :type index: list.
    :param side: Side of the array for wrapping (E or W).
    :type side: str.
    :param wrapping_size: Number of rows and columns (integer) to read from the opposite side of the array.
    :type wrapping_size: tuple.

    :return: A subset of the input array wrapped around the specified edges by the specified size.
    :rtype: np.ndarray
    """
    row_from, row_to = index[0]
    col_from, col_to = index[1]
    subset_array = input_array[row_from:row_to, col_from:col_to]
    if side == 'E':
        wrapping_array = input_array[row_from:row_to, 0:wrapping_size]
        wrapped_array = np.concatenate((subset_array, wrapping_array), axis=1)
    elif side == 'W':
        wrapping_array = input_array[row_from:row_to, wrapping_size*(-1):]
        wrapped_array = np.concatenate((wrapping_array, subset_array), axis=1)
    else:
        raise ValueError("Wrapping side is neither W nor E.")

    try:
        smoothed_array = rasterSmoothingInPolygon(wrapped_array,
                                                  filter_type,
                                                  smoothing_factor,
                                                  feedback=feedback,
                                                  runtime_percentage=runtime_percentage
                                                  )
    except Exception as e:
        raise e
    if side == "E":
        output_array = np.delete(smoothed_array, np.s_[
                                 0:wrapping_size], axis=1)
    else:
        output_array = np.delete(smoothed_array, np.s_[
                                 wrapping_size*(-1):], axis=1)

    try:
        output_array[mask_array != 1] = subset_array[mask_array != 1]
    except Exception as e:
        feedback.warning(
            "Failed to apply a mask array to the wrapped and smoothed array.")
        feedback.error(e)

    return output_array


def loadHelp(dlg):
    # set the help text in the  help box (QTextBrowser)
    files = [
        ('TaCompileTopoBathyDlg', 'compile_tb'),
        ('TaSetPaleoshorelinesDlg', 'set_pls'),
        ('TaModifyTopoBathyDlg', 'modify_tb'),
        ('TaCreateTopoBathyDlg', 'create_tb'),
        ('TaRemoveArtefactsDlg', 'remove_arts'),
        ('TaPrepareMasksDlg', 'prepare_masks'),
        ('TaRemoveArtefactsTooltip', 'remove_arts_tooltip')
    ]
    for class_name, file_name in files:
        if class_name == type(dlg).__name__:
            path_to_file = os.path.join(os.path.dirname(
                __file__), '../help_text/{}.html'.format(file_name))

    with open(path_to_file, 'r', encoding='utf-8') as help_file:
        help_text = help_file.read()
    dlg.helpBox.setHtml(help_text)


class TaProgressImitation(QThread):
    ProgressStoped = False
    processingFinished = pyqtSignal(bool)

    def __init__(self, total, total_time, feedback):
        super().__init__()
        self.total = total
        self.processingFinished.connect(self.finish)
        self.unit_time = total_time/self.total
        self.feedback = feedback

    def run(self):
        for i in range(round(self.total)):
            if self.ProgressStoped:
                break
            self.feedback.progress = self.feedback.progress+i
            time.sleep(self.unit_time)
        self.feedback.progress = self.feedback.progress+self.total

    def finish(self):
        self.ProgressStoped = True


class TaFeedbackOld(QObject):
    finished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()


class TaVectorFileWriter(QgsVectorFileWriter):
    def __init__(self):
        super().__init__()

    def writeToShapeFile(layer: QgsVectorLayer,
                         fileName: str,
                         fileEncoding: str,
                         destCRS: QgsCoordinateReferenceSystem,
                         driverName: str) -> Tuple[QgsVectorFileWriter.WriterError, str]:
        """This function is used to make writing to shapefiles compatible beteen Qgis version >3.10 and <3.10."""

        # Check if the file is already created. Acts like overwrite
        if os.path.exists(fileName):
            deleted = TaVectorFileWriter.deleteShapeFile(fileName)
            if not deleted:
                raise Exception(
                    "Could not delete shapefile {}.".format(fileName))
        try:
            result = TaVectorFileWriter.writeAsVectorFormat(
                layer, fileName, fileEncoding, destCRS, driverName)
        except Exception:
            context = QgsCoordinateTransformContext()
            context.addCoordinateOperation(destCRS, destCRS, destCRS.toProj())
            options = TaVectorFileWriter.SaveVectorOptions()
            options.driverName = driverName
            result = TaVectorFileWriter.writeAsVectorFormat2(
                layer, fileName, context, options)
        return result
