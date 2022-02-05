# -*- coding: utf-8 -*-

"""
***************************************************************************
    Date                 : August 2020
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
import sys
import os

from qgis.core import QgsNetworkAccessManager, Qgis, QgsNetworkReplyContent
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtCore import QUrl

from typing import Optional, Tuple


def qgis_unload_keyerror(plugin_dir: str) -> None:
    """ A special KeyError workaround in QGIS unloading mechanism of plugins.

        :param plugin_dir: plugin path
    """
    from collections import OrderedDict
    from qgis import utils

    _loaded_qgs_mod = {}
    count = 0

    # Stored Modules from QGIS
    plugin_dir = os.path.basename(os.path.normpath(plugin_dir))
    loaded_qgs_mod = [i for i in utils._plugin_modules[plugin_dir]]

    # Stored Modules from sys
    loaded_sys_mod = [i for i in sys.modules if i.startswith(plugin_dir)]

    for smod in loaded_sys_mod:
        if smod not in loaded_qgs_mod:
            loaded_qgs_mod.append(smod)  # Add to qgis-list

    for qmod in loaded_qgs_mod.copy():
        if qmod not in loaded_sys_mod:
            loaded_qgs_mod.remove(qmod)  # Del from qgis-list

    for mod in loaded_qgs_mod.copy():
        path = mod.split(".")
        path_len = len(mod.split("."))
        if path_len > 1:
            key = path[0] + path[1]
        elif path_len == 1:
            key = path[0]
        else:
            key = 'ERROR'
        key = str(path_len) + "/" + key + "/" + str(count)
        count += 1
        _loaded_qgs_mod.setdefault(key, mod)

    _loaded_qgs_mod = OrderedDict(sorted(_loaded_qgs_mod.copy().items(),
                                         reverse=True))
    sorted_list = [value for key, value in _loaded_qgs_mod.items()]
    utils._plugin_modules[plugin_dir] = sorted_list


def get_online_plugin_version(name: str, forceRefresh: bool = False) -> Tuple[Optional[str], str]:
    """ returns current online version str from official qgis repository

        :param name: plugins name in qgis repo
        :param forceRefresh: True do not use cached data
    """
    # create Qt request object
    url = "https://plugins.qgis.org/plugins/plugins.xml"
    version = ".".join(Qgis.QGIS_VERSION.split(".")[:2])
    request = QNetworkRequest(QUrl(f"{url}?qgis={version}"))

    # query via network manager with qgis
    manager = QgsNetworkAccessManager.instance()
    response: QgsNetworkReplyContent = manager.blockingGet(request, forceRefresh=forceRefresh)
    if response.error() != QNetworkReply.NoError:
        # oops
        return None, response.errorString()

    # parse result to QDomDocument (usually it is Xml)
    dom = QDomDocument()
    dom.setContent(response.content())
    plugin = dom.firstChildElement("plugins")
    nodes = plugin.childNodes()
    version = None
    # iter over alls pyqgis_plugin
    for index in range(nodes.length()):
        node = nodes.item(index)
        attributes = node.attributes()

        # iter over each attribute (name, version, plugin_id)
        attr_dict = {}
        for ai in range(attributes.length()):
            attr_item = attributes.item(ai).toAttr()

            attr_dict[attr_item.name()] = attr_item.value()

        if attr_dict.get("name", None) == name:
            version = attr_dict.get("version", None)

    return version, ""