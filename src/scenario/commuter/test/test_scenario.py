# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

from commuter import CommuterScenario
from jschema.query import CommuterSetting, LocationSetting
from jschema.response import DemandEvent

org = LocationSetting(locationId="Org", lat=154.1, lng=27.1)
dst = LocationSetting(locationId="Dst", lat=154.2, lng=27.3)


class CommuterScenarioTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = CommuterScenario()

    def test_one_commuter_depart_at(self):
        self.scenario.setup(
            {
                "U_001": CommuterSetting(
                    org=org,
                    dst=dst,
                    deptOut=400,
                    deptIn=800,
                    arrvOut=None,
                    arrvIn=None,
                    leadTime=0,
                    user_type="commuter_users",
                    service="commuter-trains",
                )
            },
            demand_id_format="Demand%04d",
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 400,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0001",
                    "dept": 400,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 800,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0002",
                    "dept": 800,
                    "arrv": None,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 1840,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0003",
                    "dept": 1840,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 2240,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0004",
                    "dept": 2240,
                    "arrv": None,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U_001",
                "userType": "commuter_users",
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

    def test_one_commuter_arrive_by(self):
        self.scenario.setup(
            {
                "U_001": CommuterSetting(
                    org=org,
                    dst=dst,
                    deptOut=None,
                    deptIn=None,
                    arrvOut=400,
                    arrvIn=800,
                    leadTime=15,
                    user_type="commuter_users",
                    service="commuter-trains",
                )
            },
            demand_id_format="Demand%04d",
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 385,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0001",
                    "dept": None,
                    "arrv": 400,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 785,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0002",
                    "dept": None,
                    "arrv": 800,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 1825,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0003",
                    "dept": None,
                    "arrv": 1840,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 2225,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0004",
                    "dept": None,
                    "arrv": 2240,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U_001",
                "userType": "commuter_users",
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

    def test_mixed_mode_dept_out_arrv_in(self):
        self.scenario.setup(
            {
                "U_001": CommuterSetting(
                    org=org,
                    dst=dst,
                    deptOut=400,
                    deptIn=None,
                    arrvOut=None,
                    arrvIn=800,
                    leadTime=15,
                    user_type="commuter_users",
                    service="commuter-trains",
                )
            },
            demand_id_format="Demand%04d",
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 400,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0001",
                    "dept": 400,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 785,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0002",
                    "dept": None,
                    "arrv": 800,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 1840,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0003",
                    "dept": 1840,
                    "arrv": None,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 2225,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0004",
                    "dept": None,
                    "arrv": 2240,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U_001",
                "userType": "commuter_users",
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

    def test_mixed_mode_arrv_out_dept_in(self):
        self.scenario.setup(
            {
                "U_001": CommuterSetting(
                    org=org,
                    dst=dst,
                    deptOut=None,
                    deptIn=800,
                    arrvOut=400,
                    arrvIn=None,
                    leadTime=15,
                    user_type="commuter_users",
                    service="commuter-trains",
                )
            },
            demand_id_format="Demand%04d",
        )

        expected_events = [
            {
                "eventType": "DEMAND",
                "time": 385,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0001",
                    "dept": None,
                    "arrv": 400,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 800,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0002",
                    "dept": 800,
                    "arrv": None,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 1825,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0003",
                    "dept": None,
                    "arrv": 1840,
                    "org": org.model_dump(),
                    "dst": dst.model_dump(),
                    "service": "commuter-trains",
                },
            },
            {
                "eventType": "DEMAND",
                "time": 2240,
                "details": {
                    "userId": "U_001",
                    "userType": "commuter_users",
                    "demandId": "Demand0004",
                    "dept": 2240,
                    "arrv": None,
                    "org": dst.model_dump(),
                    "dst": org.model_dump(),
                    "service": "commuter-trains",
                },
            },
        ]

        assert self.scenario.users() == [
            {
                "userId": "U_001",
                "userType": "commuter_users",
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
