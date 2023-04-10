# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import io
import zipfile
import json

from core import Location


def read_json_file(f):
    return json.load(io.TextIOWrapper(f, encoding="utf-8-sig"))


class FilesReader:
    def __init__(self, archive: zipfile.ZipFile):
        with archive.open('station_information.json') as f:
            self.stations = {
                station["station_id"]: Location(
                    id_=station["station_id"],
                    lat=station["lat"],
                    lng=station["lon"],
                ) for station in read_json_file(f)["data"]["stations"]
            }
