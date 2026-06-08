# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

from generator import DemandGenerator
from jschema.query import LocationSetting, Setup, SenDemandsSetting
from jschema.response import DemandEvent

org1 = LocationSetting(locationId="Org", lat=154.1, lng=27.1)
dst1 = LocationSetting(locationId="Dst", lat=154.2, lng=27.3)
org2 = LocationSetting(locationId="Org", lat=154.3, lng=27.5)
dst2 = LocationSetting(locationId="Dst", lat=154.4, lng=27.7)


# immediate reservation
class DemandGeneratorTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = DemandGenerator()

    def test_one_sen_one_ten(self):
        self.scenario.setup(
            Setup(
                seed=129,
                demands=[
                    SenDemandsSetting(
                        begin=10.0,
                        end=200.0,
                        org=org1,
                        dst=dst1,
                        expected_demands=2.0,
                        user_type="test-user",
                    ),
                ],
                userIDFormat="U%03d",
            )
        )

        expected_events = [
            {
                "time": 66.0,
                "eventType": "DEMAND",
                "details": {
                    "userId": "U001",
                    "userType": "test-user",
                    "demandId": "D_1",
                    "org": org1.model_dump(),
                    "dst": dst1.model_dump(),
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U001",
                "userType": "test-user",
            }
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

    def test_one_sen_two_ten(self):
        self.scenario.setup(
            Setup(
                seed=128,
                demands=[
                    SenDemandsSetting(
                        begin=10.0,
                        end=200.0,
                        org=org1,
                        dst=dst1,
                        expected_demands=2.0,
                        service="mobility-service-for-test",
                    )
                ],
                userIDFormat="U%03d",
            )
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 39.0,
                "details": {
                    "userId": "U001",
                    "demandId": "D_1",
                    "org": org1.model_dump(),
                    "dst": dst1.model_dump(),
                    "service": "mobility-service-for-test",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 52.0,
                "details": {
                    "userId": "U002",
                    "demandId": "D_2",
                    "org": org1.model_dump(),
                    "dst": dst1.model_dump(),
                    "service": "mobility-service-for-test",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U001",
                "userType": None,
            },
            {
                "userId": "U002",
                "userType": None,
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

    def test_two_sen_two_ten(self):
        self.scenario.setup(
            Setup(
                seed=30,
                demands=[
                    SenDemandsSetting(
                        begin=20.0,
                        end=160.0,
                        org=org1,
                        dst=dst1,
                        expected_demands=1.0,
                        user_type="user_A",
                        service="advanced_mobilities",
                    ),
                    SenDemandsSetting(
                        begin=40.0,
                        end=180.0,
                        org=org2,
                        dst=dst2,
                        expected_demands=1.0,
                        user_type="user_B",
                        service="lexical_mobilities",
                    ),
                ],
                userIDFormat="U%03d",
            )
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 91.0,
                "details": {
                    "userId": "U001",
                    "userType": "user_B",
                    "demandId": "D_1",
                    "org": org2.model_dump(),
                    "dst": dst2.model_dump(),
                    "service": "lexical_mobilities",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 114.0,
                "details": {
                    "userId": "U002",
                    "userType": "user_A",
                    "demandId": "D_2",
                    "org": org1.model_dump(),
                    "dst": dst1.model_dump(),
                    "service": "advanced_mobilities",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U001",
                "userType": "user_B",
            },
            {
                "userId": "U002",
                "userType": "user_A",
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

    def test_arrive_by_one_sen_one_ten(self):
        demands: list[SenDemandsSetting] = [
            SenDemandsSetting(
                begin=10.0,
                end=200.0,
                org=org1,
                dst=dst1,
                expected_demands=2.0,
                user_type="test-user",
                arrive_by=True,
            ),
        ]
        self.scenario.setup(
            Setup(
                seed=129,
                demands=demands,
                userIDFormat="U%03d",
            )
        )

        expected_events = [
            {
                "time": 0.0,
                "eventType": "DEMAND",
                "details": {
                    "userId": "U001",
                    "userType": "test-user",
                    "demandId": "D_1",
                    "org": org1.model_dump(),
                    "dst": dst1.model_dump(),
                    "arrv": 66.0,
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U001",
                "userType": "test-user",
            }
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


if __name__ == "__main__":
    unittest.main()
