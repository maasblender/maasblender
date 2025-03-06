# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import itertools
import typing
import dataclasses
from datetime import date, timedelta, datetime, time

from core import Trip, Route, Service, StopTime, Stop, StopTimeWithDateTime, Path, TripLocation, \
    DeviatedStopTimeWithDateTime, TemporaryStop, User, AbstractStopTime, StopLike, AbstractStopTimeWithDateTime

T = typing.TypeVar("T")


def _triplewise(it: typing.Iterable[T]):
    a, b, c = itertools.tee(it, 3)
    next(b, None)
    next(c, None)
    next(c, None)
    return zip(a, b, c)


def _find_stop(
    stop_times_with: typing.List[AbstractStopTime], stop: Stop, at_date: date
) -> typing.Iterator[StopTimeWithDateTime]:
    for stop_time in stop_times_with:
        match stop_time:
            case StopTime() as st:
                if st.stop == stop:
                    yield StopTimeWithDateTime(stop_time=st, reference_date=at_date)


def _find_location(
    stop_times_with: typing.List[AbstractStopTime], loc: TripLocation, at_date: date
) -> typing.Iterator[
    tuple[StopTimeWithDateTime, StopTimeWithDateTime]
]:
    for loc1, loc2, loc3 in _triplewise(stop_times_with):
        match loc2:
            case StopTime():
                pass
            case TripLocation() as p:
                if p == loc:
                    yield (
                        StopTimeWithDateTime(stop_time=loc1, reference_date=at_date),
                        StopTimeWithDateTime(stop_time=loc3, reference_date=at_date),
                    )
            case _:
                raise TypeError(f"illegal type included in stop_times_with: {type(loc2)=}")


def _find_org(
    stop_times_with: typing.List[AbstractStopTime], org: StopLike, at: date
) -> typing.Iterator[
    typing.Tuple[StopTimeWithDateTime, TemporaryStop | None]
]:
    match org:
        case Stop() as p:
            for stop in _find_stop(stop_times_with, p, at):
                yield stop, None
        case TemporaryStop() as p:
            for stop, _ in _find_location(stop_times_with, p.location, at):
                yield stop, p
        case _:
            raise TypeError(f"illegal type: {type(org)=}")


def _find_dst(
    stop_times_with: typing.List[AbstractStopTime], dst: StopLike, at: date
) -> typing.Iterator[
    typing.Tuple[TemporaryStop | None, StopTimeWithDateTime]
]:
    match dst:
        case Stop() as p:
            for stop in _find_stop(stop_times_with, p, at):
                yield None, stop
        case TemporaryStop() as p:
            for _, stop in _find_location(stop_times_with, p.location, at):
                yield p, stop
        case _:
            raise TypeError(f"illegal type: {type(dst)=}")


def _get_paths(
    stop_times_with: typing.List[AbstractStopTime], org: StopLike, dst: StopLike, at: date
) -> typing.Iterator[Path]:
    for stop_time_org, tstop_org in _find_org(stop_times_with, org, at):
        for tstop_dst, stop_time_dst in _find_dst(stop_times_with, dst, at):
            if stop_time_org.departure < stop_time_dst.arrival:
                yield Path(pick_up=stop_time_org, drop_off=stop_time_dst, pick_up_stop=tstop_org, drop_off_stop=tstop_dst)


def get_deviated_stops(
        location_id: str, departure: timedelta, arrival: timedelta, at_date: date, users: typing.Dict[str, User]
) -> typing.List[DeviatedStopTimeWithDateTime]:
    tstops: typing.List[TemporaryStop] = []
    for user in users.values():
        if tstop := user.path.pick_up_stop:  # if pick up on deviated route
            if tstop.location.location_id == location_id:
                tstops.append(tstop)
        if tstop := user.path.drop_off_stop:  # if drop off on deviated route
            if tstop.location.location_id == location_id:
                tstops.append(tstop)
    if not tstops:
        return []
    dt_initial = datetime.combine(at_date, time()) + departure
    duration: timedelta = arrival - departure
    n = len(tstops) + 1
    return [
        DeviatedStopTimeWithDateTime(tstop, dt_initial + i / n * duration)
        for i, tstop in enumerate(tstops, 1)
    ]


