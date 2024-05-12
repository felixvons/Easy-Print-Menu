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

import os.path
import os
import shutil
import sys

from datetime import datetime

from pathlib import Path

from qgis.PyQt.QtWidgets import QMenu, QApplication, QAction
from qgis.PyQt.QtCore import pyqtSignal, QObject

from qgis.core import QgsApplication, Qgis
from qgis.gui import QgsVertexMarker, QgsRubberBand, QgisInterface

from typing import List, Optional

from .submodules.tools import compatibility
from .submodules.tools.versions_reader import VersionPlugin
from .modules.template.base_class import ModuleBase, Plugin


class PluginPlot(ModuleBase, Plugin, QObject):
    """ Main class for this plugin.

        Attachments when contacting support are stored in:
        * Path to qgis profile/_temp_files/plugin name.
        * This folder will be cleared on startup and end.

        Qt Signals:
        * pluginReloaded: add your callables to trigger, when user triggered manual reloading

        :param iface: qgis interface (QMainWindow, layer handling, etc.)
        :param kwargs: dictionary with keyword arguments, if empty -> then QGIS handle this plugin, else an other
                       ModuleBase loads this
    """
    pluginUnloaded = pyqtSignal(name="pluginUnloaded")
    pluginReloaded = pyqtSignal(name="pluginReloaded")
    versionRead = pyqtSignal(ModuleBase, name="versionRead")
    feedbackClicked = pyqtSignal(ModuleBase, name="feedbackClicked")

    def __init__(self, iface: QgisInterface, **kwargs: dict):

        self.iface: QgisInterface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.plugin_dir = os.path.normpath(os.path.normcase(self.plugin_dir))
        self.plugin_py = os.path.normpath(os.path.normcase(__file__)).replace("\\", "/")
        self.meta_dir = os.path.join(self.plugin_dir, 'metadata.txt')
        self.drawings: List[QgsVertexMarker, QgsRubberBand] = []  # necessary for DrawTool!
        self.menu_bar: Optional[QMenu] = None
        self.menu_bar_action: Optional[QAction] = None

        plugins = os.path.join(QgsApplication.qgisSettingsDirPath(),
                               'python',
                               'plugins')
        test_plugin_dir = os.path.join(plugins,
                                       os.path.basename(self.plugin_dir),
                                       os.path.basename(__file__))
        test_plugin_dir = os.path.normpath(os.path.normcase(test_plugin_dir)).replace("\\", "/")
        # default plugin path equals path to this file -> is plugin
        self.__is_qgis_plugin = test_plugin_dir == self.plugin_py
        self.__is_module = not self.__is_qgis_plugin  # negates plugin value

        self.version = VersionPlugin.get_local_version(self.meta_dir)
        self.version_int = VersionPlugin.get_version_int(self.version)
        self.plugin_menu = VersionPlugin.get_meta_value(self.meta_dir, "name_menu_bar")
        self.plugin_name = VersionPlugin.get_meta_value(self.meta_dir, "name")
        self.email = ""

        # log file name -> "PluginTemplate_1_0.log"
        self.log_filename = f"{self.__class__.__name__}_{self.version.replace('.', '_')}"

        # folder to store temp files (e.g. contacting support with attachments)
        self.temp_files = os.path.join(QgsApplication.qgisSettingsDirPath(), '_temp_files', self.log_filename)
        self.cleanup_temp_files()

        # files and folders
        self.icons_dir = os.path.join(self.plugin_dir, 'templates', 'icons')
        ModuleBase.__init__(self, None, self.plugin_menu, None, **kwargs)  # has dummy log method
        QObject.__init__(self)

        self.log(f"{self.plugin_menu} version {self.version} loaded with params: {kwargs}")

        if self.is_qgis_plugin:
            self.connect(self.iface.mapCanvas().mapToolSet, self.check_map_tool_changed)
        self.load_version_info()

        # Plot
        self.plots_dir = str(Path(self.plugin_dir) / "templates" / "plots")

    def log(self, text: str, tag: str = 'Easy Print Menu') -> Optional[str]:
        """ Writes log to file an add text and tag do local history

            :param text: text
            :param tag: tag for text
            :return: logged text
        """

        QgsApplication.messageLog().logMessage(text, tag, Qgis.Info)

        return text

    def load_version_info(self):
        self.repo_version_int = -1
        self.versionRead.emit(self)

    def check_map_tool_changed(self, new_tool, old_tool):
        for drawing in self.drawings:
            if drawing:
                self.iface.mapCanvas().scene().removeItem(drawing)

        self.drawings.clear()

    def get_temp_folder(self):
        path = os.path.join(self.get_plugin().temp_files,
                            datetime.now().strftime("_%Y-%m-%d_%H-%M-%S_%f"))
        if not os.path.exists(path):
            os.makedirs(path)

        return path

    def cleanup_temp_files(self):
        """ cleanup all temp files. Nothing happens on blocking process """
        try:
            shutil.rmtree(self.temp_files)
        except:
            pass

    def get_icon_path(self, icon: str, folder: Optional[str] = None) -> str:
        """ Returns joined os path from icons folder.
            If no file ending is given, then only svg, png and jpg are valid.

            :param icon: icon name with or without file ending
        """

        icons_dir = self.icons_dir if not folder else folder

        check = icon.lower()
        endings = (".png", ".jpg", ".jpeg", ".svg")
        file_names = {icon + x for x in endings}
        if not check.endswith(endings):
            for file_name in os.listdir(icons_dir):
                path = os.path.join(icons_dir, file_name)
                if not Path(path).is_file():
                    continue

                if file_name in file_names:
                    icon = file_name
                    break

        path = os.path.join(icons_dir, icon)
        if not Path(path).is_file():
            raise FileNotFoundError(f"file '{icon}' not found in '{icons_dir}'")

        return path

    @property
    def is_qgis_plugin(self) -> bool:
        """ is this a module loaded per default from QGIS? """
        return self.__is_qgis_plugin

    @property
    def is_module(self) -> bool:
        """ is this a module loaded by an other module? """
        return self.__is_module

    # noinspection PyPep8Naming
    def initGui(self):
        """ Called by QGIS on programm start or loading this plugin.
            At this point you can interacting with QGIS gui, e.g. `self.iface.mainWindow()`.
            Add your own QActions/QToolBars in `utilities.ui_control.load_tool_bar`
        """

        # setup menu bar in QGIS
        #menu_bar = self.iface.mainWindow().menuBar()
        #self.menu_bar = QMenu(self.plugin_menu, menu_bar)
        #self.menu_bar_action: QAction = menu_bar.addMenu(self.menu_bar)

        # Do not add you actions in initGui, keep it clean and use load_tool_bar instead
        from .utilities import ui_control
        ui_control.load_tool_bar(self)

    def unload(self, self_unload: bool = False):
        """ Auto-call when plugin will be unloaded from QGIS plugin manager. """
        self.log("unloading")
        super().unload()

        QApplication.restoreOverrideCursor()

        # Entferne QActions und QToolBars
        #self.iface.mainWindow().menuBar().removeAction(self.menu_bar_action)

        # Entferne Actions
        for action in self._actions:
            self.iface.removePluginMenu(self.plugin_menu, action)
            self.iface.removeToolBarIcon(action)

        compatibility.qgis_unload_keyerror(self.plugin_dir)

        for marker in self.drawings:
            self.iface.mapCanvas().scene().removeItem(marker)
        self.drawings.clear()
        self.cleanup_temp_files()
        self.log("unloaded")

    def __repr__(self) -> str:
        if self.is_qgis_plugin:
            managed_by = "QgsApplication(stand-alone)"
            plugin = ""
        else:
            parent = self.parent_module
            if parent is None:
                managed_by = "self managed, no parent"
                plugin = ""
            else:
                managed_by = self.parent_module.__class__.__name__
                plugin = f", plugin={self.get_plugin().plugin_menu}"

        version = getattr(self, "version", "not set")
        plugin_menu = getattr(self, "plugin_menu", "not set")

        return f"{self.__class__.__name__}(version={version}, " \
               f"plugin_menu={plugin_menu}, managed_by={managed_by}{plugin})"
