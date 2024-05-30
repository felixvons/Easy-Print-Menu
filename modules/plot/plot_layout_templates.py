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
from pathlib import Path

import xml.etree.ElementTree as ET

from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (QgsPrintLayout, QgsProject, QgsReadWriteContext,
                       QgsApplication, QgsPointXY, QgsRectangle)
from typing import Dict


from .plot_layout import PlotLayout
from ..template.base_class import ModuleBase
from ..template.gui.progressbar_extended import DoubleProgressGroup
from ...submodules.tools.path import get_files


class PlotLayoutTemplates(ModuleBase):
    """ Containing all configured layout files from QGIS.
        Must defined in templates/plots/xx/plots.xml.

        get layout from file: PlotLayoutTemplates["plots/xasd.qpt"]
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # default own plugin layouts
        # try to find layouts in qgis profile path
        # https://github.com/qgis/QGIS/search?q=composer_templates
        self.plots = [self.get_plugin().plots_dir,
                      QgsApplication.instance().qgisSettingsDirPath() + "/composer_templates"]
        self.plots.extend(QgsApplication.instance().layoutTemplatePaths())
        plot_files = []
        packets = []
        for path in self.plots:
            plot_files.extend(f for f in get_files(path) if f.lower().endswith("plots.xml"))

        if not plot_files:
            raise ValueError(f"no xml files found in {self.plots}")

        with open(plot_files[0], "r", encoding="utf-8") as file:
            fp = str(Path(plot_files[0]).parent.parent).replace("\\", "/")
            self.xml = ET.parse(file)
            for child in list(self.xml.getroot()):
                child.attrib["filename"] = child.attrib["file"]
                child.attrib["file"] = fp + "/" + child.attrib["file"].replace("\\", "/")

                if child.attrib["filename"] in packets:
                    raise ValueError(f"{child.attrib['filename']} alreade loaded")

                packets.append(child.attrib["filename"])

        for path in plot_files[1:]:
            fp = str(Path(path).parent.parent).replace("\\", "/")
            with open(path, "r", encoding="utf-8") as file:
                for child in list(ET.parse(file).getroot()):
                    child.attrib["filename"] = child.attrib["file"]
                    child.attrib["file"] = fp + "/" + child.attrib["file"].replace("\\", "/")
                    self.xml.getroot().append(child)

                    if child.attrib["filename"] in packets:
                        raise ValueError(f"{child.attrib['filename']} alreade loaded")

                    packets.append(child.attrib["filename"])

        self.__layouts: Dict[str, PlotLayout] = {}

    def get_orientation(self, file: str):
        """ returns Qgis page orientation

            :param file: file
        """
        layout = self.__layouts[file]
        page = layout.page
        return page.orientation()

    def get_layout_extent(self, file: str, center: QgsPointXY, scale: int, rotation: float) -> QgsRectangle:
        """ Returns extent with given center and scale from layout

            :param file: file
            :param center: center of rectangle/extent (e.g. mouse position on plot layer
            :param scale: map scale
        """
        item_map = self.__layouts[file].item_map

        x_center = center.x()
        y_center = center.y()

        x_low = x_center - (x_center / 100)
        x_high = x_center + (x_center / 100)

        y_low = y_center - (y_center / 100)
        y_high = y_center + (y_center / 100)

        rectangle = QgsRectangle(x_low, y_low, x_high, y_high)
        item_map.zoomToExtent(rectangle)
        item_map.setScale(scale)
        item_map.setMapRotation(rotation)

        return item_map.extent()

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def load_layouts(self):
        """ loads templates into local dictionary. """

        packets = [x for x in self.xml.getroot()]
        count = len(packets)

        progress: DoubleProgressGroup = getattr(self.get_parent(), "progress", None)
        progress.start_progressbars(0, count, use_subbar=False,
                                    can_cancel=False, hide_widgets=[self.get_parent().ScrollArea])

        progress.get_mainbar().setValue(0)
        progress.get_mainbar().setMaximum(count)

        for item in packets:
            # xml child from plots.xml
            name = item.get('name')
            filename = item.get('filename')
            path = item.get('file')
            group = item.get('group')
            project = QgsProject.instance()
            layout = QgsPrintLayout(project)
            document = QDomDocument()

            progress.set_text_main(self.tr_('Loading') + " " + self.tr_('Template') + f" '{filename}'")
            progress.add_main(1)

            with open(path, "rt") as file:
                # reads qpt template file
                document.setContent(file.read(), False)

            item_list = layout.loadFromTemplate(document, QgsReadWriteContext())[0]
            plot_layout = PlotLayout(name, filename, group, layout, item_list, xml=item, filepath=path)
            plot_layout.set_parent(self)
            self.__layouts[filename] = plot_layout

    @property
    def layouts(self):
        return self.__layouts.values()

    def __getitem__(self, item) -> PlotLayout:
        return self.__layouts[item]

    def __iter__(self):
        """ you can iterate over this object """
        for layout in self.__layouts.values():
            yield layout
