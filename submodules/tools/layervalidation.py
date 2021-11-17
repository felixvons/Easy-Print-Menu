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

import os
from typing import Any, Dict, Optional

from qgis.core import (QgsField, QgsMapLayer, QgsProject, QgsVectorLayer,
                       QgsWkbTypes)


def get_layer_source(layer: QgsMapLayer) -> str:
    """ Returns file path to layer """
    source = layer.source()
    source = source.split("|")[0]  # "path/awdawd.gpkg|name"

    return source


def get_layer_from_source(source: str) -> Optional[QgsMapLayer]:
    """ Returns layer from source

        :param source: layer source path
        :return: returns True, if layer is already loaded with given source
    """

    source = os.path.normpath(source)
    source = os.path.normcase(source)
    layers = QgsProject.instance().mapLayers().values()
    sources = {os.path.normcase(os.path.normpath(layer.source())): layer for layer in layers}

    return sources.get(source, None)


def get_layer_by_template(name: str, epsg: str, template: Dict[Any, Any]) -> QgsVectorLayer:
    """ Creates new layer with given `epsg` and `template`.

        :param name: layer name
        :param epsg: crs auth id
        :param template: template to use (containing columns, layer type)
        :return:
        :rtype:
    """
    layer_type: str = {
        QgsWkbTypes.Point: "Point",
        QgsWkbTypes.LineString: "Linestring",
        QgsWkbTypes.Polygon: "Polygon",
        QgsWkbTypes.NoGeometry: "NoGeometry",
    }[template['WKBTYPE']]

    if not epsg.casefold().startswith("epsg:"):
        epsg = f"EPSG:{epsg}"

    new_layer = QgsVectorLayer(layer_type + "?crs=" + epsg, name, "memory")

    # Erstelle Attribut-Listen für Provider
    attributes = []
    for name, value in template['Attributes'].items():
        field = QgsField(name, value['type'])
        attributes.append(field)

    new_layer.dataProvider().addAttributes(attributes)
    new_layer.updateFields()

    return new_layer