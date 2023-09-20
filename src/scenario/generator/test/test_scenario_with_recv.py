# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

import jschema.query
import jschema.response
from generator import DemandGenerator

org1 = {
    "locationId": "Org",
    "lat": 154.1,
    "lng": 27.1,
}
dst1 = {
    "locationId": "Dst",
    "lat": 154.2,
    "lng": 27.3,
}

org2 = {
    "locationId": "Org",
    "lat": 154.3,
    "lng": 27.5,
}
dst2 = {
    "locationId": "Dst",
    "lat": 154.4,
    "lng": 27.7,
}


# advance reservation
class DemandGeneratorWithRecvTestCase(unittest.TestCase):
    def setUp(self):
        self.scenario = DemandGenerator()

    def test_one_sen_one_ten(self):
        self.scenario.setup(jschema.query.Setup(
            seed=129,
            demands=[{
                "begin": 10.0,
                "end": 200.0,
                "org": org1,
                "dst": dst1,
                "expected_demands": 2,
                "user_type": "test-user",
                "resv": 5,
            }],
            userIDFormat="U%03d",
        ))

        expected_events = [
            {
                'time': 5.0,
                'eventType': 'DEMAND',
                'details': {
                    'userId': 'U001',
                    "org": org1,
                    "dst": dst1,
                    'dept': 66.0,
                }
            },
        ]

        assert self.scenario.users() == [{
            "userId": "U001",
            "userType": "test-user",
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

    def test_one_sen_two_ten(self):
        self.scenario.setup(jschema.query.Setup(
            seed=128,
            demands=[{
                "begin": 10.0,
                "end": 200.0,
                "org": org1,
                "dst": dst1,
                "expected_demands": 2.0,
                "service": "mobility-service-for-test",
                "resv": 7,
            }],
            userIDFormat="U%03d",
        ))

        expected_events = [
            {
                'eventType': 'DEMAND',
                'time': 7.0,
                'details': {
                    'userId': 'U001',
                    "org": org1,
                    "dst": dst1,
                    'service': 'mobility-service-for-test',
                    'dept': 39.0,
                }
            },
            {
                'eventType': 'DEMAND',
                'time': 7.0,
                'details': {
                    'userId': 'U002',
                    "org": org1,
                    "dst": dst1,
                    'service': 'mobility-service-for-test',
                    'dept': 52.0,
                }
            },
        ]

        assert self.scenario.users() == [{
            "userId": "U001",
            "userType": None,
        }, {
            "userId": "U002",
            "userType": None,
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

    def test_two_sen_two_ten(self):
        self.scenario.setup(jschema.query.Setup(
            seed=30,
            demands=[{
                "begin": 20.0,
                "end": 160.0,
                "org": org1,
                "dst": dst1,
                "expected_demands": 1.0,
                "user_type": "user_A",
                "service": "advanced_mobilities",
                "resv": 13,
            }, {
                "begin": 40.0,
                "end": 180.0,
                "org": org1,
                "dst": dst1,
                "expected_demands": 1.0,
                "user_type": "user_B",
                "service": "lexical_mobilities",
                "resv": 13,
            }],
            userIDFormat="U%03d",
        ))

        expected_events = [
            {
                'eventType': 'DEMAND',
                'time': 13.0,
                'details': {
                    'userId': 'U001',
                    "org": org1,
                    "dst": dst1,
                    'service': 'lexical_mobilities',
                    'dept': 91.0,
                }
            }, {
                'eventType': 'DEMAND',
                'time': 13.0,
                'details': {
                    'userId': 'U002',
                    "org": org1,
                    "dst": dst1,
                    'service': 'advanced_mobilities',
                    'dept': 114.0,
                }
            },
        ]

        assert self.scenario.users() == [{
            "userId": "U001",
            "userType": "user_B",
        }, {
            "userId": "U002",
            "userType": "user_A",
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
