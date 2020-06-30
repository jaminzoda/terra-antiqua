def writerRaster(out_file, out_array, geotransform, crs):

    if os.path.exists(out_file):
            driver = gdal.GetDriverByName('GTiff')
            driver.Delete(out_file)
    geotransform = raster_ds.GetGeoTransform()
    smoothed_raster = gdal.GetDriverByName('GTiff').Create(out_file, out_array.shape[1], out_array.shape[0], 1, gdal.GDT_Float32)
    smoothed_raster.SetGeoTransform(geotransform)
    smoothed_raster.SetProjection(crs.toWkt())
    smoothed_band = smoothed_raster.GetRasterBand(1)
    smoothed_band.WriteArray(out_array)
    smoothed_band.FlushCache()
