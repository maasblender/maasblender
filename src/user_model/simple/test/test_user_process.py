# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest

import simpy
import user_manager
from core import Location, User
from event import DepartEvent, ReservedEvent, ReserveEvent
from event import Manager as EventManager
from jschema.query import PreferenceMode
from user_manager import UserManager

import planner
from planner import Route

# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
locations = {
    "1_1": Location(id_="1_1", lat=36.699941, lng=137.212183),
    "5_1": Location(id_="5_1", lat=36.692495, lng=137.223181),
    "9_1": Location(id_="9_1", lat=36.693708, lng=137.231302),
    "13_1": Location(id_="13_1", lat=36.686913, lng=137.228431),
    "17_1": Location(id_="17_1", lat=36.686592, lng=137.221622),
    "21_1": Location(id_="21_1", lat=36.689415, lng=137.218713),
    "25_1": Location(id_="25_1", lat=36.688971, lng=137.210680),
    "29_1": Location(id_="29_1", lat=36.685340, lng=137.202158),
    "33_1": Location(id_="33_1", lat=36.699350, lng=137.205897),
}


class ReservationFlowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env = simpy.Environment()
        self.event_manager = EventManager(env=self.env)

    def test_reservation_flow(self):
        org = locations["1_1"]
        dst = locations["21_1"]
        user_id = "U_001"
        demand_id = "D_0001"

        user = User(
            user_id=user_id,
            demand_id=demand_id,
            org=org,
            dst=dst,
            dept=0,
            tasks=[
                user_manager.Trip(
                    self.event_manager,
                    org=org,
                    dst=dst,
                    dept=0,
                    service="walking",
                )
            ],
        )
        self.env.process(user.run())
        self.env.run(1)
        # confirm a reservation event for user's trip.
        triggered_events = self.event_manager.dequeue()
        expected_events = [
            ReserveEvent(
                service="walking",
                user_id=user_id,
                demand_id=demand_id,
                org=org,
                dst=dst,
                dept=0,
                now=0,
            )
        ]
        self.assertEqual(len(expected_events), len(triggered_events))
        for expected, triggered in zip(expected_events, triggered_events):
            self.assertEqual(expected.dumps(), triggered.dumps())

        # trigger a reservation failed event for the reservation event (originally from the walking module).
        self.event_manager.trigger(
            ReservedEvent(
                source="walking",
                user_id=user_id,
                demand_id=demand_id,
            )
        )
        self.env.run(2)
        # confirm a reservation event for user's walking trip.
        triggered_events = self.event_manager.dequeue()
        expected_events = [
            DepartEvent(
                service="walking",
                user_id=user_id,
                demand_id=demand_id,
                now=1,
            )
        ]
        self.assertEqual(len(expected_events), len(triggered_events))
        for expected, triggered in zip(expected_events, triggered_events):
            self.assertEqual(expected.dumps(), triggered.dumps())

    def test_failed_reservation_flow(self):
        org = locations["1_1"]
        dst = locations["21_1"]
        user_id = "U_001"
        demand_id = "D_0001"

        user = User(
            user_id=user_id,
            demand_id=demand_id,
            org=org,
            dst=dst,
            dept=0,
            tasks=[
                user_manager.Trip(
                    self.event_manager,
                    org=org,
                    dst=dst,
                    dept=0,
                    service="mobility",
                    fail=[
                        user_manager.Trip(
                            self.event_manager,
                            org=org,
                            dst=dst,
                            dept=0,
                            service="walking",
                        )
                    ],
                )
            ],
        )
        self.env.process(user.run())
        self.env.run(1)
        # confirm a reservation event for user's trip.
        triggered_events = self.event_manager.dequeue()
        expected_events = [
            ReserveEvent(
                service="mobility",
                user_id=user_id,
                demand_id=demand_id,
                org=org,
                dst=dst,
                dept=0,
                now=0,
            )
        ]
        self.assertEqual(len(expected_events), len(triggered_events))
        for expected, triggered in zip(expected_events, triggered_events):
            self.assertEqual(expected.dumps(), triggered.dumps())

        # trigger a reservation failed event for the reservation event (originally from the walking module).
        self.event_manager.trigger(
            ReservedEvent(
                source="mobility", user_id=user_id, demand_id=demand_id, success=False
            )
        )
        self.env.run(2)
        # confirm a reservation event for user's walking trip.
        triggered_events = self.event_manager.dequeue()
        expected_events = [
            ReserveEvent(
                service="walking",
                user_id=user_id,
                demand_id=demand_id,
                org=org,
                dst=dst,
                dept=1,
                now=1,
            )
        ]
        self.assertEqual(len(expected_events), len(triggered_events))
        for expected, triggered in zip(expected_events, triggered_events):
            self.assertEqual(expected.dumps(), triggered.dumps())


