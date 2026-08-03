# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import re
import typing

from core import Location, MobilityNetwork, Path, Trip
from jschema.response import DistanceMatrix

logger = logging.getLogger(__name__)


class Planner:
    def meters_for_all_stops_combinations(
        self, stops: list[Location]
    ) -> DistanceMatrix:
        raise NotImplementedError()

    def plan(self, org: Location, dst: Location, dept: float) -> list[Path]:
        raise NotImplementedError()


pattern = re.compile(r".+:(.*)")


class DirectPathPlanner(Planner):
    def __init__(self, networks: typing.Collection[MobilityNetwork]):
        super().__init__()
        self.networks = list(networks)

    def meters_for_all_stops_combinations(
        self, stops: list[Location]
    ) -> DistanceMatrix:
        def _distance(org: Location, dst: Location):
            if org.id_ == dst.id_:
                return 0
            distance = org.distance(dst)
            return distance

        matrix = [
            [_distance(org=stop_a, dst=stop_b) for stop_b in stops] for stop_a in stops
        ]
        return DistanceMatrix(stops=[stop.id_ for stop in stops], matrix=matrix)

    def _shortest_paths(self, org: Location, dst: Location, dept: float):
        return sorted(
            (network.shortest_path(org, dst, dept) for network in self.networks),
            key=lambda path: path.arrv,
        )

    def plan(self, org: Location, dst: Location, dept: float):
        paths = self._shortest_paths(org, dst, dept)
        paths = filter(lambda path: path.arrv < float("inf"), paths)

        return [
            Path(
                [
                    Trip(
                        org=trip.org,
                        dst=trip.dst,
                        dept=trip.dept,
                        arrv=trip.arrv,
                        service=trip.service,
                    )
                    for trip in path.trips
                ]
            )
            for path in paths
        ]
