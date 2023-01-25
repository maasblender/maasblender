# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import collections
import csv
import typing
import datetime
import io
import zipfile
import re

from core import Location
from gtfs.object import StopTime, Service, Trip


p = re.compile(r"(\d\d?):(\d\d?):(\d\d?)")


def str_time(time: str):
    if match := p.fullmatch(time):
        hours, minutes, seconds = match.groups()
        return datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
    return None


def str_date(time: str):
    return datetime.datetime.strptime(time, '%Y%m%d').date()


class FileReader:
    def __init__(self, f, parse: typing.Callable[[typing.Dict[str, str]], typing.Tuple]):
        self.reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        self.parse = parse

    def __iter__(self):
        return self

    def __next__(self):
        return self.parse(next(self.reader))


def parse_stop(row: typing.Dict[str, str]):
    return row["stop_id"], Location(
        id_=row["stop_id"],
        lat=float(row["stop_lat"]),
        lng=float(row["stop_lon"])
    )


def parse_calendar(row: typing.Dict[str, str]):
    return row["service_id"], Service(
        start_date=str_date(row["start_date"]),
        end_date=str_date(row["end_date"]),
        monday=row["monday"] == "1",
        tuesday=row["tuesday"] == "1",
        wednesday=row["wednesday"] == "1",
        thursday=row["thursday"] == "1",
        friday=row["friday"] == "1",
        saturday=row["saturday"] == "1",
        sunday=row["sunday"] == "1",
    )


def parse_calendar_dates(row: typing.Dict[str, str]):
    return row["service_id"], str_date(row["date"]), row["exception_type"] == "1"


class FilesReader:
    def __init__(self, archive: zipfile.ZipFile):
        self.stops: typing.Dict[str, Location] = {}
        self._stop_times: typing.Dict[str, typing.List[StopTime]] = collections.defaultdict(list)
        self._services: typing.Dict[str, Service] = {}
        self.trips: typing.Dict[str, Trip] = {}

        with archive.open('stops.txt') as f:
            for k, v in FileReader(f, parse_stop):
                self.stops.update({k: v})

        with archive.open('calendar.txt') as f:
            for k, v in FileReader(f, parse_calendar):
                self._services.update({k: v})

        with archive.open('calendar_dates.txt') as f:
            for service_id, exception_date, is_added in FileReader(f, parse_calendar_dates):
                self._services[service_id].append_exception(exception_date, is_added)

        with archive.open("stop_times.txt") as f:
            for k, v in FileReader(f, self.parse_stop_time):
                self._stop_times[k].append(v)

        with archive.open("trips.txt") as f:
            for k, v in FileReader(f, self.parse_trip):
                self.trips.update({k: v})

    def parse_stop_time(self, row: typing.Dict[str, str]):
        return row["trip_id"], StopTime(
            stop=self.stops[row["stop_id"]],
            arrival=str_time(row["arrival_time"]),
            departure=str_time(row["departure_time"]),
        )

    def parse_trip(self, row: typing.Dict[str, str]):
        return row["trip_id"], Trip(
            service=self._services[row["service_id"]],
            stop_times=self._stop_times[row["trip_id"]]
        )
