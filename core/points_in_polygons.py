import points_spatial_tree
import math
import pygplates
import sys


def find_polygons(
        points,
        polygons,
        polygon_proxies = None,
        all_polygons = False,
        subdivision_depth = points_spatial_tree.DEFAULT_SUBDIVISION_DEPTH):
    """
    Efficient point-in-polygon testing when there are many relatively uniformly spaced points to be tested against polygons.

    points: a sequence of 'pygplates.PointOnSphere'.

    polygons: a sequence of 'pygplates.PolygonOnSphere'.

    polygon_proxies: Optional sequence of objects associated with 'polygons'.
                     If not specified then the proxies default to the polygons themselves.
                     These can be any object (such as the 'pygplates.Feature' that the polygon came from).

    all_polygons: Whether to find all polygons containing each point or just the first one encountered.
                  Set to True if polygons overlap each other, otherwise set to False (for non-overlapping polygons).
                  Defaults to False (non-overlapping polygons).

    subdivision_depth: The depth of the lat/lon quad tree used to speed up point-in-polygon queries.
                       The lat/lon width of a leaf quad tree node is (90 / (2^subdivision_depth)) degrees.
                       Generally the denser the 'points' the larger the depth should be.
                       Setting this value too high causes unnecessary time to be spent generating a deep quad tree.
                       Setting this value too low reduces the culling efficiency of the quad tree.
                       However a value of 4 seems to work quite well for a uniform lat/lon spacing of 'points' of 1 degree and below
                       without the cost of generating a deep quad tree.
                       So most of the time the subdivision depth can be left at its default value.

    Returns: A list of polygon proxies associated with 'points'.
             The length of the returned list matches the length of 'points'.
             For each point in 'points', if the point is contained by a polygon then that polygon's proxy
             is stored (otherwise None is stored) at the same index (as the point) in the returned list.
             If 'all_polygons' is False then each item in returned list is a single polygon proxy (or a single None).
             If 'all_polygons' is True then each item in returned list is a *list* of polygon proxies (or a single None).

    Raises ValueError if the lengths of 'polygons' and 'polygon_proxies' (if specified) do not match.
    """

    spatial_tree_of_points = points_spatial_tree.PointsSpatialTree(points, subdivision_depth)
    return find_polygons_using_points_spatial_tree(points, spatial_tree_of_points, polygons, polygon_proxies, all_polygons)


def find_polygons_using_points_spatial_tree(
        points,
        spatial_tree_of_points,
        polygons,
        polygon_proxies = None,
        all_polygons = False):
    """
    Same as 'find_polygons()' except 'spatial_tree_of_points' is a 'points_spatial_tree.PointsSpatialTree' of 'points'.

    This is useful when re-using a single 'points_spatial_tree.PointsSpatialTree'.
    For example, when using it both for point-in-polygon queries and minimum distance queries.

    Note that 'spatial_tree_of_points' should have been built from 'points' since it contains
    indices into the 'points' sequence.
    """

    # Use the polygons as proxies if no proxies have been specified.
    if polygon_proxies is None:
        polygon_proxies = polygons

    if len(polygons) != len(polygon_proxies):
        raise ValueError('Number of polygons must match number of proxies.')

    # Sort the polygons from largest to smallest area.
    # This makes searching for points/geometries more efficient.
    #
    # 'polygons_and_proxies' is a list of 2-tuples (polygon, polygon_proxy).
    polygons_and_proxies = sorted(
            ((polygons[index], polygon_proxies[index]) for index in range(len(polygons))),
            key=lambda polygon_and_proxy: polygon_and_proxy[0].get_area(),
            reverse=True)

    # By default all points are outside all polygons.
    # If any are found to be inside then we'll set the relevant polygon proxy.
    polygon_proxies_containing_points = [None] * len(points)

    # Use a quad tree for efficiency - enables us to cull large groups of points that are either
    # outside all polygons or inside a polygon (avoids point-in-polygon tests for these points).
    for root_node in spatial_tree_of_points.get_root_nodes():
        _visit_spatial_tree_node(root_node, points, polygons_and_proxies, polygon_proxies_containing_points, all_polygons)

    return polygon_proxies_containing_points


