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

import inspect
import os.path

from re import fullmatch

from typing import Any, Type, Dict, Callable, List, Tuple, Union, Optional

from pathlib import Path

from qgis.core import QgsApplication

from PyQt5.QtCore import (QMetaObject, QObject, pyqtBoundSignal, pyqtSignal,
                          QTranslator, QCoreApplication)
from PyQt5.QtWidgets import (QAction, QWidget, QFrame, QLabel, QApplication,
                             QGridLayout, QToolBar, QMainWindow,
                             QComboBox, QMessageBox)
from PyQt5.QtGui import QIcon
from PyQt5 import uic


class Connection:
    """ internal use only in ModuleBase in connect method. """

    def __init__(self, c: Callable, log: Optional[Callable] = None):
        self.callable = c
        self.name = self.callable.name if hasattr(self.callable, "name") else self.callable.__qualname__
        self.log = log

    def call(self, *args, **kwargs):
        msg = f"calling pyqtBoundSignal '{self.name}': {self.callable} with args: {args} and kwargs: {kwargs}"
        if callable(self.log):
            self.log(msg)

        return self.callable(*args, **kwargs)

    def __repr__(self):
        return f"Connection({self.callable})"


class Plugin:
    """ use this class in plugin.py to identify it as a plugin class.
        This is necessary to find correct module to use plugin path attributes, e.g. "plugin_dir"

    """
    pass


