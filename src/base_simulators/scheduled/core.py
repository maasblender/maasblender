# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import dataclasses
from enum import Enum, auto
from datetime import date, time, datetime, timedelta


class EventType(str, Enum):
    DEPARTED = 'DEPARTED'
    ARRIVED = 'ARRIVED'
    RESERVED = 'RESERVED'


class UserStatus(Enum):
    """ A user is in one of the following states """
    RESERVED = auto()
    WAITING = auto()
    RIDING = auto()


class Agency(typing.NamedTuple):
    """ Transit agencies with service represented in this dataset. """

    agency_name: str
    agency_url: str
    agency_timezone: str


class Stop(typing.NamedTuple):
    """ Stops where vehicles pick up or drop off riders. """

    stop_id: str
    name: str
    lat: float
    lng: float


class Route(typing.NamedTuple):
    """ Transit routes. A route is a group of trips that are displayed to riders as a single service. """

    agency: Agency
    long_name: str
    short_name: str
    route_type: str


@dataclasses.dataclass(init=False)
class StopTime:
    """ Times that a vehicle arrives at and departs from stops for each trip."""
    stop: Stop
    arrival: timedelta
    departure: timedelta

    def __init__(self, stop: Stop, arrival: timedelta = None, departure: timedelta = None):
        assert arrival or departure
        self.stop = stop
        self.arrival = arrival if arrival else departure
        self.departure = departure if departure else arrival


@dataclasses.dataclass(frozen=True)
class StopTimeWithDateTime:
    stop_time: StopTime
    reference_date: date

    @property
    def stop(self):
        return self.stop_time.stop

    @property
    def arrival(self):
        return datetime.combine(self.reference_date, time()) + self.stop_time.arrival

    @property
    def departure(self):
        return datetime.combine(self.reference_date, time()) + self.stop_time.departure


@dataclasses.dataclass
class Service:
    """ A set of dates when service is available for one or more routes.

    Indicates whether the service operates for each day of the week in the date range specified in the start_date and
    end_date fields. Exceptions for particular dates can be explicitly activated or deactivated by date. """

    _start_day: date
    _end_day: date
    _weekday: tuple[bool, bool, bool, bool, bool, bool, bool]
    _added_exceptions: typing.List[date]
    _removed_exceptions: typing.List[date]

    def __init__(self, start_date: date, end_date: date,
                 monday=False, tuesday=False, wednesday=False, thursday=False, friday=False,
                 saturday=False, sunday=False):
        self._start_day = start_date
        self._end_day = end_date
        self._weekday = (monday, tuesday, wednesday, thursday, friday, saturday, sunday)
        self._added_exceptions = []
        self._removed_exceptions = []

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


@dataclasses.dataclass(frozen=True)
class Trip:
    """ Sequence of two or more stops that occur during a specific time period. """
    route: Route
    service: Service
    stop_times: typing.List[StopTime]

    def __post_init__(self):
        assert len(self.stop_times) >= 2

    def stop_times_at(self, at_date: date):
        return [
            StopTimeWithDateTime(stop_time=stop_time, reference_date=at_date)
            for stop_time in self.stop_times
        ]

    def start_time(self, at: date):
        return list(self.stop_times_at(at))[0].arrival

    def end_time(self, at: date):
        return list(self.stop_times_at(at))[-1].departure

    def paths(self, org: Stop, dst: Stop, at: date):
        if not self.service.is_operation(at):
            return

        for stop_time_org in self.stop_times_at(at):
            if stop_time_org.stop == org:
                for stop_time_dst in self.stop_times_at(at):
                    if stop_time_dst.stop == dst and stop_time_org.departure < stop_time_dst.arrival:
                        yield Path(pick_up=stop_time_org, drop_off=stop_time_dst)


@dataclasses.dataclass(frozen=True)
class Path:
    pick_up: StopTimeWithDateTime
    drop_off: StopTimeWithDateTime

    def __lt__(self, other: 'Path'):
        if not isinstance(other, Path):
            return NotImplementedError()
        return self.drop_off.arrival < other.drop_off.arrival if self.drop_off.arrival != other.drop_off.arrival else\
            self.duration < other.duration

    @property
    def duration(self):
        return self.drop_off.arrival - self.pick_up.departure

    @property
    def org(self):
        return self.pick_up.stop

    @property
    def dst(self):
        return self.drop_off.stop

    @property
    def departure(self):
        return self.pick_up.departure

    @property
    def arrival(self):
        return self.drop_off.arrival


@dataclasses.dataclass
class User:
    user_id: str
    path: Path
    _status: UserStatus = UserStatus.RESERVED

    @property
    def status(self):
        return self._status

    def wait(self):
        assert self.status == UserStatus.RESERVED, f"{self.status}"
        self._status = UserStatus.WAITING

    def ride(self):
        assert self.status == UserStatus.WAITING
        self._status = UserStatus.RIDING


class Mobility:
    """ Mobility is moving according to a timetable (`Trip`) """

    def __init__(self, mobility_id, trip: Trip):
        self.mobility_id = mobility_id
        self._trip = trip

    @property
    def current_datetime(self) -> datetime:
        raise NotImplementedError()

    @property
    def stop(self) -> Stop:
        raise NotImplementedError()

    def trip(self, at: date = None):
        if at is None:
            at = self.operation_date

        return self._trip if self._trip.service.is_operation(at) else None

    @property
    def operation_date(self):
        """ Returns the operation date from the current time.

        If the previous day's operation has not been completed, returns the previous day's date.
        If the previous day's operation has been completed and there are some operations for the current day,
        returns the date of the current day.
        If the previous day's operation has been completed and there is no operation for the current day,
        returns the date of the current day.
        If today's operation has been completed, returns the next day's date.
        """

        date_time = self.current_datetime
        today_date = date_time.date()

        before_date = today_date - timedelta(days=1)
        if trip := self.trip(before_date):
            # If the previous day's operation has not been completed, returns the previous day's date.
            if date_time < trip.end_time(before_date):
                return before_date

        if trip := self.trip(today_date):
            # If today's operation has been completed, returns the next day's date.
            if trip.end_time(today_date) <= date_time:
                return date_time.date() + timedelta(days=1)

        return today_date

    def paths(self, org: Stop, dst: Stop, at: date):
        if trip := self.trip(at):
            for path in trip.paths(org, dst, at):
                yield path
