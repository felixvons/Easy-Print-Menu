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
import traceback

import importlib

from pathlib import Path

from qgis.core import (QgsProject, QgsMapLayer, QgsVectorLayer,
                       QgsLayoutSize, QgsLayoutItemPage,
                       QgsLayoutItemLabel, QgsLayoutItemPicture,
                       QgsCoordinateReferenceSystem, QgsGeometry,
                       QgsApplication)

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QMainWindow, QApplication, QListWidgetItem,
                             QCheckBox, QFileDialog, QMessageBox)

from typing import Callable, Optional, List, Union

from ..template.base_class import UiModuleBase, ModuleBase
from ..template.gui.progressbar_extended import DoubleProgressGroup
from ...submodules.tools.qt_functions import set_label_status
from ...submodules.tools._qt_constants import STYLE_SHEET_ERROR, STYLE_SHEET_WARNING
from ...submodules.tools.geometrytools import transform_geometry
from .plot_new_layout import PlotNewLayout
from .plot_layer import PlotLayer, PlotPage
from .plot_layout import PlotLayout
from .plot_layout_templates import PlotLayoutTemplates
from .plot_layout_menu import PlotLayoutMenu
from .plot import PrintLayout, TaskSavePdfLayout
from .plot_overview import PlotOverviewRectangles

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class PlotMenu(UiModuleBase, FORM_CLASS, QMainWindow):
    """ Main Plot Menu, inheriting other plot modules.
    """

    def __init__(self, parent_module: Optional['ModuleBase'] = None, module_name: str = '',
                 log: Optional[Callable] = None, **kwargs: dict):

        UiModuleBase.__init__(self, parent_module, module_name, log, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent', None))

        self.setupUi(self)
        self.global_layout_menu = None
        self.plot_layer = None
        self.page_layout_menu = None
        self.iface = self.get_parent_plugin().iface
        icon = QIcon(self.get_parent_plugin().get_icon_path("printer_graphical.png"))
        self.setWindowIcon(icon)
        self.But_Create_PDF.setIcon(icon)

        icon = QIcon(self.get_parent_plugin().get_icon_path("map_view.png"))
        self.But_CreateOverview.setIcon(icon)

        icon = QIcon(self.get_parent_plugin().get_icon_path("plus_graphical_256.png"))
        self.But_AddPage.setIcon(icon)
        self.But_AddPage.setIconSize(QSize(32, 32))
        self.But_AddPage.setText("")
        icon_portrait = QIcon(self.get_parent_plugin().get_icon_path("add_page_portrait.png"))
        self.But_AddPage_Portrait.setIcon(icon_portrait)
        self.But_AddPage_Portrait.setIconSize(QSize(32, 32))
        icon_landscape = QIcon(self.get_parent_plugin().get_icon_path("add_page_landscape.png"))
        self.But_AddPage_Landscape.setIcon(icon_landscape)
        self.But_AddPage_Landscape.setIconSize(QSize(32, 32))

        icon = QIcon(self.get_parent_plugin().get_icon_path("decrease_graphical_256.png"))
        self.But_DeletePage.setIcon(icon)
        self.But_DeletePage.setIconSize(QSize(32, 32))
        self.But_DeletePage.setText("")

        # add ui modules
        self.progress: DoubleProgressGroup = self.add_ui_module("DoubleProgressGroup",
                                                                self.Frame_Progress,
                                                                DoubleProgressGroup)
        self.progress.hide()
        self.progress.Group_Progress.setTitle(self.tr_("Progress-Container"))
        self.List_Pages.setDragEnabled(True)
        self.List_Pages.setAcceptDrops(True)

        # add some Qt connections
        self.connect(self.But_NewLayout.clicked, self.add_new_layout)
        self.connect(self.But_Create_PDF.clicked, self.create_pdf)
        self.connect(self.But_AddFile.clicked, self.add_file)
        self.connect(self.But_Create_PrintLayout.clicked, self.create_qgs_print_layout)
        self.connect(self.But_AddPage.clicked, self.add_new_page)
        self.connect(self.But_AddPage_Portrait.clicked, self.add_new_page_portrait)
        self.connect(self.But_AddPage_Landscape.clicked, self.add_new_page_landscape)
        self.connect(self.But_CreateOverview.clicked, self.add_over_view_pages)
        self.connect(self.But_DeletePage.clicked, self.delete_page)
        self.connect(self.DrD_PrintLayoutsGpkg.currentIndexChanged, self.layout_selected)
        self.connect(QgsProject.instance().layersAdded, self.layers_added)
        self.connect(QgsProject.instance().legendLayersAdded, self.layers_added)
        self.connect(QgsProject.instance().layersRemoved, self.layers_removed)
        self.connect(self.SpinBox_Dpi.valueChanged, self.dpi_changed)
        self.connect(self.SpinBox_Scale.valueChanged, self.scale_changed)
        self.SpinBox_Page_Scale.setValue(self.SpinBox_Scale.value())
        self.connect(self.List_Pages.model().rowsMoved, self.page_moved)
        self.connect(self.List_Pages.itemDoubleClicked, self.open_page_item)
        self.connect(self.List_Pages.currentItemChanged, self.page_item_changed)
        self.connect(self.CheckBox_Legend_Extra.stateChanged,
                     lambda x: self.check_box_state_changed(self.CheckBox_Legend_Extra))
        self.connect(self.CheckBox_Overview.stateChanged,
                     lambda x: self.check_box_state_changed(self.CheckBox_Overview))

        # other Qt Connections
        self.connect(self.get_parent_plugin().versionRead,
                     lambda plugin: self.set_ui_version_info(self.Label_Version_Nr))

        self.layouts: PlotLayoutTemplates = self.add_module("PlotLayoutTemplates", PlotLayoutTemplates)

        # load existing plot layers to drd
        self.DrD_PrintLayoutsGpkg.clear()
        self.DrD_PrintLayoutsGpkg.addItem(f"-- {self.tr_('choose or create')} --", None)
        self.layers_added(QgsProject.instance().mapLayers().values())

        self.page_item_changed(None, None)

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def keyReleaseEvent(self, event):
        """user presses button"""
        pressed_key = event.key()
        if pressed_key == Qt.Key_F5:
            self.global_layout_menu.key_f5_reset()
            self.reload_pages()

        if pressed_key == Qt.Key_Escape:
            self.close()

        event.accept()

    def create_qgs_print_layout(self, checked: bool):
        """ creates new QgsPrintLayout in QgsProject """
        self.progress.start_progressbars(0, 100, hide_widgets=[self.ScrollArea])
        try:
            layout = self.add_module("PrintLayout", PrintLayout,
                                     plot_layer=self.plot_layer, progress=self.progress, layouts=self.layouts)
            layout.add_to_instance()
            layout.unload(True)
        except AssertionError as e:
            self.progress.restore()
            set_label_status(self.Label_Status, str(e), STYLE_SHEET_ERROR)

    def create_pdf(self, checked: bool):
        """ creates new QgsPrintLayout in QgsProject """

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr_("Save file"),
            os.path.join(QgsProject.instance().absolutePath(),
                         self.plot_layer.source.replace(".gpkg", ".pdf")),
            'PDF (*.pdf)'
        )
        if not save_path:
            return

        self.progress.start_progressbars(0, 100, hide_widgets=[self.ScrollArea])
        try:
            layout: PrintLayout = self.add_module("PrintLayout", PrintLayout,
                                                  plot_layer=self.plot_layer, progress=self.progress,
                                                  layouts=self.layouts,
                                                  auto_finish=False)
            bar = self.progress.get_mainbar()
            bar.setMaximum(bar.maximum() + 1)
            self.progress.set_text_main(self.tr_("PDF will be saved. Please wait."))
            self.progress.add_main(1)

            self.progress.get_subbar().setValue(0)
            self.progress.get_subbar().setMaximum(101)
        except AssertionError as e:
            self.progress.restore()
            set_label_status(self.Label_Status, str(e), STYLE_SHEET_ERROR)
            self.iface.messageBar().pushWarning(self.tr_("Print Menu"), str(e))

            if "FileError" in str(e) and Path(save_path).is_file():
                QMessageBox.warning(self.iface.mainWindow(),
                                    self._tr("Error"),
                                    self.tr_("File %s could not be saved. "
                                             "Please close needed applications.") % save_path)
            return

        # Zeit schinden für den Ladebalken!!
        for _ in range(100):
            self.progress.set_text_single(self.tr_("Preparing writing PDF %s.\n"
                                                   " Depending on your layers, network connection, layout size "
                                                   "and more this process can take a moment.") % save_path)
            self.progress.add_sub(1)

        layout.create_pdf(save_path, self.create_pdf_callback)
        QgsProject.instance().removeMapLayers([layer.id()
                                               for layer in layout.legend_layers])
        layout.remove_legend_group()
        layout.unload(True)
        self.progress.set_text_single(self.tr_("Writing PDF %s. "
                                               "Writing in seperate QGIS Task. "
                                               "This can take a moment.") % save_path)
        self.progress.add_sub(1)

    def create_pdf_callback(self, task: TaskSavePdfLayout):
        self.progress.restore()
        if not task.error:
            self.iface.messageBar().pushSuccess(self.tr_("Print Menu"), self.tr_("PDF print finished without errors."))
            QMessageBox.information(self.iface.mainWindow(),
                                    self.tr_("Print Menu"),
                                    self.tr_("PDF print finished without errors."))
        else:
            self.iface.messageBar().pushWarning(self.tr_("Error"), self.tr_("PDF print finished with errors."))
            QMessageBox.warning(self.iface.mainWindow(),
                                self.tr_("Error"),
                                str(task.error))

    def delete_page(self, checked: bool):
        """ deletes a page from plot layer """
        item: QListWidgetItem = self.List_Pages.currentItem()
        row = self.List_Pages.currentRow()

        if not item:
            return

        page: PlotPage = self.plot_layer.get_page_from_fid(item.data(Qt.UserRole))
        page.delete()
        self.reload_pages()

        if row > self.List_Pages.count() - 1:
            self.List_Pages.setCurrentRow(row - 1)
        else:
            self.List_Pages.setCurrentRow(row)

    def add_new_page_landscape(self, checked: bool, bring_to_front: bool = True):

        for row in range(self.DrD_Page_Templates.count()):
            layout = self.DrD_Page_Templates.itemData(row, Qt.UserRole)
            if layout is not None:
                if layout.page.orientation() == QgsLayoutItemPage.Landscape:
                    self.DrD_Page_Templates.setCurrentIndex(row)
                    self.add_new_page(True, bring_to_front=bring_to_front)
                    break
        else:
            set_label_status(self.Label_Status,
                             self.tr_("Something went wrong. No landscape layout found."))

    def add_new_page_portrait(self, checked: bool, bring_to_front: bool = True):

        for row in range(self.DrD_Page_Templates.count()):
            layout = self.DrD_Page_Templates.itemData(row, Qt.UserRole)
            if layout is not None:
                if layout.page.orientation() == QgsLayoutItemPage.Portrait:
                    self.DrD_Page_Templates.setCurrentIndex(row)
                    self.add_new_page(True, bring_to_front=bring_to_front)
                    break
        else:
            set_label_status(self.Label_Status,
                             self.tr_("Something went wrong. No portrait layout found."))

    def add_new_page(self, checked: bool, bring_to_front: bool = True):
        """ Activates map tool to create new pages """
        from .plot_map_tool import PlotPageMapTool
        layout: PlotLayout = self.DrD_Page_Templates.currentData()

        if self.DrD_Page_Templates.count() < 0:
            raise ValueError("no layouts found")

        # nothing selected in combobox
        # select matching layout from plot layer and call it again
        if layout is None:
            file = self.plot_layer.file
            self.select_page_layout_template(file)

            self.add_new_page(checked)
            return

        scale = self.SpinBox_Page_Scale.value()

        iface = self.get_plugin().iface
        self.initialize_defaults(self.plot_layer, layout)

        map_tool = PlotPageMapTool(iface,
                                   iface.mapCanvas().mapTool(),
                                   layout,
                                   scale,
                                   self.plot_layer,
                                   drawings=self.get_plugin().drawings)
        map_tool.pageAdded.connect(lambda x=0: self.reload_pages())
        if bring_to_front:
            map_tool.finished.connect(lambda x=0: self.show())
        self.get_plugin().iface.mapCanvas().setMapTool(map_tool)
        self.close()

    def select_page_layout_template(self, file: str):
        """ selects given file in page layout dropdown or the first item, if not found """

        for row in range(self.DrD_Page_Templates.count()):
            layout: PlotLayout = self.DrD_Page_Templates.itemData(row, Qt.UserRole)
            if layout.path.endswith(file):
                self.DrD_Page_Templates.setCurrentIndex(row)
                break
        else:
            self.DrD_Page_Templates.setCurrentIndex(0)
            self.log(f"{file} not found in dropdown layouts")

    def page_item_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        """ Current page Item changed """
        item: QListWidgetItem = self.List_Pages.currentItem()
        if item is None:
            self.Frame_DeletePage.hide()
            if self.plot_layer is not None:
                self.plot_layer.select_feature(None)
            return

        if self.plot_layer is not None:
            self.plot_layer.select_feature(item.data(Qt.UserRole))
        self.Frame_DeletePage.show()

    def check_box_state_changed(self, box: QCheckBox):
        if box is self.CheckBox_Legend_Extra:
            # save state for extra legend
            self.plot_layer.legend_on_extra_page = Qt.Checked == self.CheckBox_Legend_Extra.checkState()

        if box is self.CheckBox_Overview:
            # save state for overview page
            self.plot_layer.create_overview_page = Qt.Checked == self.CheckBox_Overview.checkState()

    def page_moved(self, *args, **kwargs):
        """ internal page moved """
        for row in range(self.List_Pages.count()):
            page: PlotPage = self.plot_layer.get_page_from_fid(self.List_Pages.item(row).data(Qt.UserRole))
            page.page = row + 1

        self.reload_pages()
        self.plot_layer.layer_pages.triggerRepaint()

    def open_page_item(self, current):
        """ current page item changed """

        item: QListWidgetItem = self.List_Pages.currentItem()
        if item is None or item is not current:
            return

        fid: int = current.data(Qt.UserRole)
        page: PlotPage = self.plot_layer.get_page_from_fid(fid)
        layout = self.layouts[page.file]

        self.page_layout_menu = self.add_module("PagePlotLayoutMenu",
                                                PlotLayoutMenu,
                                                parent=self,
                                                plot_layout=layout,
                                                plot_layer=self.plot_layer,
                                                edit=page)
        self.page_layout_menu.show()
        self.page_layout_menu.setWindowTitle(item.text())
        self.page_layout_menu.setWindowModality(Qt.WindowModal)

    def initialize_defaults(self, plot_layer: PlotLayer, layout: PlotLayout = None):
        """ loads defaults into PlotLayer """
        options = plot_layer.options
        if layout is None:
            layout = self.layouts[plot_layer.file]

        for item_id, value_pair in layout.defaults.items():
            type_, value = value_pair

            current_value = options.get(item_id, ("", False))[0]
            if current_value:
                continue

            value_to_set = ""
            item = layout.layout.itemById(item_id)
            if type_ == "function":
                # call something from defined function with importlib
                try:
                    path = Path(self.get_parent_plugin().plugin_dir)
                    if path.name == "":
                        path = path.parent
                    parents = []
                    while path.name != "plugins":
                        parents.append(path.name)
                        path = path.parent
                    parents = ".".join(reversed(parents))
                    import_path = f"{parents}.templates.plots.{value}"

                    *import_path, attribute = import_path.split(".")
                    module = importlib.import_module(".".join(import_path))
                    value_to_set = getattr(module, attribute)(self.get_parent_plugin(), layout, item)
                except:
                    self.log(str(traceback.format_exc()), "plot-function-call")
                    value_to_set = ""
                assert isinstance(value_to_set, str), f"returned value from plot_functions.{value} is not a string, " \
                                                      f"got '{value_to_set}' with type {type(value_to_set)}"

            if type_ == "value":
                value_to_set = value

            if item is not None and value_to_set is not None:
                if isinstance(item, QgsLayoutItemLabel):
                    # item.setText(value_to_set)
                    options[item_id] = (value_to_set, False)
        plot_layer.options = options

        # load icons, e.g. company icon
        for item_id, icon_str in layout.icons.items():
            item = layout.layout.itemById(item_id)

            if isinstance(item, QgsLayoutItemPicture):
                if not icon_str:
                    icon = ""
                else:
                    icon = self.get_parent_plugin().get_icon_path(icon_str)

                item.setPicturePath(icon)

    def load_page_templates(self, selected_layout: PlotLayout):
        """ something to setup later, after module has been fully loaded """

        def is_layout_loadable(l: PlotLayout):
            """ Checks, if given layout size equals to selected layout size.
                Sizes are checked with swapped size values.

            """
            size: QgsLayoutSize = l.page.pageSize()
            size_swapped = QgsLayoutSize(size.height(), size.width(), size.units())

            if selected_layout.group != l.group and selected_layout.group:
                # only layouts with same group name or empty group name
                return False

            if selected_layout.page.pageSize() == size or selected_layout.page.pageSize() == size_swapped:
                return True

            return False

        # loads available print templates to dropdown
        self.DrD_Page_Templates.clear()
        self.GroupBox_Template.show()
        self.But_AddPage.show()
        self.But_AddPage_Portrait.hide()
        self.But_AddPage_Landscape.hide()
        count_landscape = 0
        count_portrait = 0
        for i, layout in enumerate(self.layouts):

            if is_layout_loadable(layout):
                if layout.group:
                    self.DrD_Page_Templates.addItem(f"{layout.name} [{layout.group}]", layout)
                else:
                    self.DrD_Page_Templates.addItem(f"{layout.name}", layout)

                orientation = layout.page.orientation()
                if orientation == QgsLayoutItemPage.Landscape:
                    count_landscape += 1
                if orientation == QgsLayoutItemPage.Portrait:
                    count_portrait += 1

        self.select_page_layout_template(selected_layout.path)

        if count_portrait == 1 and count_landscape == 1:
            # hides normal page add button when only 1 portrait page and only 1 landscape page is there
            self.GroupBox_Template.hide()
            self.But_AddPage.hide()
            self.But_AddPage_Portrait.show()
            self.But_AddPage_Landscape.show()

            self.add_action(
                f"{self.tr_('Add new page (portrait)')} - {self.plot_layer.layer_pages.name()}",
                QIcon(self.get_parent_plugin().get_icon_path("add_page_portrait.png")),
                True,
                lambda x=0: self.add_new_page_portrait(True, False),
                False,
                "telekom_plot",
                self.tr_("Print Menu"),
                False,
                True,
                self.iface.mainWindow()
            )

            self.add_action(
                f"{self.tr_('Add new page (landscape)')} - {self.plot_layer.layer_pages.name()}",
                QIcon(self.get_parent_plugin().get_icon_path("add_page_landscape.png")),
                True,
                lambda x=0: self.add_new_page_landscape(True, False),
                False,
                "telekom_plot",
                self.tr_("Print Menu"),
                False,
                True,
                self.iface.mainWindow()
            )

    def dpi_changed(self, value: int):
        self.global_layout_menu.plot_layer.dpi = value

    def scale_changed(self, value: int):
        self.global_layout_menu.plot_layer.scale = value
        self.SpinBox_Page_Scale.setValue(value)

    def get_layer_index(self, layer: Union[str, QgsMapLayer]):
        """ returns index from layer in dropdown, if layer is already in dropdown
            Defaults to -1.

        """
        for row in range(self.DrD_PrintLayoutsGpkg.count()):
            data = self.DrD_PrintLayoutsGpkg.itemData(row, Qt.UserRole)

            if isinstance(layer, QgsVectorLayer):
                if data == layer.id():
                    return row
            elif isinstance(layer, str):
                if data == layer:
                    return row

        return -1

    def layers_removed(self, layers: List[str]):
        """ removes dropdown items """
        for layer_id in layers:
            index = self.get_layer_index(layer_id)
            if index > -1:
                if index == self.DrD_PrintLayoutsGpkg.currentIndex():
                    # need to do, because upcoming plot layout menus
                    self.DrD_PrintLayoutsGpkg.setCurrentIndex(0)
                self.DrD_PrintLayoutsGpkg.removeItem(index)

        if self.global_layout_menu is not None:
            self.global_layout_menu.reset_layer_view()

    def layers_added(self, layers: List[QgsMapLayer]):
        """ adds layers to dropdown """
        for layer in layers:
            index = self.get_layer_index(layer)
            is_vector = isinstance(layer, QgsVectorLayer)
            is_plot = PlotLayer.is_plot_layer(layer)

            if index == -1 and is_vector and is_plot:
                self.DrD_PrintLayoutsGpkg.addItem(layer.name(), layer.id())

        if self.global_layout_menu is not None:
            self.global_layout_menu.reset_layer_view()

    def set_layer(self, layer: QgsVectorLayer):
        index = self.get_layer_index(layer)
        self.DrD_PrintLayoutsGpkg.setCurrentIndex(index)

    def layout_selected(self, index: int):
        """ plot layer selected in dropdown, do something """
        data: str = self.DrD_PrintLayoutsGpkg.currentData()
        layer: QgsVectorLayer = QgsProject.instance().mapLayer(data)

        self.List_Pages.clear()
        set_label_status(self.Label_Status, "")

        self.remove_managed_actions()

        if self.global_layout_menu is not None:
            self.Frame_Layout_Menu_Global._ui_module_base.replace_with_empty_frame()
            self.global_layout_menu.unload(True)
            self.global_layout_menu.hide()
            self.global_layout_menu.close()
            self.global_layout_menu = None
            self.plot_layer = None

        try:
            self['PlotLayoutMenu'].unload(True)
            self['PlotLayoutMenu'].hide()
            self['PlotLayoutMenu'].close()
            self.global_layout_menu = None
            self.plot_layer = None
        except KeyError:
            pass

        if layer is None:
            self.Frame_Plotlayer.setEnabled(False)
            set_label_status(self.Label_Status,
                             self.tr_("No Print Layer selected."),
                             STYLE_SHEET_ERROR)
        else:
            self.Frame_Plotlayer.setEnabled(True)
            layer.loadNamedStyle(os.path.join(self.get_plugin().plugin_dir,
                                              'templates',
                                              'plots',
                                              'plot_layer_stil.qml'),
                                 True)
            self.plot_layer = PlotLayer(layer)
            self.initialize_defaults(self.plot_layer)
            for layout in self.layouts:
                if layout.path == self.plot_layer.file:
                    continue
                self.initialize_defaults(self.plot_layer, layout)

            layout = self.layouts[self.plot_layer.file]

            self.load_page_templates(layout)

            self.global_layout_menu = self.add_ui_module("PlotLayoutMenu",
                                                         self.Frame_Layout_Menu_Global,
                                                         PlotLayoutMenu,
                                                         plot_layout=layout,
                                                         plot_layer=self.plot_layer,
                                                         edit=self.plot_layer)
            self.global_layout_menu.GroupBox_Layers.setCheckable(False)
            self.global_layout_menu.Label_Layers.hide()
            self.global_layout_menu.Label_Field_Info.hide()

            self.Frame_Plotlayer.setEnabled(True)

            # load values to window
            self.CheckBox_Legend_Extra.setCheckState(Qt.Checked if self.plot_layer.legend_on_extra_page
                                                     else Qt.Unchecked)
            self.CheckBox_Overview.setCheckState(Qt.Checked if self.plot_layer.create_overview_page
                                                 else Qt.Unchecked)
            self.SpinBox_Dpi.setValue(self.plot_layer.dpi)
            self.SpinBox_Scale.setValue(self.plot_layer.scale)

            self.reload_pages()
            self.List_Pages.setCurrentItem(None)

            # check if plot layer crs is different to current QgsProject projection
            if self.plot_layer.get_crs().authid().lower() != QgsProject.instance().crs().authid().lower():
                set_label_status(self.Label_Status,
                                 self.tr_("Coordinate Reference System from Print Layer and current QGIS Project are different. "
                                          "Maybe the page rectangles will have mystery orientations."),
                                 STYLE_SHEET_WARNING)

    def reload_pages(self):
        # loads pages from plot layer
        self.List_Pages.clear()
        for page in self.plot_layer:
            self.add_page_feature(page)

    def add_page_feature(self, page: PlotPage):
        orientation = self.layouts.get_orientation(page.file)
        if orientation == QgsLayoutItemPage.Portrait:
            orientation = self.tr_("portr.")
        elif orientation == QgsLayoutItemPage.Landscape:
            orientation = self.tr_("lands.")
        else:
            orientation = "unknown"

        item = QListWidgetItem(f'#{page.page} ({orientation}, ${page.fid})')
        item.setData(Qt.UserRole, page.fid)

        self.List_Pages.addItem(item)

    def add_new_layout(self, checked: bool):
        module: PlotNewLayout = self.add_module("PlotNewLayout", PlotNewLayout, parent=self)

    def add_file(self, checked: bool):
        """ select existing GeoPackage plot file and add it to project """
        set_label_status(self.Label_Status, "")
        file, _ = QFileDialog.getOpenFileName(
            self.iface.mainWindow(),
            'Wählen Sie eine GeoPackage:',
            QgsProject.instance().absolutePath(),
            "GeoPackage (*.gpkg)")

        if not file:
            return

        ok = PlotLayer.is_plot_file(file)
        if not ok:
            set_label_status(self.Label_Status,
                             self.tr_("File '%s' not compatible.") % os.path.basename(file),
                             STYLE_SHEET_ERROR)
            return

        layer = QgsVectorLayer(PlotLayer.get_plot_uri(file), os.path.basename(file).split(".")[0])
        if not layer.isValid():
            set_label_status(self.Label_Status,
                             self.tr_("File '%s' could not be opened.") % os.path.basename(file),
                             STYLE_SHEET_ERROR)
            return

        layer = QgsProject.instance().addMapLayer(layer, False)
        root = QgsProject.instance().layerTreeRoot()
        root.insertLayer(0, layer)
        self.set_layer(layer)

    def add_over_view_pages(self, checked: bool):
        """ Adds pages from calculated page rectangles """
        layers = QgsProject.instance().mapLayers().values()
        layers = [layer for layer in layers
                  if isinstance(layer, QgsVectorLayer) and not PlotLayer.is_plot_layer(layer)]

        layout: PlotLayout = self.DrD_Page_Templates.currentData()

        crs: QgsCoordinateReferenceSystem = self.plot_layer.layer_pages.dataProvider().crs()
        center = transform_geometry(QgsGeometry.fromRect(crs.bounds()),
                                    QgsCoordinateReferenceSystem("EPSG:4326"),
                                    crs).boundingBox().center()
        layout.item_map.setCrs(crs)
        scale = self.SpinBox_Page_Scale.value()
        rectangle = self.layouts.get_layout_extent(layout.path,
                                                   center,
                                                   scale)

        overview = PlotOverviewRectangles(layers, self.plot_layer.layer_pages.dataProvider().crs(), rectangle)
        for rectangle in overview.rectangles:
            page = self.plot_layer.add_page(layout, QgsGeometry.fromRect(rectangle), scale)
        else:
            if not overview.rectangles:
                QMessageBox.information(self.iface.mainWindow(),
                                        self.tr_("Plot Menu (Overview)"),
                                        self.tr_("No pages calculated."))
            else:
                self.reload_pages()

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """

        super().unload(self_unload)
        self.close()

        del self

    @classmethod
    def load(cls, parent_module: UiModuleBase):
        """ Loads this module into parent module.
            It will be loaded as a stand-alone ui.
        """
        if cls.__name__ in parent_module:
            module: cls = parent_module[cls.__name__]
            module.show()
            module.activateWindow()
        else:
            module: Union[cls, UiModuleBase] = parent_module.add_module(cls.__name__, cls)
            module.show()
            module.get_plugin().iface.messageBar().pushMessage(cls.tr_("Plot Menu"), cls.tr_("Templates loading. Please wait."))
            module.setEnabled(False)
            QApplication.setOverrideCursor(Qt.BusyCursor)
            module.layouts.load_layouts()
            module.setEnabled(True)
            QApplication.restoreOverrideCursor()

            if module.layouts.exceptions:
                error = cls.tr_("Errors occured while loading QGIS Printlayout Templates") \
                        + ("\n".join(module.layouts.exceptions))
                module.get_plugin().iface.messageBar().pushWarning(cls.tr_("Print Menu"),
                                                                   cls.tr_("Errors occured while loading QGIS Printlayout Templates"))
            else:
                error = ""
            set_label_status(module.Label_Status, error, STYLE_SHEET_ERROR)

        if hasattr(parent_module, "load_version_info"):
            parent_module.load_version_info()

        return module
