# -*- coding: utf-8 -*-
import sys
import tempfile
import os

import numpy as np
import subprocess
from random import randrange

try:
    from scipy.ndimage.filters import gaussian_filter, uniform_filter
except Exception:
    install_package('scipy')
    from scipy.ndimage.filters import gaussian_filter, uniform_filter

import time
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QVariant, QThread, QObject, pyqtSignal

import random
from osgeo import gdal, osr, ogr
from osgeo import gdalconst
from qgis.core import (
    QgsRasterLayer,
    QgsVectorLayer,
    QgsRasterBandStats,
    QgsColorRampShader,
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
    QgsFields,
    NULL,
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

from qgis.gui import QgsMessageBar
try:
    from plugins import processing
    from plugins.processing.tools import vector
except Exception:
    import processing
    from processing.tools import vector

from .logger import TaFeedback



def fillNoData(in_layer, out_file_path=None, no_data_value=None):
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

    raster_ds = None


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
        raster_ds = gdal.Open(in_layer.dataProvider().dataSourceUri(), gdal.GA_Update)
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

    mask_path = os.path.join(temp_dir, "Valid_data_mask_for_interpolation.tiff")

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

    # Set the no_data values outside the polygon to -99999
    ## Rasterize the input vector layer with polygon masks
    poly_array = vectorToRaster(poly_layer, geotransform, width, height)
    mapped_array = np.zeros((height, width))
    mapped_array[np.isnan(in_array)*(poly_array != 1)==1] = 1
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

    ## Output raster
    raster_ds = gdal.Open(out_file_path, gdal.GA_Update)
    raster_array = raster_ds.GetRasterBand(1).ReadAsArray()
    raster_array[mapped_array==1] = np.nan
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
        out_array = gaussian_filter(in_array, factor / 2, mode="wrap")
    elif filter_type == 'Uniform filter':
        out_array = uniform_filter(in_array, factor*3-(factor-1))


    #set the initial nan values back to nan
    out_array[nan_mask]=np.nan

    # Write the smoothed raster
    # If the out_file argument is specified the smoothed raster will written in a new raster, otherwise the old raster will be updated
    if out_file != None:
        try:
            if os.path.exists(out_file):
                driver = gdal.GetDriverByName('GTiff')
                driver.Delete(out_file)
        except Exception as e:
            raise e
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
        smoothed_layer = QgsRasterLayer(in_layer.dataProvider().dataSourceUri(), 'Smoothed paleoDEM', 'gdal')

    fdbck.finished.emit(True)
    while not imit_progress.isFinished():
        time.sleep(2)

    return smoothed_layer


def setRasterSymbology(in_layer):
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

    #Finally, we need to apply the symbology we’ve created to the raster layer.
    #First, we’ll create a renderer using our raster shader.
    #Then we’ll Assign the renderer to our raster layer.

    renderer = QgsSingleBandPseudoColorRenderer(in_layer.dataProvider(), 1, shader)
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
    for  f in list_of_fields:
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
        layer_style['color'] = '%d, %d, %d' % (randrange(0, 256), randrange(0, 256), randrange(0, 256))
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
    renderer = QgsCategorizedSymbolRenderer(layer.fields().field(fni).name(), categories)

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
    output = os.path.join(tempfile.gettempdir(), "Rasterized_vector_layer.tiff") if output_path is None else output_path
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

    #Burn values from a field in the attribute table if the field is supplied
    field_to_burn = field_to_burn if field_to_burn is not None else None

    #Specify NODATA value
    nodata = no_data if no_data is not None else np.nan
    # If a fixed value should be burned, specify the value to burn
    burn_value = burn_value if burn_value is not None else 1

    #Check if the input vector layer contains any feature
    assert (in_layer.featureCount()>0), "The Input vector layer does not contain any feature (polygon, polyline or point)."


    r_params = {
        'INPUT': in_layer,
        'FIELD': field_to_burn,
        'BURN': burn_value, # 1 - if no fixed value is burned
        'UNITS': 0, # 0- Pixels; 1 - Georeferenced units
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

def polygonsToPolylines(in_layer, out_layer_path: str):
    """
    Converts polygons to polylines.

    :param out_layer_path: the path to store the layer with polylines.
    :return: QgsVectorLayer.
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
        polylines = processing.run("qgis:polygonstolines", {'INPUT': fixed_polygons, 'OUTPUT': 'memory:polylines_from_prolygons'})
    except Exception as e:
        raise e


    polylines_layer = polylines['OUTPUT']

    return polylines_layer

def polylinesToPolygons(in_layer:QgsVectorLayer, feedback:TaFeedback)->QgsVectorLayer:
    """Creates polygon feature from the points of line features.

    :param in_layer: Input vector layer.
    :param feedback: A feedback object to show progress and log info.
    :type: TaFeedback
    :return: QgsVectorLayer
    """
    features = in_layer.getFeatures()
    assert in_layer.featureCount() >0, "The input layer is empty."
    polygonFeatures = []
    for feature in features:
        if feedback.canceled:
            break
        #get the geometry of a feature
        geometry = feature.geometry()
        attributes = feature.attributes()

        # checking if the geometry is polyline or multipolyline
        if geometry.wkbType() == QgsWkbTypes.LineString:
            coordinates = geometry.asPolyline()
        elif geometry.wkbType() == QgsWkbTypes.MultiLineString:
            coordinates = geometry.asMultiPolyline()
        else:
            feedback.info("The geometry is neither polyline nor multipolyline.")
        polygonGeometry = QgsGeometry.fromPolygonXY(coordinates)
        feature = QgsFeature()
        feature.setGeometry(polygonGeometry)
        feature.setAttributes(attributes)
        polygonFeatures.append(feature)


    if not feedback.canceled:
        out_layer = QgsVectorLayer('Polygon?crs='+in_layer.crs().authid(), in_layer.name(), 'memory')
        out_layer.dataProvider().addFeatures(polygonFeatures)
        del polygonFeatures

        #Fix invalid geometries
        output_layer = processing.run('native:fixgeometries',
                                      {'INPUT': out_layer, 'OUTPUT': 'memory:'})['OUTPUT']
        output_layer.setName(in_layer.name())
        feedback.info("Fixed invalid geometries in layer {}.".format(in_layer.name()))
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

    params = {'INPUT': layer1, 'FIELDS_MAPPING': field_mapping, 'OUTPUT': 'memory:{}'.format(out_layer_name)}
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
    out_array[out_array >= fmin] = fmin + (in_array[in_array >= fmin] - fmin) / ratio
    return out_array

def modRescale(in_array, min: int, max: int):
    """
    Modifies the elevation/bathimetry
    values based on the current and provided
    minimum and maximum values.
    This is basically flattening and roughening.

    :param in_array: input numpy array for modification.
    :param fmin: final minimum value of elevation/bathymetry.
    :param fmax: final maximum value of elevation/bathymetry.
    :return: numpy.array
    """

    # Define the initial minimum and maximum values of the array
    if in_array.size>0 and np.isfinite(in_array).size>0:
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
def isPathValid(path: str, output_type: str)-> tuple: # for now is used for output paths. Modify the raise texts to fit in other contexts.
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
        elif output_type=='vector':
            if file_ext == ".shp":
                file_check = True



    dir_path = os.path.split(path)[0]
    if dir_path:
        if os.access(dir_path, os.W_OK):
            path_check = True

    if path_check and file_check:
        return (True,"")
    else:
        if not file_check and output_type=='raster':
            return(False, "Error: The file output file name is incorrect. Please provide a proper file name for the output. The file name should have a '.tif' or '.tiff' extension.")
        elif not file_check and output_type=='vector':
            return(False, "Error: The file output file name is incorrect. Please provide a proper file name for the output. The file name should have a '.shp' extension.")
        elif not path_check:
            return(False, "Error: The output path does not exist or you do not have write permissions.")
        else:
            return(False, "Error: The provided path for the output is not correct. Example: {} or {}".format(r'C:\\Users\user_name\Documents\file.tiff', r'C:\\Users\user_name\Documents\file.shp'))



def addRasterLayerForDebug(array, geotransform, iface):
    out_path = os.path.join(tempfile.tempdir, "Raster_layer_for_debug.tiff")
    nrows, ncols = np.shape(array)
    drv = gdal.GetDriverByName("GTIFF")
    raster = drv.Create(out_path, ncols, nrows, 1, gdal.GDT_Int32)
    raster.SetGeoTransform(geotransform)
    crs = osr.SpatialReference()
    crs.ImportFromEPSG(4326)
    raster.SetProjection(crs.ExportToWkt())
    raster.GetRasterBand(1).WriteArray(array)
    raster.GetRasterBand(1).SetNoDataValue(np.nan)
    raster.GetRasterBand(1).FlushCache()
    raster=None


    rlayer = QgsRasterLayer(out_path, "Raster_Layer_For_Debug", "gdal")
    iface.addRasterLayer(rlayer)
def addVectorLayerForDebug(vlayer, iface):
    iface.addVectorLayer(vlayer)


def generateUniqueIds(vlayer, id_field) -> QgsVectorLayer:
    id_found  = False
    fields = vlayer.fields().toList()
    for field in fields:
        if field.name().lower == id_field:
            id_found = True
            id_field = field
        else:
            pass



    if  not id_found:
        id_field = QgsField("id", QVariant.Int, "integer")
        vlayer.startEditing()
        vlayer.addAttribute(id_field)
        vlayer.commitChanges()


    features = vlayer.getFeatures()
    vlayer.startEditing()
    for current, feature in enumerate(features):
        feature[id_field.name()]=current
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
        if da.areaUnits()!=8:
            area = da.convertAreaMeasurement(area, 8)

        pointCount = int(round(point_density* area))

        if pointCount == 0:
            feedback.warning("Warning: Skip feature {} while creating random points as number of points for it is 0.".format(f.id()))
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
                    f['name'] if f['name']!=NULL else "NoName"
                )
            )
        except KeyError:
            feedback.info("{0} random points being created inside feature ID {1}.".format(pointCount, f.id()))

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
                if int(progress_count)<int(nPoints*feature_total):
                    progress_count +=int(nPoints*feature_total)
                    feedback.progress=progress_count
            nIterations += 1

        if nPoints < pointCount:
            feedback.info('Could not generate requested number of random points. Maximum number of attempts exceeded.')

    points_layer_dp.addFeatures(created_features)
    points_layer_dp = None
    nPolygons = source.featureCount()
    feedback.info("Created random points inside {} polygons.".format(nPolygons))

    return points_layer

def bufferAroundGeometries(in_layer, buf_dist, num_segments, feedback, runtime_percentage):
    """Creates buffer around polygon geometries.

    :param in_layer: QgsVectorLayer or QgsFeatureItterator
    :param buf_dist: int Buffer distance
    :param num_segments: Number of segments (int) used to approximate curves
    :param feedback: a TaFeedback object to report feedback into log tab
    :param runtime_percentage: Percentage of runtime (int) to report progress
    """

    feats = in_layer.getFeatures()

    buffer_layer = QgsVectorLayer('Polygon?crs={}'.format(in_layer.crs().authid()), '', 'memory')
    fixed_layer = QgsVectorLayer('Polygon?crs={}'.format(in_layer.crs().authid()), '', 'memory')
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
        if progress>=1:
            feedback.progress += int(progress)
            progress = 0
    dp = None
    dp_fixed = None
    params = {
                'INPUT':buffer_layer,
                'OVERLAY':fixed_layer,
                'OUTPUT':'TEMPORARY_OUTPUT'
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
            if i ==j:
                continue
            if features[i].geometry().overlaps(features[j].geometry()):
                overlaps_number+=1
        if feedback:
            feedback.progress += total/len(features)

    return overlaps_number

def assignUniqueIds(vlayer, feedback, run_time):
    progress_count = feedback.progress
    id_found  = False
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
        if not int(feedback.progress)==int(progress_count):
            feedback.progress = int(progress_count)

    if  not id_found:
        id_field = QgsField("id", QVariant.Int, "integer")
        vlayer.startEditing()
        vlayer.addAttribute(id_field)
        vlayer.commitChanges()


    features = vlayer.getFeatures()
    vlayer.startEditing()
    for current, feature in enumerate(features):
        if feedback and feedback.canceled:
            break
        feature[id_field.name()]=current
        vlayer.updateFeature(feature)
        progress_count += total*0.7/vlayer.featureCount()
        if not int(feedback.progress)==int(progress_count):
            feedback.progress = int(progress_count)


    ret_code = vlayer.commitChanges()

    if ret_code:
        return (vlayer, True)
    else:
        return (None, False)





def loadHelp(dlg):
    #set the help text in the  help box (QTextBrowser)
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
        if class_name    == type(dlg).__name__:
            path_to_file = os.path.join(os.path.dirname(__file__),'../help_text/{}.html'.format(file_name))

    with open(path_to_file, 'r', encoding='utf-8') as help_file:
        help_text = help_file.read()
    dlg.helpBox.setHtml(help_text)

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])



def isProcessingPluginEnabled(settings):
    value = settings.value("PythonPlugins/processing")
    if value == False:
        settings.setValue("PythonPlugins/processing",True)




class TaProgressImitation(QThread):
    finished = False

    def __init__(self, total,total_time, finish_signal, feedback):
        super().__init__()
        self.total = total
        self.signal = finish_signal.finished
        self.signal.connect(self.finish)
        self.unit_time = total_time/self.total
        self.feedback = feedback
    def run(self):
        for i in range(round(self.total)):
            if self.finished:
                break
            self.feedback.progress = self.feedback.progress+i
            time.sleep(self.unit_time)
        self.feedback.progress = self.feedback.progress+self.total



    def finish(self):
        self.finished=True



class TaFeedbackOld(QObject):
    finished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

class TaVectorFileWriter(QgsVectorFileWriter):
    def __init__(self):
        super().__init__()
    def writeToShapeFile(layer:QgsVectorLayer,
                         fileName:str,
                         fileEncoding:str,
                         destCRS:QgsCoordinateReferenceSystem,
                         driverName:str) -> (QgsVectorFileWriter.WriterError, str):
        """This function is used to make writing to shapefiles compatible beteen Qgis version >3.10 and <3.10."""

        # Check if the file is already created. Acts like overwrite
        if os.path.exists(fileName):
            deleted = TaVectorFileWriter.deleteShapeFile(fileName)
            if not deleted:
                raise Exception("Could not delete shapefile {}.".format(fileName))
        try:
            result = TaVectorFileWriter.writeAsVectorFormat(layer, fileName, fileEncoding, destCRS, driverName)
        except Exception:
            context = QgsCoordinateTransformContext()
            context.addCoordinateOperation(destCRS, destCRS, destCRS.toProj())
            options = TaVectorFileWriter.SaveVectorOptions()
            options.driverName = driverName
            result= TaVectorFileWriter.writeAsVectorFormat2(layer, fileName, context, options)
        return result


