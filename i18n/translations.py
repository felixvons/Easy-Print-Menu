
import sys

from lxml import etree
from lxml.etree import _Element, Element

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (QMainWindow, QApplication, QFileDialog,
                             QMessageBox, QTreeWidgetItem, QInputDialog,
                             QTreeWidgetItemIterator)
from PyQt5.uic import loadUiType

FormClass, _ = loadUiType(__file__.replace(".py", ".ui"))

class TranslationHelper(QMainWindow, FormClass):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent'))

        self.setupUi(self)

        self.show()
        self.tree = None
        self.context = None

        self.widget.layout().setAlignment(Qt.AlignTop)
        self.centralWidget().layout().setAlignment(Qt.AlignTop)

        # setup Qt connections
        self.But_Open.clicked.connect(self.open_ts_file)
        self.But_Add.clicked.connect(self.add_element)
        self.But_Remove.clicked.connect(self.remove_element)
        self.But_Save.clicked.connect(self.save_file)

        self.disable()

    def disable(self):
        self.xmlView.clear()
        self.xmlView.setEnabled(False)
        self.Frame_View.setEnabled(False)
        self.tree = None
        self.context = None
        self.Frame_Save.setEnabled(False)
        self.Frame_Open.setEnabled(True)
        self.Label_File.setText("")
        self.Edit_Context.setText("")
        self.Group_Context.setEnabled(False)

    def enable(self):
        self.xmlView.clear()
        self.xmlView.setEnabled(True)
        self.Frame_Save.setEnabled(True)
        self.Frame_View.setEnabled(True)
        self.Frame_Open.setEnabled(False)

    def error(self, msg: str):
        QMessageBox.warning(self, "Information/Warning", msg)

    def open_ts_file(self):
        """ try to open and parse ts/xml file. """
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Choose your file",
            str(Path(__file__).parent),
            "Translation (*.ts)")

        self.disable()

        if not file:
            self.error("No file selected")
            return

        try:
            self.tree = etree.parse(file)
            self.Label_File.setText(file)
            self.enable()
            self.load_tree_to_view()
        except Exception as e:
            self.error(f"File could not be loaded. Exception:\n\n{e}")
            self.disable()

    def add_element(self):
        text, ok = QInputDialog.getText(self, "Enter source text", "English:")

        text = text.lstrip().rstrip()

        if not ok or not text.strip():
            return

        new_element = Element("message")
        new_elem_source = Element("source")
        new_elem_source.text = text
        new_element.append(new_elem_source)
        new_elem_translation = Element("translation")
        new_elem_translation.text = ""
        new_element.append(new_elem_translation)

        self.context.append(new_element)

        self.add_element_to_tree(new_element)

    def remove_element(self):
        items = self.xmlView.selectedItems()
        if not items:
            return

        item: QTreeWidgetItem = items[0]

        element = item.data(0, Qt.UserRole)
        if not isinstance(element, _Element):
            return

        self.xmlView.invisibleRootItem().removeChild(item)
        self.context.remove(element)

    def save_file(self):
        reply = QMessageBox.question(
            self,
            "save ts file?",
            "Do you want to overwrite existing ts file?"
        )
        if reply != QMessageBox.Yes:
            return

        iterator = QTreeWidgetItemIterator(self.xmlView)
        while iterator.value():

            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            text = item.text(0) #.replace("'", "&apos;")

            # only save something, when it has no children (it is translation or source element)
            if len(data) == 0:
                data.text = text

            iterator += 1
        Path(self.Label_File.text()).write_bytes(etree.tostring(self.tree, pretty_print=True))

    def load_tree_to_view(self):
        """ Loads ts/xml file to tree widget.
        """

        context = self.tree.getroot().findall("./context")

        if len(context) != 1:
            raise ValueError(f"ts file can have only one defined context, not more or less! - got {len(context)}")

        self.context = context[0]

        self.Edit_Context.setText(f"{self.context.find('./name').text} "
                                  f"({self.tree.getroot().attrib['sourcelanguage']} -> "
                                  f"{self.tree.getroot().attrib['language']})")
        self.Group_Context.setEnabled(True)

        for i, element in enumerate(self.context.findall("./message")):
            self.add_element_to_tree(element)

    def add_element_to_tree(self, element: _Element):

        root = self.xmlView.invisibleRootItem()
        source = element.find("./source")
        translation = element.find("./translation")

        german = QIcon(str(Path(__file__).parent / "germany.png"))
        destination = QIcon(str(Path(__file__).parent / "destination.png"))

        item = QTreeWidgetItem([f"{root.childCount()} // {source.text}"])
        item.setData(0, Qt.UserRole, element)
        item_source = QTreeWidgetItem([source.text])
        #item_source.setIcon(0, QIcon(german))
        item.addChild(item_source)

        if translation is not None:
            if translation.text:
                item_translation = QTreeWidgetItem([translation.text])
                item.setForeground(0, QColor(120, 120, 120, 255))
            else:
                item_translation = QTreeWidgetItem([""])
                item.setForeground(0, QColor(0, 0, 0, 255))
        else:
            translation = Element("translation")
            translation.text = ""
            element.append(translation)
            item_translation = QTreeWidgetItem([""])
            item.setForeground(0, QColor(0, 0, 0, 255))


        item_translation.setIcon(0, QIcon(german))
        item_translation.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
        item_source.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
        item_source.setData(0, Qt.UserRole, source)
        item_translation.setData(0, Qt.UserRole, translation)
        item.addChild(item_translation)


        root.addChild(item)



if __name__ == "__main__":
    app = QApplication(sys.argv[1:])
    window = TranslationHelper()
    sys.exit(app.exec_())
