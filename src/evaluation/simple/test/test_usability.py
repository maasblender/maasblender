# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import pathlib
import unittest
import unittest.mock

from jschema.query import EvaluationTiming
from mblib.io.result import FileResultWriter
from core import Location
from planner import Route, Trip
from usability import UsabilityEvaluator

logger = logging.getLogger(__name__)

TEST_FILE = pathlib.Path("test.txt")

# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
locations = {
    "1_1": Location("1_1", lat=36.699941, lng=137.212183),
    "5_1": Location("5_1", lat=36.692495, lng=137.223181),
    "9_1": Location("9_1", lat=36.693708, lng=137.231302),
    "13_1": Location("13_1", lat=36.686913, lng=137.228431),
    "17_1": Location("17_1", lat=36.686592, lng=137.221622),
    "21_1": Location("21_1", lat=36.689415, lng=137.218713),
    "25_1": Location("25_1", lat=36.688971, lng=137.210680),
    "29_1": Location("29_1", lat=36.685340, lng=137.202158),
    "33_1": Location("33_1", lat=36.699350, lng=137.205897),
}


class EvaluationTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.evaluator = UsabilityEvaluator(
            FileResultWriter(TEST_FILE),
            "",
            "",
            timing=EvaluationTiming.ON_DEPARTURE,
        )
        reservable = unittest.mock.AsyncMock()
        reservable.return_value = True
        self.evaluator.reserver.reservable = reservable

    async def asyncTearDown(self):
        await self.evaluator.close()
        await self.evaluator.logger.close()
        TEST_FILE.unlink(missing_ok=True)

    async def test_to_evaluate_none(self):
        org = locations["1_1"]
        dst = locations["21_1"]

        routes = [
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=locations["5_1"],
                        dept=621.0,
                        arrv=623,
                        service="walking",
                    ),
                    Trip(
                        org=locations["5_1"],
                        dst=locations["17_1"],
                        dept=624,
                        arrv=628,
                        service="1st_service",
                    ),
                    Trip(
                        org=locations["17_1"],
                        dst=dst,
                        dept=628,
                        arrv=643,
                        service="walking",
                    ),
                ]
            ),
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=dst,
                        dept=621.0,
                        arrv=650.0,
                        service="walking",
                    )
                ]
            ),
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=locations["33_1"],
                        dept=621.0,
                        arrv=623,
                        service="walking",
                    ),
                    Trip(
                        org=locations["33_1"],
                        dst=locations["25_1"],
                        dept=624,
                        arrv=628,
                        service="1st_service",
                    ),
                    Trip(
                        org=locations["25_1"],
                        dst=dst,
                        dept=628,
                        arrv=631,
                        service="walking",
                    ),
                ]
            ),
        ]
        result = await self.evaluator._evaluate(
            routes, None, 0.0, 0.0, demand_id="Demand123"
        )

        self.assertEqual(
            {
                "org": routes[0].org.location_id,
                "dst": routes[0].dst.location_id,
                "time": 0.0,
                "actual_service": None,
                "event_time": 0.0,
                "demand_id": "Demand123",
                "plans": [
                    [
                        {
                            "org": trip.org.location_id,
                            "dst": trip.dst.location_id,
                            "dept": trip.dept,
                            "arrv": trip.arrv,
                            "service": trip.service,
                            "reservable": True,
                        }
                        for trip in route.trips
                    ]
                    for route in routes
                ],
            },
            result,
        )

    async def test_to_evaluate_with_actual(self):
        org = locations["1_1"]
        dst = locations["21_1"]

        routes = [
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=locations["5_1"],
                        dept=621.0,
                        arrv=623,
                        service="walking",
                    ),
                    Trip(
                        org=locations["5_1"],
                        dst=locations["17_1"],
                        dept=624,
                        arrv=628,
                        service="1st_service",
                    ),
                    Trip(
                        org=locations["17_1"],
                        dst=dst,
                        dept=628,
                        arrv=635,
                        service="walking",
                    ),
                ]
            ),
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=dst,
                        dept=621.0,
                        arrv=648,
                        service="walking",
                    )
                ]
            ),
            Route(
                trips=[
                    Trip(
                        org=org,
                        dst=locations["33_1"],
                        dept=621.0,
                        arrv=623,
                        service="walking",
                    ),
                    Trip(
                        org=locations["33_1"],
                        dst=locations["25_1"],
                        dept=624,
                        arrv=628,
                        service="1st_service",
                    ),
                    Trip(
                        org=locations["25_1"],
                        dst=dst,
                        dept=628,
                        arrv=632,
                        service="walking",
                    ),
                ]
            ),
        ]
        result = await self.evaluator._evaluate(
            routes, "test-service", 1000.0, dept=1000.0, demand_id="D999"
        )
        self.assertEqual(
            result,
            {
                "org": routes[0].org.location_id,
                "dst": routes[0].dst.location_id,
                "time": 1000.0,
                "actual_service": "test-service",
                "event_time": 1000.0,
                "demand_id": "D999",
                "plans": [
                    [
                        {
                            "org": trip.org.location_id,
                            "dst": trip.dst.location_id,
                            "dept": trip.dept,
                            "arrv": trip.arrv,
                            "service": trip.service,
                            "reservable": True,
                        }
                        for trip in route.trips
                    ]
                    for route in routes
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
