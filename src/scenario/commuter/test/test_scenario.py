# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import unittest

import jschema.query
import jschema.response
from commuter import CommuterScenario

logger = logging.getLogger(__name__)

org = {
    "locationId": "Org",
    "lat": 154.1,
    "lng": 27.1,
}
dst = {
    "locationId": "Dst",
    "lat": 154.2,
    "lng": 27.3,
}


class CommuterScenarioTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = CommuterScenario()

    def test_one_commuter(self):
        self.scenario.setup({
            "U_001": jschema.query.CommuterSetting(
                org=jschema.query.LocationSetting(
                    locationId=org["locationId"],
                    lat=org["lat"],
                    lng=org["lng"],
                ),
                dst=jschema.query.LocationSetting(
                    locationId=dst["locationId"],
                    lat=dst["lat"],
                    lng=dst["lng"],
                ),
                deptOut=400,
                deptIn=800,
                user_type="commuter_users",
                service="commuter-trains",
            )
        })

        expected_events = [
            {
                'eventType': 'DEMAND',
                'time': 400,
                'details': {
                    'userId': 'U_001',
                    'org': org,
                    'dst': dst,
                    'service': 'commuter-trains',
                }
            },
            {
                'eventType': 'DEMAND',
                'time': 800,
                'details': {
                    'userId': 'U_001',
                    'org': dst,
                    'dst': org,
                    'service': 'commuter-trains',
                }
            },
            {
                'eventType': 'DEMAND',
                'time': 1840,
                'details': {
                    'userId': 'U_001',
                    'org': org,
                    'dst': dst,
                    'service': 'commuter-trains',
                }
            },
            {
                'eventType': 'DEMAND',
                'time': 2240,
                'details': {
                    'userId': 'U_001',
                    'org': dst,
                    'dst': org,
                    'service': 'commuter-trains',
                }
            }
        ]

        assert self.scenario.users() == [{
            "userId": "U_001",
            "userType": "commuter_users",
        }]
        self.scenario.start()
        actual_events = []
        while self.scenario.peek() < 2880:
            now, events = self.scenario.step()
            actual_events += [e | {"time": now} for e in events]
        self.assertEqual(len(expected_events), len(actual_events))
        for expected, actual in zip(expected_events, actual_events):
            self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
