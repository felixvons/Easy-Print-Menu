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

import math
from pathlib import Path

from datetime import datetime

from PyQt5.QtGui import QColor, QFont

from qgis.core import (QgsProject, QgsPrintLayout, QgsUnitTypes,
                       QgsLayoutItemPage, QgsLayoutItem, QgsLayoutItemScaleBar,
                       QgsLayoutItemMap, QgsLayoutItemPicture, QgsLayoutItemLabel,
                       QgsLayoutItemLegend, QgsRuleBasedRenderer, QgsSymbol,
                       QgsVectorLayer, QgsWkbTypes, QgsLayerTreeLayer, QgsLayerTree,
                       QgsLegendModel, QgsLegendStyle, QgsMapLayer,
                       QgsLayoutPoint, QgsFeature, QgsLayerTreeGroup,
                       QgsLegendRenderer, QgsRectangle, QgsGeometry,
                       QgsLayoutItemPolyline, QgsLayoutItemShape,
                       QgsLayoutSize, QgsFillSymbol, QgsLayoutExporter, QgsRenderContext,
                       QgsLayoutRenderContext, QgsTask, Qgis, QgsApplication)

from typing import Dict, Tuple, Union, List

from .plot_layer import PlotLayer, PlotPage
from .plot_layout_templates import PlotLayoutTemplates
from ..template.gui.progressbar_extended import DoubleProgressGroup
from ..template.base_class import ModuleBase
from ...submodules.tools.geometrytools import polygon_to_rectangle