class ModuleBase:
    """ base class for each module class (must be inherited!) """

    def __init__(self, parent_module: Optional['ModuleBase'] = None, module_name: str = '',
                 log: Optional[Callable] = None, **kwargs: dict):

        # check mro if highest class is a module base (ui or not)
        # this check is important to keep parent and child relationships valid
        mro = inspect.getmro(type(self))
        module_classes = (ModuleBase, UiModuleBase)
        if mro[0] not in module_classes and mro[1] not in module_classes:
            module_class = UiModuleBase if UiModuleBase in mro else ModuleBase

            ok = False

            for i, class_ in enumerate(mro[1:]):
                # checks each class in inherited order to look for module bases
                class_mro = inspect.getmro(class_)
                if module_class in class_mro:
                    ok = True
                    break

                break

            if not ok:

                # find first class, which inherits a module base
                use_class = None
                for class_ in mro[1:]:
                    class_mro = inspect.getmro(class_)
                    if module_class in class_mro:
                        use_class = class_
                        break

                new_mro = (use_class.__name__,) + tuple(x.__name__ for x in mro if x not in (UiModuleBase,
                                                                                             use_class,
                                                                                             ModuleBase,
                                                                                             self.__class__))
                origin_mro = tuple(x.__name__ for x in mro if x != self.__class__)
                raise TypeError("\noriginal inheritance:\n\t"
                                f"{self.__class__.__name__}({', '.join(origin_mro)})\n\n"
                                "expected class inheritance (first inheritance should be a module base):\n\t"
                                f"{self.__class__.__name__}({', '.join(new_mro)})\n\n"
                                "Hint: class name 'Ui_MainWindow' is usually FORM_CLASS from ui file.\n"
                                "This is a approximate hint to let you fix your issue")

        self._parent_module: Optional[ModuleBase] = parent_module
        self.module_name = module_name
        self._log: Callable = log
        self._log_enabled = True

        # module stuff
        self._modules: Dict[str, ModuleBase] = {}
        self._translators: List[QTranslator] = []

        # ui relevant attributes
        self._connections: List[Tuple[QObject, Callable, Any, Connection]] = []
        self._toolbars_managed: Dict[str, List[QAction]] = {}  # {'toolbars object name': [action objects]}
        self._actions: List[QAction] = []
        self._actions_managed: List[QAction] = []

        self.__unloaded = False
        self.unloaded = self.__unloaded

    @property
    def unloaded(self):
        return self.__unloaded

    @unloaded.setter
    def unloaded(self, value: bool):
        assert isinstance(value, bool)
        self.__unloaded = value

    def add_action(self, name: str, icon: QIcon, manage: bool, callback_action: Callable, add_to_menu_bar: bool,
                   toolbar_name: Optional[str] = None, toolbar_displayname: Optional[str] = None,
                   to_plugin_menu: bool = True, init_enabled: bool = True, main_window: QMainWindow = None,
                   tool_tip: str = "") -> QAction:
        """ loads icon into tool/menu bar.

            :param name: visual action name for user
            :param icon: icon path, empty string means no icon
            :param manage: should the action should be "registered as managed" action for this module?
            :param callback_action: function/method/lambda to call
            :param add_to_menu_bar: make action visible in menu bar?
            :param toolbar_name: object name for QToolBar
            :param toolbar_displayname: visual toolbar name for hide and show.
                                        only necessary, when no new bar is needed
            :param to_plugin_menu: add to plugin menu bar
            :param init_enabled: init enable state, defaults to True
            :param main_window: main window from qgis
            :param tool_tip: tool tip string
            :return: new created QAction
        """

        if main_window is None:
            from qgis.utils import iface
            main_window = iface.main_window()

        action = QAction(icon, name, None)
        action.triggered.connect(callback_action)
        action.setEnabled(init_enabled)
        action.setToolTip(tool_tip)

        # Anzeige- sowie Objektname der Toolbar (Werkzeugleiste) sind vorhanden
        if toolbar_displayname and toolbar_name:
            toolbar = self.get_toolbar(toolbar_displayname, toolbar_name, main_window)
            toolbar.addAction(action)
            self._toolbars_managed[toolbar_name][1].append(action)

        if add_to_menu_bar:
            assert hasattr(self, 'menu_bar')
            getattr(self, 'menu_bar').addAction(action)

        if to_plugin_menu:
            from qgis.utils import iface
            assert hasattr(self, 'plugin_menu')
            iface.addPluginToMenu(getattr(self, 'plugin_menu'), action)

        if manage:
            self._actions_managed.append(action)

        self._actions.append(action)

        self.log(f"toolbar action '{name}' loaded :: object={toolbar_name} // displayname={toolbar_displayname}")

        return action

    def add_module(self, keyword: str, module_class, parent: Optional[QWidget] = None, *args: list,
                   **kwargs) -> Union['UiModuleBase', 'ModuleBase']:
        """ Add new module to this module and returns it. It can be a ModuleBase or UiModuleBase

        Example:
            self.register_module('APL',  # Internale module dict key
                                 self.ui.Tab_APL.layout(),  # layout where to insert this new ui module
                                 self.ui.P_A_Module_Frame,  # widget to replace with this module
                                 apl.ModuleAPL)  #  new module class

            :param keyword: keyword for module dictionary (must be unique)
            :param module_class: module class to load
            :param parent: parent widget for WindowModality, defaults to None
        """
        if keyword in self._modules:
            raise KeyError(f"module '{keyword}' already loaded.")

        # check if module_class bases on ModuleBase
        if ModuleBase not in inspect.getmro(module_class):
            raise ValueError(f"module class does not inherit '{ModuleBase.__name__}'")

        # updating default arguments for new base module
        dict_ = {
            'parent': parent,
            'parent_module': self,
            'name': keyword,
            'module_name': keyword,
            'log': self.get_plugin().log,
        }
        kwargs.update(dict_)
        module = module_class(*args, **kwargs)
        self._modules[keyword] = module

        return module

    def disable_managed_actions(self):
        for action in self._actions_managed:
            action.setEnabled(False)

    def enable_managed_actions(self):
        for action in self._actions_managed:
            action.setEnabled(True)

    def install_translator(self, file: Union[str, Path]) -> bool:
        """ Install translation file (.qm).
            :return: True on success
        """

        if not isinstance(file, str):
            file = str(file)

        translator = QTranslator()
        # file found and loaded
        if translator.load(file):
            # add loaded translator to instance
            if QCoreApplication.instance().installTranslator(translator):
                self._translators.append(translator)
                return True

        return False

    def remove_managed_actions(self):

        for _, value in self._toolbars_managed.items():
            toolbar, actions = value

            for action in actions:
                if action in self._actions_managed:
                    toolbar.removeAction(action)
                    self._actions_managed.remove(action)

            if len(toolbar.actions()) == 0:
                # toolbar is empty, remove it
                toolbar.setParent(None)  # nimmt Beziehung raus und wird löschbar
                del toolbar

    def connect(self, obj: Union[pyqtBoundSignal, pyqtSignal], callable_: Callable, track: bool = True) -> Tuple[QObject, Callable, QMetaObject.Connection]:
        """ Connects new callable to a Qt signal and store the connection.
            Set connections will be unloaded later in `unload` method.

            Keep in mind, that some Qt connections will call the connected method/function with extra arguments,
            e.g. sometimes QPushButton with a boolean.

            :param obj: QObject
            :param callable_: function/method
            :param track: track signal calling in self.log?
            :return: qt connection object
        """
        if track:
            con = Connection(callable_, log=self.log)
        else:
            con = Connection(callable_, log=None)

        connection = obj.connect(con.call)
        entry = (obj, callable_, connection, con)
        self._connections.append(entry)

        return entry

    def get_parent(self):
        return self._parent_module

    def get_plugin(self, next_plugin: bool = False) -> 'ModuleBase':
        """ finds the highest available plugin-object.
            Plugin must based on Plugin class.

        """
        current = self.get_parent()

        if current is None and isinstance(self, Plugin):
            # no parent, plugin itself
            return self

        if current is None:
            raise ModuleNotFoundError(f"{self} has no parent and not based on Plugin")

        iterations = 0

        while True:

            if iterations > 100:
                raise StopIteration(f"{self} no plugin found")

            parent = current.get_parent()

            if (parent is None or next_plugin) and isinstance(current, Plugin):
                return current

            current = parent
            iterations += 1

    def get_parent_plugin(self) -> 'ModuleBase':
        """ Finds the next available plugin-object.
            Plugin must based on Plugin class.

        """
        return self.get_plugin(next_plugin=True)

    def get_log_state(self) -> bool:
        """ returns bool, whether logging is enabled (True) or not (False) """
        return self._log_enabled

    def get_toolbar(self, toolbar_name: str, toolbar_object_name: str, main_window: QMainWindow) -> QToolBar:
        """ Creates new toolbar or returns existing one with given params.

            :param toolbar_name: object name for QToolBar
            :param toolbar_object_name: object name for QToolBar
            :param main_window: QMainWindow with toolbar
            :return: found or created QToolBar
        """

        toolbar = None
        # find alls toolbar objects in given main window
        _menus_objects = main_window.findChildren(QToolBar)
        _menus = [x.objectName() for x in _menus_objects]

        if toolbar_object_name not in _menus:
            # no toolbar found with given object name, create new one
            toolbar = main_window.addToolBar(toolbar_name)
            toolbar.setObjectName(toolbar_object_name)
        else:
            for menu in _menus_objects:
                if menu.objectName() == toolbar_object_name:
                    # toolbar found
                    toolbar = menu

        self._toolbars_managed.setdefault(toolbar_object_name, [toolbar, []])

        return toolbar

    def log(self, *args, **kwargs) -> Any:
        """ calls set log method and returns return-value from log method.
        """

        name = self.__class__.__name__
        if args:
            args = (f"<< class: {name} >> {args[0]}", *args[1:])

        if hasattr(self, 'log_') and self._log_enabled:
            # fall back for Logging class
            return self.log_(*args, **kwargs)

        if callable(self._log) and self._log_enabled:
            return self._log(*args, **kwargs)

    def reset_qt_connections(self):
        """ disconnects qt signal from QObject """
        for obj, callable_, *_ in self._connections:
            try:
                obj.disconnect(callable_)
            except (RuntimeError, TypeError):
                ...

        self._connections.clear()

    def set_log_state(self, active: bool):
        """ changes logging state """
        assert isinstance(active, bool)

        self._log_enabled = active

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        if self.unloaded:
            return

        self.reset_qt_connections()

        # uninstall translators
        for translator in self._translators:
            QCoreApplication.instance().removeTranslator(translator)
        self._translators.clear()

        parent_name = getattr(self.get_parent(), 'module_name', '<no parent>')
        self.log(f"parent module {parent_name} unloads me ({self.module_name})")
        for module_name, module in tuple(self._modules.items()):
            self.log(f"module {self.module_name} unloads module {module_name}")
            module.unload()
            self.log(f"module {self.module_name} unloaded module {module_name}")

        for _, value in self._toolbars_managed.items():
            toolbar, actions = value

            for action in actions:
                toolbar.removeAction(action)

            if len(toolbar.actions()) == 0:
                # toolbar is empty, remove it
                toolbar.setParent(None)  # nimmt Beziehung raus und wird löschbar
                del toolbar

        if self_unload and self.get_parent() is not None:
            del self.get_parent()._modules[self.module_name]

        self.unloaded = True

    property(fget=get_log_state, fset=set_log_state, fdel=None, doc=None)

    def __contains__(self, item: Union[str, 'ModuleBase']):

        # works, if item is str
        if item in self._modules:
            return True

        return item in self._modules.values()

    def __getitem__(self, item):
        try:
            return self._modules[item]
        except KeyError:
            raise KeyError(f"module '{self.module_name}' has no sub module '{item}'")

    def __repr__(self):
        name = self.module_name if self.module_name else "< no name >"
        parent = self.get_parent()
        if parent is None:
            parent = "None"
        else:
            parent = parent.module_name
        return f"{self.__class__.__name__}('{name}', parent={parent})"


