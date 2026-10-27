# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

"""Compatibility layer so one code base runs on QGIS 3.10 (Qt5) up to QGIS 4.x (Qt6).

Everything that differs between QGIS/Qt versions is resolved here once, at import
time, so the rest of the plugin can use plain names.

Note on the QGIS 4 port (v1.1.1):
Terra Antiqua was originally designed for QGIS 3. Compatibility with QGIS 4 (Qt6) was
added in v1.1.1 with the assistance of an AI model (Claude, by Anthropic), and reviewed
and tested by Diego Ruiz. This was not part of the original development of the plugin, which only reached v1.1.
It was done so that the plugin remains usable as QGIS 3 reaches the end of its support.
The port does not change any tool or its results.
"""

# Every change made to the rest of the plugin for v1.1.1 is marked "# [QGIS4 port]",
# and each changed file starts with a summary of its changes. This whole file is new in v1.1.1.

import os

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateTransform,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsVectorFileWriter,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

# --- QGIS version -----------------------------------------------------------
QGIS_VERSION_INT = getattr(Qgis, "QGIS_VERSION_INT", None) or Qgis.versionInt()

# --- QAction moved from QtWidgets (Qt5) to QtGui (Qt6) ----------------------
try:
    from qgis.PyQt.QtGui import QAction  # noqa: F401  (Qt6)
except ImportError:
    from qgis.PyQt.QtWidgets import QAction  # noqa: F401  (Qt5)


# --- Field types for QgsField -----------------------------------------------
# QGIS >= 3.38 takes QMetaType.Type; older versions take QVariant.Type.
# PyQt6 has no QVariant.Type at all, so QGIS 4 requires QMetaType.
if QGIS_VERSION_INT >= 33800:
    from qgis.PyQt.QtCore import QMetaType
    FIELD_INT = QMetaType.Type.Int
    FIELD_DOUBLE = QMetaType.Type.Double
    FIELD_STRING = QMetaType.Type.QString
else:
    FIELD_INT = QVariant.Int
    FIELD_DOUBLE = QVariant.Double
    FIELD_STRING = QVariant.String


def enum_to_int(value):
    """Returns the integer value of a Qt/QGIS enum on both PyQt5 and PyQt6."""
    return value.value if hasattr(value, "value") else int(value)


# --- Layer filters for QgsMapLayerComboBox ----------------------------------
# Moved from QgsMapLayerProxyModel.Filter to Qgis.LayerFilter in QGIS 3.34.
def _layer_filter(name):
    layer_filter = getattr(Qgis, "LayerFilter", None)
    if layer_filter is not None:
        return getattr(layer_filter, name)
    return getattr(QgsMapLayerProxyModel, name)


FILTER_RASTER = _layer_filter("RasterLayer")
FILTER_VECTOR = _layer_filter("VectorLayer")
FILTER_POLYGON = _layer_filter("PolygonLayer")
FILTER_LINE = _layer_filter("LineLayer")
FILTER_POINT = _layer_filter("PointLayer")


# --- Geometry and WKB types -------------------------------------------------
# Moved from QgsWkbTypes to Qgis.GeometryType / Qgis.WkbType in QGIS 3.30.
if hasattr(Qgis, "GeometryType"):
    GEOMETRY_POLYGON = Qgis.GeometryType.Polygon
    GEOMETRY_LINE = Qgis.GeometryType.Line
else:
    GEOMETRY_POLYGON = QgsWkbTypes.GeometryType.PolygonGeometry
    GEOMETRY_LINE = QgsWkbTypes.GeometryType.LineGeometry

if hasattr(Qgis, "WkbType"):
    WKB_LINESTRING = Qgis.WkbType.LineString
    WKB_MULTILINESTRING = Qgis.WkbType.MultiLineString
else:
    WKB_LINESTRING = QgsWkbTypes.Type.LineString
    WKB_MULTILINESTRING = QgsWkbTypes.Type.MultiLineString


