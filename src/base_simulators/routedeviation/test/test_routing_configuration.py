# SPDX-FileCopyrightText: 2026 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import io
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import controller
from jschema.query import RouteCalculationMethod, Setup
from pydantic import ValidationError
from routing import EqualIntervalRouter, RoadDistanceRouter


class RoutingConfigurationTestCase(unittest.IsolatedAsyncioTestCase):
    def settings(self, *, mobility=None, **kwargs):
        return Setup(
            reference_time="20220101",
            input_files=[{"filename": "gtfs.zip"}],
            mobility=mobility if mobility is not None else {"capacity": 2},
            **kwargs,
        )

    async def setup_router(self, settings):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w"):
            pass
        with (
            patch.object(
                controller,
                "file_table",
                new=SimpleNamespace(
                    pop=AsyncMock(return_value=("gtfs.zip", archive.getvalue()))
                ),
            ),
            patch(
                "controller.gtfs.GtfsFilesReader",
                return_value=SimpleNamespace(trips={}, blocks={}),
            ),
            patch("controller.Simulation") as simulation,
            patch.object(controller, "sim", None),
        ):
            result = await controller.setup(settings)
        self.assertEqual({"message": "successfully configured."}, result)
        return simulation.call_args.kwargs["router"]

    async def test_legacy_setup_defaults_to_equal_interval(self):
        settings = self.settings()
        self.assertEqual(
            RouteCalculationMethod.EQUAL_INTERVAL, settings.route_calculation_method
        )
        self.assertEqual(350, settings.mobility.speed)
        router = await self.setup_router(settings)
        self.assertIsInstance(router, EqualIntervalRouter)

    async def test_brute_force_setup_selects_road_distance_router(self):
        settings = self.settings(
            route_calculation_method="brute_force",
            planner={"endpoint": "http://planner/"},
            mobility={"capacity": 2, "speed": 200},
        )
        router = await self.setup_router(settings)
        self.assertIsInstance(router, RoadDistanceRouter)
        self.assertEqual("http://planner", router.endpoint)
        self.assertEqual(200, router.speed)

    def test_brute_force_requires_planner(self):
        with self.assertRaises(ValidationError):
            self.settings(route_calculation_method="brute_force")

    def test_rejects_unknown_routing_method(self):
        with self.assertRaises(ValidationError):
            self.settings(route_calculation_method="unknown")

    def test_rejects_invalid_speed(self):
        for speed in (0, -1, float("inf"), float("nan")):
            with self.subTest(speed=speed), self.assertRaises(ValidationError):
                Setup(
                    reference_time="20220101",
                    input_files=[{"filename": "gtfs.zip"}],
                    mobility={"capacity": 2, "speed": speed},
                )

    def test_reservable_api_still_accepts_location_ids_via_get(self):
        operations = controller.app.openapi()["paths"]["/reservable"]
        self.assertEqual({"get"}, set(operations))
        operation = operations["get"]
        self.assertNotIn("requestBody", operation)
        self.assertEqual(
            {"org", "dst"},
            {parameter["name"] for parameter in operation["parameters"]},
        )
        for parameter in operation["parameters"]:
            self.assertEqual("query", parameter["in"])
            self.assertEqual("string", parameter["schema"]["type"])
