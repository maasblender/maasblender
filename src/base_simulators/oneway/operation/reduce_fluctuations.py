# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import logging
import typing
import dataclasses

import simpy

from location import Station


logger = logging.getLogger("operation")


@dataclasses.dataclass(frozen=True)
class OperatedStation:
    station: Station
    proper_upper: int  # 車両数が適正上限値を上回る場合に配回送の対象になり得る。
    proper_lower: int  # 車両数が適正下限値を下回る場合に配回送の対象になり得る。

    @property
    def proper(self):
        return (self.proper_upper + self.proper_lower) / 2  # 車両数が適正値に近づくように配回送される。適正値は適正上限値と適正下限値の平均とする。


@dataclasses.dataclass(frozen=True)
class Operation:
    org: OperatedStation
    dst: OperatedStation
    number_of_mobilities: int


class Operator:
    """The entity that operates a mobility."""

    def __init__(self, env: simpy.Environment, location: OperatedStation, capacity: int):
        self.env = env
        self.v = 1000  # (m/min)
        self.loading_time = 1  # (min/mobilities)
        self._location: OperatedStation = location
        self._capacity = capacity

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

        yield self.env.timeout(self.loading_time * len(mobilities))
        yield self.env.process(self.move(operation.dst))
        yield self.env.timeout(self.loading_time * len(mobilities))

        # park all mobilities to be operated
        for mobility in mobilities:
            self.location.station.park(mobility)

    def move(self, to: OperatedStation):
        yield self.env.timeout(self.location.station.distance(to.station) / self.v)
        self._location = to


class Manager:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self.begin_time = 360
        self.end_time = 720
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

    def setup(self, stations: typing.Iterable[OperatedStation], operators: typing.Iterable[Operator]):
        self.stations = stations
        self.operators = operators

    def run(self):
        while True:
            yield self.env.timeout(self.begin_time)
            while self.env.now % 1440 < self.end_time:
                yield self.env.all_of({
                    self.env.process(operator.run(operation))
                    for operator, operation in zip(self.operators, self.operations)
                } | {
                    self.env.timeout(15)  # interval
                })
            yield self.env.timeout(1440 - self.end_time)