# --- Area units for QgsDistanceArea ----------------------------------------
# Moved from QgsUnitTypes.AreaUnit to Qgis.AreaUnit in QGIS 3.30. PyQt6 no longer
# accepts plain integers where QGIS expects one of these units.
if hasattr(Qgis, "AreaUnit"):
    AREA_SQUARE_DEGREES = Qgis.AreaUnit.SquareDegrees
else:
    from qgis.core import QgsUnitTypes
    AREA_SQUARE_DEGREES = QgsUnitTypes.AreaUnit.AreaSquareDegrees


# --- Raster band statistics -------------------------------------------------
# QGIS 3.40+ wants Qgis.RasterBandStatistic; older versions use QgsRasterBandStats.Stats.
if hasattr(Qgis, "RasterBandStatistic"):
    RASTER_STATS_ALL = Qgis.RasterBandStatistic.All
else:
    from qgis.core import QgsRasterBandStats
    RASTER_STATS_ALL = QgsRasterBandStats.Stats.All


# --- Processing algorithm ids -----------------------------------------------
def alg_id(*candidates):
    """Returns the first algorithm id that the running QGIS knows.

    Several algorithms were ported from Python ("qgis:...") to C++ ("native:...")
    during the 3.x series. Pass the preferred id first and fallbacks after it.
    """
    registry = QgsApplication.processingRegistry()
    for candidate in candidates:
        if registry.algorithmById(candidate) is not None:
            return candidate
    return candidates[0]


# --- Writing vector layers to disk ------------------------------------------
def write_vector_layer(layer, file_name, file_encoding, dest_crs, driver_name):
    """Writes a vector layer to disk on any QGIS version.

    Returns a tuple (error_code, error_message), where error_code can be
    compared with QgsVectorFileWriter.NoError.
    """
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = driver_name
    options.fileEncoding = file_encoding
    if dest_crs is not None and dest_crs.isValid() and dest_crs != layer.crs():
        options.ct = QgsCoordinateTransform(layer.crs(), dest_crs, QgsProject.instance())
    context = QgsProject.instance().transformContext()

    if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3"):  # QGIS >= 3.20
        result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, file_name, context, options)
    elif hasattr(QgsVectorFileWriter, "writeAsVectorFormatV2"):  # QGIS >= 3.10.3
        result = QgsVectorFileWriter.writeAsVectorFormatV2(layer, file_name, context, options)
    else:
        result = QgsVectorFileWriter.writeAsVectorFormat(
            layer, file_name, file_encoding, dest_crs, driver_name)

    if not isinstance(result, tuple):
        return result, ""
    error = result[0]
    message = next((r for r in result[1:] if isinstance(r, str) and r and r != file_name), "")
    return error, message


VECTOR_WRITER_NO_ERROR = QgsVectorFileWriter.WriterError.NoError


# --- Deleting temporary and output rasters ---------------------------------
def delete_raster_file(path, feedback=None):
    """Deletes a raster file (and its GDAL side files) without stopping the tool.

    On Windows a file cannot be deleted while it is still open, and QGIS 4 makes
    GDAL raise an exception when a deletion fails. A file that cannot be deleted is
    left in place and reported, as QGIS 3 effectively did. Returns True if the file
    no longer exists.
    """
    if not path or not os.path.exists(path):
        return True
    from osgeo import gdal
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        gdal.GetDriverByName("GTiff").Delete(path)
    except Exception:
        pass
    finally:
        gdal.PopErrorHandler()
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    deleted = not os.path.exists(path)
    if not deleted and feedback is not None:
        feedback.info(f"Could not delete {path} because it is still in use. "
                      "It will be overwritten the next time it is needed.")
    return deleted


# --- Icons ------------------------------------------------------------------
_RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")


def icon_path(file_name):
    """Returns the absolute path to an icon in the plugin's resources folder."""
    return os.path.join(_RESOURCES_DIR, file_name)
