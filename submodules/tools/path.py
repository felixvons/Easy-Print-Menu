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
import os

from typing import List


def get_files(path, recursive: bool = True, ignore_paths: List[str] = []):
    """ get all files from folder.

        :param path: path
        :param recursive: go deeper?
        :param ignore_paths: list of paths to ignore
    """

    ignored_roots = []

    def skip_root(file_):
        for x in ignored_roots:
            if file_.startswith(x):
                return True

        return False

    for root, _, files in os.walk(path):

        # current iter path should be ignored
        root = os.path.normpath(root)
        if root in ignore_paths:
            ignored_roots.append(root)
            continue

        if skip_root(root):
            continue

        for file in files:

            if skip_root(file):
                continue

            path = os.path.normpath(os.path.join(root, file))

            # file path should be ignored
            if path in ignore_paths:
                continue

            yield path

        # do not go deeper in folder structure
        if not recursive:
            break
