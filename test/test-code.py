#Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
#Full copyright notice in file: terra_antiqua.py

from osgeo import gdal
from matplotlib import pyplot as plt
import numpy as np
path="/home/jon/PycharmProjects/databundle/data-80Ma/Results/paleo_dem_copy.tif"



# file=gdal.Open(path)
# array=file.GetRasterBand(1).ReadAsArray()
# sarray=array[1000:1300,1100:1500]
#
# sarray[np.isnan(sarray)]=0
sarray=np.random.random((10,10))
#print(sarray)

#for i,j in np.ndindex(sarray.shape):
#     subset=sarray[i-3:i+3,j-3:j+3]
#     print([i-3:i+3,j-3:j+3])
#     sarray[i,j]=np.mean(subset)

#plt.imshow(sarray)
#plt.show()
factor=3

cols=sarray.shape[1]
rows=sarray.shape[0]
out_array=np.array(sarray)
#out_array[:]=sarray[:]
import time

for i in range(rows):
    for j in range(cols):
        # Define smoothing mask; periodic boundary along date line

        x_vector = np.mod((np.arange((i - factor), (i + factor + 1))), (cols))
        #x_vector = x_vector.reshape(1, len(x_vector))
        y_vector = np.arange(np.maximum(0, j - factor), (np.minimum((rows - 1), j + factor) + 1), 1)
        y_vector = y_vector.reshape(len(y_vector), 1)

        out_array[i, j] = np.mean(sarray[y_vector, x_vector])
        print(sarray[y_vector,x_vector])
        #print(y_vector,x_vector)

#print(out_array)
