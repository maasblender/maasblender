# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import logging
import typing

import simpy

from core import calc_distance
from event import EventQueue, DepartedEvent, ArrivedEvent
from location import Station

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class OperatorParameter:
    start_time: float  # [min]
    end_time: float  # [min]
    interval: float  # [min]
    speed: float  # [m/min]
    loading_time: int  # (min/mobilities)
    capacity: int


@dataclasses.dataclass(frozen=True)
class OperatedStation:
    station: Station
    proper_upper: int  # If the number of vehicles exceeds this value, they may be eligible for allocation rounding.
    proper_lower: int  # The Station with vehicle counts below this value may be eligible for allocation rounding.

    @property
    def proper(self):
        # The number of vehicles is allocated so that the number of vehicles reaches the appropriate value.
        # The appropriate value is the average of the proper_upper and proper_lower limits.
        return (self.proper_upper + self.proper_lower) / 2


@dataclasses.dataclass(frozen=True)
class Operation:
    org: OperatedStation
    dst: OperatedStation
    number_of_mobilities: int


class Operator:
    """The entity that operates a mobility."""

    def __init__(self, env: simpy.Environment, queue: EventQueue, params: OperatorParameter, location: OperatedStation):
        self.env = env
        self.queue = queue
        self.v = params.speed
        self.loading_time = params.loading_time
        self._capacity = params.capacity
        self._location: OperatedStation = location

    @property
    def location(self):
        return self._location

    def run(self, operation: Operation):
        dst = operation.dst
        yield self.env.process(self.move(operation.org))

        # reserve mobilities in the org parking and areas in the dst parking
        # pick all mobilities to be operated
        mobilities = []
        for _ in range(min((operation.number_of_mobilities, self._capacity))):
            if self.location.station.any_reservable_mobility and dst.station.any_reservable_dock:
                mobility = self.location.station.reserve_mobility()
                dst.station.reserve_dock(mobility)
                self.location.station.pick(mobility)
                mobilities.append(mobility)
                # notify event
                self.queue.enqueue(DepartedEvent(
                    mobility=mobility,
                    location=operation.org.station,
                ))
        yield self.env.timeout(self.loading_time * len(mobilities))
        yield self.env.process(self.move(operation.dst))
        yield self.env.timeout(self.loading_time * len(mobilities))

        # park all mobilities to be operated
        for mobility in mobilities:
            self.location.station.park(mobility)
            # notify event
            self.queue.enqueue(ArrivedEvent(
                mobility=mobility,
                location=operation.dst.station,
            ))

    def move(self, to: OperatedStation):
        yield self.env.timeout(calc_distance(self.location.station, to.station) / self.v)
        self._location = to


class Manager:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self.begin_time = 360.0
        self.end_time = 720.0
        self.interval = 15.0
        self.stations: typing.Iterable[OperatedStation] = []
        self.operators: typing.Iterable[Operator] = []

    @property
    def operations(self):
        def num_mobilities(station: OperatedStation):
            return len(station.station.reservable_mobilities)

        def difference_actual_between_proper(station: OperatedStation):
            return abs(num_mobilities(station) - station.proper)

        org_candidates = sorted([
            station for station in self.stations
            if num_mobilities(station) > station.proper_upper
        ], key=difference_actual_between_proper, reverse=True)

        dst_candidates = sorted([
            station for station in self.stations
            if num_mobilities(station) < station.proper_lower
        ], key=difference_actual_between_proper, reverse=True)

        for org, dst in zip(org_candidates, dst_candidates):
            yield Operation(
                org=org, dst=dst,
                number_of_mobilities=int(
                    (difference_actual_between_proper(org) + difference_actual_between_proper(dst)) / 2
                )
            )

    def setup(self, stations: typing.Iterable[OperatedStation], operators: typing.Iterable[Operator],
              params: OperatorParameter):
        self.stations = stations
        self.operators = operators
        self.begin_time = params.start_time
        self.end_time = params.end_time
        self.interval = params.interval

    def run(self):
        while True:
            yield self.env.timeout(self.begin_time)
            while self.env.now % 1440 < self.end_time:
                yield self.env.all_of(
                    {
                        self.env.process(operator.run(operation))
                        for operator, operation in zip(self.operators, self.operations)
                    } | {
                        self.env.timeout(self.interval)
                    }
                )
            yield self.env.timeout(1440 - self.end_time)
