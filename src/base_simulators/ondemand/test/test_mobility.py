# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import Mock

from ..core import User, Stop, Group, Trip, Service, StopTime as flex_StopTime, Network
from ..environment import Environment
from ..mobility import Car, Route, StopTime, Delay, CarManager, CarSetting

base_datetime = datetime(year=2022, month=1, day=1)
stops = [
    Stop(stop_id="S001", name=..., lat=..., lng=...),
    Stop(stop_id="S002", name=..., lat=..., lng=...),
    Stop(stop_id="S003", name=..., lat=..., lng=...),
]

group = Group(
    group_id="g1",
    name='g1',
    locations=stops,
)
service = Service(
    start_date=base_datetime.date(),
    end_date=base_datetime.date() + timedelta(days=1),
    monday=True,
    tuesday=True,
    wednesday=True,
    thursday=True,
    friday=True,
    saturday=True,
    sunday=True
)
start_windows = [9 * 60, 18 * 60, 22 * 60]
trips = [Trip(
    service=service,
    stop_time=flex_StopTime(
        group=group,
        start_window=timedelta(minutes=s),
        end_window=timedelta(minutes=s + 3 * 60),
    )) for s in start_windows]


class RoutingTestCase(TestCase):
    def setUp(self):
        self.base_datetime = base_datetime
        self.board_time = 10
        self.max_delay_time = 9999
        self.network = Network()
        self.network.add_edge(stops[0].stop_id, stops[1].stop_id, 30, with_rev=True)
        self.network.add_edge(stops[0].stop_id, stops[2].stop_id, 40, with_rev=True)
        self.network.add_edge(stops[1].stop_id, stops[2].stop_id, 50, with_rev=True)
        self.mobility1 = Car(
            mobility_id=...,
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=1,
            trip=trips[0],
            stop=stops[0],
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time)
        )
        self.mobility2 = Car(
            mobility_id=...,
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=4,
            trip=trips[1],
            stop=stops[0],
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time)
        )

    def test_find_a_route(self):
        user = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user]),
                StopTime(stop=stops[1], off=[user])
            ])
        ]
        actual = self.mobility1.routes_appended_new_user(user)

        self.assertEqual(expected, actual)

    def test_find_routes_who_have_same_org_dst(self):
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility2._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1, user2], off=[]),
                StopTime(stop=stops[1], on=[], off=[user1, user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[], off=[user1]),
                StopTime(stop=stops[0], on=[user2], off=[]),
                StopTime(stop=stops[1], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user2], off=[]),
                StopTime(stop=stops[1], on=[], off=[user2]),
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[], off=[user1]),
            ]),
        ]
        actual = self.mobility2.routes_appended_new_user(user2)
        order = [expected.index(e) for e in actual]
        self.assertEqual(order, [2, 0, 1])  
        expected = [a for i, a in sorted(enumerate(expected), key=lambda e: order.index(e[0]))]
        self.assertEqual(expected, actual)

    def test_find_routes_of_exceeded_capacity_bus_who_have_same_org_dst(self):
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility1._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[], off=[user1]),
                StopTime(stop=stops[0], on=[user2], off=[]),
                StopTime(stop=stops[1], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user2], off=[]),
                StopTime(stop=stops[1], on=[], off=[user2]),
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[], off=[user1]),
            ]),
        ]
        actual = self.mobility1.routes_appended_new_user(user2)
        order = [expected.index(e) for e in actual]
        self.assertEqual(order, [1, 0])  
        expected = [a for i, a in sorted(enumerate(expected), key=lambda e: order.index(e[0]))]
        self.assertEqual(expected, actual)

    def test_find_come_back_routes(self):
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility1._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1]),
                StopTime(stop=stops[1], on=[user2], off=[user1]),
                StopTime(stop=stops[0], off=[user2])
            ]),
            Route(stop_times=[
                StopTime(stop=stops[1], on=[user2]),
                StopTime(stop=stops[0], on=[user1], off=[user2]),
                StopTime(stop=stops[1], off=[user1])
            ]),
        ]
        actual = self.mobility1.routes_appended_new_user(user2)
        order = [expected.index(e) for e in actual]
        self.assertEqual(order, [1, 0])  
        expected = [a for i, a in sorted(enumerate(expected), key=lambda e: order.index(e[0]))]
        self.assertEqual(expected, actual)

    def test_find_routes_with_a_passenger_and_a_user(self):
        passenger = User(
            user_id="Passenger",
            org=stops[2],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger]),
                StopTime(stop=stops[1], on=[], off=[user1]),
            ]),
        ]
        self.mobility2._passengers.update({passenger.user_id: passenger})
        self.assertEqual(expected, self.mobility2.routes_appended_new_user(user1))

    def test_find_routes_with_a_passenger_and_two_users(self):
        passenger = User(
            user_id="Passenger",
            org=stops[2],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="U002",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        expected = [
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger]),
                StopTime(stop=stops[1], on=[user2], off=[user1]),
                StopTime(stop=stops[0], on=[], off=[user2])
            ]),
            Route(stop_times=[
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[user1], off=[passenger, user2]),
                StopTime(stop=stops[1], on=[], off=[user1])
            ]),
        ]
        self.mobility2._passengers.update({passenger.user_id: passenger})
        self.mobility2._waiting_users.update({user1.user_id: user1})

        actual = self.mobility2.routes_appended_new_user(user2)
        order = [expected.index(e) for e in actual]
        self.assertEqual(order, [1, 0])  
        expected = [a for i, a in sorted(enumerate(expected), key=lambda e: order.index(e[0]))]
        self.assertEqual(expected, actual)

    def test_find_routes_with_two_passengers_and_two_users(self):
        passenger1 = User(
            user_id="Passenger1",
            org=stops[2],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        passenger2 = User(
            user_id="Passenger2",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=stops[0],
            dst=stops[2],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="U002",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        expected = [
            Route(stop_times=[
                StopTime(stop=stops[1], on=[user2], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[passenger1, user2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[1], on=[user2], off=[passenger2]),
                StopTime(stop=stops[0], on=[], off=[user2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[], off=[passenger1]),
                StopTime(stop=stops[1], on=[user2], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[user2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[1], on=[user2], off=[passenger2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[1], on=[user2], off=[passenger2]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[], off=[user2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[passenger1]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[], off=[passenger1]),
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[], off=[user2]),
                StopTime(stop=stops[2], on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[], off=[passenger1]),
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=stops[0], on=[], off=[passenger1]),
                StopTime(stop=stops[1], on=[], off=[passenger2]),
                StopTime(stop=stops[0], on=[user1], off=[]),
                StopTime(stop=stops[2], on=[], off=[user1]),
                StopTime(stop=stops[1], on=[user2], off=[]),
                StopTime(stop=stops[0], on=[], off=[user2]),
            ]),
        ]
        self.mobility2._passengers.update({passenger1.user_id: passenger1, passenger2.user_id: passenger2})
        self.mobility2._waiting_users.update({user1.user_id: user1})

        actual = self.mobility2.routes_appended_new_user(user2)
        order = [expected.index(e) for e in actual]
        self.assertEqual(order, [4, 1, 3, 5, 2, 9, 10, 11, 0, 7, 8, 6]) 
        expected = [a for i, a in sorted(enumerate(expected), key=lambda e: order.index(e[0]))]
        self.assertEqual(expected, actual)


class DelayCalculationTestCase(TestCase):
    def setUp(self):
        self.base_datetime = base_datetime
        self.board_time = 10
        self.max_delay_time = 30
        self.network = Network()
        self.network.add_edge(stops[0].stop_id, stops[1].stop_id, 30, with_rev=True)
        self.network.add_edge(stops[0].stop_id, stops[2].stop_id, 40, with_rev=True)
        self.network.add_edge(stops[1].stop_id, stops[2].stop_id, 50, with_rev=True)
        self.mobility = Car(
            mobility_id="M001",
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=1,
            trip=trips[0],
            stop=stops[0],
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time),
        )

    def test_ideal_time_when_only_one_user(self):
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user])
        ]))

        expected = [
            timedelta()
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_ideal_time_when_only_one_user_but_wait_for_service(self):
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window - timedelta(minutes=10),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user])
        ]))

        expected = [
            timedelta(minutes=10)
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_ideal_time_when_only_one_user_but_out_of_sevice_time(self):
        desired = trips[0].stop_time.end_window + timedelta(minutes=10) + timedelta(days=1)
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility.env.run(until=desired.total_seconds() / 60)

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user])
        ]))

        expected = [
            self.mobility._max_delay_time
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_ideal_time_when_only_one_user_tomorrow(self):
        desired = trips[0].stop_time.end_window + timedelta(minutes=10)
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility.env.run(until=desired.total_seconds() / 60)
        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user])
        ]))

        expected = [
            trips[0].stop_time.start_window + timedelta(days=1) - desired
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_ideal_time_when_only_one_user_but_out_of_sevice(self):
        desired = timedelta(days=2) + trips[0].stop_time.start_window
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        self.mobility.env.run(until=desired.total_seconds() / 60)

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user])
        ]))

        expected = [
            self.mobility._max_delay_time
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_delayed_by_the_time_the_buses_move_in(self):
        user = User(
            user_id="User",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[1], on=[user], off=[]),
            StopTime(stop=stops[0], on=[], off=[user])
        ]))

        expected = [
            timedelta(minutes=30)
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_two_users_with_same_org_and_dst(self):
        user1 = User(
            user_id="User1",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window + timedelta(minutes=10),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user1, user2], off=[]),
            StopTime(stop=stops[1], on=[], off=[user1, user2])
        ]))

        expected = [
            timedelta(minutes=10), timedelta()
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_two_users(self):
        user1 = User(
            user_id="User1",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window + timedelta(minutes=10),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime + trips[0].stop_time.start_window + timedelta(minutes=40),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=stops[0], on=[user1], off=[]),
            StopTime(stop=stops[1], on=[user2], off=[user1]),
            StopTime(stop=stops[0], on=[], off=[user2])
        ]))

        expected = [
            timedelta(), timedelta(minutes=20)
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)


