# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import io
import zipfile
import json


def read_json_file(f):
    return json.load(io.TextIOWrapper(f, encoding="utf-8"))


class GbfsFiles:
    def __init__(self, archive: zipfile.ZipFile):
        with archive.open('station_information.json') as f:
            self.station_information = read_json_file(f)

        with archive.open('free_bike_status.json') as f:
            self.free_bike_status = read_json_file(f)