@dataclasses.dataclass(frozen=True)
class SingleTrip(Trip):
    """Sequence of two or more stops that occur during a specific time period."""

    route: Route
    service: Service
    stop_times_with: typing.List[AbstractStopTime]
    block_id: str = ""

    def __post_init__(self):
        assert len(self.stop_times) >= 2
        assert isinstance(self.stop_times_with[0], StopTime)
        assert isinstance(self.stop_times_with[-1], StopTime)

    @property
    def stop_times(self) -> typing.List[StopTime]:
        return [stop_time for stop_time in self.stop_times_with if isinstance(stop_time, StopTime)]

    @property
    def locations(self) -> typing.List[TripLocation]:
        return [stop_time for stop_time in self.stop_times_with if isinstance(stop_time, TripLocation)]

    @property
    def stops(self) -> typing.List[Stop]:
        return [stop_time.stop for stop_time in self.stop_times]

    def is_operation(self, at: date) -> bool:
        return self.service.is_operation(at)

    def stop_times_at(self, at_date: date) -> typing.List[StopTimeWithDateTime]:
        return [
            StopTimeWithDateTime(stop_time=stop_time, reference_date=at_date)
            for stop_time in self.stop_times
        ]

    def iter_stop_times_at(
        self, at_date: date, users: typing.Dict[str, User]
    ) -> typing.Iterator[AbstractStopTimeWithDateTime]:
        yield StopTimeWithDateTime(stop_time=self.stop_times_with[0], reference_date=at_date)
        for loc1, loc2, loc3 in _triplewise(self.stop_times_with):
            match loc2:
                case StopTime() as p:
                    yield StopTimeWithDateTime(stop_time=p, reference_date=at_date)
                case TripLocation() as p:
                    tstops = get_deviated_stops(p.location_id, loc1.departure, loc3.arrival, at_date, users)
                    yield from tstops
                case _:
                    raise TypeError(f"illegal type included in stop_times_with: {type(loc2)=}")
        yield StopTimeWithDateTime(stop_time=self.stop_times_with[-1], reference_date=at_date)

    def start_time(self, at: date):
        return list(self.stop_times_at(at))[0].arrival

    def end_time(self, at: date):
        return list(self.stop_times_at(at))[-1].departure

    def paths(self, org: StopLike, dst: StopLike, at: date):
        if not self.service.is_operation(at):
            return

        # This is redundant because a single trip may contain multiple identical stations.
        stop_times_with = self.stop_times_with
        yield from _get_paths(stop_times_with, org, dst, at)


@dataclasses.dataclass(frozen=True)
class BlockTrip(Trip):
    """Sequence of trips which belong to a block"""

    trips: typing.List[SingleTrip]

    def __post_init__(self):
        assert len(self.trips) >= 2
        assert len(set(trip.block_id for trip in self.trips)) <= 1
        assert self.trips[0].block_id != ""

        # The following assertion is generally true for most cases,
        assert (
            self.trips[0].stop_times[0].departure
            < self.trips[1].stop_times[0].departure
        )

    @property
    def stops(self) -> typing.List[Stop]:
        return [stop_time.stop for trip in self.trips for stop_time in trip.stop_times]

    def is_operation(self, at: date) -> bool:
        return any([trip.service.is_operation(at) for trip in self.trips])

    def stop_times_at(self, at: date):
        # Depending on the service configuration, a block trip can be split into multiple trips
        # instead of being treated as a single block trip depending on the day of the week,
        # but this will not be considered for now.
        return [
            StopTimeWithDateTime(stop_time=stop_time, reference_date=at)
            for trip in self.trips
            if trip.service.is_operation(at)
            for stop_time in trip.stop_times
        ]

    def iter_stop_times_at(
        self, at_date: date, users: typing.Dict[str, User]
    ) -> typing.Iterator[AbstractStopTimeWithDateTime]:
        stop_times_with = self.stop_times_with(at_date)
        yield StopTimeWithDateTime(stop_time=stop_times_with[0], reference_date=at_date)
        for loc1, loc2, loc3 in _triplewise(stop_times_with):
            match loc2:
                case StopTime() as p:
                    yield StopTimeWithDateTime(stop_time=p, reference_date=at_date)
                case TripLocation() as p:
                    tstops = get_deviated_stops(p.location_id, loc1.departure, loc3.arrival, at_date, users)
                    yield from tstops
                case _:
                    raise TypeError(f"illegal type included in stop_times_with: {type(loc2)=}")
        yield StopTimeWithDateTime(stop_time=stop_times_with[-1], reference_date=at_date)

    def stop_times_with(self,  at: date) -> typing.List[AbstractStopTime]:
        return [
            stop_time
            for trip in self.trips
            if trip.service.is_operation(at)
            for stop_time in trip.stop_times_with
        ]

    def start_time(self, at: date):
        return list(self.stop_times_at(at))[0].arrival

    def end_time(self, at: date):
        return list(self.stop_times_at(at))[-1].departure

    def paths(self, org: StopLike, dst: StopLike, at: date):
        if not self.is_operation(at):
            return

        stop_times_with = self.stop_times_with(at)
        yield from _get_paths(stop_times_with, org, dst, at)
