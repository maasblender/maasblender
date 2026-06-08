# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

from jschema.query import HistoricalDemandSetting, LocationSetting
from jschema.response import DemandEvent
from historical import HistoricalScenario

org = LocationSetting(locationId="Org", lat=154.1, lng=27.1)
dst = LocationSetting(locationId="Dst", lat=154.2, lng=27.3)


class HistoricalScenarioTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = HistoricalScenario()

    def test_one_trip(self):
        self.scenario.setup(
            [
                HistoricalDemandSetting(
                    org=org,
                    dst=dst,
                    time=400.0,
                    dept=400.0,
                    arrv=None,
                    service="mobility",
                    user_type="user-xyz",
                ),
                HistoricalDemandSetting(
                    org=org,
                    dst=dst,
                    time=400.0,
                    dept=400.0,
                    arrv=None,
                    service="mobility",
                    user_type="user-xyz",
                    actual_duration=20.0,
                ),
            ],
            "U_%d",
            "D_%d",
        )

        expected_events = [
            {
                "time": 400,
                "eventType": "DEMAND",
                "details": {
                    "userId": "U_1",
                    "userType": "user-xyz",
                    "demandId": "D_1",
                    "dept": 400,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "mobility",
                    "actualDuration": None,
                },
            },
            {
                "time": 400,
                "eventType": "DEMAND",
                "details": {
                    "userId": "U_2",
                    "userType": "user-xyz",
                    "demandId": "D_2",
                    "dept": 400,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "mobility",
                    "actualDuration": 20.0,
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U_1",
                "userType": "user-xyz",
            },
            {
                "userId": "U_2",
                "userType": "user-xyz",
            },
        ]
        self.scenario.start()
        actual_events = []
        while self.scenario.peek() < 2880:
            now, events = self.scenario.step()
            actual_events += [e | {"time": now} for e in events]
        self.assertEqual(len(expected_events), len(actual_events))
        for expected, actual in zip(expected_events, actual_events):
            self.assertEqual(
                DemandEvent.model_validate(expected),
                DemandEvent.model_validate(actual),
            )

    def test_arrive_by_trip(self):
        self.scenario.setup(
            [
                HistoricalDemandSetting(
                    org=org,
                    dst=dst,
                    time=0.0,
                    dept=None,
                    arrv=400.0,
                    service="mobility",
                    user_type="user-xyz",
                ),
            ],
            "U_%d",
            "D_%d",
        )

        expected_events = [
            {
                "time": 0,
                "eventType": "DEMAND",
                "details": {
                    "userId": "U_1",
                    "userType": "user-xyz",
                    "demandId": "D_1",
                    "dept": None,
                    "arrv": 400,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "mobility",
                    "actualDuration": None,
                },
            },
        ]

        assert self.scenario.users() == [{"userId": "U_1", "userType": "user-xyz"}]
        self.scenario.start()
        actual_events = []
        while self.scenario.peek() < 2880:
            now, events = self.scenario.step()
            actual_events += [e | {"time": now} for e in events]
        self.assertEqual(len(expected_events), len(actual_events))
        for expected, actual in zip(expected_events, actual_events):
            self.assertEqual(
                DemandEvent.model_validate(expected),
                DemandEvent.model_validate(actual),
            )


if __name__ == "__main__":
    unittest.main()
