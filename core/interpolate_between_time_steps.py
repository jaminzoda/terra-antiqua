import os
import math
import numpy as np
import points_in_polygons
import points_spatial_tree
from proximity_query import find_closest_geometries_to_points_using_points_spatial_tree
import pygplates

from .base_algorithm import TaBaseAlgorithm

class TaInterpolateBetweenTimeSteps(TaBaseAlgorithm):
    def __init__(self, dlg):
        self.dlg = dlg
        super().__init__(dlg)
        self.static_polygons = None
        self.rotation_model = None
        self.from_layer = None
        self.to_layer = None
        self.time_from = None
        self.time_to = None
        self.time_to_interp = None
        self.grid_sampling=1.
        self.anchor_plate_id=0
        self.extent = None
        self.layers = {}

    def getParameters(self):
        pass

    def run(self):
        xmin = self.extent.xMinimum()
        xmax= self.extent.xMaximum()
        ymin = self.extent.yMinimum()
        ymax= self.extent.yMaximum()
        (points,
        spatial_tree_of_uniform_recon_points) = self.createPoints(xmin,
                                                                  xmax,
                                                                  ymin,
                                                                  ymax,
                                                                  self.grid_sampling)

        (time_from_point_lons,
        time_from_point_lats,
        time_to_point_lons,
        time_to_point_lats,
        time_to_interp_point_lons,
        time_to_interp_point_lats) = reconstructRaster(self.static_polygons,
                                                      self.rotation_model,
                                                      self.time_from,
                                                      self.time_to,
                                                      self.time_interp,
                                                      points,
                                                      spatial_tree_of_uniform_recon_points,
                                                      self.anchor_plate_id)

        interpolated_features = []
        for lon_from, lat_from, lon_to, lat_to, lon_interp, lat_interp in zip(
                                                                            time_from_point_lons,
                                                                            time_from_point_lats,
                                                                            time_to_point_lons,
                                                                            time_to_point_lats,
                                                                            time_to_interp_point_lons,
                                                                            time_to_interp_point_lats):
            z_from = self.from_layer.dataProvider().identify(QgsPoint(lon_from, lat_from),
                                                             QgsRaster.IdentifyFormatValue).results().get(1)
            z_to = self.to_layer.dataProvider().identify(QgsPoint(lon_to, lat_to),
                                                         Qgs.Raster.IdentifyFormatValue).results().get(1)
            z_interpolated = numpy.interp(self.time_to_interp, [time_from, time_to],[z_from, z_to])
            interpolated_point = QgsPoint(lon_interp,
                                          lat_interp,
                                          z_interpolated)
            interpolated_feature = QgsFeature()
            interpolated_feature.setGeometry(interpolated_point)
            interpolated_features.append(interpolated_feature)

        interpolated_layer = QgsVectorLayer(f"PointZM?crs={self.crs}", "Interpolated points layer", "memory")
        interpolated_layer.dataProvider().addFeatures(interpolated_features)
        self.finished.emit(True, interpolated_layer.source())




    def reconstructRaster(self, static_polygon_features,
                                 rotation_model,
                                 time_from,
                                 time_to,
                                 time_interp,
                                 uniform_recon_points,
                                 spatial_tree_of_uniform_recon_points,
                                 anchor_plate_id=0):

        self.feedback.info('Reconstructing static polygons...')

        # Reconstruct the multipoint feature.
        recon_static_polygon_features = []
        pygplates.reconstruct(static_polygon_features, rotation_model, recon_static_polygon_features, time_to, anchor_plate_id=anchor_plate_id)

        # Extract the polygons and plate IDs from the reconstructed static polygons.
        recon_static_polygons = []
        recon_static_polygon_plate_ids = []
        for recon_static_polygon_feature in recon_static_polygon_features:
            recon_plate_id = recon_static_polygon_feature.get_feature().get_reconstruction_plate_id()
            recon_polygon = recon_static_polygon_feature.get_reconstructed_geometry()

            recon_static_polygon_plate_ids.append(recon_plate_id)
            recon_static_polygons.append(recon_polygon)

        self.feedback.info('Find plate ids for generated points...')

        # Find the reconstructed static polygon (plate IDs) containing the uniform (reconstructed) points.
        #
        # The order (and length) of 'recon_point_plate_ids' matches the order (and length) of 'uniform_recon_points'.
        # Points outside all static polygons return a value of None.
        recon_point_plate_ids = points_in_polygons.find_polygons_using_points_spatial_tree(
                uniform_recon_points, spatial_tree_of_uniform_recon_points, recon_static_polygons, recon_static_polygon_plate_ids)

        self.feedback.info('Grouping points by plate ids...')

        # Group recon points with plate IDs so we can later create one multipoint per plate.
        recon_points_grouped_by_plate_id = {}
        for point_index, point_plate_id in enumerate(recon_point_plate_ids):
            # Reject any points outside all reconstructed static polygons.
            if point_plate_id is None:
                continue

            # Add empty list to dict if first time encountering plate ID.
            if point_plate_id not in recon_points_grouped_by_plate_id:
                recon_points_grouped_by_plate_id[point_plate_id] = []

            # Add to list of points associated with plate ID.
            recon_point = uniform_recon_points[point_index]
            recon_points_grouped_by_plate_id[point_plate_id].append(recon_point)

        self.feedback.info('Reverse reconstructing points...')

        # Reconstructed points.
        recon_point_lons = []
        recon_point_lats = []

        # Present day points associated with reconstructed points.
        point_lons = []
        point_lats = []

        #points at the time interpolation
        interp_point_lons=[]
        interp_point_lats=[]
        # Create a multipoint feature for each plate ID and reverse-reconstruct it to get present-day points.
        #
        # Iterate over key/value pairs in dictionary.
        for plate_id, recon_points_in_plate in recon_points_grouped_by_plate_id.items():
            # Reverse reconstructing a multipoint is much faster than individually reverse-reconstructing points.
            multipoint_feature = pygplates.Feature()
            multipoint_feature.set_geometry(pygplates.MultiPointOnSphere(recon_points_in_plate))
            multipoint_feature.set_reconstruction_plate_id(plate_id)

            # Reverse reconstruct the multipoint feature.
            pygplates.reverse_reconstruct(multipoint_feature, rotation_model, time_to, anchor_plate_id=anchor_plate_id)

            #Forward reconstruct multipoint to
            multipoint_at_from_time = []
            pygplates.reconstruct(multipoint_feature,rotation_model,multipoint_at_from_time,time_from, anchor_plate_id=anchor_plate_id)

            # Extract reverse-reconstructed geometry.
            multipoint = multipoint_at_from_time[0].get_reconstructed_geometry()

            # Collect present day and associated reconstructed points.
            for point_index, point in enumerate(multipoint):
                lat, lon = point.to_lat_lon()
                point_lons.append(lon)
                point_lats.append(lat)

                recon_point = recon_points_in_plate[point_index]
                recon_lat, recon_lon = recon_point.to_lat_lon()
                recon_point_lons.append(recon_lon)
                recon_point_lats.append(recon_lat)

            multipoint_at_interp_time = []
            pygplates.reconstruct(multipoint_at_from_time[0].get_feature(), rotation_model, multipoint_at_interp_time,
                                  time_interp, anchor_plate_id=anchor_plate_id)

            multipoint = multipoint_at_interp_time[0].get_reconstructed_geometry()
            for point_index, point in enumerate(multipoint):
                lat, lon = point.to_lat_lon()
                interp_point_lons.append(lon)
                interp_point_lats.append(lat)


        return (point_lons,point_lats,
               recon_point_lons,recon_point_lats,
               interp_point_lons, interp_point_lats)



    def createPoints(self, xmin, xmax, ymin, ymax, grid_sampling):
        assert all([type(x)==float for x in [xmin,xmax,ymin,ymax, grid_sampling]])
        grid_longitudes, grid_latitudes = np.meshgrid(np.arange(xmin,xmax,grid_sampling), np.arange(ymin, ymax,grid_sampling))
        grid_longitudes = grid_longitudes.flatten()
        grid_latitudes = grid_latitudes.flatten()
        points = [pygplates.PointOnSphere(point) for point in zip(grid_latitudes, grid_longitudes)]

        spatial_tree_of_uniform_recon_points = points_spatial_tree.PointsSpatialTree(points)
        return points, spatial_tree_of_uniform_recon_points

    def interp(self, z_from, z_to,time_from, time_to, time_to_interp)-> float:
            return numpy.interp(recon_time, [start_time, end_time], [s_arr[i], e_arr[i]])

        return out_arr
