# -*- coding: utf-8 -*-

"""
***************************************************************************
    Date                 : September 2021
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

from datetime import datetime
import traceback
from typing import Callable, Optional

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow
from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsApplication
from qgis.gui import QgsFileWidget

from ..template.base_class import UiModuleBase, ModuleBase
from ...submodules.tools.qt_functions import set_label_status
from ...submodules.tools._qt_constants import STYLE_SHEET_ERROR
from .plot_layer import PlotLayer
from .plot_layout import PlotLayout

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class PlotNewLayout(UiModuleBase, FORM_CLASS, QMainWindow):
    """ Creates new plot layout
    """

    def __init__(self, parent_module: Optional['ModuleBase'] = None, module_name: str = '',
                 log: Optional[Callable] = None, **kwargs: dict):

        UiModuleBase.__init__(self, parent_module, module_name, log, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent', None))


        self.setupUi(self)
        self.show()

        # Qt Connection
        self.connect(self.But_Cancel.clicked, self.close)
        self.connect(self.But_Create.clicked, self.create_new_layout)
        self.connect(self.CheckBox_Temporary.stateChanged, self.temporary_state_changed)

        self.temporary_state_changed(self.CheckBox_Temporary.checkState())
        self.layouts = self.get_parent().layouts

        self.post_checks()

        self.FileEdit.setFilter("GeoPackage (*.gpkg)")
        self.FileEdit.setStorageMode(QgsFileWidget.SaveFile)

        # loads available CRS to the dropdown
        default_crs = QgsProject.instance().crs()
        default_crs = QgsCoordinateReferenceSystem("EPSG:25832") if not default_crs.isValid() else default_crs
        self.DrD_Crs.setLayerCrs(default_crs)
        self.DrD_Crs.setCrs(default_crs)
        self.DrD_Crs.setLayerCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.DrD_Crs.setLayerCrs(QgsCoordinateReferenceSystem("EPSG:4258"))
        self.DrD_Crs.setLayerCrs(QgsCoordinateReferenceSystem("EPSG:25833"))
        self.DrD_Crs.setLayerCrs(QgsCoordinateReferenceSystem("EPSG:3857"))

        # loads available print templates to dropdown
        self.DrD_Templates.clear()
        for layout in self.layouts:
            if layout.group:
                self.DrD_Templates.addItem(f"[{layout.group}] {layout.name}", layout)
            else:
                self.DrD_Templates.addItem(f"{layout.name}", layout)

        set_label_status(self.Label_Status, "")

    def get_temp_path(self, path: str):
        base = os.path.basename(path).split(".")[0]
        base = base + f" ({self.tr_('memory')}).qpt"
        path = os.path.join(self.get_plugin().temp_files,
                            base + datetime.now().strftime("_%Y-%m-%d_%H-%M-%S_%f") + ".gpkg")
        return path

    def temporary_state_changed(self, state: Qt.CheckState):
        self.FileEdit.setEnabled(state == Qt.Unchecked)

        if self.CheckBox_Temporary.checkState() == Qt.Checked:
            self.FileEdit.lineEdit().setPlaceholderText(self.tr_('memory'))
        else:
            self.FileEdit.lineEdit().setPlaceholderText(self.tr_('Select save location'))


    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def create_new_layout(self, checked: bool):
        """ try to create new plot layer """
        set_label_status(self.Label_Status, "")

        layout: PlotLayout = self.DrD_Templates.currentData()
        if layout is None:
            set_label_status(self.Label_Status,
                             self.tr_("No Print Layout template selected."),
                             STYLE_SHEET_ERROR)
            return

        if self.CheckBox_Temporary.isChecked():
            path = self.get_temp_path(layout.path)
        else:
            path = self.FileEdit.filePath()
            if not path:
                set_label_status(self.Label_Status, self.tr_("No save location set."), STYLE_SHEET_ERROR)
                return
            if Path(path).is_file():
                set_label_status(self.Label_Status,
                                 self.tr_("File '%s' already exists.") % Path(path).name,
                                 STYLE_SHEET_ERROR)
                return

        crs: QgsCoordinateReferenceSystem = self.DrD_Crs.crs()
        if not crs.isValid():
            set_label_status(self.Label_Status,
                             self.tr_("CRS '%s' is invalid.") % crs.authid(),
                             STYLE_SHEET_ERROR)
            return

        try:
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            plot_layer = PlotLayer.create_new(path, crs)
            plot_layer.file = layout.path
            self.get_parent().set_layer(plot_layer.layer_pages)
            self.unload(True)
        except TypeError as e:
            self.log(str(traceback.format_exc()))
            set_label_status(self.Label_Status,
                             self.tr_("Layout could not be created. Unknown error."),
                             STYLE_SHEET_ERROR)

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """

        super().unload(self_unload)
        self.close()

        del self

    def keyReleaseEvent(self, event):
        """ user presses button """
        pressed_key = event.key()

        if pressed_key == Qt.Key_Escape:
            self.close()

        event.accept()

    def close(self, *args, **kwargs):
        QMainWindow.close(self)

    def closeEvent(self, event) -> None:
        event.accept()
        self.unload(True)
