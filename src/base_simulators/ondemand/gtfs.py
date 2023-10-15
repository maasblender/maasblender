# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import datetime
import csv
import io
import zipfile
import re

from .core import Stop, Group, StopTime, Service, Trip


p = re.compile(r"(\d\d?):(\d\d?):(\d\d?)")


def str_time(time: str):
    if match := p.fullmatch(time):
        hours, minutes, seconds = match.groups()
        return datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
    return None


def str_date(time: str):
    return datetime.datetime.strptime(time, '%Y%m%d').date()


class GtfsFlexFilesReader:
    def __init__(self):
        self.stops: typing.Dict[str, Stop] = {}
        self.location_groups: typing.Dict[str, Group] = {}
        self._stop_times: typing.Dict[str, StopTime] = {}
        self._services: typing.Dict[str, Service] = {}
        self.trips: typing.Dict[str, Trip] = {}

    def read(self, archive: zipfile.ZipFile):
        for filename, parse in {
            "stops.txt": self._parse_stop,
            "location_groups.txt": self._parse_location_groups,
            'calendar.txt': self._parse_calender,
            'calendar_dates.txt': self._parse_calender_dates,
            "stop_times.txt": self._parse_stop_time,
            "trips.txt": self._parse_trip
        }.items():
            with archive.open(filename) as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                    parse(row)
        return self

    def _parse_stop(self, row: typing.Mapping[str, str]):
        self.stops.update({
            row["stop_id"]: Stop(
                stop_id=row["stop_id"],
                name=row["stop_name"],
                lat=float(row["stop_lat"]),
                lng=float(row["stop_lon"])
            )
        })

    def _parse_location_groups(self, row: typing.Mapping[str, str]):
        group_id = row["location_group_id"]
        group = self.location_groups.get(group_id, None)
        if not group:
            group = Group(
                group_id=group_id,
                name=row["location_group_name"]
            )
            self.location_groups[group_id] = group
        group.locations.append(self.stops[row["location_id"]])

    def _parse_calender(self, row: typing.Mapping[str, str]):
        self._services.update({
            row["service_id"]: Service(
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
        })

    def _parse_calender_dates(self, row: typing.Mapping[str, str]):
        self._services[row["service_id"]].append_exception(
            exception_date=str_date(row["date"]),
            added=row["exception_type"] == "1"
        )

    def _parse_stop_time(self, row: typing.Mapping[str, str]):
        self._stop_times.update({
            row["trip_id"]: StopTime(
                group=self.location_groups[row["stop_id"]],
                start_window=str_time(row["start_pickup_dropoff_window"]),
                end_window=str_time(row["end_pickup_dropoff_window"])
            )
        })

    def _parse_trip(self, row: typing.Mapping[str, str]):
        self.trips.update({
            row["trip_id"]: Trip(
                service=self._services[row["service_id"]],
                stop_time=self._stop_times[row["trip_id"]]
            )
        })
