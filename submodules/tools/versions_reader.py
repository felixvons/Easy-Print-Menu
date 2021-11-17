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

import configparser


class VersionPlugin:

    @classmethod
    def get_local_version(cls, metadata_path: str) -> str:
        """ Reads local version string from local metadata.txt

            :param metadata_path: path to metadata.txt file
        """

        return cls.get_meta_value(metadata_path, 'version')

    @staticmethod
    def get_version_int(version: str) -> int:
        """ converts version str e.g. "1.0.1" into version integer 101 """

        version = version.replace(".", "").replace(",", "")
        version = int(version)
        return version

    @staticmethod
    def get_meta_value(metadata_path: str, key: str) -> str:
        """ Reads a value from metadata.txt.

            :param metadata_path: path to metadata.txt file
            :param key: key in 'general' section
        """

        config = configparser.ConfigParser()
        config.read(metadata_path, encoding='utf-8')
        return config['general'][key]
