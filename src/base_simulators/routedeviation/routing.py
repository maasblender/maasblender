# SPDX-FileCopyrightText: 2026 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import itertools
import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import aiohttp
from core import DeviatedStopTimeWithDateTime, Stop, TemporaryStop


class Router(ABC):
    @abstractmethod
    async def plan(
        self,
        origin: Stop,
        destination: Stop,
        temporary_stops: list[TemporaryStop],
        departure: datetime,
        arrival: datetime,
    ) -> list[DeviatedStopTimeWithDateTime] | None:
        raise NotImplementedError


class EqualIntervalRouter(Router):
    async def plan(
        self,
        origin: Stop,
        destination: Stop,
        temporary_stops: list[TemporaryStop],
        departure: datetime,
        arrival: datetime,
    ) -> list[DeviatedStopTimeWithDateTime]:
        duration = arrival - departure
        return [
            DeviatedStopTimeWithDateTime(
                stop, departure + i / (len(temporary_stops) + 1) * duration
            )
            for i, stop in enumerate(temporary_stops, 1)
        ]


class RoadDistanceRouter(Router):
    def __init__(self, endpoint: str, speed: float):
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("mobility speed must be finite and greater than zero")
        self.endpoint = endpoint.rstrip("/")
        self.speed = speed  # [m/min]

    async def plan(
        self,
        origin: Stop,
        destination: Stop,
        temporary_stops: list[TemporaryStop],
        departure: datetime,
        arrival: datetime,
    ) -> list[DeviatedStopTimeWithDateTime] | None:
        # Identical pickup/drop-off points need only one visit. Different
        # coordinates within the same location ID remain separate stops.
        stops = []
        for stop in temporary_stops:
            if stop not in stops:
                stops.append(stop)
        points = [origin, *stops, destination]
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.endpoint}/matrix",
                json=[
                    {"locationId": point.stop_id, "lat": point.lat, "lng": point.lng}
                    for point in points
                ],
            ) as response,
        ):
            response.raise_for_status()
            matrix = (await response.json())["matrix"]

        # Fix the endpoints and exhaustively compare all temporary-stop orders.
        destination_index = len(points) - 1
        best = None
        for order in itertools.permutations(range(1, destination_index)):
            distances = [
                matrix[a][b]
                for a, b in itertools.pairwise((0, *order, destination_index))
            ]
            if any(
                not math.isfinite(distance) or distance < 0 for distance in distances
            ):
                continue
            candidate = (order, sum(distances))
            if best is None or candidate[1] < best[1]:
                best = candidate
        if best is None:
            return None

        best_order, best_distance = best
        # Include the final leg to the fixed destination in the time check.
        if departure + timedelta(minutes=best_distance / self.speed) > arrival:
            return None

        elapsed = 0.0
        planned = []
        previous = 0
        for index in best_order:
            elapsed += matrix[previous][index] / self.speed
            planned.append(
                DeviatedStopTimeWithDateTime(
                    stops[index - 1], departure + timedelta(minutes=elapsed)
                )
            )
            previous = index
        return planned
