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

import datetime
import getpass
import hashlib
import json
import os

from pathlib import Path

from zipfile import ZipFile, ZIP_DEFLATED
from typing import List, Optional

from .path import get_files


class CreatePluginZip:
    """ CreatePluginZip will create a new plugin zip file for QGIS.

        All __pycache__ files will not be zipped.
        To ignore specific paths, you have to specify them in the parameters.

        :param zip_file_name: new zip file name (without file ending)
        :param source_location: source folder to zip
        :param destination_path: destination path for new zip file
        :param ignore_paths: ignore given relative pathes in this folder
    """

    def __init__(self, zip_file_name: str, source_location: str,
                 destination_path: str, ignore_paths: List[str],
                 overwrite: bool = False):

        if not overwrite:
            if Path(destination_path).is_file():
                raise FileExistsError(f"file '{destination_path}' already exists")
        else:
            if Path(destination_path).is_file():
                os.remove(destination_path)

        self.zip_file_name = zip_file_name
        self.source_location = os.path.normpath(source_location)
        self.destination_path = os.path.normpath(destination_path)
        self.ignore_paths = [os.path.normpath(os.path.join(self.source_location, path)) for path in ignore_paths]
        if self.destination_path in self.ignore_paths:
            self.ignore_paths.remove(self.destination_path)

        self.errors = []
        self.log = []

        self.files_to_zip = list(get_files(source_location, ignore_paths=self.ignore_paths))

        self.write()

    def write(self):
        """ writes to new zip zile """

        with ZipFile(self.destination_path, mode="w", compression=ZIP_DEFLATED) as zip_:
            for file in self.files_to_zip:

                if "__pycache__" in file:
                    continue

                self.log.append(f"writing {file}")
                path_in_zip = self.zip_file_name + "/" + file[len(self.source_location):]
                zip_.write(file, path_in_zip)
