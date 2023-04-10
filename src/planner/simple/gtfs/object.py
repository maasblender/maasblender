# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from datetime import datetime, date, time, timedelta

from core import Location


class StopTime(typing.NamedTuple):
    """ Times that a vehicle arrives at and departs from stops for each trip."""

    stop: Location
    arrival: timedelta
    departure: timedelta


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


class StopTimeWithDatetime:
    def __init__(self, stop_time: StopTime, at: date):
        self._stop_time = stop_time
        self._at = at

    @property
    def stop(self):
        return self._stop_time.stop

    @property
    def arrival(self):
        return datetime.combine(self._at, time()) + self._stop_time.arrival

    @property
    def departure(self):
        return datetime.combine(self._at, time()) + self._stop_time.departure


class Trip:
    """ Sequence of two or more stops that occur during a specific time period. """

    def __init__(self, service: Service, stop_times: typing.List[StopTime]):
        assert len(stop_times) >= 2
        self.service = service
        self._stop_times = stop_times

    def stop_times(self, at: date) -> typing.List[StopTimeWithDatetime]:
        return [
            StopTimeWithDatetime(stop_time, at)
            for stop_time in self._stop_times
        ] if self.service.is_operation(at) else []
