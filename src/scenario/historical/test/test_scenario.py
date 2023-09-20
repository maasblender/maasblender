# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

import jschema.query
import jschema.response
from historical import HistoricalScenario

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


class HistoricalScenarioTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = HistoricalScenario()

    def test_one_trip(self):
        self.scenario.setup([
            jschema.query.HistoricalDemandSetting(
                org=jschema.query.LocationSetting(
                    locationId=org["locationId"],
                    lat=org["lat"],
                    lng=org["lng"],
                ),
                dst=jschema.query.LocationSetting(
                    locationId=dst["locationId"],
                    lat=dst["lat"],
                    lng=dst["lng"]
                ),
                dept=400.0,
                service="mobility",
                user_type="user-xyz",
            )
        ], "U_%d")

        expected_events = [
            {
                'time': 400,
                'eventType': 'DEMAND',
                'details': {
                    'userId': 'U_1',
                    'org': org,
                    'dst': dst,
                    "service": "mobility"
                }
            },
        ]

        assert self.scenario.users() == [{
            "userId": "U_1",
            "userType": "user-xyz",
        }]
        self.scenario.start()
        actual_events = []
        while self.scenario.peek() < 2880:
            now, events = self.scenario.step()
            actual_events += [e | {"time": now} for e in events]
        self.assertEqual(len(expected_events), len(actual_events))
        for expected, actual in zip(expected_events, actual_events):
            self.assertEqual(
                jschema.response.DemandEvent.parse_obj(expected),
                jschema.response.DemandEvent.parse_obj(actual),
            )


if __name__ == '__main__':
    unittest.main()
