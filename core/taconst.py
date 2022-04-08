# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

# This file contains the constant values that are used within Terra Antiqua modules.

import gdalconst
import numpy as np


class taconst():
    # Numpy data types to use for data and mask arrays.
    # Data type is set to float32 to make it consistent with the output of gdal algorithms (see below).
    NP_TopoDType = np.dtype(np.float32)
    NP_MaskDType = np.dtype(np.int16)

    # Gdal data types to use in rasterization algorithm and while reading and writing data from/to
    # raster files. Data arrays cannot be smaller than 32 bit, because there is no Float16 or Float8 in
    # gdalconst module. It can be set to int16 for example, but in that case it is not possible to
    # use np.nan. it becomes 0 in the array.
    GDT_TopoDType = gdalconst.GDT_Float32
    # should be 8 bit, but in qgis the rasterization algorithm returns int16.
    GDT_MaskDType = gdalconst.GDT_Byte