##################
# Implementation #
##################


def _visit_spatial_tree_node(
        node,
        points,
        parent_overlapping_polygons_and_proxies,
        polygon_proxies_containing_points,
        all_polygons):

    # See if the current quad tree node's bounding polygon overlaps any polygons.
    overlapping_polygons_and_proxies = []
    for polygon, polygon_proxy in parent_overlapping_polygons_and_proxies:

        # See if quad tree node and current polygon overlap.
        if pygplates.GeometryOnSphere.distance(
                node.get_bounding_polygon(),
                polygon,
                1e-4, # Arbitrarily small threshold for efficiency since only interested in zero distance (intersection).
                geometry1_is_solid = True,
                geometry2_is_solid = True) == 0:

            # See if quad tree node is contained completely inside polygon.
            # We test this by only considering the quad tree node polygon as solid (the polygon is an outline).
            if pygplates.GeometryOnSphere.distance(
                    node.get_bounding_polygon(),
                    polygon,
                    1e-4, # Arbitrarily small threshold for efficiency since only interested in zero distance (intersection).
                    geometry1_is_solid = True) != 0:

                # Recursively fill the entire quad sub-tree as inside current polygon.
                _fill_spatial_tree_node_inside_polygon(node, polygon_proxy, polygon_proxies_containing_points, all_polygons)

                if not all_polygons:
                    # Only storing first polygon proxy encountered, so skip remaining polygons.
                    return

                # Note: No need to add polygon to 'overlapping_polygons_and_proxies' since we've already taken care of it.

            else:
                overlapping_polygons_and_proxies.append((polygon, polygon_proxy))

    # If quad tree node is outside all polygons then nothing left to do since all points are marked as outside by default.
    if not overlapping_polygons_and_proxies:
        return

    # Visit child nodes (if internal node) or test each point (if leaf node).
    if node.is_internal_node():
        for child_node in node.get_child_nodes():
            _visit_spatial_tree_node(
                    child_node, points, overlapping_polygons_and_proxies, polygon_proxies_containing_points, all_polygons)
    else:
        for point_index in node.get_point_indices():
            point = points[point_index]
            for polygon, polygon_proxy in overlapping_polygons_and_proxies:
                if polygon.is_point_in_polygon(point):
                    # Point is inside a polygon.
                    if all_polygons:
                        # Each point has a *list* of polygon proxies (or None).
                        # Create list if first polygon proxy encountered for current point.
                        if polygon_proxies_containing_points[point_index] is None:
                            polygon_proxies_containing_points[point_index] = []
                        polygon_proxies_containing_points[point_index].append(polygon_proxy)
                    else:
                        # Each point has a *single* polygon proxy (or None).
                        polygon_proxies_containing_points[point_index] = polygon_proxy
                        # No need to visit remaining polygons for the current point.
                        break


def _fill_spatial_tree_node_inside_polygon(
        node,
        polygon_proxy,
        polygon_proxies_containing_points,
        all_polygons):

    if node.is_internal_node():
        for child_node in node.get_child_nodes():
            _fill_spatial_tree_node_inside_polygon(child_node, polygon_proxy, polygon_proxies_containing_points, all_polygons)
    else:
        for point_index in node.get_point_indices():
            # Point is inside a polygon.
            if all_polygons:
                # Each point has a *list* of polygon proxies (or None).
                # Create list if first polygon proxy encountered for current point.
                if polygon_proxies_containing_points[point_index] is None:
                    polygon_proxies_containing_points[point_index] = []
                polygon_proxies_containing_points[point_index].append(polygon_proxy)
            else:
                # Each point has a *single* polygon proxy (or None).
                polygon_proxies_containing_points[point_index] = polygon_proxy


