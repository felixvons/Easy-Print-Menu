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

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent
from qgis.core import (QgsVectorLayer, Qgis, QgsRectangle,
                       QgsPointXY, QgsGeometry, QgsProject,
                       QgsApplication)
from qgis.gui import QgisInterface, QgsMapCanvas, QgsMapTool, QgsRubberBand

from .plot_layer import PlotLayer, PlotPage
from .plot_layout import PlotLayout

from ...submodules.tools.geometrytools import transform_geometry


class PlotPageMapTool(QgsMapTool):
    """ Map Tool to add new Pages to PlotLayer.
        Item_map and target_crs and scale working together to calculate correct page size in given crs.

        :param iface: qgis interface with map canvas
        :param previous_map_tool: tool to restore
        :param layout: layout for this new page
        :param scale: map scale to use
        :param plot_layer: PlotLayer
        :param drawings: drawings
    """
    pageAdded = pyqtSignal(PlotPage, name="pageAdded")
    finished = pyqtSignal(name="finished")

    def __init__(self, iface: QgisInterface,
                 previous_map_tool: QgsMapTool,
                 layout: PlotLayout,
                 scale: int,
                 plot_layer: PlotLayer,
                 drawings: list = []):
        self.canvas: QgsMapCanvas = iface.mapCanvas()
        QgsMapTool.__init__(self, self.canvas)

        self.layout = layout
        self.iface = iface
        self.item_map = self.layout.item_map
        self.previous_map_tool = previous_map_tool
        self.plot_layer = plot_layer
        layer = self.plot_layer.layer_pages
        self.crs = layer.dataProvider().crs()
        del layer
        self.layer = QgsVectorLayer(f"Point?crs={self.crs.authid()}", "dummy", "memory")

        self.drawings = drawings
        self.canvas_item: QgsRubberBand = None
        self.scale = scale

        self.item_map.setScale(scale)
        self.item_map.setCrs(self.crs)

        self.iface.messageBar().pushMessage(
            self.tr_('Hint'),
            self.tr_("Left mouse button click on canvas to add new pages. Right mouse button click to finish/cancel map tool."),
            level=Qgis.Info,
            duration=10
        )

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def canvasMoveEvent(self, event):
        """
        QgsMapTool Funktion. Verschiebt ein Rechteck mit
        auf der Karte, wo sich die Maus so lang bewegt.
        """
        center: QgsPointXY = self.toLayerCoordinates(self.layer,
                                                     self.toMapCoordinates(event.pos()))
        if self.canvas_item is None:
            self.canvas_item = QgsRubberBand(self.iface.mapCanvas(), False)
            self.drawings.append(self.canvas_item)

        rectangle: QgsRectangle = self.layout.get_parent().get_layout_extent(self.layout.path,
                                                                             center,
                                                                             self.scale)

        # Setze Geometrie
        self.canvas_item.reset()
        geometry = QgsGeometry.fromRect(rectangle)
        geometry = transform_geometry(geometry, self.crs, QgsProject.instance().crs())
        self.canvas_item.setToGeometry(geometry, None) # Bewegt sich mit Maus mit
        self.canvas_item.setColor(QColor(123, 50, 75, 128))
        self.canvas_item.setWidth(9)
        self.canvas_item.updateCanvas()

    def canvasReleaseEvent(self, event: QMouseEvent):
        btn = event.button()
        if btn != Qt.LeftButton:
            self.iface.mapCanvas().setMapTool(self.previous_map_tool)
            self.iface.mapCanvas().unsetMapTool(self)
            self.iface.messageBar().pushMessage(
                self.tr_('Hint'),
                self.tr_('Finished'),
                level=Qgis.Info,
                duration=5
            )
            if self.canvas_item:
                self.iface.mapCanvas().scene().removeItem(self.canvas_item)
            self.finished.emit()
            return

        # holt die Koordinaten der Maus aus dem PlotLayer
        center: QgsPointXY = self.toLayerCoordinates(self.layer, event.pos())
        rectangle: QgsRectangle = self.layout.get_parent().get_layout_extent(self.layout.path,
                                                                             center,
                                                                             self.scale)
        rect_geom = QgsGeometry.fromRect(rectangle)

        page = self.plot_layer.add_page(self.layout, rect_geom, self.scale)

        self.pageAdded.emit(page)