class ReservationFailedTripServiceTestCase(unittest.TestCase):
    def assertEqualTrips(
        self,
        expected_trips: list[user_manager.Trip],
        actual_trips: list[user_manager.Trip],
    ):
        self.assertEqual(len(expected_trips), len(actual_trips))
        for expected, actual in zip(expected_trips, actual_trips):
            self.assertEqual(
                (expected.org, expected.dst, expected.service),
                (actual.org, actual.dst, actual.service),
            )
            if expected.fail:
                self.assertEqualTrips(expected.fail, actual.fail)

    def setUp(self):
        self.manager = UserManager(preference_mode=PreferenceMode.fixed)

    def test_plans_contain_only_walking(self):
        org = Location(id_="ORG", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)
        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                )
            ],
            service=None,
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            )
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_contain_only_walking_when_fixed(self):
        org = Location(id_="ORG", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)
        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                )
            ],
            service="walking",
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            )
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_best_walking_plans(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
            ],
            service=None,
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            )
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_placed_walking_second(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
            ],
            service=None,
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=loc_a,
                dept=0,
                service="walking",
                fail=[],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_a,
                dst=loc_b,
                dept=0,
                service="service",
                fail=[
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_a,
                        dst=dst,
                        dept=0,
                        service="walking",
                        fail=[],
                    )
                ],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_b,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_placed_walking_third(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        loc_c = Location(id_="C", lat=0, lng=0)
        loc_d = Location(id_="D", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_c, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_c, dst=loc_d, dept=0, arrv=0, service="another"
                        ),
                        planner.Trip(
                            org=loc_d, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
            ],
            service=None,
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=loc_a,
                dept=0,
                service="walking",
                fail=[],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_a,
                dst=loc_b,
                dept=0,
                service="service",
                fail=[
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_a,
                        dst=loc_c,
                        dept=0,
                        service="walking",
                        fail=[],
                    ),
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_c,
                        dst=loc_d,
                        dept=0,
                        service="another",
                        fail=[
                            user_manager.Trip(
                                manager=self.manager._event_manager,
                                org=loc_c,
                                dst=dst,
                                dept=0,
                                service="walking",
                                fail=[],
                            )
                        ],
                    ),
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_d,
                        dst=dst,
                        dept=0,
                        service="walking",
                        fail=[],
                    ),
                ],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_b,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_contain_fixed_service_plan(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
            ],
            service="service",
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=loc_a,
                dept=0,
                service="walking",
                fail=[],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_a,
                dst=loc_b,
                dept=0,
                service="service",
                fail=[
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_a,
                        dst=dst,
                        dept=0,
                        service="walking",
                        fail=[],
                    )
                ],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_b,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_doesnt_contain_fixed_service_plan(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
            ],
            service="another",
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)


class PreferenceModePreferTestCase(unittest.TestCase):
    def assertEqualTrips(
        self,
        expected_trips: list[user_manager.Trip],
        actual_trips: list[user_manager.Trip],
    ):
        self.assertEqual(len(expected_trips), len(actual_trips))
        for expected, actual in zip(expected_trips, actual_trips):
            self.assertEqual(
                (expected.org, expected.dst, expected.service),
                (actual.org, actual.dst, actual.service),
            )
            self.assertEqual(len(expected.fail), len(actual.fail))
            if expected.fail:
                self.assertEqualTrips(expected.fail, actual.fail)

    def setUp(self):
        self.manager = UserManager(preference_mode=PreferenceMode.prefer)

    def test_plans_contain_prefer_service_plan(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="service"
                        )
                    ]
                ),
            ],
            service="service",
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=loc_a,
                dept=0,
                service="walking",
                fail=[],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_a,
                dst=loc_b,
                dept=0,
                service="service",
                fail=[
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_a,
                        dst=org,
                        dept=0,
                        service="walking",
                        fail=[],
                    ),
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=org,
                        dst=dst,
                        dept=0,
                        service="service",
                        fail=[
                            user_manager.Trip(
                                manager=self.manager._event_manager,
                                org=org,
                                dst=dst,
                                dept=0,
                                service="walking",
                                fail=[],
                            ),
                        ],
                    ),
                ],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_b,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)

    def test_plans_doesnt_contain_prefer_service_plan(self):
        org = Location(id_="ORG", lat=0, lng=0)
        loc_a = Location(id_="A", lat=0, lng=0)
        loc_b = Location(id_="B", lat=0, lng=0)
        dst = Location(id_="DST", lat=0, lng=0)

        trips = self.manager.plans_to_trips(
            [
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=loc_a, dept=0, arrv=0, service="walking"
                        ),
                        planner.Trip(
                            org=loc_a, dst=loc_b, dept=0, arrv=0, service="service"
                        ),
                        planner.Trip(
                            org=loc_b, dst=dst, dept=0, arrv=0, service="walking"
                        ),
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="walking"
                        )
                    ]
                ),
                Route(
                    trips=[
                        planner.Trip(
                            org=org, dst=dst, dept=0, arrv=0, service="service"
                        )
                    ]
                ),
            ],
            service="another",
        )

        expected_trips = [
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=org,
                dst=loc_a,
                dept=0,
                service="walking",
                fail=[],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_a,
                dst=loc_b,
                dept=0,
                service="service",
                fail=[
                    user_manager.Trip(
                        manager=self.manager._event_manager,
                        org=loc_a,
                        dst=dst,
                        dept=0,
                        service="walking",
                        fail=[],
                    )
                ],
            ),
            user_manager.Trip(
                manager=self.manager._event_manager,
                org=loc_b,
                dst=dst,
                dept=0,
                service="walking",
                fail=[],
            ),
        ]
        self.assertEqualTrips(expected_trips, trips)


if __name__ == "__main__":
    unittest.main()
