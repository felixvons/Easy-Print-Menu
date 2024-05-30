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

from qgis.PyQt.QtWidgets import QLabel

from ._qt_constants import STYLE_SHEET_NEUTRAL


def set_label_status(label: QLabel, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
    """ sets labels text and css style

        :param label: label where to change text and stylesheet in css
        :param text: text to set, keep it empty and label will be hidden
        :param style: css stylesheet, defaults to `_qt_constants.STYLE_SHEET_NEUTRAL`
    """
    label.setText(text)
    if not text:
        label.hide()
        return

    label.setStyleSheet(style)
    label.show()
