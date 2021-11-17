# -*- coding: utf-8 -*-

"""
***************************************************************************
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
import inspect
from qgis.gui import QgisInterface
from typing import Type

# Edit this import and references in this file to new name
from .plugin import PluginPlot
from .modules.template.base_class import Plugin


def get_class() -> Type[PluginPlot]:
    """ returns plugin class """
    assert Plugin in inspect.getmro(PluginPlot), f"main plugin class must base on Plugin class"
    return PluginPlot


# noinspection PyPep8Naming
def classFactory(iface: QgisInterface, **kwargs: dict) -> PluginPlot:  # pylint: disable=invalid-name
    """Loads this plugin an loads it. Automatically called by QGIS

    :param iface: A QGIS interface instance.
    """

    return get_class()(iface, **kwargs)
