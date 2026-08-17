# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import itertools
from datetime import date

from core import Path, Route, Service, Stop, StopTime, StopTimeWithDateTime, Trip


@dataclasses.dataclass(frozen=True)
class SingleTrip(Trip):
    """Sequence of two or more stops that occur during a specific time period."""

    route: Route
    service: Service
    stop_times: list[StopTime]
    block_id: str = ""

    def __post_init__(self):
        assert len(self.stop_times) >= 2

    @property
    def stops(self) -> list[Stop]:
        return [stop_time.stop for stop_time in self.stop_times]

    def is_operation(self, at: date) -> bool:
        return self.service.is_operation(at)

    def stop_times_at(self, at: date):
        return [
            StopTimeWithDateTime(stop_time=stop_time, reference_date=at)
            for stop_time in self.stop_times
        ]

    def start_time(self, at: date):
        return next(iter(self.stop_times_at(at))).arrival

    def end_time(self, at: date):
        return list(self.stop_times_at(at))[-1].departure

    def paths(self, org: Stop, dst: Stop, at: date):
        if not self.service.is_operation(at):
            return

        # This is redundant because a single trip may contain multiple identical stations.
        for stop_time_org in self.stop_times_at(at):
            if stop_time_org.stop == org:
                for stop_time_dst in self.stop_times_at(at):
                    if (
                        stop_time_dst.stop == dst
                        and stop_time_org.departure < stop_time_dst.arrival
                    ):
                        yield Path(pick_up=stop_time_org, drop_off=stop_time_dst)


@dataclasses.dataclass(frozen=True)
class BlockTrip(Trip):
    """Sequence of trips which belong to a block"""

    trips: list[SingleTrip]

    def __post_init__(self):
        assert len(self.trips) >= 2
        assert len({trip.block_id for trip in self.trips}) == 1
        assert self.trips[0].block_id != ""

        # The following assertion is generally true for most cases,
        # Trips in a block are expected to be ordered by first stop departure.
        assert (
            self.trips[0].stop_times[0].departure
            < self.trips[1].stop_times[0].departure
        )

    @property
    def stops(self) -> list[Stop]:
        return [stop_time.stop for trip in self.trips for stop_time in trip.stop_times]

    def is_operation(self, at: date) -> bool:
        return any(trip.service.is_operation(at) for trip in self.trips)

    def _normalized_stop_times(self, at: date) -> list[StopTime]:
        operating_trips = [trip for trip in self.trips if trip.service.is_operation(at)]
        if not operating_trips:
            return []

        normalized: list[StopTime] = [
            StopTime(
                stop=stop_time.stop,
                arrival=stop_time.arrival,
                departure=stop_time.departure,
            )
            for stop_time in operating_trips[0].stop_times
        ]

        for previous_trip, current_trip in itertools.pairwise(operating_trips):
            previous_last = normalized[-1]
            current_first = current_trip.stop_times[0]
            assert (
                previous_trip.stop_times[0].departure
                < current_trip.stop_times[0].departure
            )
            if previous_last.stop == current_first.stop:
                normalized[-1] = StopTime(
                    stop=previous_last.stop,
                    arrival=previous_last.arrival,
                    departure=current_first.departure,
                )
                next_trip_stop_times = current_trip.stop_times[1:]
            else:
                normalized[-1] = StopTime(
                    stop=previous_last.stop,
                    arrival=previous_last.arrival,
                    departure=previous_last.arrival,
                )
                normalized.append(
                    StopTime(
                        stop=current_first.stop,
                        arrival=current_first.departure,
                        departure=current_first.departure,
                    )
                )
                next_trip_stop_times = current_trip.stop_times[1:]

            normalized.extend(
                StopTime(
                    stop=stop_time.stop,
                    arrival=stop_time.arrival,
                    departure=stop_time.departure,
                )
                for stop_time in next_trip_stop_times
            )

        return normalized

    def stop_times_at(self, at: date):
        # Depending on the service configuration, a block trip can be split into multiple trips
        # instead of being treated as a single block trip depending on the day of the week,
        # but this will not be considered for now.
        return [
            StopTimeWithDateTime(stop_time=stop_time, reference_date=at)
            for stop_time in self._normalized_stop_times(at)
        ]

    def start_time(self, at: date):
        return next(iter(self.stop_times_at(at))).arrival

    def end_time(self, at: date):
        return list(self.stop_times_at(at))[-1].departure

    def paths(self, org: Stop, dst: Stop, at: date):
        if not self.is_operation(at):
            return

        for stop_time_org in self.stop_times_at(at):
            if stop_time_org.stop == org:
                for stop_time_dst in self.stop_times_at(at):
                    if (
                        stop_time_dst.stop == dst
                        and stop_time_org.departure < stop_time_dst.arrival
                    ):
                        yield Path(pick_up=stop_time_org, drop_off=stop_time_dst)
