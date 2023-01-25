# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
from datetime import date, datetime, timedelta

from core import Location

class Stop(Location):
    """ Stops where vehicles pick up or drop off riders. """
    def __init__(self, id_: str, lat: float, lng: float, name = None):
        super().__init__(id_, lat, lng)
        self.name = name if name else id_ 

class Group:
    """ Group of stops """

    def __init__(self, group_id: str, name: str, locations: list[Stop] = None):
        self.group_id = group_id
        self.name = name
        self.locations: list[Stop] = locations if locations else []


class Service:
    """ A set of dates when service is available for one or more routes.

    Indicates whether the service operates for each day of the week in the date range specified in the start_date and
    end_date fields. Exceptions for particular dates can be explicitly activated or deactivated by date. """

    def __init__(self, start_date: date, end_date: date,
                 monday=False, tuesday=False, wednesday=False, thursday=False, friday=False,
                 saturday=False, sunday=False):
        self._start_day = start_date
        self._end_day = end_date
        self._weekday = [monday, tuesday, wednesday, thursday, friday, saturday, sunday]
        self._added_exceptions: typing.List[date] = []
        self._removed_exceptions: typing.List[date] = []

    def append_exception(self, exception_date: date, added=True):
        if added:
            assert exception_date not in self._removed_exceptions
            self._added_exceptions.append(exception_date)
        else:
            assert exception_date not in self._added_exceptions
            self._removed_exceptions.append(exception_date)

    def is_operation(self, at: date):
        if at in self._added_exceptions:
            return True
        if at in self._removed_exceptions:
            return False

        if self._start_day <= at <= self._end_day:
            return self._weekday[at.weekday()]

        return False


class StopTime(typing.NamedTuple):
    """ Times that a vehicle arrives at and departs from stops for each trip."""

    group: Group
    start_window: timedelta
    end_window: timedelta


class Trip:
    """ Sequence of two or more stops that occur during a specific time period. """

    def __init__(self, service: Service, stop_time: StopTime):
        self.service = service
        self.stop_time = stop_time
