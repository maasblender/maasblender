# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import unittest
import logging
from datetime import datetime, date, time, timedelta

from simulation import Simulation
from core import EventType, Stop, StopTime, Service, Trip, Group, Network
from jschema.query import Mobility

logger = logging.getLogger('schedsim')


def run(simulation: Simulation, until: float):
    events = []
    while simulation.peek() < until:
        _ = simulation.step()
        events.extend(simulation.event_queue.events)

    if simulation.env.now < until:
        # expect nothing to happen. just let time forward.
        simulation.env.run(until=until)
    return events


class OneMobilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base_datetime = datetime.combine(date.today(), time())
        self.stop1 = Stop(stop_id="Stop1", name=..., lat=..., lng=...)
        self.stop2 = Stop(stop_id="Stop2", name=..., lat=..., lng=...)
        self.stop3 = Stop(stop_id="Stop3", name=..., lat=..., lng=...)
        self.stops = {"Stop1": self.stop1, "Stop2": self.stop2, "Stop3": self.stop3}
        self.network = Network()
        self.network.add_edge(self.stop1.stop_id, self.stop2.stop_id, 30, with_rev=True)
        self.network.add_edge(self.stop1.stop_id, self.stop3.stop_id, 15, with_rev=True)
        self.network.add_edge(self.stop2.stop_id, self.stop3.stop_id, 20, with_rev=True)

        self.simulation = Simulation(
            start_time=self.base_datetime,
            board_time=10,
            max_delay_time=30,
            network=self.network,
            trips={
                "trip": Trip(
                    service=Service(
                        start_date=self.base_datetime.date(),
                        end_date=self.base_datetime.date() + timedelta(days=1),
                        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True,
                        saturday=True, sunday=True
                    ),
                    stop_time=StopTime(
                        group=Group(
                            group_id=...,
                            name=...,
                            locations=[stop for stop in self.stops.values()]
                        ),
                        start_window=timedelta(hours=1),
                        end_window=timedelta(hours=23),
                    )
                )
            },
            settings={
                "trip": Mobility(
                    mobility_id="trip",
                    trip_id="trip",
                    capacity=2,
                    stop=self.stops["Stop1"].stop_id
                )
            }
        )
        self.simulation.start()

    def test_no_operation_without_reservations(self):
        triggered_events = run(self.simulation, until=24 * 60)
        expected_events = []
        self.assertEqual(expected_events, triggered_events)

    def test_a_single_user_lifetime(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_a_user_twice_lifetime(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=481)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")
        triggered_events = run(self.simulation, until=550)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=570.0,
        )
        triggered_events = run(self.simulation, until=571)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 550.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 580.0,
                'arrv': 630.0
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 550.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")
        triggered_events = run(self.simulation, until=650)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 580.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 580.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 590.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 620.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 630.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_two_users_in_two_round_trips_lifetime(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=481)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop1",
            dst="Stop2",
            dept=570.0,
        )
        triggered_events = run(self.simulation, until=482)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 481.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 570.0,
                'arrv': 620.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")
        self.simulation.ready_to_depart(user_id="User2")
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 540.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 570.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 570.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 580.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 610.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 620.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_reserve_while_moving(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")

        triggered_events = run(self.simulation, until=510)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop2",
            dst="Stop1",
            dept=530.0,
        )
        triggered_events = run(self.simulation, until=511)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 510.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dept': 540.0,
                'arrv': 590.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User2")
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 540.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 550.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 580.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 590.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_reserve_another_route_with_a_different_first_stop_while_moving(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop2",
            dst="Stop3",
            dept=580.0,
        )
        triggered_events = run(self.simulation, until=481)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 580.0,
                'arrv': 620.0
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 480.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")

        run(self.simulation, until=485)
        self.simulation.reserve_user(
            user_id="User2",
            org="Stop3",
            dst="Stop2",
            dept=520.0,
        )
        triggered_events = run(self.simulation, until=486)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 485.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 530.0,
                'arrv': 570.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User2")
        triggered_events = run(self.simulation, until=511)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 510.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 510.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        triggered_events = run(self.simulation, until=541)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 530.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 540.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        triggered_events = run(self.simulation, until=571)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 560.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 570.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 580.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            },
        }, {
            'eventType': EventType.DEPARTED,
            'time': 590.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            },
        }, {
            'eventType': EventType.ARRIVED,
            'time': 610.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 620.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_reserve_after_boarding_while_on_boarding(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop2",
            dst="Stop3",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 510.0,
                'arrv': 550.0
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 480.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")

        triggered_events = run(self.simulation, until=515)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 510.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 510.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop2",
            dst="Stop3",
            dept=521.0,
        )
        triggered_events = run(self.simulation, until=516)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 515.0,
            'details': {
                'success': False,
                'userId': 'User2',
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User3",
            org="Stop2",
            dst="Stop3",
            dept=519.0,
        )
        triggered_events = run(self.simulation, until=517)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 516.0,
            'details': {
                'success': True,
                'userId': 'User3',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 519.0,
                'arrv': 559.0
            }
        }], triggered_events)

    def test_reserve_while_on_boarding(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop2",
            dst="Stop3",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 510.0,
                'arrv': 550.0
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 480.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")

        triggered_events = run(self.simulation, until=515)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 510.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 510.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop1",
            dst="Stop2",
            dept=550.0,
        )
        triggered_events = run(self.simulation, until=516)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 515.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 570.0,
                'arrv': 620.0
            }
        }], triggered_events)
        self.simulation.ready_to_depart(user_id="User2")

        triggered_events = run(self.simulation, until=551)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 520.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 550.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 550.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        triggered_events = run(self.simulation, until=580)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 565.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 565.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 575.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 605.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 615.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_reserve_same_org_while_on_boarding(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop2",
            dst="Stop3",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 510.0,
                'arrv': 550.0
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 480.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")

        triggered_events = run(self.simulation, until=515)
        self.assertEqual([{
            'eventType': EventType.ARRIVED,
            'time': 510.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 510.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop2",
            dst="Stop3",
            dept=516.0,
        )
        triggered_events = run(self.simulation, until=516)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 515.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dept': 516.0,
                'arrv': 556.0
            }
        }], triggered_events)
        self.simulation.ready_to_depart(user_id="User2")

        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 520.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 550.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 560.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 560.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_two_users_lifetime(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=481.0)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop3",
            dst="Stop2",
            dept=510.0,
        )
        triggered_events = run(self.simulation, until=482)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 481.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop3", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 515.0,
                'arrv': 555.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart("User1")
        self.simulation.ready_to_depart("User2")

        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 515.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 515.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 525.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop3", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 545.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 555.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 555.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)

    def test_two_reservations(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=481.0)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.reserve_user(
            user_id="User2",
            org="Stop2",
            dst="Stop1",
            dept=530.0,
        )
        triggered_events = run(self.simulation, until=482.0)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 481.0,
            'details': {
                'success': True,
                'userId': 'User2',
                'mobilityId': 'trip',
                'org': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dept': 540.0,
                'arrv': 590.0
            }
        }], triggered_events)
        self.simulation.ready_to_depart(user_id="User1")
        self.simulation.ready_to_depart(user_id="User2")
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 540.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 550.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 580.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 590.0,
            'details': {
                'userId': "User2",
                'mobilityId': 'trip',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }], triggered_events)


class TwoMobilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base_datetime = datetime.combine(date.today(), time())
        self.stop1 = Stop(stop_id="Stop1", name=..., lat=..., lng=...)
        self.stop2 = Stop(stop_id="Stop2", name=..., lat=..., lng=...)
        self.stop3 = Stop(stop_id="Stop3", name=..., lat=..., lng=...)
        self.stops = {"Stop1": self.stop1, "Stop2": self.stop2, "Stop3": self.stop3}
        self.network = Network()
        self.network.add_edge(self.stop1.stop_id, self.stop2.stop_id, 30, with_rev=True)
        self.network.add_edge(self.stop1.stop_id, self.stop3.stop_id, 40, with_rev=True)
        self.network.add_edge(self.stop2.stop_id, self.stop3.stop_id, 50, with_rev=True)

        self.simulation = Simulation(
            start_time=self.base_datetime,
            network=self.network,
            board_time=10,
            max_delay_time=30,
            trips={
                "trip1": Trip(
                    service=Service(
                        start_date=self.base_datetime.date(),
                        end_date=self.base_datetime.date() + timedelta(days=1),
                        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True,
                        saturday=True, sunday=True
                    ),
                    stop_time=StopTime(
                        group=Group(
                            group_id=...,
                            name=...,
                            locations=[stop for stop in self.stops.values()]
                        ),
                        start_window=timedelta(hours=1),
                        end_window=timedelta(hours=23),
                    )
                ),
                "trip2": Trip(
                    service=Service(
                        start_date=self.base_datetime.date(),
                        end_date=self.base_datetime.date() + timedelta(days=1),
                        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True,
                        saturday=True, sunday=True
                    ),
                    stop_time=StopTime(
                        group=Group(
                            group_id=...,
                            name=...,
                            locations=[stop for stop in self.stops.values()]
                        ),
                        start_window=timedelta(hours=1),
                        end_window=timedelta(hours=23),
                    )
                )
            },
            settings={
                "trip1": Mobility(
                    mobility_id="trip1",
                    trip_id="trip1",
                    capacity=1,
                    stop=self.stops["Stop1"].stop_id
                ),
                "trip2": Mobility(
                    mobility_id="trip2",
                    trip_id="trip2",
                    capacity=1,
                    stop=self.stops["Stop2"].stop_id
                )
            }
        )
        self.simulation.start()

    def test_no_operation_without_reservations(self):
        triggered_events = run(self.simulation, until=24 * 60)
        expected_events = []
        self.assertEqual(expected_events, triggered_events)

    def test_a_single_user_lifetime(self):
        run(self.simulation, until=480.0)

        self.simulation.reserve_user(
            user_id="User1",
            org="Stop1",
            dst="Stop2",
            dept=490.0,
        )
        triggered_events = run(self.simulation, until=480.1)
        self.assertEqual([{
            'eventType': EventType.RESERVED,
            'time': 480.0,
            'details': {
                'success': True,
                'userId': 'User1',
                'mobilityId': 'trip1',
                'org': {"locationId": "Stop1", "lat": ..., "lng": ...},
                'dst': {"locationId": "Stop2", "lat": ..., "lng": ...},
                'dept': 490.0,
                'arrv': 540.0
            }
        }], triggered_events)

        self.simulation.ready_to_depart(user_id="User1")
        triggered_events = run(self.simulation, until=1440)
        self.assertEqual([{
            'eventType': EventType.DEPARTED,
            'time': 490.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip1',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.DEPARTED,
            'time': 500.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip1',
                'location': {"locationId": "Stop1", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 530.0,
            'details': {
                'userId': None,
                'mobilityId': 'trip1',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }, {
            'eventType': EventType.ARRIVED,
            'time': 540.0,
            'details': {
                'userId': "User1",
                'mobilityId': 'trip1',
                'location': {"locationId": "Stop2", "lat": ..., "lng": ...},
            }
        }], triggered_events)
