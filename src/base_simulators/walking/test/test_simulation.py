# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import math
import unittest

from core import EventType
from simulation import *


class TestSimulation(unittest.TestCase):
    def test_reserve(self):
        sim = Simulation(80)
        user_id = "user1"
        org = Location("a", 36.700860517989156, 137.21399177886272)
        dst = Location("b", 36.69283395675775, 137.21149599026634)
        dept = 1234.56
        arrv = 1246.0377760560712

        # Reserve
        sim.reserve(user_id, org, dst, dept, arrv)

        # After reservation
        expected = [
            (0, []),
            (0, [{
                'time': 0,
                'eventType': EventType.RESERVED,
                'details': {
                    'success': True,
                    'userId': user_id,
                    'route': [{
                        'org': org.dumps(),
                        'dst': dst.dumps(),
                        'dept': dept,
                        'arrv': arrv,
                    }]
                }
            }]),
            (0, []),
        ]
        for s, e in expected:
            self.assertEqual(s, sim.peek())
            now, events = sim.step()
            self.assertEqual(s, now)
            self.assertEqual(e, events)

        # Departure
        sim.depart("user1")

        # After departure
        expected = [
            (0, []),
            (dept, [{
                'time': dept, 'eventType': EventType.DEPARTED,
                'details': {'subjectId': user_id, 'userId': user_id, 'mobilityId': None, 'location': org.dumps()}
            }]),
            (arrv, [{
                'time': arrv, 'eventType': EventType.ARRIVED,
                'details': {'subjectId': user_id, 'userId': user_id, 'mobilityId': None, 'location': dst.dumps()}
            }]),
            (arrv, []),
        ]
        for s, e in expected:
            self.assertEqual(s, sim.peek(), s)
            now, events = sim.step()
            self.assertEqual(s, now)
            self.assertEqual(e, events)

        self.assertEqual(math.inf, sim.peek())