class PrintLayout(ModuleBase):
    """
        Class holds QGIS PrintLayout to print it later to pdf or add it to QGIS Project instance.
        Per default live rendering is disabled and must be called separately.
    """
    def __init__(self, plot_layer: PlotLayer, progress: DoubleProgressGroup,
                 layouts: PlotLayoutTemplates, auto_finish: bool = True, *args, **kwargs):

        ModuleBase.__init__(self, *args, **kwargs)

        self.__plot_layer = plot_layer
        self.__layouts = layouts
        self.__progress = progress

        assert self.plot_layer.get_next_page_number() > 1, self.tr_("No pages in Print Layer.")

        self.remove_legend_group()

        # initialize defaults and remove defaults first page
        self.layout: QgsPrintLayout = QgsPrintLayout(QgsProject.instance())
        self.layout.setName(self.plot_layer.name)
        self.layout.setUnits(QgsUnitTypes.LayoutMillimeters)
        self.layout.initializeDefaults()
        self.layout.pageCollection().clear()

        # page iterations
        max_normal_page_count = self.plot_layer.get_next_page_number() - 1
        main_count = max_normal_page_count
        # extra page "Übersicht"
        if self.plot_layer.create_overview_page:
            main_count += 1
        # extra page "Legend"
        if self.plot_layer.legend_on_extra_page:
            main_count += 1

        # placeholder value, to keep progressbar visible
        main_count += 1

        self.progress.get_mainbar().setMaximum(main_count)

        pages = {}

        # 1. overview page
        if self.plot_layer.create_overview_page:
            self.progress.set_text_main("Erstelle Übersichtsseite")
            self.progress.add_main(1)
            index, page, page_items = self.create_page(self.plot_layer.file)

            # delete legend
            item_id = self.layouts[self.plot_layer.file].id_item_legend
            if item_id in page_items:
                self.layout.removeLayoutItem(page_items[item_id])
                del page_items[item_id]

            # delete Mini Map
            item_id = self.layouts[self.plot_layer.file].id_item_minimap
            if item_id in page_items:
                self.layout.removeLayoutItem(page_items[item_id])
                del page_items[item_id]

            # set title
            item_id = self.layouts[self.plot_layer.file].id_item_title
            if item_id in page_items:
                page_items[item_id].setText(self.tr_("Overview"))

            feature = QgsFeature(self.plot_layer.layer_pages.fields())
            rectangle = self.plot_layer.layer_pages.dataProvider().extent().scaled(1.1)
            feature.setGeometry(QgsGeometry.fromRect(rectangle))
            self.setup_page(self.tr_("Overview"),
                            page_items,
                            self.plot_layer.file,
                            0,
                            feature,
                            self.plot_layer.visibility,
                            self.plot_layer.show_map_tips,
                            False,
                            None,
                            1)
            pages['overview'] = (index, None, page_items)

        # 2. legend page, Landscape!
        if self.plot_layer.legend_on_extra_page:
            self.progress.set_text_main(self.tr_("Creating extra legend page"))
            self.progress.add_main(1)
            # create legend layers
            layers = self.plot_layer.visibility.get_layers()
            layers = [layer for layer in layers if self.plot_layer.visibility.is_layer_visible_on_legend(layer)]
            self.create_legend_by_layers(layers)

            item_page = QgsLayoutItemPage(self.layout)
            item_page.setPageSize(self.layouts[self.plot_layer.file].get_page_size().name,
                                  QgsLayoutItemPage.Orientation(QgsLayoutItemPage.Landscape))
            self.layout.pageCollection().addPage(item_page)
            index = self.layout.pageCollection().pageCount() - 1

            columns = max([2, int(item_page.pageSize().width() / 65)])

            item_legend = QgsLayoutItemLegend(self.layout)
            self.layout.addLayoutItem(item_legend)
            item_legend.setStyleFont(QgsLegendStyle.Title, QFont('Arial', 12))
            item_legend.setStyleFont(QgsLegendStyle.Subgroup, QFont('Arial', 8))
            item_legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont('Arial', 8))
            item_legend.setBackgroundColor(QColor(255, 255, 255, 30))

            item_legend.setColumnCount(columns)

            position = QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters)  # top left corner
            item_legend.attemptMove(position, page=index)
            item_legend.setLinkedMap(None)
            self.configure_item_legend(item_legend, layers)
            pages['extra_legend'] = (index, None, {})

        # 3. pages
        for plot_page in self.plot_layer:
            self.progress.add_main(1)
            self.progress.set_text_main(f"{self.tr_('Creating')} {self.tr_('page')} {plot_page.page} / {max_normal_page_count}")
            index, page, page_items = self.create_page(plot_page.file)
            pages[plot_page.page] = (index, plot_page, page_items)

            if not plot_page.show_mini_map:
                # delete Mini Map
                item_id = self.layouts[plot_page.file].id_item_minimap
                if item_id in page_items:
                    self.layout.removeLayoutItem(page_items[item_id])
                    del page_items[item_id]

            self.setup_page(str(plot_page.page),
                            page_items,
                            plot_page.file,
                            plot_page.scale,
                            self.plot_layer.layer_pages.getFeature(plot_page.feature_id),
                            plot_page.visibility,
                            plot_page.show_map_tips,
                            plot_page.show_legend_on_page,
                            plot_page=plot_page)

            item_id = self.layouts[self.plot_layer.file].id_item_title
            if item_id in page_items:
                self.layout.removeLayoutItem(page_items[item_id])

        # finished
        if auto_finish:
            self.progress.restore()

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def create_page(self, file: str) -> Tuple[int, QgsLayoutItemPage, Dict[str, QgsLayoutItem]]:
        """ Creates a page.
            Most individual options per layout item will be copied to new layout item.

            :returns 0: page index
            :returns 1: page
            :returns 2: item dictionary of items with element id
        """
        layout = self.layouts[file]  # layout to use as new page
        item_page = QgsLayoutItemPage(self.layout)
        item_page.setPageSize(layout.page.pageSize())
        self.layout.pageCollection().addPage(item_page)
        index = self.layout.pageCollection().pageCount() - 1

        page_items = {}
        map_old_new = {}
        map_new_old = {}

        linked_maps = {}  # new item, old map
        self.progress.get_subbar().setValue(0)
        self.progress.get_subbar().setMinimum(0)
        self.progress.get_subbar().setMaximum(len(layout.item_list))

        for item in layout.item_list:

            if isinstance(item, QgsLayoutItemPage):
                continue

            self.progress.set_text_single(f"{type(item).__name__}(id: '{item.id()}', uuid: '{item.uuid()}')")
            self.progress.add_sub(1)

            new_item = self.copy_layout_item(item, self.layout, linked_maps)[0]
            new_item.setZValue(item.zValue())  # stacking/overlapping

            new_item.setReferencePoint(item.referencePoint())

            new_item.attemptMove(item.positionWithUnits(), page=index)
            new_item.attemptResize(item.sizeWithUnits())
            # new_item.setFixedSize(new_item.sizeWithUnits())

            # mappings
            map_old_new[item] = new_item
            map_new_old[new_item] = item

            if item.id():
                page_items[item.id()] = new_item
                new_item.setId(f"{item.id()}_p{index}")

        # load linked maps
        for new_item, old_map in linked_maps.items():
            new_item.setLinkedMap(map_old_new.get(old_map, None))

        return index, item_page, page_items

    def copy_layout_item(self, item: QgsLayoutItem, layout: QgsPrintLayout, linked_maps):

        new_item = type(item)(layout)
        layout.addLayoutItem(new_item)

        # copy default options to new item
        if hasattr(item, 'font'):
            # Font aufs neue Item übertragen
            new_item.setFont(item.font())

        # copy default options to new item
        if hasattr(item, 'linkedMap'):
            link = item.linkedMap()
            if link is not None:
                linked_maps[new_item] = link

        # take flags
        new_item.setFrameEnabled(item.frameEnabled())
        if new_item.frameEnabled():
            new_item.setFrameStrokeColor(item.frameStrokeColor())
            new_item.setFrameStrokeWidth(item.frameStrokeWidth())
        new_item.setBackgroundEnabled(item.hasBackground())
        if new_item.hasBackground():
            new_item.setBackgroundColor(item.backgroundColor())
        new_item.setItemRotation(item.itemRotation())
        new_item.setLocked(item.isLocked())
        new_item.setExcludeFromExports(item.excludeFromExports())

        # copy type specific options to new item
        if isinstance(new_item, QgsLayoutItemMap):
            # exportLayerDetails: not used, because it can be different between project files
            # exportLayerBehavior: not used, because it can be different between project files
            # mapRotation: every time north
            # setAtlasDriven: every time False, no Atlas support
            # setDrawAnnotations: maybe overwritten
            # dpi: will be set later
            # scale: will be set later
            # setExtent: will be set later
            new_item.setFrameStrokeWidth(item.frameStrokeWidth())
            new_item.setMapRotation(0)

            # if not set (setExtent), map will not be valid (containing nan-values)
            size = new_item.sizeWithUnits()  # old/copied size
            new_item.attemptResize(size)  # MUST HAVE, bad QGIS! 1. attemptResize
            new_item.setRect(item.rect()) # MUST HAVE, bad QGIS! 2. setRect
            new_item.setExtent(QgsRectangle(0.1, 0.1, 0.2, 0.2))  # MUST HAVE, bad QGIS! 3. setExtent
            new_item.setCrs(self.plot_layer.get_crs())
            new_item.setScale(500, True)

        if isinstance(new_item, QgsLayoutItemPicture):
            # setPicturePath: Use picture, if it is there
            # setSvgFillColor: not used
            # setSvgStrokeColor: not used
            # setSvgStrokeWidth: not used
            new_item.setMode(item.mode())
            if item.linkedMap() is not None:
                new_item.setNorthMode(item.northMode())
                new_item.setNorthOffset(item.northOffset())
            else:
                new_item.setPictureRotation(item.pictureRotation())
                new_item.setPictureAnchor(item.pictureAnchor())
            new_item.setResizeMode(item.resizeMode())
            picture_path = item.picturePath()
            if Path(picture_path).is_file():
                new_item.setPicturePath(picture_path)

        if isinstance(new_item, QgsLayoutItemLabel):
            new_item.setHAlign(item.hAlign())
            new_item.setVAlign(item.vAlign())
            new_item.setMarginX(item.marginX())
            new_item.setMarginY(item.marginY())
            new_item.setMode(item.mode())
            new_item.setText(item.text())

        if isinstance(new_item, QgsLayoutItemLegend):
            # exportLayerBehavior: not used
            new_item.setFontColor(item.fontColor())
            new_item.setLegendFilterByMapEnabled(item.legendFilterByMapEnabled())
            new_item.setLineSpacing(item.lineSpacing())
            new_item.setMaximumSymbolSize(item.maximumSymbolSize())
            new_item.setAutoUpdateModel(item.autoUpdateModel())
            new_item.setBoxSpace(item.boxSpace())
            new_item.setEqualColumnWidth(item.equalColumnWidth())
            new_item.setResizeToContents(item.resizeToContents())
            new_item.setSplitLayer(item.splitLayer())
            new_item.setSymbolAlignment(item.symbolAlignment())
            new_item.setSymbolHeight(item.symbolHeight())
            new_item.setSymbolWidth(item.symbolWidth())
            new_item.setTitle(item.title())
            new_item.setTitleAlignment(item.titleAlignment())
            new_item.setWmsLegendHeight(item.wmsLegendHeight())
            new_item.setWmsLegendWidth(item.wmsLegendWidth())
            new_item.setWrapString(item.wrapString())
            if item.drawRasterStroke():
                new_item.setDrawRasterStroke(True)
                new_item.setRasterStrokeColor(item.rasterStrokeColor())
                new_item.setRasterStrokeWidth(item.rasterStrokeWidth())

            # styles
            styles = [QgsLegendStyle.Title, QgsLegendStyle.Subgroup,
                      QgsLegendStyle.SymbolLabel, QgsLegendStyle.Symbol,
                      QgsLegendStyle.Group]
            for style in styles:
                new_item.setStyleFont(style, item.styleFont(style))
                new_item.setStyle(style, item.style(style))

        if isinstance(new_item, QgsLayoutItemScaleBar):
            new_item.setAlignment(item.alignment())
            symbol = item.alternateFillSymbol().clone()  # without clone, Qgis crash (object ownership)!
            new_item.setAlternateFillSymbol(symbol)

            new_item.setBoxContentSpace(item.boxContentSpace())

            symbol = item.divisionLineSymbol().clone()  # without clone, Qgis crash (object ownership)!
            new_item.setDivisionLineSymbol(symbol)

            symbol = item.fillSymbol().clone()  # without clone, Qgis crash (object ownership)!
            new_item.setFillSymbol(symbol)

            new_item.setHeight(item.height())
            new_item.setLabelBarSpace(item.labelBarSpace())
            new_item.setLabelHorizontalPlacement(item.labelHorizontalPlacement())
            new_item.setLabelVerticalPlacement(item.labelVerticalPlacement())

            symbol = item.lineSymbol().clone()  # without clone, Qgis crash (object ownership)!
            new_item.setLineSymbol(symbol)

            new_item.setMapUnitsPerScaleBarUnit(item.mapUnitsPerScaleBarUnit())
            new_item.setSegmentSizeMode(item.segmentSizeMode())
            new_item.setMaximumBarWidth(item.maximumBarWidth())
            new_item.setMinimumBarWidth(item.minimumBarWidth())
            new_item.setStyle(item.style())

            symbol = item.subdivisionLineSymbol().clone()  # without clone, Qgis crash (object ownership)!
            new_item.setSubdivisionLineSymbol(symbol)

            new_item.setSubdivisionsHeight(item.subdivisionsHeight())
            new_item.setTextFormat(item.textFormat())
            new_item.setUnitLabel(item.unitLabel())
            new_item.setUnits(item.units())
            new_item.setUnitsPerSegment(item.unitsPerSegment())

        if isinstance(new_item, QgsLayoutItemPolyline):
            new_item.setArrowHeadFillColor(item.arrowHeadFillColor())
            new_item.setArrowHeadStrokeColor(item.arrowHeadStrokeColor())
            new_item.setArrowHeadStrokeWidth(item.arrowHeadStrokeWidth())
            new_item.setArrowHeadWidth(item.arrowHeadWidth())
            new_item.setEndSvgMarkerPath(item.endSvgMarkerPath())
            new_item.setStartSvgMarkerPath(item.startSvgMarkerPath())
            new_item.setEndMarker(item.endMarker())
            new_item.setStartMarker(item.startMarker())
            new_item.setMinimumSize(item.minimumSize())

            symbol = item.symbol().clone()
            new_item.setSymbol(symbol)

            new_item.refresh()

        return new_item, linked_maps

    def remove_legend_group(self):
        """ Resets extra page legend from qgis project
        """
        # Entferne alle bestehenden Gruppen, wenn nicht umbenannt
        root = QgsProject.instance().layerTreeRoot()
        if root.findGroup(self.group_name):
            grp = root.findGroup(self.group_name)
            sub_layer_ids = grp.findLayerIds()
            QgsProject.instance().removeMapLayers(sub_layer_ids)
            root.removeChildNode(grp)

    def setup_page(self, page_str: str,
                   page_items: Dict[str, Union[QgsLayoutItem, QgsLayoutItemMap, QgsLayoutItemPicture,
                                               QgsLayoutItemLegend, QgsLayoutItemLabel]],
                   file: str,
                   scale: int,
                   feature: QgsFeature,
                   visibility,
                   show_map_tips,
                   show_legend_on_page,
                   plot_page: PlotPage = None,
                   page_type: int = 0):
        """ Setups the page with defined options in page (visibility etc.)

            page_type: 0=normal page, 1=overview, 2=legend page
        """
        layout = self.layouts[file]

        # crs name
        item_id = layout.id_item_crs
        if item_id in page_items:
            item_text_crs: QgsLayoutItemLabel = page_items[item_id]
            item_text_crs.setText(self.plot_layer.get_crs().authid())

        # page number
        item_id = layout.id_item_page_current
        if item_id in page_items:
            item_text_page_current: QgsLayoutItemLabel = page_items[item_id]
            item_text_page_current.setText(page_str)

        # max page number
        item_id = layout.id_item_page_max
        if item_id in page_items:
            item_text_page_max: QgsLayoutItemLabel = page_items[item_id]
            item_text_page_max.setText(str(self.plot_layer.get_next_page_number() - 1))

        # current date
        item_id = layout.id_item_date
        if item_id in page_items:
            item_text_date: QgsLayoutItemLabel = page_items[item_id]
            item_text_date.setText(datetime.now().strftime(getattr(layout, item_id).text()))

        # scale bar
        item_id = layout.id_item_map_scale_bar
        if item_id in page_items:
            item_scale_bar: QgsLayoutItemScaleBar = page_items[item_id]

        # north symbol / compass
        item_id = layout.id_item_map_rotation_icon
        if item_id in page_items:
            item_compass: QgsLayoutItemPicture = page_items[item_id]

        # company icon
        item_id = layout.id_item_company_icon
        if item_id in page_items:
            item_company_icon: QgsLayoutItemPicture = page_items[item_id]

        # item_map
        item_id = layout.id_item_map
        if item_id in page_items and visibility is not None:
            item_map: QgsLayoutItemMap = page_items[item_id]
            layer_pages = self.plot_layer.layer_pages

            # sort layers
            layers_to_use = []
            if page_type == 0:
                layers = visibility.get_layer_visibilities('page')
            elif page_type == 1:
                layers = [layer_pages] + visibility.get_layer_visibilities('overview')
            else:
                raise AssertionError(f"page_type {page_type} unknown")
            for layer in QgsProject.instance().layerTreeRoot().layerOrder():
                if layer in layers:
                    layers_to_use.append(layer)

            self.configure_map(item_map,
                               polygon_to_rectangle(feature.geometry()),
                               scale,
                               layers_to_use,
                               show_map_tips)
        else:
            item_map = None

        # item_minimap
        item_id = layout.id_item_minimap
        if item_id in page_items and visibility is not None and page_type == 0:
            item_minimap: QgsLayoutItemMap = page_items[item_id]
            layer_pages = self.plot_layer.layer_pages

            # sort layer visibilities
            layers_to_use = []
            layers = [layer_pages] + visibility.get_layer_visibilities('mini_map')
            for layer in QgsProject.instance().layerTreeRoot().layerOrder():
                if layer in layers:
                    layers_to_use.append(layer)

            rect: QgsRectangle = polygon_to_rectangle(feature.geometry())
            rect_scaled = rect.scaled(1.25)
            self.configure_map(item_minimap,
                               rect_scaled,
                               0,
                               layers_to_use,
                               show_map_tips)

            # a dirty trick to create a yellow rectangle on minimap
            shape = QgsLayoutItemShape(self.layout)
            shape.setReferencePoint(shape.Middle)
            shape.setId(f"marker_p{item_minimap.page()}")
            self.layout.addLayoutItem(shape)

            # create new symbol
            shape.setShapeType(shape.Rectangle)
            symbol: QgsFillSymbol = shape.symbol().clone()
            symbol.setOpacity(0.3)
            sym_layer = symbol.symbolLayer(0)
            sym_layer.setFillColor(QColor('yellow'))
            sym_layer.setStrokeColor(QColor('black'))
            properties = sym_layer.dataDefinedProperties()
            stroke_width = properties.property(sym_layer.PropertyStrokeWidth)
            stroke_width.setStaticValue(0)
            properties.setProperty(sym_layer.PropertyStrokeWidth, stroke_width)
            sym_layer.setDataDefinedProperties(properties)
            shape.setSymbol(symbol)

            # find position, use center from mini map
            point = item_minimap.positionAtReferencePoint(shape.Middle)
            layout_point = QgsLayoutPoint(point,
                                          QgsUnitTypes.LayoutMillimeters)
            size: QgsLayoutSize = shape.sizeWithUnits()
            size.setWidth(int(min(item_minimap.sizeWithUnits().height(),
                                  item_minimap.sizeWithUnits().width()) / 1.5))
            size.setHeight(int(min(item_minimap.sizeWithUnits().height(),
                                   item_minimap.sizeWithUnits().width()) / 1.5))
            shape.attemptResize(size)
            shape.attemptMove(layout_point)


        # item_legend
        item_id = layout.id_item_legend
        if item_id in page_items and visibility is not None:
            layers = visibility.get_layer_visibilities('legend')
            item_legend: QgsLayoutItemLegend = page_items[item_id]
            if show_legend_on_page:
                self.configure_item_legend(item_legend,
                                           layers)
                item_legend.setLegendFilterOutAtlas(True)
                item_legend.setLegendFilterByMapEnabled(True)
                self.remove_legend_entries(item_legend.model().rootGroup(), plot_page)

            if not layers or not show_legend_on_page:
                self.layout.removeLayoutItem(item_legend)

        # item_map_scale_text
        item_id = layout.id_item_map_scale_text
        if item_id in page_items:
            item_text_scale: QgsLayoutItemLabel = page_items[item_id]
            if scale > 0:
                item_text_scale.setText("1:" + str(int(scale)))
            elif item_map is not None and not math.isnan(item_map.scale()) and not math.isinf(item_map.scale()):
                item_text_scale.setText("1:" + str(int(item_map.scale())))
            else:
                item_text_scale.setText("ubk.")

        if plot_page is not None or page_type == 1:
            # load user individual texts to page
            layer_options = self.plot_layer.options
            if page_type == 0:
                page_options = plot_page.options
            elif page_type == 1:
                page_options = {}
            else:
                raise AssertionError(f"page_type {page_type} unknown")

            for item_id, global_value_pair in layer_options.items():

                page_value_pair = page_options.get(item_id, ("", False))
                value = page_value_pair[0]
                use_from_layer = not page_value_pair[1]

                if use_from_layer:
                    value = global_value_pair[0]

                if item_id in page_items:
                    item: QgsLayoutItemLabel = page_items[item_id]
                    item.setText(str(value))

    def configure_map(self, item_map: QgsLayoutItemMap, rectangle, scale: int,
                      layers: List[QgsMapLayer], annotations: bool):
        # if list is empty, each layer will be visible depending on qgis settings
        item_map.setLayers(layers)
        item_map.setKeepLayerSet(True)
        item_map.setKeepLayerStyles(True)
        item_map.zoomToExtent(rectangle)
        item_map.setDrawAnnotations(bool(annotations))

        if scale > 0:
            item_map.setScale(scale, True)

        item_map.setFrameEnabled(True)
        item_map.refresh()

    def configure_item_legend(self, item_legend, layers):
        """ Create layout item "QgsLayoutItemMap" per print page.

            Parameters: - item_legend -> QgsLayoutItemLegend
        """

        item_legend.setTitle("Legende")
        item_legend.setLocked(True)
        item_legend.setAutoUpdateModel(False)
        item_legend.setLegendFilterOutAtlas(False)
        item_legend.setLegendFilterByMapEnabled(False)
        item_legend.refresh()

        lm: QgsLegendModel = item_legend.model()
        lt: QgsLayerTree = lm.rootGroup()
        lt.removeChildrenPrivate(0, len(lt.children()))

        for layer in layers:
            lt.addLayer(layer)

    def remove_legend_entries(self, root, plot_page: PlotPage = None):
        """ Removes unchecked/invisible tree entries from legend.
            Search and remove is recursively.
        """
        children = root.children()
        for child in range(len(children) - 1, -1, -1):

            if not children[child].isVisible():
                # fully not visible child/tree item, remove it
                root.removeChildren(child, 1)

            elif isinstance(children[child], QgsLayerTreeGroup):
                # handle group item, remove group name from legend, but keep children
                QgsLegendRenderer.setNodeLegendStyle(children[child], QgsLegendStyle.Hidden)
                self.remove_legend_entries(children[child])  # go deeper, recursive

            elif isinstance(children[child], QgsLayerTreeLayer):
                # it is a layer,
                # if layer shot not be visible, remove it
                QgsLegendRenderer.setNodeLegendStyle(children[child], QgsLegendStyle.Hidden)
                if plot_page is not None:
                    if not plot_page.visibility.is_layer_visible_on_legend(children[child].layer()):
                        root.removeChildren(child, 1)

    def create_legend_by_layers(self, layers: list):
        """ Erstellt ein `QgsLayoutItemLegend` für eine allgemeine
            Legenden Übersicht im Druck.
            Primärschlüssel für Abgleich sind Legendenname des Symbols sowie ein einfacher dump-Wert

            Parameters: - layers - Liste von QgsVectorLayer für Legende

            Returns:    - legend layers - Liste von QgsVectorLayer'n mit Stil (nur Symbolosierung)
                        - layerTreeRoot-Group
        """
        proj_root = QgsProject.instance().layerTreeRoot()

        current_labelings = {l.id(): l.renderer().clone() for l in layers
                             if isinstance(l, QgsVectorLayer) and not l.renderer() is None}

        def new_renderer(renderer_: QgsRuleBasedRenderer):
            """ creates new renderer """

            if isinstance(renderer_, QgsRuleBasedRenderer):
                geometry_type = QgsWkbTypes.geometryType(QgsWkbTypes.NoGeometry)
                symbol = QgsSymbol.defaultSymbol(geometry_type)
                r = QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(symbol))
            else:
                r = renderer_.clone()

            return r

        empty_renderer = {l.id(): new_renderer(l.renderer()) for l in layers
                          if isinstance(l, QgsVectorLayer) and not l.renderer() is None}

        dumps = []

        def remove_invisible_childs(rule):
            """ inner-function
                Entfernt unsichtbare Punkte in aktuellem Baum (nicht rekursiv).
            """

            for c in rule.children():
                if not c.active():
                    # Children entfernen, wenn unsichtbar
                    rule.removeChild(c)

        def recursive_rule_adder(new, rule):
            """ inner-function
                Übernimmt Symbolisierungsregeln von alt zu neu,
                wenn diese Kinder oder ein Symbol besitzen.
            """

            remove_invisible_childs(rule)
            for child_rule in rule.children():
                remove_invisible_childs(child_rule)
                if len(child_rule.children()) == 0 and child_rule.symbol() is None:
                    # Keine Kinder mehr da ;( und ist KEIN Symbol
                    continue
                new_child = child_rule.clone()
                # Wird hinzugefügt, sonst wird nur gelöscht
                if not child_rule.symbol() is None:
                    new.insertChild(len(new.children()), new_child)
                recursive_rule_adder(new, child_rule)

        def remove_empty_childs(rule):
            """ inner-function
                Entfernt leere Punkte im Baum.
            """

            for child_rule in rule.children():

                remove_empty_childs(child_rule)
                if (len(child_rule.children()) == 0 and child_rule.symbol() is None) or not child_rule.active():
                    # Keine Kinder mehr da ;( und ist KEIN Symbol
                    rule.removeChild(child_rule)
                    continue

        def reduce_duplicated_symbols(rule):
            """ inner-function
                Entfernt doppelte Symbole.
                Als Schlüssel dienen hier Symbol-Titel sowie ein dump-Wert!
                    -> es sollte sichergestellt sein, dass der Titel in diesem
                       Layer einmalig ist!
            """
            for child in rule.children():
                label = child.label()
                symbol = child.symbol()
                if isinstance(symbol, QgsSymbol):
                    d = label + "//" + symbol.dump()

                    if d in dumps:
                        # Symbol entfernen, da bereits übernommen
                        rule.removeChild(child)
                        continue
                    else:
                        dumps.append(d)
                reduce_duplicated_symbols(child)

        # neue memory VectorLayer
        new_layers = []

        # Starte nun mit Übertragen der Symbole in rootRule
        for l_id, renderer in current_labelings.items():
            if proj_root.findLayer(l_id) is None:
                continue

            if not proj_root.findLayer(l_id).itemVisibilityChecked():
                continue

            layer = QgsProject.instance().mapLayer(l_id)
            # dumps der symbole je layer
            dumps.clear()

            new_renderer = empty_renderer[l_id]
            # Regelbasierten Renderer übernehmen
            if isinstance(new_renderer, QgsRuleBasedRenderer):
                root = renderer.rootRule()
                new_root = new_renderer.rootRule()

                # Übernehmen
                recursive_rule_adder(new_root, root)

                # Reduzieren (doppelte Icons)
                reduce_duplicated_symbols(new_root)

                # Leere Symboleinträge oder children löschen
                remove_empty_childs(new_root)

            name = layer.name()

            # Neuen Legend-Layer erstellen
            layer_type = QgsWkbTypes.displayString(layer.wkbType())  # Point, LineString, ...
            vector_layer = QgsVectorLayer("{}?crs=EPSG:4258".format(layer_type),
                                          "Legende - " + name,
                                          "memory")
            vector_layer.setRenderer(new_renderer)
            new_layers.append(vector_layer)

        new_layers = QgsProject.instance().addMapLayers(new_layers, False)

        # Erstelle Gruppe
        root = QgsProject.instance().layerTreeRoot()
        legend_group = root.insertGroup(0, self.group_name)
        for l in new_layers:
            tree = QgsLayerTreeLayer(l)
            legend_group.insertChildNode(-1, tree)

        return new_layers

    def add_to_instance(self):

        # removes existing layout
        manager = QgsProject.instance().layoutManager()
        for layout in manager.printLayouts():
            if layout.name() == self.plot_layer.name:
                manager.removeLayout(layout)
        manager.addLayout(self.layout)

    @property
    def group_name(self):
        return self.plot_layer.name + " (Legende)"

    def get_pdf_exporter(self):
        """ returns pdf exporter """
        exporter = QgsLayoutExporter(self.layout)
        settings = QgsLayoutExporter.PdfExportSettings()
        settings.dpi = self.plot_layer.dpi
        settings.simplifyGeometries = True
        settings.exportMetadata = False
        settings.forceVectorOutput = False
        if hasattr(settings, 'appendGeoreference'):
            settings.appendGeoreference = True
        if hasattr(settings, 'rasterizeWholeImage'):
            # Gekachelte Rasterlayerexporte abschalten, negierte GUI von QGIS, haken gesetzt, dann hier False
            settings.rasterizeWholeImage = False

        #if hasattr(settings, 'writeGeoPdf'):
        #    settings.writeGeoPdf = self.checkbox_as_geopdf.isChecked()
        #    if settings.writeGeoPdf:
        #        settings.includeGeoPdfFeatures = False
        #        settings.useIso32000ExtensionFormatGeoreferencing = True
        #        settings.useOgcBestPracticeFormatGeoreferencing  = False

        render_context = self.layout.renderContext()
        render_context.setDpi(settings.dpi)

        render_context.setFlag(QgsLayoutRenderContext.FlagAntialiasing, True)
        render_context.setFlag(QgsLayoutRenderContext.FlagDebug, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagDisableTiledRasterLayerRenders, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagDrawSelection, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagForceVectorOutput, True)
        render_context.setFlag(QgsLayoutRenderContext.FlagHideCoverageLayer, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagOutlineOnly, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagRenderLabelsByMapLayer, False)
        render_context.setFlag(QgsLayoutRenderContext.FlagUseAdvancedEffects, True)

        try:
            render_context.setTextRenderFormat(QgsRenderContext.TextFormatAlwaysText)
        except AttributeError as e:
            print("render_context TextRenderFormat gibt es in dieser QGIS Version nicht ;( -> ", str(e))
            pass
        try:
            # Render context Einstellungen ändern
            settings.textRenderFormat = QgsRenderContext.TextFormatAlwaysText
        except AttributeError as e:
            print("settings TextRenderFormat gibt es in dieser QGIS Version nicht ;( -> ", str(e))

        return exporter, settings

    def create_pdf(self, save_path: str, call_back=None):
        """ Exports generated layout to pdf

            :param save_path: pdf file path
            :param call_back: call back for save task (gets task as kwarg)
        """
        exporter, settings = self.get_pdf_exporter()
        task = TaskSavePdfLayout("TaskSavePdfLayout", self.layout, exporter, settings, save_path)
        if call_back:
            task.taskCompleted.connect(lambda: call_back(task=task))
            task.taskTerminated.connect(lambda: call_back(task=task))
        QgsApplication.taskManager().addTask(task)

    @property
    def plot_layer(self) -> PlotLayer:
        return self.__plot_layer

    @property
    def layouts(self) -> PlotLayoutTemplates:
        return self.__layouts

    @property
    def progress(self) -> DoubleProgressGroup:
        return self.__progress


