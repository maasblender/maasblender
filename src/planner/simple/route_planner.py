# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import re
import typing
import logging

from core import Location, Path, Trip, MobilityNetwork


logger = logging.getLogger("planner")


class Planner:
    async def meters_for_all_stops_combinations(self, stops: list[Location]):
        raise NotImplementedError()

    def plan(self, org: Location, dst: Location, dept: float) -> typing.List[Path]:
        raise NotImplementedError()


pattern = re.compile(r".+:(.*)")


class DirectPathPlanner(Planner):
    def __init__(self, networks: typing.Collection[MobilityNetwork]):
        super().__init__()
        self.networks = list(networks)

    async def meters_for_all_stops_combinations(self, stops: list[Location]):
        def _distance(org: Location, dst: Location):
            if org.id_ == dst.id_:
                return 0
            distance = org.distance(dst)
            return distance

        yield ",".join(stop.id_ for stop in stops) + "\n"
        for stop_a in stops:
            vals = [
                _distance(org=stop_a, dst=stop_b)
                for stop_b in stops
            ]
            yield ",".join(str(v) for v in vals) + "\n"

    def _shortest_paths(self, org: Location, dst: Location, dept: float):
        return sorted((network.shortest_path(org, dst, dept) for network in self.networks), key=lambda path: path.arrv)

    def plan(self, org: Location, dst: Location, dept: float):
        paths = self._shortest_paths(org, dst, dept)
        paths = filter(lambda path: path.arrv < float('inf'), paths)

        return [
            Path([
                Trip(
                    org=trip.org,
                    dst=trip.dst,
                    dept=trip.dept,
                    arrv=trip.arrv,
                    service=trip.service
                )
                for trip in path.trips
            ])
            for path in paths
        ]
