# SPDX-FileCopyrightText: 2026 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from core import Stop, TemporaryStop, TripLocation
from routing import RoadDistanceRouter


class RoadDistanceRouterTestCase(unittest.IsolatedAsyncioTestCase):
    async def plan(self, matrix, *, speed=1, minutes=60, duplicate=False):
        origin = Stop("origin", "Origin", 36, 137)
        destination = Stop("destination", "Destination", 36.1, 137.1)
        location = TripLocation("flex", timedelta(hours=9), timedelta(hours=10))
        stops = [
            TemporaryStop(36 + i / 100, 137, location)
            for i in range(1, len(matrix) - 1)
        ]
        response = MagicMock()
        response.json = AsyncMock(return_value={"matrix": matrix})
        request = MagicMock()
        request.__aenter__ = AsyncMock(return_value=response)
        session = MagicMock()
        session.post.return_value = request
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        departure = datetime.combine(date(2022, 1, 1), time())
        with patch("routing.aiohttp.ClientSession", return_value=client):
            plan = await RoadDistanceRouter("http://planner/", speed).plan(
                origin,
                destination,
                stops + stops[:1] if duplicate else stops,
                departure,
                departure + timedelta(minutes=minutes),
            )
        self.session = session
        self.departure = departure
        return plan, stops

    async def test_selects_shortest_order_and_times_each_stop(self):
        matrix = [
            [0, 8, 2, 10],
            [8, 0, 3, 2],
            [2, 3, 0, 7],
            [10, 2, 7, 0],
        ]
        plan, stops = await self.plan(matrix, speed=2)
        self.assertEqual(stops[::-1], [stop.stop for stop in plan])
        self.assertEqual(
            [self.departure + timedelta(minutes=elapsed) for elapsed in (1, 2.5)],
            [stop.arrival for stop in plan],
        )
        self.session.post.assert_called_once_with(
            "http://planner/matrix",
            json=[
                {"locationId": "origin", "lat": 36, "lng": 137},
                {"locationId": "flex", "lat": 36.01, "lng": 137},
                {"locationId": "flex", "lat": 36.02, "lng": 137},
                {"locationId": "destination", "lat": 36.1, "lng": 137.1},
            ],
        )

    async def test_ignores_unreachable_orders(self):
        matrix = [
            [0, 2, 3, 10],
            [2, 0, -1, 2],
            [3, 2, 0, 2],
            [10, 2, 2, 0],
        ]
        plan, stops = await self.plan(matrix)
        self.assertEqual(stops[::-1], [stop.stop for stop in plan])

    async def test_rejects_when_every_order_is_unreachable(self):
        plan, _ = await self.plan([[0, -1, 10], [-1, 0, -1], [10, -1, 0]])
        self.assertIsNone(plan)

    async def test_nonfinite_distances_are_unreachable(self):
        for distance in (float("inf"), float("nan")):
            with self.subTest(distance=distance):
                plan, _ = await self.plan([[0, distance, 10], [1, 0, 1], [10, 1, 0]])
                self.assertIsNone(plan)

    async def test_time_limit_includes_final_leg(self):
        matrix = [[0, 2, 10], [2, 0, 59], [10, 59, 0]]
        plan, _ = await self.plan(matrix)
        self.assertIsNone(plan)

    async def test_accepts_arrival_exactly_at_time_limit(self):
        plan, _ = await self.plan([[0, 2, 10], [2, 0, 58], [10, 58, 0]])
        self.assertIsNotNone(plan)

    async def test_identical_coordinates_need_only_one_visit(self):
        plan, stops = await self.plan(
            [[0, 2, 10], [2, 0, 3], [10, 3, 0]], duplicate=True
        )
        self.assertEqual(stops, [stop.stop for stop in plan])
        self.assertEqual(3, len(self.session.post.call_args.kwargs["json"]))

    async def test_http_errors_are_propagated(self):
        response = MagicMock()
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            MagicMock(), (), status=500
        )
        request = MagicMock()
        request.__aenter__ = AsyncMock(return_value=response)
        session = MagicMock()
        session.post.return_value = request
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        stop = Stop("origin", "Origin", 36, 137)
        departure = datetime.combine(date(2022, 1, 1), time())
        with (
            patch("routing.aiohttp.ClientSession", return_value=client),
            self.assertRaises(aiohttp.ClientResponseError),
        ):
            await RoadDistanceRouter("http://planner", 350).plan(
                stop, stop, [], departure, departure + timedelta(minutes=10)
            )

    def test_rejects_invalid_speed(self):
        for speed in (0, -1, float("inf"), float("nan")):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                RoadDistanceRouter("http://planner", speed)
