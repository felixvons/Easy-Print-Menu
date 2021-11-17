# About
Main language of this plugin is German, so some translation from German to English may not be valid.
Per default English will be used. In you QGIS Profile settings you have to activated German locale.

References:
[pyqt-programming/internationalization](https://www.pythonstudio.us/pyqt-programming/internationalization.html)


## Load a transaltor in PyQt5

### 1. recommended imports
```python
from pathlib import Path
from PyQt5.QtCore import QTranslator, QCoreApplication
```

### 2. load a translation
You have to attach a successfull loaded translator object at something to prevent from collecting from Pythons garbage collector
```python
def load_translator(self):
    translator = QTranslator()
    path = str(Path(__file__).parent / "i18n" / "translation_de.qm")
    if translator.load(path):
        # IMPORT STEP
        # ATTACH IT ON A OBJECT, KEEP IT ALIVE!!!
        # If you don't do it, the the Python garbage collector will come and eat it.
        self.translator = translator
        QCoreApplication.instance().installTranslator(self.translator)
```


## Translation files:
# translation_de.ts
Ui translation from Qt Designer and Qt Linguist.

# messages_de.ts
Individual messages/translations in the xml format expected by lrelease.
[Qt DTD TS File](https://doc.qt.io/qt-5/linguist-ts-file-format.html)
Translations will be avaiable on QgsApplication.
More information on [i18n on riverbankcomputing](https://www.riverbankcomputing.com/static/Docs/PyQt5/i18n.html)

A little assistance menu is available. See translations.py.


# 1. Create a .ts file from .ui

## create and update ts file
searches a folder recursive and put found ui files into one ts-file for Qt Linguist.
Maybe your paths are different.
```
lupdate -no-obsolete "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/modules/plot" -ts "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/i18n/translation_de.ts"
```

```
"%LOCALAPPDATA%\WPy64-3940\python-3.9.4.amd64\Scripts\pylupdate5.exe" -noobsolete "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\modules\plot" -ts "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\modules\plot/i18n/translation_de.ts"
```

```
"%LOCALAPPDATA%\WPy64-3940\python-3.9.4.amd64\Lib\site-packages\pyqt5_tools\Qt\bin\lupdate.exe" -no-obsolete "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\modules/plot" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\i18n/translation_de.ts"
```

# 2. Create .dm file from .ts
Create `dm` file.
Maybe your paths are different.
## ui
```
lrelease -compress "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/i18n/translation_de.ts" "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/i18n/translation_de.qm"
```

```
"%LOCALAPPDATA%\WPy64-3940\python-3.9.4.amd64\Lib\site-packages\pyqt5_tools\Qt\bin\lrelease.exe" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\i18n/translation_de.ts" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\i18n/translation_de.qm"
```

## messages
```
lrelease -compress "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/i18n/messages_de.ts" "/home/felix/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plot/i18n/messages_de.qm"
```

```
"%LOCALAPPDATA%\WPy64-3940\python-3.9.4.amd64\Lib\site-packages\pyqt5_tools\Qt\bin\lrelease.exe" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\i18n/messages_de.ts" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plot\i18n/messages_de.qm"
```