class TaskSavePdfLayout(QgsTask):
    """ do not run to many tasks. QGIS do not like many tasks. """
    def __init__(self, description, layout: QgsPrintLayout, exporter: QgsLayoutExporter,
                 settings: QgsLayoutExporter.PdfExportSettings,
                 save_path: str):
        QgsTask.__init__(self, description)
        self.layout = layout
        self.exporter = exporter
        self.settings = settings
        self.save_path = save_path
        self.error = ""
        self.exception = None

    def run(self):

        QgsApplication.messageLog().logMessage(f"PDF-Druck '{self.save_path}' gestartet", "TaskSaveLayout", Qgis.Info)

        result = self.exporter.exportToPdf(self.save_path, self.settings)
        if result != self.exporter.Success:
            code = {
                self.exporter.Canceled: "Canceled",
                self.exporter.FileError: "FileError",
                self.exporter.IteratorError: "IteratorError",
                self.exporter.MemoryError: "MemoryError",
                self.exporter.PrintError: "PrintError",
                self.exporter.SvgLayerError: "SvgLayerError",
            }
            error = f"PDF konnte nicht erzeugt werden, QGIS Fehler-Code: {result} ({code[result]})"
            QgsApplication.messageLog().logMessage(f"PDF-Druck auf Fehler gelaufen: {error}",
                                                   "TaskSaveLayout",
                                                   Qgis.Info)
            self.error = error
            return False

        QgsApplication.messageLog().logMessage('beendet', "TaskSaveLayout", Qgis.Info)
        self.setProgress(100)
        return True

    def finished(self, result):
        QgsApplication.messageLog().logMessage(f'finished result: {result}', "TaskSaveLayout", Qgis.Info)

    def cancel(self):
        QgsApplication.messageLog().logMessage('TaskReadTemplates cancel', "TaskSaveLayout", Qgis.Critical)
