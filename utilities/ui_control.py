import os

from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QTranslator, QLocale
from qgis.core import QgsApplication

from ..plugin import PluginPlot
from ..modules.plot.plot_menu import PlotMenu


def load_tool_bar(plugin: PluginPlot):
    """ loads default action for your plugin """

    # load translation
    language = QgsApplication.instance().locale()
    if language == "de":
        QLocale.setDefault(QLocale("de_DE"))
        # menu translations
        plugin.menu_translator = QTranslator()
        qm = str(Path(__file__).parent.parent / "i18n" / "translation_de.qm")
        plugin.menu_translator.load(qm)
        QgsApplication.instance().installTranslator(plugin.menu_translator)

        # message translator
        plugin.msg_translator = QTranslator()
        qm = str(Path(__file__).parent.parent / "i18n" / "messages_de.qm")
        plugin.msg_translator.load(qm)
        QgsApplication.instance().installTranslator(plugin.msg_translator)

    tr_ = lambda text: QgsApplication.translate("QgsApplication", text)

    icon = QIcon(plugin.get_icon_path("printer_graphical.png"))
    plugin.add_action(tr_("Open Print Menu"),
                      icon,
                      False,
                      lambda x=1: PlotMenu.load(plugin),
                      False,
                      "telekom_plot",
                      tr_("Print Menu"),
                      True,
                      True,
                      plugin.iface.mainWindow())

    if os.name == "posix":
        path = Path(plugin.plugin_dir) / "templates" / "plots"
        plugin.add_action(tr_("Open templates folder"),
                        QIcon(),
                        False,
                        lambda x=1: os.system(f'xdg-open "{path}"'),
                        False,
                        "",
                        "",
                        True,
                        True,
                        plugin.iface.mainWindow())

    if os.name == "nt":
        # Windows
        from subprocess import Popen

        path = Path(plugin.plugin_dir) / "templates" / "plots"
        plugin.add_action(tr_("Open templates folder"),
                        QIcon(),
                        False,
                        lambda x=1: Popen(r'explorer /select,"{}"'.format(path)),
                        False,
                        "",
                        "",
                        True,
                        True,
                        plugin.iface.mainWindow())
    # PlotMenu.load(plugin).hide()  # direkt nach QGIS Start laden