class UiModuleBase(ModuleBase):
    """ Needs a widget named `MainWidget` in inherited class.
        `MainWidget` gets a new attribute `_ui_module_base` to have a reference to this module.

        Information: If you want to use this base class to create a directy usable widget, e.g. TabWidget,
                     then call `make_valid` method.
    """

    def __init__(self, *args, **kwargs):
        # will be set via self.setupUI during ui dings bums wuahhahaha
        self.MainWidget: Optional[QWidget] = None

        super().__init__(*args, **kwargs)

        self.connect(QApplication.instance().aboutToQuit, self.about_to_quit)

        self._post_check_results: List[str] = []

    def add_ui_module(self, keyword: str, plugin_widget: Union[QWidget, None],
                      module_class, use_directly: bool = False, parent: Optional[QWidget] = None, *args: list,
                      **kwargs) -> Union['UiModuleBase', 'ModuleBase']:
        """ Add new module to this module and returns it. It can be a ModuleBase or UiModuleBase

        Example:
            self.register_module('APL',  # Internale module dict key
                                 self.ui.Tab_APL.layout(),  # layout where to insert this new ui module
                                 self.ui.P_A_Module_Frame,  # widget to replace with this module
                                 apl.ModuleAPL)  #  new module class

            :param keyword: keyword for module dictionary (must be unique)
            :param plugin_widget: None or Layout
            :param module_class: module class to load
            :param use_directly: use given module class directly as new widget?
            :param parent: parent widget for WindowModality, defaults to None
        """
        assert UiModuleBase in inspect.getmro(module_class), f"'{module_class.__class__.__name__}' " \
                                                             f"must inherit UiBaseModule"

        module: UiModuleBase = self.add_module(keyword, module_class, parent, *args, **kwargs)

        if use_directly:
            module.make_valid()

        if plugin_widget is not None:
            plugin_layout = plugin_widget.parent().layout()

            object_name = plugin_widget.objectName()
            self.is_object_name_valid(object_name)

            if plugin_layout is not None:
                # load module into existing module
                # more information in `UiModuleBase`
                # gui references are set, load it
                widget: QWidget = module.MainWidget
                widget._ui_module_base = module

                # removes all children from widget to replace
                for child in plugin_widget.findChildren(QWidget):
                    child.setParent(None)
                    del child

                replaced_widget_item = plugin_layout.replaceWidget(plugin_widget, widget)
                widget.show()
                plugin_widget.hide()
                plugin_widget.setParent(None)

                # set new object on old object/attribute name in module
                source_object_name = plugin_widget.objectName()
                setattr(self, source_object_name, widget)

                del plugin_widget

                if replaced_widget_item is not None:
                    replaced_widget = replaced_widget_item.widget()
                    replaced_widget.setParent(None)
                    plugin_layout.removeWidget(replaced_widget)
                    del replaced_widget
                    del replaced_widget_item

                # resets object name to origin "MainWidget" from ui becomes e.g. "Frame_Progressbar"
                widget.setObjectName(source_object_name)

        return module

    def get_widget(self, object_name: str) -> Optional[QWidget]:
        """ returns widget with given objectName """
        for child in self.findChildren(QWidget):
            if child.objectName() == object_name:
                return child

        return None

    # noinspection PyPep8Naming
    def setupUi(self,  widget: QWidget):

        use = None
        for x in reversed(self.__class__.__mro__[1:]):
            if hasattr(x, "setupUi"):
                use = x
                break

        use.setupUi(self, widget)
        self.post_checks()

        if self._post_check_results:
            QMessageBox.warning(
                self,
                "developer post process warnings ( after self.setupUi(self) )",
                "\n".join(self._post_check_results)
            )

    def set_ui_version_info(self, label: QLabel):
        """
        Reads the version from the repo and the local installation
        and informs the user about possible updates
        """
        from ...submodules.tools.compatibility import get_online_plugin_version

        label.setToolTip("")

        version = self.get_parent_plugin().version
        online_version, error = get_online_plugin_version(self.get_parent_plugin().plugin_name)

        if version != online_version and online_version is not None:
            # found in https://raw.githubusercontent.com/qgis/QGIS/master/i18n/qgis_de.ts
            hint = QgsApplication.translate("QgsPluginInstaller", "There is a new plugin available")
            label.setText(f"Easy Print Menu: v{version} ({hint} -> {online_version})")
            label.setStyleSheet("color: rgb(0, 0, 255); font-weight: bold;")
        else:
            label.setText(f"Easy Print Menu: v{version}")
            label.setStyleSheet("color: rgb(0, 0, 255);")

        if error:
            label.setText(label.text() + " - " + error)
            label.setStyleSheet("color: rgb(200, 80, 80); font-weight: bold;")

    @staticmethod
    def is_object_name_valid(object_name: str) -> bool:
        """ Checks if object name is valid.

        :param object_name: object name
        :return: True if ok, else raises AssertionErrors
        """
        assert fullmatch('[A-Za-z_][A-Za-z_0-9]+', object_name), f"object name '{object_name}' is not valid"

        return True

    def is_object_name_free(self, object_name: str) -> bool:
        """ Checks if object name is free and valid.

        :param object_name: object name
        :return: True if ok, else raises AssertionErrors
        """
        objects = self.findChildren(QWidget)
        names = [x.objectName() for x in objects]
        assert object_name not in names, f"object name '{object_name}' already in use by a child"
        assert object_name not in dir(self), f"object name '{object_name}' already in use by self"

        self.is_object_name_valid(object_name)

        return True

    def _create_frame(self, layout: QGridLayout, object_name: str,
                      position: Optional[Tuple[int, int]] = None) -> QFrame:
        """ creates an empty frame in given layout as dummy.

        :param layout: Layout where to insert new frame
        :param object_name: object_name for new frame and attribute name for `self`
        :param position: tuple(row, column)
        :return: created frame
        """
        # self.is_object_name_free(object_name)

        # QFrame for ModuleBase
        page_frame = QFrame()
        page_frame.setObjectName(object_name)
        page_frame.setFrameShape(QFrame.NoFrame)
        page_frame.setContentsMargins(1, 1, 1, 1)

        # adds QLabel to frame with dummy text
        frame_layout = QGridLayout()
        page_frame.setLayout(frame_layout)
        frame_label = QLabel()
        frame_label.setText("I am a dummy who likes bugs bunny")
        frame_layout.addWidget(frame_label)

        if position is None:
            layout.addWidget(page_frame)
        else:
            layout.addWidget(page_frame, position[0], position[1])

        setattr(self, object_name, page_frame)

        return page_frame

    @staticmethod
    def _get_module(module_or_widget: Union[QWidget, ModuleBase]) -> 'UiModuleBase':

        # simple loaded element
        if hasattr(module_or_widget, '_ui_module_base'):
            return getattr(module_or_widget, '_ui_module_base')

        iteration = 0
        while not isinstance(module_or_widget, ModuleBase):
            if iteration > 100:
                raise StopIteration(f"no module found for object '{module_or_widget.objectName()}'")

            if module_or_widget is None:
                return None

            module_or_widget = module_or_widget.parent()

            # parent has no this information
            if hasattr(module_or_widget, '_ui_module_base'):
                return getattr(module_or_widget, '_ui_module_base')

            iteration += 1

        return module_or_widget

    @classmethod
    def get_ui_file(cls, python_file: str) -> str:
        """ Returns found ui file in same directory of `python_file`
            and instead of 'py' as file ending looks for 'ui'.
            Python file and ui file must be in same folder.

        :param python_file: path to python file -> __file__
        :return:
        """
        base = os.path.basename(python_file)
        folder = os.path.dirname(python_file)

        assert base.endswith(".py"), f"file name '{base}' must end with '.py'"
        ui_file = base[:-3] + ".ui"

        ui_file_path = os.path.join(folder, ui_file)
        if not Path(ui_file_path).is_file():
            raise FileNotFoundError(f"no ui file found '{ui_file_path}'")

        return ui_file_path

    @classmethod
    def get_uic_classes(cls, python_or_ui_file: str) -> Tuple[Any, Type[QWidget]]:
        """ Returns objects/classes from uic.loadType.
            Python file and ui file must be in same folder.

            See `PyQt5.uic.loadUiType` for more information.

            :param python_or_ui_file: python file path or path to ui file
            :return: form class (most needed) and Qt base class from Qt Designer, e.g QMainWindow
        """
        assert python_or_ui_file.endswith((".py", ".ui"))

        if python_or_ui_file.endswith(".py"):
            # python file is given, get ui file path
            python_or_ui_file = cls.get_ui_file(python_or_ui_file)

        form_class, base_class = uic.loadUiType(python_or_ui_file)

        return form_class, base_class

    def make_valid(self):
        """ make object valid to use itself als 'MainWidget' """
        assert getattr(self, 'MainWidget', None) is None, "make_valid cannot be called, already 'MainWidget' here"

        self.MainWidget: QWidget = self

    def post_checks(self):
        """ Runs some basic checks.
            Following checks are made:
                - QComboBox's have expected sizeAdjustPolicy for adjusting in layouts correctly

            This method has to be called manually in __init__.
        """

        # check combo boxes, if their sizeAdjustPolicy is ok for layouts
        for child in self.findChildren(QComboBox):
            policy = child.sizeAdjustPolicy()
            expects = (QComboBox.AdjustToMinimumContentsLengthWithIcon,
                       QComboBox.AdjustToContents)
            if policy not in expects and child.objectName():
                text = f"post_checks(): QComboBox {child.objectName()} " \
                       f"has possible invalid Qt configuration in 'sizeAdjustPolicy'. " \
                       f"Got '{policy}' expecting '{expects}' "

                if text in self._post_check_results:
                    continue

                self.log(text)
                self._post_check_results.append(text)

    def replace_with_empty_frame(self):
        """ unload this module and replace it with an empty frame """

        layout = self.MainWidget.parent().layout()
        if layout is None:
            # print("not layout found for", self.__class__.__name__, "parent of MainWidget")
            return

        if not isinstance(layout, QGridLayout):
            raise NotImplementedError(f"Layout '{layout.__class__.__name__}' is not a QGridLayout. Not implemented yet")

        for column in range(layout.columnCount()):
            for row in range(layout.rowCount()):

                # locate item at row and column in grid
                layout_item = layout.itemAtPosition(row, column)
                layout_widget = layout_item.widget()
                module = self._get_module(layout_widget)
                if not hasattr(layout_widget, 'MainWidget') and not hasattr(module, 'MainWidget'):
                    continue

                module = self._get_module(layout_widget)
                if self is module:
                    frame = self.get_parent()._create_frame(layout, layout_widget.objectName(), (row, column))
                    for child in frame.findChildren(QWidget):
                        child.setParent(None)
                        del child
                    replaced_widget_item = layout.replaceWidget(self.MainWidget, frame)
                    if replaced_widget_item is not None:
                        replaced_widget = replaced_widget_item.widget()
                        layout.removeWidget(replaced_widget)
                        replaced_widget.setParent(None)
                        del replaced_widget
                        del replaced_widget_item

                    self.unload(True)
                    return

        raise TypeError("Nothing found to replace :o")

    def about_to_quit(self):
        """ QCoreApplication is about to quit/close """

        self.log(f"QApplication is about to quit, cancel progress")

        # cancel something?
        if hasattr(self, "cancel"):
            self.cancel()

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        if self.unloaded:
            return

        super().unload(self_unload)

        if isinstance(self, QWidget):
            self.close()
            self.setParent(None)