class PlanningTestCase(TestCase):
    def setUp(self):
        self.base_datetime = base_datetime
        self.board_time = 10
        self.max_delay_time = 30
        self.network = Network()
        self.network.add_edge(stops[0].stop_id, stops[1].stop_id, 30, with_rev=True)
        self.network.add_edge(stops[0].stop_id, stops[2].stop_id, 40, with_rev=True)
        self.network.add_edge(stops[1].stop_id, stops[2].stop_id, 50, with_rev=True)

    def test_plan_the_ideal_route(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[0],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        actual = manager.minimum_delay(user)

        expected = [
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user]),
        ]

        self.assertEqual(expected, actual.stop_times)

    def test_plan_the_ideal_route_but_out_of_service_time(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[0],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        desired = trips[0].stop_time.end_window
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        manager.mobilities["M001"].env.run(until=desired.total_seconds() / 60)

        actual = manager.minimum_delay(user)

        self.assertIsNone(actual)

    def test_plan_the_ideal_route_but_out_of_service(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[0],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        desired = trips[0].stop_time.start_window + timedelta(days=2)
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        manager.mobilities["M001"].env.run(until=desired.total_seconds() / 60)

        actual = manager.minimum_delay(user)

        self.assertIsNone(actual)

    def test_plan_the_ideal_route_after_midnight(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[2],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        desired = trips[2].stop_time.end_window - timedelta(minutes=50)
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        manager.mobilities["M001"].env.run(until=desired.total_seconds() / 60)
        actual = manager.minimum_delay(user)

        expected = [
            StopTime(stop=stops[0], on=[user], off=[]),
            StopTime(stop=stops[1], on=[], off=[user]),
        ]

        self.assertEqual(expected, actual.stop_times)

    def test_plan_the_ideal_route_yesterday_after_midnight(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[2],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        desired = trips[2].stop_time.end_window - timedelta(minutes=50) - timedelta(days=1)
        user = User(
            user_id="User",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + desired,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        manager.mobilities["M001"].env.run(until=desired.total_seconds() / 60)

        actual = manager.minimum_delay(user)

        self.assertIsNone(actual)

    def test_plan_a_route_requested_by_two_users(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[0],
                stop=stops[0]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        user1 = User(
            user_id="User1",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime + trips[0].stop_time.start_window + timedelta(minutes=30),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        manager.mobilities["M001"]._waiting_users.update({user1.user_id: user1})
        actual = manager.minimum_delay(user2)

        expected = [
            StopTime(stop=stops[0], on=[user1], off=[]),
            StopTime(stop=stops[1], on=[user2], off=[user1]),
            StopTime(stop=stops[0], on=[], off=[user2]),
        ]

        self.assertEqual(expected, actual.stop_times)

    def test_plan_a_route_requested_by_two_users_when_two_buses(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=trips[0],
                stop=stops[0]
            ), CarSetting(
                mobility_id="M002",
                capacity=1,
                trip=trips[0],
                stop=stops[1]
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time
        )
        user1 = User(
            user_id="User1",
            org=stops[0],
            dst=stops[1],
            desired=self.base_datetime + trips[0].stop_time.start_window,
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=stops[1],
            dst=stops[0],
            desired=self.base_datetime + trips[0].stop_time.start_window + timedelta(minutes=30),
            ideal=timedelta(minutes=self.network.duration(stops[0].stop_id, stops[1].stop_id) + self.board_time * 2)
        )

        manager.mobilities["M001"]._waiting_users.update({user1.user_id: user1})
        actual = manager.minimum_delay(user2)

        expected = [
            StopTime(stop=stops[1], on=[user2], off=[]),
            StopTime(stop=stops[0], on=[], off=[user2]),
        ]

        self.assertEqual(expected, actual.stop_times)


if __name__ == '__main__':
    unittest.main()
