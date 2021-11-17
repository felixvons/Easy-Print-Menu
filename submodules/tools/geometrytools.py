# -*- coding: utf-8 -*-

"""
***************************************************************************
    Date                 : January 2021
    Copyright            : Felix von Studsinske
    Email                : /
    Developer            : Felix von Studsinske
    Description          : -- optional --
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import (QgsCoordinateTransform, QgsGeometry,
                       QgsCoordinateReferenceSystem, QgsProject, QgsRectangle)


def get_transform(src_coordinate_system: QgsCoordinateReferenceSystem,
                  dst_coordinate_system: QgsCoordinateReferenceSystem) -> QgsCoordinateTransform:
    """ get transform object

        :param src_coordinate_system: source coordinate system
        :param dst_coordinate_system: destination coordinate system
        :return: transform object
    """
    transform_params = QgsCoordinateTransform(
        src_coordinate_system,
        dst_coordinate_system,
        QgsProject.instance())

    return transform_params


def transform_geometry(geometry: QgsGeometry, src_coordinate_system: QgsCoordinateReferenceSystem,
                       dst_coordinate_system: QgsCoordinateReferenceSystem) -> QgsGeometry:
    """ Transform Geometry-Points to another coordinate
        reference system

        :param geometry: geometry to transform
        :param src_coordinate_system: source coordinate system
        :param dst_coordinate_system: destination coordinate system
        :return: converted point
    """

    # get geometry from point
    copy_geometry = QgsGeometry(geometry)

    transform_params = get_transform(src_coordinate_system, dst_coordinate_system)
    copy_geometry.transform(transform_params)

    return copy_geometry


def polygon_to_rectangle(polygon: QgsGeometry) -> QgsRectangle:
    """ converts simple geometry(polygon) to rectangle.
        Geometry should have only four points orientated as a rectangle.

        :param polygon: polygon geometry
        :return: converted rectangle
    """
    point_list = polygon.asPolygon()[0]
    x_axis = [p.x() for p in point_list]
    x_min = min(x_axis)
    x_max = max(x_axis)

    y_axis = [p.y() for p in point_list]
    y_min = min(y_axis)
    y_max = max(y_axis)

    return QgsRectangle(x_min, y_min, x_max, y_max)


def is_geometry_valid(geometry: QgsGeometry) -> bool:
    """ Checks geometry validness

        :param geometry: geometry
        :return: True = is valid
    """
    valid = not geometry.isNull() and not geometry.isEmpty() and geometry.isGeosValid()
    # Prüfe nun, ob "nan" oder "inf" vorkommt
    wkt_valid = geometry.asWkt()
    wkt_valid = "inf" not in wkt_valid and "nan" not in wkt_valid

    return valid and wkt_valid
