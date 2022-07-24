# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py

from threading import local
from xmlrpc.client import APPLICATION_ERROR
from PyQt5.QtCore import (
    QVariant
)
import os
from osgeo import (
    gdal
)
from qgis.core import (
    QgsRasterLayer,
    QgsField,
    QgsVectorLayer,
    QgsProcessingException,
    NULL,
    QgsProject
)


import numpy as np
from sympy import jn

import cppwtt as wt

from .utils import (
    fillNoDataInPolygon,
    vectorToRaster,
    modRescale,
    randomPointsInPolygon,
    assignUniqueIds,
    findNearestPowerOfTwo,
    polygonsToPolylines
)


try:
    from plugins import processing
except Exception:
    import processing

from .base_algorithm import TaBaseAlgorithm
from .taconst import taconst


class TaCreateTopoBathy(TaBaseAlgorithm):

    def __init__(self, dlg):
        super().__init__(dlg)
        self.topo_layer = None
        self.mask_layer = None
        self.features = None
        self.projection = None
        self.geotransform = None
        self.height = None
        self.width = None

    def run(self):
        self.getParameters()
        if not self.killed:
            if self.dlg.featureTypeBox.currentText() == "Sea":
                self.createSea()
            elif self.dlg.featureTypeBox.currentText() == "Mountain range (random)":
                self.createMountainRange()
            elif self.dlg.featureTypeBox.currentText() == "Mountain range (fractal)":
                self.createMountainRangeFractal()

    def getParameters(self):
        if not self.killed:
            self.feedback.info('Loading raster layer ...')
            self.topo_layer = self.dlg.baseTopoBox.currentLayer()
            topo_ds = gdal.Open(self.topo_layer.dataProvider().dataSourceUri())
            self.projection = topo_ds.GetProjection()
            # this geotransform is used to rasterize extracted masks below
            self.geotransform = topo_ds.GetGeoTransform()
            self.height = self.topo_layer.height()
            self.width = self.topo_layer.width()
            topo_ds = None

            if self.topo_layer.isValid():
                self.feedback.info("Raster layer is loaded properly.")
            else:
                self.feedback.error(
                    "Raster layer is not valid. Please, choose a valid raster layer. ")
                self.kill()

            # Get the vector masks
            self.feedback.info('Loading  vector layer')
            self.mask_layer = self.dlg.masksBox.currentLayer()

            if self.mask_layer.isValid() and self.mask_layer.featureCount() > 0:
                self.feedback.info('Mask layer is loaded properly')
            elif self.mask_layer.isValid() and self.mask_layer.featureCount() == 0:
                self.feedback.error(
                    "The mask layer is empty. Please add polygon features to the mask layer and try again.")
                self.kill()
            else:
                self.feedback.error(
                    'There is a problem with mask layer - not loaded properly')
                self.kill()
         # Check if input polygon features have unique ids
         # If not create
        if not self.killed:
            self.feedback.info("Assigning unique ids to each feature.")
            self.mask_layer, ret_code = assignUniqueIds(self.mask_layer, feedback=self.feedback,
                                                        run_time=5)
            if ret_code:
                self.feedback.info("Id numbers assigned successfully.")
            else:
                self.feedback.error("Id number assignment failed.")
                self.feedback.error(
                    "For the tool to work properly, each feature should have a unique number.")
                self.feedback.error(
                    "Please, assign unique numbers manually and try again.")
                self.kill()
            # get fetures
            if self.dlg.selectedFeaturesBox.isChecked():
                if self.mask_layer.selectedFeatureCount() > 0:
                    self.features = self.mask_layer.getSelectedFeatures()
                else:
                    self.feedback.error(
                        "There are no features selected in the input layer")
                    self.kill()
            else:
                if self.mask_layer.featureCount() > 0:
                    self.features = self.mask_layer.getFeatures()
                else:
                    self.feedback.error(
                        "There are no features in the input layer.")
                    self.kill()

    def createSea(self):
        if not self.killed:

            pixel_size_avrg = (self.topo_layer.rasterUnitsPerPixelX(
            )+self.topo_layer.rasterUnitsPerPixelY())/2
            # density of points for random points inside polygon algorithm -Found empirically
            point_density = 3*0.1/pixel_size_avrg
            # Get the input raster bathymetry
            bathy_layer_ds = gdal.Open(self.topo_layer.source())
            bathy = bathy_layer_ds.GetRasterBand(
                1).ReadAsArray(buf_type=taconst.GDT_TopoDType)

            # Remove the existing values before assigning
            # Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
            # creare an empty array
            initial_values = np.empty(bathy.shape, dtype=taconst.NP_TopoDType)
            # Copy the elevation values from initial raster
            initial_values[:] = bathy[:]
            self.context = self.getExpressionContext(self.mask_layer)
            modified_area_array = np.zeros(
                bathy.shape, dtype=taconst.NP_TopoDType)

        progress_unit = 80 / \
            self.mask_layer.featureCount() if self.mask_layer.featureCount() > 0 else 0
        for feature in self.features:
            if self.killed:
                break
            self.context.setFeature(feature)
            try:
                self.feedback.info(
                    "<b><i>Creating {} sea".format(
                        feature.attribute('name')
                        if feature.attribute('name') != NULL else "NoName"
                    )
                )
            except Exception as e:
                self.feedback.info(
                    "<b><i>Processing feature {}".format(feature.attribute('id')))
                self.feedback.debug(e)
            # Reading parameters for creating feature from the dialog or attributes
            shelf_width, ok = self.dlg.shelfWidth.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                shelf_width = self.dlg.shelfWidth.spinBox.value()
            max_sea_depth, ok = self.dlg.maxDepth.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                max_sea_depth = self.dlg.maxDepth.spinBox.value()
            min_sea_depth, ok = self.dlg.minDepth.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                min_sea_depth = self.dlg.minDepth.spinBox.value()
            slope_width, ok = self.dlg.contSlopeWidth.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                slope_width = self.dlg.contSlopeWidth.spinBox.value()
            max_shelf_depth, ok = self.dlg.shelfDepth.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                max_shelf_depth = self.dlg.shelfDepth.spinBox.value()

            # Create a memory vector layer to store a feature at a time
            feature_layer = QgsVectorLayer(
                f"Polygon?crs={self.crs.authid()}", "Feature layer", "memory")
            feature_layer.dataProvider().addAttributes(self.mask_layer.fields())
            feature_layer.updateFields()
            feature_layer.dataProvider().addFeature(feature)

            # Densifying the vertices in the feature outlines
            # # Parameters for densification
            self.feedback.info(
                "Densifying polygon vertices... Densification interval is 0.1 (map units).")

            try:
                d_params = {
                    'INPUT': feature_layer,
                    'INTERVAL': pixel_size_avrg,
                    'OUTPUT': self.processing_output
                }
                mask_layer_densified = processing.run(
                    "native:densifygeometriesgivenaninterval", d_params)['OUTPUT']

            except QgsProcessingException:
                # the algorithm name and output parameter are different in earlier versions of Qgis (E.g 3.4)
                d_params = {
                    'INPUT': feature_layer,
                    'INTERVAL': pixel_size_avrg,
                    'OUTPUT': self.processing_output
                }

                mask_layer_densified = processing.run(
                    "qgis:densifygeometriesgivenaninterval", d_params)['OUTPUT']
            finally:
                if not mask_layer_densified.isValid() or mask_layer_densified.featureCount() == 0:
                    mask_layer_densified = feature_layer
                    self.feedback.warning(
                        "Densification of vertices for the feature outlines failed. Initial feature outlines are used. You may densify your geometries manually for smoother surface generation.")

            if not self.killed:
                self.feedback.info(
                    "Creating depth points inside feature polygons...")
                # Creating random points inside feature outline polygons
                # # Parameters for random points algoriithm
                try:
                    random_points_layer = randomPointsInPolygon(mask_layer_densified, point_density,
                                                                pixel_size_avrg, self.feedback, 10)
                except Exception as e:
                    self.feedback.error(
                        "Failed to create random points inside feature polygons with the following exception: {}".format(e))
                    self.kill()

            if not self.killed:
                # Extracting geographic feature vertices
                # # Parameters for extracting vertices
                self.feedback.info("Extracting polygon feature vertices...")
                try:
                    ev_params = {
                        'INPUT': mask_layer_densified,
                        'OUTPUT': self.processing_output
                    }
                    extracted_vertices_layer = processing.run(
                        "native:extractvertices", ev_params)['OUTPUT']
                except Exception as e:
                    self.feedback.error(
                        "Feature outline vertices are not extracted because of the following error: {}. The distances cannot be calculated. Therefore the algorithm has stopped.".format(e))
                    self.kill()
                else:
                    if extracted_vertices_layer.featureCount() == 0:
                        self.feedback.error(
                            "Polygon feature vertices are not extracted.")
                        self.kill()

            if not self.killed:
                self.feedback.info("Calculating distances to coastline...")
                # Calculating distance to nearest hub for the random points
                # # Parameters for the distance calculation
                try:
                    id_field = self.mask_layer.fields().field('id')
                except KeyError:
                    id_field = self.mask_layer.fields().field('Id')
                except KeyError:
                    id_field = self.mask_layer.fields().field('iD')
                except KeyError:
                    id_field = self.mask_layer.fields().field('ID')

                try:
                    dc_params = {
                        'INPUT': random_points_layer,
                        'HUBS': extracted_vertices_layer,
                        'FIELD': id_field.name(),
                        'UNIT': 3,  # km
                        'OUTPUT': self.processing_output
                    }

                    r_points_distance_layer = processing.run(
                        "qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
                except Exception as e:
                    self.feedback.error("Distance calculation for randomly created\
                                  depth points failed with the following error: {}".format(e))
                    self.kill()
                else:
                    if r_points_distance_layer.featureCount() == 0:
                        self.feedback.error(
                            "There was an error while calculating distances to coastline.")
                        self.kill()

            if not self.killed:
                self.feedback.info(
                    "Sampling existing bathymetry from the input raster...")
                # TODO Consider rearanging this part to first check if the keep_deeper_bathy is checked
                # Sampling the existing bathymetry values from the input raster
                try:
                    sampling_params = {
                        'INPUT': r_points_distance_layer,
                        'RASTERCOPY': self.topo_layer,
                        'COLUMN_PREFIX': 'd_value',
                        'OUTPUT': self.processing_output
                    }
                    points_dist_depth_layer = processing.run(
                        "qgis:rastersampling", sampling_params)['OUTPUT']
                except Exception as e:
                    self.feedback.warning(
                        "Sampling the initial topography failed with the following error: {}. The depths will be calculated without taking the initial topography into account.".format(e))

            if not self.killed:
                # Finding bounding distance values
                total = progress_unit*0.1 / \
                    points_dist_depth_layer.featureCount() if points_dist_depth_layer.featureCount() else 0
                progress_count = self.feedback.progress
                features = points_dist_depth_layer.getFeatures()
                dists = []
                for feat in features:
                    dist = feat.attribute("HubDist")
                    if dist > shelf_width:
                        dists.append(dist)
                    progress_count += total
                    if not int(self.feedback.progress) == int(progress_count):
                        self.feedback.progress = int(progress_count)

            if len(dists) > 0:
                min_dist = min(dists)
                max_dist = max(dists)
            else:
                name = feature.attribute('name') if feature.attribute(
                    'name') != NULL else 'NoName'
                self.feedback.warning(
                    f"Something went wrong while processing feature {name}.")
                self.feedback.warning("The distances between the shoreline and\
                                      depth points are not calculated.")
                continue

            if not self.killed:
                self.feedback.info("Calculating depth values ... ")
                features = points_dist_depth_layer.getFeatures()
                features_out = []

                total = progress_unit*0.8 / \
                    points_dist_depth_layer.featureCount() if points_dist_depth_layer.featureCount() else 0
                for feat in features:
                    attr = feat.attributes()
                    dist = feat.attribute("HubDist")
                    # TODO Consider rearanging this part to first check if the keep_deeper_bathy is checked
                    try:
                        in_depth = feat.attribute("d_value_1")
                    except KeyError as e:
                        in_depth = feat["d_value1"]
                    except KeyError as e:
                        in_depth = None

                    if dist > shelf_width + slope_width:
                        depth = (max_sea_depth - min_sea_depth) * (dist -
                                                                   min_dist) / (max_dist - min_dist) + min_sea_depth
                        if in_depth and self.dlg.keepDeepBathyCheckBox.isChecked():
                            if depth > in_depth:
                                depth = in_depth
                        attr.append(depth)
                        feat.setAttributes(attr)
                        features_out.append(feat)
                    elif dist <= shelf_width:
                        depth = max_shelf_depth * dist / shelf_width
                        # if the calculated depth value for a point is shallower than the initial depth, the initial depth will taken.
                        if in_depth and self.dlg.keepDeepBathyCheckBox.isChecked():
                            if depth > in_depth:
                                depth = in_depth
                        attr.append(depth)
                        feat.setAttributes(attr)
                        features_out.append(feat)
                    else:
                        pass
                    progress_count += total
                    if not int(self.feedback.progress) == int(progress_count):
                        self.feedback.progress = int(progress_count)

            if not self.killed:
                depth_layer = QgsVectorLayer(
                    f"Point?crs={self.crs.authid()}", "Depth layer", "memory")
                depth_layer_dp = depth_layer.dataProvider()
                fields = points_dist_depth_layer.fields().toList()
                depth_field = QgsField("Depth", QVariant.Double, "double")
                fields.append(depth_field)

                depth_layer_dp.addAttributes(fields)
                depth_layer.updateFields()
                depth_layer_dp.addFeatures(features_out)
                depth_layer_dp = None

            if not self.killed:
                # Rasterize the depth points layer
                # # Rasterization parameters
                self.feedback.info("Rasterizing  depth points ...")
                try:
                    points_array = vectorToRaster(
                        depth_layer,  # layer to rasterize
                        self.geotransform,  # layer to take crs from
                        self.width,
                        self.height,
                        feedback=self.feedback,
                        field_to_burn='Depth',  # field to take burn value from
                        no_data=np.nan,
                        burn_value=0,
                        data_type=taconst.GDT_TopoDType)  # Here we use topo dtype instead of mask, because the output will contain el values
                except Exception as e:
                    self.feedback.error(
                        "Rasterization of depth points failed with the following error: {}.".format(e))
                    self.kill()

            if not self.killed:
                self.feedback.info(
                    "Removing the existing bathymetry within the feature polygons ... ")
                try:
                    pol_array = vectorToRaster(
                        mask_layer_densified,
                        self.geotransform,
                        self.width,
                        self.height,
                        feedback=self.feedback,
                        field_to_burn=None,
                        no_data=0
                    )
                except Exception as e:
                    self.feedback.error(
                        "Rasterization of polygon features outlining geographic features failed with the following error: {}.".format(e))
                    self.kill()

            if not self.killed:
                bathy[pol_array == 1] = np.nan
                # assign values to the topography raster
                bathy[np.isfinite(points_array)
                      ] = points_array[np.isfinite(points_array)]

            if not self.killed:
                self.feedback.info("Setting the coastline to zero ...")
                # Rasterize sea boundaries
                try:
                    ptol_params = {
                        'INPUT': mask_layer_densified,
                        'OUTPUT': self.processing_output
                    }
                    mlayer_line = processing.run(
                        "native:polygonstolines", ptol_params)["OUTPUT"]
                except Exception as e:
                    ptol_params = {
                        'INPUT': mask_layer_densified,
                        'OUTPUT': self.processing_output
                    }
                    mlayer_line = processing.run(
                        "qgis:polygonstolines", ptol_params)["OUTPUT"]
                finally:
                    if not mlayer_line.isValid() or mlayer_line.featureCount() == 0:
                        self.feedback.error(
                            "Extracting polygon boundaries failed with the following error: {}.".format(e))
                        self.kill()

                if not self.killed:
                    try:
                        sea_boundary_array = vectorToRaster(
                            mlayer_line,
                            self.geotransform,
                            self.width,
                            self.height,
                            feedback=self.feedback,
                            field_to_burn=None,
                            no_data=0
                        )
                    except Exception as e:
                        self.feedback.error(
                            "Rasterization of feature outline boundaries failed with the following error: {}.".format(e))
                        self.kill()

                if not self.killed:
                    # assign 0m values to the sea line
                    bathy[(sea_boundary_array == 1) * (bathy > 0) == 1] = 0
                    bathy[(sea_boundary_array == 1) * np.isnan(bathy) * np.isfinite(initial_values) * (
                        initial_values > 0) == 1] = 0
                if not self.killed:
                    # store modified area in an array for removing artefact after interpolation
                    modified_area_array[pol_array ==
                                        1] = pol_array[pol_array == 1]

                progress_count += progress_unit*0.1
                if not int(self.feedback.progress_count) == int(progress_count):
                    self.feedback.progress = int(progress_count)

        if not self.killed:
            self.feedback.info("Interpolating depth values for gaps...")

            # Create a temporary raster to store modified data for interpolation
            out_file_path = os.path.join(
                self.temp_dir, "Interpolated_raster.tiff")

            raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
                out_file_path,
                self.width,
                self.height,
                1,  # number of bands
                taconst.GDT_TopoDType  # data type
            )
            raster_for_interpolation.SetGeoTransform(self.geotransform)
            raster_for_interpolation.SetProjection(self.projection)
            band = raster_for_interpolation.GetRasterBand(1)
            band.SetNoDataValue(np.nan)
            band.WriteArray(bathy)
            raster_for_interpolation = None
            bathy = None

            rlayer = QgsRasterLayer(
                out_file_path, "Raster for interpolation", "gdal")

            self.feedback.progress += 5

            try:
                fillNoDataInPolygon(
                    rlayer, self.mask_layer, self.out_file_path)
            except Exception as e:
                self.feedback.error(
                    "Raster interpolation failed with the following error: {}.".format(e))
                self.kill()

            self.feedback.progress += 5

        if not self.killed:
            self.feedback.info("Removing some artifacts")
            # Load the raster again to remove artifacts
            final_raster = gdal.Open(self.out_file_path, gdal.GA_Update)
            bathy = final_raster.GetRasterBand(
                1).ReadAsArray(buf_type=taconst.GDT_TopoDType)

            # Re-scale the artifacts bsl.
            try:
                in_array = bathy[(modified_area_array == 1) * (bathy > 0)]
                if in_array.size > 0:
                    bathy[(modified_area_array == 1) * (bathy > 0)
                          ] = modRescale(in_array, -15, -1)
                    final_raster.GetRasterBand(1).WriteArray(bathy)
            except Exception:
                self.feedback.warning("Removing artefacts failed.")

            bathy = None
            final_raster = None

            self.feedback.progress = 100

            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def createMountainRange(self):
        if not self.killed:
            pixel_size_avrg = (self.topo_layer.rasterUnitsPerPixelX(
            )+self.topo_layer.rasterUnitsPerPixelY())/2
            # density of points for random points inside polygon algorithm -Found empirically
            point_density = 10*0.1/pixel_size_avrg

        # Get the input topography raster
        topo_layer_ds = gdal.Open(self.topo_layer.source())
        topo = topo_layer_ds.GetRasterBand(
            1).ReadAsArray(buf_type=taconst.GDT_TopoDType)
        topo_layer_ds = None

        # Remove the existing values before assigning
        # Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
        # creare an empty array
        initial_values = np.empty(topo.shape, dtype=taconst.NP_TopoDType)
        # Copy the elevation values from initial raster
        initial_values[:] = topo[:]
        self.context = self.getExpressionContext(self.mask_layer)
        modified_area_array = np.zeros(topo.shape, taconst.NP_TopoDType)

        progress_unit = 80 / \
            self.mask_layer.featureCount() if self.mask_layer.featureCount() > 0 else 0

        for feature in self.features:
            if self.killed:
                break
            self.context.setFeature(feature)
            try:
                self.feedback.info(
                    "<b><i>Creating {} mountain".format(
                        feature.attribute('name')
                        if feature.attribute('name') != NULL else "NoName"
                    )
                )
            except Exception as e:
                self.feedback.info(
                    "<b><i>Processing feature {}".format(feature.attribute('id')))
                self.feedback.debug(e)

            # Reading parameters for creating feature from the dialog or attributes
            max_mount_elev, ok = self.dlg.maxElev.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                max_mount_elev = self.dlg.maxElev.spinBox.value()
            min_mount_elev, ok = self.dlg.minElev.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                min_mount_elev = self.dlg.minElev.spinBox.value()
            ruggedness, ok = self.dlg.mountRugged.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                ruggedness = self.dlg.mountRugged.spinBox.value()
            slope_width, ok = self.dlg.mountSlope.overrideButton.toProperty().valueAsInt(self.context)
            if not ok:
                slope_width = self.dlg.mountSlope.spinBox.value()

            # Create a memory vector layer to store a feature at a time
            feature_layer = QgsVectorLayer(
                f"Polygon?crs={self.crs.authid()}", "Feature layer", "memory")
            feature_layer.dataProvider().addAttributes(self.mask_layer.fields())
            feature_layer.updateFields()
            feature_layer.dataProvider().addFeature(feature)
            # Densifying the vertices in the feature outlines
            # # Parameters for densification

            try:
                self.feedback.info(
                    "Densifying polygon vertices... Densification interval is {} (map units).".format(pixel_size_avrg))
                d_params = {
                    'INPUT': feature_layer,
                    'INTERVAL': pixel_size_avrg,
                    'OUTPUT': self.processing_output
                }

                mask_layer_densified = processing.run(
                    "native:densifygeometriesgivenaninterval", d_params)['OUTPUT']
            except QgsProcessingException:
                # the algorithm name and output parameters are different in earlier versions of Qgis (E.g 3.4)
                d_params = {
                    'INPUT': feature_layer,
                    'INTERVAL': pixel_size_avrg,
                    'OUTPUT': self.processing_output
                }

                mask_layer_densified = processing.run(
                    "qgis:densifygeometriesgivenaninterval", d_params)['OUTPUT']
            finally:
                if not mask_layer_densified.isValid() or mask_layer_densified.featureCount() == 0:
                    mask_layer_densified = feature_layer
                    self.feedback.warning(
                        "Densification of vertices for the feature outlines failed. Initial feature outlines are used. You may densify your geometries manually for smoother surface generation.")

            if not self.killed:
                self.feedback.info(
                    "Creating elevation points inside feature polygons...")
                # Creating random points inside feature outline polygons
                try:
                    random_points_layer = randomPointsInPolygon(
                        mask_layer_densified, point_density, pixel_size_avrg, self.feedback, 10)
                except Exception as e:
                    self.feedback.error(
                        "Failed to create random points inside polygon features. The error is: {}".format(e))
                    self.kill()
                else:
                    if random_points_layer.featureCount() == 0:
                        self.feedback.error(
                            "Failed to create random points inside polygon features.")
                        self.kill()

            if not self.killed:
                # Extracting geographic feature vertices
                # # Parameters for extracting vertices
                self.feedback.info("Extracting polygon feature vertices...")
                try:
                    ev_params = {
                        'INPUT': mask_layer_densified,
                        'OUTPUT': self.processing_output
                    }
                    extracted_vertices_layer = processing.run(
                        "native:extractvertices", ev_params)['OUTPUT']
                except QgsProcessingException as e:
                    self.feedback.error(
                        "Extracting feature outline vertices failed with the following error: {}. The algorithm cannot proceed.".format(e))
                    self.kill()
                else:
                    if extracted_vertices_layer.featureCount() == 0:
                        self.feedback.error(
                            "Polygon feature vertices are not extracted.")
                        self.kill()

            if not self.killed:
                self.feedback.info(
                    "Calculating distances to boundaries of the mountain...")
                # Calculating distance to nearest hub for the random points
                # # Parameters for the distance calculation
                try:
                    id_field = self.mask_layer.fields().field('id')
                except KeyError:
                    id_field = self.mask_layer.fields().field('Id')
                except KeyError:
                    id_field = self.mask_layer.fields().field('iD')
                except KeyError:
                    id_field = self.mask_layer.fields().field('ID')
                try:
                    dc_params = {
                        'INPUT': random_points_layer,
                        'HUBS': extracted_vertices_layer,
                        'FIELD': id_field.name(),
                        'UNIT': 3,  # km
                        'OUTPUT': self.processing_output
                    }

                    r_points_distance_layer = processing.run(
                        "qgis:distancetonearesthubpoints", dc_params)['OUTPUT']
                except QgsProcessingException as e:
                    self.feedback.error(
                        "Distance calculation for random points inside feature outlines failed with the following error: {}.".format(e))
                    self.kill()
                else:
                    if r_points_distance_layer.featureCount() == 0:
                        self.feedback.error(
                            "There was an error while calculating distances to coastline.")
                        self.kill()

            if not self.killed:
                self.feedback.info(
                    "Sampling existing topography from the input raster...")
                # TODO rearrange the code to check if the keep_high_topo checkbox is checked
                # Sampling the existing topography values from the input raster
                try:
                    sampling_params = {
                        'INPUT': r_points_distance_layer,
                        'RASTERCOPY': self.topo_layer,
                        'COLUMN_PREFIX': 'elev_value',
                        'OUTPUT': self.processing_output
                    }
                    points_dist_elev_layer = processing.run(
                        "qgis:rastersampling", sampling_params)['OUTPUT']
                except QgsProcessingException as e:
                    self.feedback.warning(
                        "Sampling existing topography/bathymetry failed. Depth calculation will be done without considering initial topography. The following error was thrown: {}".format(e))

            if not self.killed:
                # Finding bounding distance values
                total = progress_unit*0.1 / \
                    points_dist_elev_layer.featureCount() if points_dist_elev_layer.featureCount() else 0
                progress_count = self.feedback.progress
                features = points_dist_elev_layer.getFeatures()
                dists = []
                for feat in features:
                    dist = feat.attribute("HubDist")
                    if dist > slope_width:
                        dists.append(dist)
                    progress_count += total
                    if not int(self.feedback.progress) == int(progress_count):
                        self.feedback.progress == int(progress_count)

                if len(dists) > 0:
                    min_dist = min(dists)
                    max_dist = max(dists)
                else:
                    name = feature.attribute('name') if feature.attribute(
                        'name') != NULL else 'NoName'
                    self.feedback.warning(
                        f"Something went wrong while processing feature {name}.")
                    self.feedback.warning("The distances between the mountain boundary and\
                                          elevation  points are not calculated.")
                    continue

            if not self.killed:
                self.feedback.info("Calculating elevation values ... ")
                features = points_dist_elev_layer.getFeatures()
                features_out = []

                total = progress_unit*0.8 / \
                    points_dist_elev_layer.featureCount() if points_dist_elev_layer.featureCount() else 0
                for feat in features:
                    attr = feat.attributes()
                    dist = feat.attribute("HubDist")
                    # TODO reaarange to first check if the keep_high_topo checkbox is checked
                    try:
                        in_elev = feat.attribute("elev_value_1")
                    except KeyError:
                        in_elev = feat.attribute("elev_value1")
                    except KeyError:
                        in_elev = None

                    if dist > slope_width:
                        elev = (max_mount_elev - min_mount_elev) * (dist -
                                                                    min_dist) / (max_dist - min_dist) + min_mount_elev
                        if in_elev and self.dlg.keepHighTopoCheckBox.isChecked():
                            if elev < in_elev:
                                elev = in_elev
                        # Introducing ruggedness to the created mountain range
                        # change the elevation randomly by 10 percent
                        max_bound = elev*ruggedness/100
                        min_bound = max_bound*-1

                        elev = elev+np.random.randint(min_bound, max_bound)
                        attr.append(elev)
                        feat.setAttributes(attr)
                        features_out.append(feat)
                    else:
                        pass
                    progress_count += total
                    if not int(self.feedback.progress) == int(progress_count):
                        self.feedback.progress = int(progress_count)

                elev_layer = QgsVectorLayer(
                    f"Point?crs={self.crs.authid()}",
                    "Topography layer",
                    "memory"
                )
                elev_layer_dp = elev_layer.dataProvider()
                fields = points_dist_elev_layer.fields().toList()
                elev_field = QgsField("Elev", QVariant.Double, "double")
                fields.append(elev_field)

                elev_layer_dp.addAttributes(fields)
                elev_layer.updateFields()
                elev_layer_dp.addFeatures(features_out)
                elev_layer_dp = None

            if not self.killed:
                # Rasterize the elevation points layer
                self.feedback.info("Rasterizing  elevation points ...")
                try:
                    points_array = vectorToRaster(
                        elev_layer,  # layer to rasterize
                        self.geotransform,  # layer to take crs from or geotransform
                        self.width,
                        self.height,
                        feedback=self.feedback,
                        field_to_burn='Elev',  # field take burn value from
                        no_data=np.nan,
                        burn_value=0,
                        # rasterizing elevation data, hence need to use topo data type
                        data_type=taconst.GDT_TopoDType
                    )
                except Exception as e:
                    self.feedback.error(
                        "Rasterization of elevation points failed with the following error: {}.".format(e))
                    self.kill()

            if not self.killed:
                self.feedback.info(
                    "Removing the existing topography within the feature polygons ... ")
                try:
                    pol_array = vectorToRaster(
                        mask_layer_densified,
                        self.geotransform,
                        self.width,
                        self.height,
                        feedback=self.feedback,
                        field_to_burn=None,
                        no_data=0
                    )
                except Exception as e:
                    self.feedback.error(
                        "Rasterization of geographic feature polygons failed with the following error: {}.".format(e))
                    self.kill()

                # Setting the initial topo values inside the boundaries of mountain
                # to be created to NaN
                topo[pol_array == 1] = np.nan
                # assign values to the topography raster
                topo[np.isfinite(points_array)
                     ] = points_array[np.isfinite(points_array)]

                if not self.killed:
                    # store modified area in an array for removing artefact after interpolation
                    modified_area_array[pol_array ==
                                        1] = pol_array[pol_array == 1]

                progress_count += progress_unit*0.1
                if not int(self.feedback.progress_count) == int(progress_count):
                    self.feedback.progress = int(progress_count)

        if not self.killed:
            self.feedback.info("Interpolating elevation values for gaps...")

            # Create a temporary raster to store modified data for interpolation
            out_file_path = os.path.join(
                self.temp_dir, "Interpolated_raster.tiff")
            raster_for_interpolation = gdal.GetDriverByName('GTIFF').Create(
                out_file_path,
                self.width,
                self.height,
                1,  # number of bands
                taconst.GDT_TopoDType  # data type
            )
            raster_for_interpolation.SetGeoTransform(self.geotransform)
            raster_for_interpolation.SetProjection(self.projection)
            band = raster_for_interpolation.GetRasterBand(1)
            band.SetNoDataValue(np.nan)
            band.WriteArray(topo)
            raster_for_interpolation = None
            topo = None

            rlayer = QgsRasterLayer(
                out_file_path, "Raster for interpolation", "gdal")

            self.feedback.progress += 5

            try:
                fillNoDataInPolygon(
                    rlayer, self.mask_layer, self.out_file_path)
            except Exception as e:
                self.feedback.error(
                    "Interpolation failed with the following error: {}.".format(e))
                self.kill()

            self.feedback.progress += 5

        if not self.killed:
            self.feedback.info("Removing some artefacts")
            # Load the raster again to remove artifacts

            final_raster = gdal.Open(self.out_file_path, gdal.GA_Update)
            topo = final_raster.GetRasterBand(1).ReadAsArray(
                buf_type=taconst.GDT_TopoDType)

            # Re-scale the artifacts asl.

            try:
                in_array = topo[(modified_area_array == 1) * (topo < 0)]
                if in_array.size > 0:
                    topo[(modified_area_array == 1) * (topo < 0)
                         ] = modRescale(in_array, 15, 1)
                    final_raster.GetRasterBand(1).WriteArray(topo)
            except Exception as e:
                self.feedback.warning("Removing artefacts failed.")
                self.feedback.debug(e)
            topo = None
            final_raster = None

            self.feedback.progress = 100

            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def createMountainRangeFractal(self) -> None:
        """Creates a mountain range using the stream power law for generating
        drainage network and fractal geometry for producing topography details
        regardless of the scale.
        """
        if not self.killed:
            # Get the input topography raster
            topo_layer_ds = gdal.Open(self.topo_layer.source())
            topo_to_modify = topo_layer_ds.GetRasterBand(
                1).ReadAsArray(buf_type=taconst.GDT_TopoDType)
            topo_layer_ds = None
        if not self.killed:
            # Remove the existing values before assigning
            # Before we remove values inside the boundaries of the features to be created, we map initial empty cells.
            # creare an empty array
            initial_values = np.empty(
                topo_to_modify.shape, dtype=taconst.NP_TopoDType)
            # Copy the elevation values from initial raster
            initial_values[:] = topo_to_modify[:]
            self.context = self.getExpressionContext(self.mask_layer)

            progress_unit = 80 / \
                self.mask_layer.featureCount() if self.mask_layer.featureCount() > 0 else 0

        for feature in self.features:
            if self.killed:
                break
            self.context.setFeature(feature)
            try:
                self.feedback.info(
                    "<b><i>Creating {} mountain".format(
                        feature.attribute('name')
                        if feature.attribute('name') != NULL else "NoName"
                    )
                )
            except Exception as e:
                self.feedback.info(
                    "<b><i>Processing feature {}".format(feature.attribute('id')))
                self.feedback.debug(e)

            # Reading parameters for creating feature from the dialog or attributes
            max_mount_elev, ok = self.dlg.maxElevFractal.overrideButton.toProperty(
            ).valueAsInt(self.context)
            if not ok:
                max_mount_elev = self.dlg.maxElevFractal.value()

            tm, ok = self.dlg.mExponentFractal.overrideButton.toProperty().valueAsDouble(self.context)
            if not ok:
                tm = self.dlg.mExponentFractal.value()

            tn, ok = self.dlg.nExponentFractal.overrideButton.toProperty().valueAsDouble(self.context)
            if not ok:
                tn = self.dlg.nExponentFractal.value()

            tKref, ok = self.dlg.rockErodabilityFractal.overrideButton.toProperty(
            ).valueAsDouble(self.context)
            if not ok:
                tKref = self.dlg.rockErodabilityFractal.value()

            tAcrit, ok = self.dlg.drainageAreaFractal.overrideButton.toProperty(
            ).valueAsDouble(self.context)
            if not ok:
                tAcrit = self.dlg.drainageAreaFractal.value()

            tS_c, ok = self.dlg.channelSlopeFractal.overrideButton.toProperty(
            ).valueAsDouble(self.context)
            if not ok:
                tS_c = self.dlg.channelSlopeFractal.value()

            # Create a memory vector layer to store a feature at a time
            feature_layer = QgsVectorLayer(
                f"Polygon?crs={self.crs.authid()}", "Feature layer", "memory")
            feature_layer.dataProvider().addAttributes(self.mask_layer.fields())
            feature_layer.updateFields()
            feature_layer.dataProvider().addFeature(feature)
            vlayer_extent = feature_layer.extent()

            width = round((vlayer_extent.xMaximum() - vlayer_extent.xMinimum()) /
                          self.topo_layer.rasterUnitsPerPixelX())
            height = round((vlayer_extent.yMaximum() - vlayer_extent.yMinimum()) /
                           self.topo_layer.rasterUnitsPerPixelY())

            self.feedback.debug(
                f"Width of the modification rectangle: {width}")
            self.feedback.debug(
                f"Height of the modification rectangle: {height}")

            # create a square mask array to make it consistent with the topography model
            # 64, 128, 256 ...
            mask_size = findNearestPowerOfTwo(max((width, height)))
            self.feedback.debug(
                f"Size of the mask to be used for masking the model: {mask_size}x{mask_size}")

            # Original dimensions
            nx, ny = 8, 8
            dx, dy = 1000, 1000
            lx, ly = (nx) * dx, (ny) * dy
            boundaries = "4edges"
            self.feedback.debug(f"Boundaries set to: {boundaries}")
            nrefining = 1
            n_equ = 4

            # find number of iterations that will result in an array of a size that
            # can fit in the initial global raster
            m_size = mask_size
            while m_size > nx:
                nrefining += 1
                m_size /= 2

            m_size = None

            self.feedback.debug(
                f"Number of itterations for running the model: {nrefining}")

            # Initialising the model
            model = wt.MiniLEM()
            # Sets the dimensions of the regular grid
            model.initialise_graph(nx, ny, dx, dy, boundaries)
            # initialise white noise
            model.init_topo(1, "white_noise")
            self.feedback.info("Initializing the model with a white noise.")
            # feeds param to the model
            model.set_uniform_parameters(tm, tn, tKref, tAcrit, tS_c, 5)
            model.set_hillslope_mode("critical_slope")  # critical_slope
            self.feedback.info("Hillslope mode is set to 'critical slope'.")

            # Running the model
            unit_of_progress = progress_unit/nrefining
            for j in range(nrefining):
                for i in range(50 if (j == 0) else n_equ):
                    model.solve_analytically()
                model.double_resolution() if(j < nrefining - 1) else 0
                model.graph.set_boundaries_to(0) if(j < nrefining - 1) else 0
                self.feedback.debug(f"iteration: {j}")
                self.feedback.debug(
                    f"Minimum generated elevation: {model.graph.get_topo_np().min()}")
                self.feedback.debug(
                    f"Maximum generated elevation: {model.graph.get_topo_np().max()}")

                self.applyMask(model, feature_layer, mask_size, width, height)
                model.add_noise(20) if(j < nrefining - 1) else 0

                self.feedback.progress += int(unit_of_progress)

            # model.blur(5)

            # reading topography from the model
            dims = model.graph.get_dimensions()
            topo = model.graph.get_topo_np()
            topo = topo.reshape(dims['ny'], dims['nx'])
            self.feedback.debug("Final generated topo:")
            self.feedback.debug(f"Minimum generated elevation: {topo.min()}")
            self.feedback.debug(f"Maximum generated elevation: {topo.max()}")
            self.feedback.progress += int(progress_unit)
            topo = topo[0:height, 0:width]
            # Normalize elevations
            mask_outline_layer = polygonsToPolylines(feature_layer)
            rlayer_extent = self.topo_layer.extent()
            x_res = self.topo_layer.rasterUnitsPerPixelX()
            y_res = -self.topo_layer.rasterUnitsPerPixelY()
            geotransform = (rlayer_extent.xMinimum(), x_res, 0.0,
                            rlayer_extent.yMaximum(), 0.0, y_res)
            mask_outline_array = vectorToRaster(mask_outline_layer,
                                                geotransform,
                                                self.topo_layer.width(),
                                                self.topo_layer.height(),
                                                feedback=self.feedback,
                                                field_to_burn=None,
                                                no_data=0)
            initial_outline_elev = initial_values[mask_outline_array == 1]
            min_mount_elev = initial_outline_elev.mean()
            topo[topo == 0] = np.nan
            topo_normalized = modRescale(topo, min_mount_elev, max_mount_elev)
            # Rasterize mask with topography layer extent and geotransform
            mask_array = vectorToRaster(feature_layer,
                                        geotransform,
                                        self.topo_layer.width(),
                                        self.topo_layer.height(),
                                        feedback=self.feedback,
                                        field_to_burn=None,
                                        no_data=0)
            local_extent_xmin = round(np.sqrt(pow((vlayer_extent.xMinimum() -
                                                   rlayer_extent.xMinimum()), 2))/x_res)
            local_extent_ymax = round(np.sqrt(pow((vlayer_extent.yMaximum() -
                                                   rlayer_extent.yMaximum()), 2))/(-y_res))

            self.feedback.debug(f"local extent xmin: {local_extent_xmin}")
            self.feedback.debug(f"local extent ymax: {local_extent_ymax}")
            self.feedback.debug(
                f"local extent xmax: {local_extent_xmin+width}")
            self.feedback.debug(
                f"local extent ymin: {local_extent_ymax+height}")

            local_mask_array = mask_array[local_extent_ymax:local_extent_ymax+height,
                                          local_extent_xmin:local_extent_xmin+width]
            local_mask_array = local_mask_array.reshape(height, width)

            array_diff = topo_to_modify[mask_array == 1].size - \
                topo_normalized[local_mask_array == 1].size

            if array_diff != 0:
                local_mask_array = self.compensateForMaskDifference(
                    local_mask_array,
                    array_diff,
                    1 if array_diff > 0 else 0
                )

            topo_to_modify[mask_array ==
                           1] = topo_normalized[local_mask_array == 1]

        #  processing and saving the result
        if not self.killed:
            self.feedback.debug("Saving ... ")
            rlayer_extent = self.topo_layer.extent()
            geotransform = (rlayer_extent.xMinimum(),
                            self.topo_layer.rasterUnitsPerPixelX(),
                            0.0,
                            rlayer_extent.yMaximum(),
                            0.0,
                            -self.topo_layer.rasterUnitsPerPixelY())
            output_raster = gdal.GetDriverByName('GTIFF').Create(
                self.out_file_path, self.topo_layer.width(), self.topo_layer.height(), 1, taconst.GDT_TopoDType)

            output_raster.SetGeoTransform(geotransform)
            output_raster.SetProjection(self.projection)
            output_raster.GetRasterBand(1).SetNoDataValue(-9999)
            output_raster.GetRasterBand(1).WriteArray(topo_to_modify)
            output_raster.GetRasterBand(1).FlushCache()
            self.feedback.progress = 100
            self.finished.emit(True, self.out_file_path)
        else:
            self.finished.emit(False, "")

    def applyMask(self, model, featureLayer, maxMaskSize, maxMaskWidth, maxMaskHeight):
        # Read the model dimensions
        dims = model.graph.get_dimensions()

        # calculate mask dimensions
        extent = featureLayer.extent()
        x_min = extent.xMinimum()
        x_max = extent.xMaximum()
        y_min = extent.yMinimum()
        y_max = extent.yMaximum()

        ncols = int(round(dims['nx']*maxMaskWidth/maxMaskSize))
        nrows = int(round(dims['ny']*maxMaskHeight/maxMaskSize))

        pixel_size_x = (x_max-x_min)/ncols
        pixel_size_y = (y_max-y_min)/nrows
        self.feedback.debug(f"Pixel size X: {pixel_size_x}")
        self.feedback.debug(f"Pixel size Y: {pixel_size_y}")
        geotransform = (x_min, pixel_size_x, 0.0, y_max, 0.0, -pixel_size_y)
        self.feedback.debug(f"Mask layer extent: {extent}")
        self.feedback.debug(
            f"Geotransform for mask rasterizaton: {geotransform}")

        self.feedback.debug(
            f"Number of cols and rows in the mask: {ncols}x{nrows}")

        # rasterize the mask polygon
        temp_mask_array = vectorToRaster(
            featureLayer,
            geotransform,
            ncols,
            nrows,
            feedback=self.feedback,
            field_to_burn=None,
            no_data=0
        )
        mask_array = np.zeros((dims['nx'], dims['ny']), taconst.NP_MaskDType)
        mask_array[0:temp_mask_array.shape[0],
                   0:temp_mask_array.shape[1]] = temp_mask_array

        self.feedback.debug(f"Graph dimensions: {dims}")
        self.feedback.debug(f"Mask dimensions: {mask_array.shape}")
        self.feedback.debug(f"Mask min value: {mask_array.min()}")
        self.feedback.debug(f"Mask max value: {mask_array.max()}")
        model.init_boundaries_from_binary_array(
            mask_array.ravel(), True)

        # adding random boundary from a sin cos wave
        x = np.linspace(dims['extents'][0], dims['extents'][1], dims['nx'])
        y = np.linspace(dims['extents'][2], dims['extents'][3], dims['ny'])
        xx, yy = np.meshgrid(x, y)
        preexisting_topo = np.abs(50 * np.sin(xx) * np.cos(yy))
        model.burn_data_to_base_levels(preexisting_topo.ravel())

    def compensateForMaskDifference(self, maskArray, diffSize, mode=1):
        """Since the model for generating fractal topography is run on a small subset
        of the input raster and inserted back afterward, due to rounding width and
        heigh of the mask arrays, the local mask array and 'global' mask array may
        end up havng different masking areas (with value of 1). Therefore, this function
        should compensate for this difference by setting values (of equal amount of pixels)
         at the boundary of the creating feature to 1.

         :param maskArray: the array in which the difference should be compensated for.
         :type maskArray: numpy.ndarray
         :param diffSize: masking area difference in pixels.
         :type diffSize: int.
         :param mode: compensation mode. Can be 1 or 0. If masking area in the local mask array is smaller
                        than the area in the global mask array, the mode is 1, hence the masking
                        area should be increased and viceversa. 
         :type mode: int.

         :return: compensated mask array.
         :rtype: numpy.ndarray.
         """
        item1 = None
        mask_array1D = maskArray.ravel()
        for i in range(diffSize):
            for j in range(mask_array1D.size):
                if j == 0:
                    item1 = mask_array1D[j]
                    continue
                if item1 != mask_array1D[j] and item1 == mode:
                    mask_array1D[j] = mode
                    break
                else:
                    item1 = mask_array1D[j]
        return mask_array1D.reshape(maskArray.shape)
