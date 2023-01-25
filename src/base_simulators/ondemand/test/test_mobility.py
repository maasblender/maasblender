# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
from unittest import TestCase
from unittest.mock import Mock
from datetime import datetime, timedelta

from core import User, Stop, Network
from environment import Environment
from mobility import Car, Route, StopTime, Delay, CarManager, CarSetting


class RoutingTestCase(TestCase):
    def setUp(self):
        self.base_datetime = datetime(year=2022, month=1, day=1)
        self.board_time = 10
        self.max_delay_time = 9999
        self.stop1 = Stop(stop_id="S001", name=..., lat=..., lng=...)
        self.stop2 = Stop(stop_id="S002", name=..., lat=..., lng=...)
        self.stop3 = Stop(stop_id="S003", name=..., lat=..., lng=...)
        self.network = Network()
        self.network.add_edge(self.stop1.stop_id, self.stop2.stop_id, 30, with_rev=True)
        self.network.add_edge(self.stop1.stop_id, self.stop3.stop_id, 40, with_rev=True)
        self.network.add_edge(self.stop2.stop_id, self.stop3.stop_id, 50, with_rev=True)
        self.mobility1 = Car(
            mobility_id=...,
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=1,
            trip=...,
            stop=self.stop1,
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time)
        )
        self.mobility2 = Car(
            mobility_id=...,
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=4,
            trip=...,
            stop=self.stop1,
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time)
        )

    def test_find_a_route(self):
        user = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        expected = [
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user]),
                StopTime(stop=self.stop2, off=[user])
            ])
        ]
        actual = self.mobility1.routes_appended_new_user(user)

        self.assertEqual(expected, actual)

    def test_find_routes_who_have_same_org_dst(self):
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        self.mobility2._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1, user2], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user1, user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user1]),
                StopTime(stop=self.stop1, on=[user2], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user2], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user2]),
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user1]),
            ]),
        }
        self.assertEqual(expected, set(self.mobility2.routes_appended_new_user(user2)))

    def test_find_routes_of_exceeded_capacity_bus_who_have_same_org_dst(self):
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        self.mobility1._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user1]),
                StopTime(stop=self.stop1, on=[user2], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user2], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user2]),
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[], off=[user1]),
            ]),
        }
        self.assertEqual(expected, set(self.mobility1.routes_appended_new_user(user2)))

    def test_find_come_back_routes(self):
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        self.mobility1._reserved_users.update({user1.user_id: user1})

        user2 = User(
            user_id="U002",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1]),
                StopTime(stop=self.stop2, on=[user2], off=[user1]),
                StopTime(stop=self.stop1, off=[user2])
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[user2]),
                StopTime(stop=self.stop1, on=[user1], off=[user2]),
                StopTime(stop=self.stop2, off=[user1])
            ]),
        }
        self.assertEqual(expected, set(self.mobility1.routes_appended_new_user(user2)))

    def test_find_routes_with_a_passenger_and_a_user(self):
        passenger = User(
            user_id="Passenger",
            org=self.stop3,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger]),
                StopTime(stop=self.stop2, on=[], off=[user1]),
            ]),
        }
        self.mobility2._passengers.update({passenger.user_id: passenger})
        self.assertEqual(expected, set(self.mobility2.routes_appended_new_user(user1)))

    def test_find_routes_with_a_passenger_and_two_users(self):
        passenger = User(
            user_id="Passenger",
            org=self.stop3,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="U002",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger]),
                StopTime(stop=self.stop2, on=[user2], off=[user1]),
                StopTime(stop=self.stop1, on=[], off=[user2])
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[user1], off=[passenger, user2]),
                StopTime(stop=self.stop2, on=[], off=[user1])
            ]),
        }
        self.mobility2._passengers.update({passenger.user_id: passenger})
        self.mobility2._waiting_users.update({user1.user_id: user1})

        self.assertEqual(expected, set(self.mobility2.routes_appended_new_user(user2)))

    def test_find_routes_with_two_passengers_and_two_users(self):
        passenger1 = User(
            user_id="Passenger1",
            org=self.stop3,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        passenger2 = User(
            user_id="Passenger2",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user1 = User(
            user_id="U001",
            org=self.stop1,
            dst=self.stop3,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="U002",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        expected = {
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[user2], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[passenger1, user2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop2, on=[user2], off=[passenger2]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[], off=[passenger1]),
                StopTime(stop=self.stop2, on=[user2], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[user2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop2, on=[user2], off=[passenger2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop2, on=[user2], off=[passenger2]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[passenger1]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[], off=[passenger1]),
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[], off=[passenger1]),
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
            Route(stop_times=[
                StopTime(stop=self.stop1, on=[], off=[passenger1]),
                StopTime(stop=self.stop2, on=[], off=[passenger2]),
                StopTime(stop=self.stop1, on=[user1], off=[]),
                StopTime(stop=self.stop3, on=[], off=[user1]),
                StopTime(stop=self.stop2, on=[user2], off=[]),
                StopTime(stop=self.stop1, on=[], off=[user2]),
            ]),
        }
        self.mobility2._passengers.update({passenger1.user_id: passenger1, passenger2.user_id: passenger2})
        self.mobility2._waiting_users.update({user1.user_id: user1})

        self.assertEqual(expected, set(self.mobility2.routes_appended_new_user(user2)))


class DelayCalculationTestCase(TestCase):
    def setUp(self):
        self.base_datetime = datetime(year=2022, month=1, day=1)
        self.board_time = 10
        self.max_delay_time = 30
        self.stop1 = Stop(stop_id="S001", name=..., lat=..., lng=...)
        self.stop2 = Stop(stop_id="S002", name=..., lat=..., lng=...)
        self.stop3 = Stop(stop_id="S003", name=..., lat=..., lng=...)
        self.network = Network()
        self.network.add_edge(self.stop1.stop_id, self.stop2.stop_id, 30, with_rev=True)
        self.network.add_edge(self.stop1.stop_id, self.stop3.stop_id, 40, with_rev=True)
        self.network.add_edge(self.stop2.stop_id, self.stop3.stop_id, 50, with_rev=True)
        self.mobility = Car(
            mobility_id="M001",
            network=self.network,
            queue=Mock(env=Environment(self.base_datetime)),
            capacity=1,
            trip=...,
            stop=self.stop1,
            board_time=timedelta(minutes=self.board_time),
            max_delay_time=timedelta(minutes=self.max_delay_time),
        )

    def test_ideal_time_when_only_one_user(self):
        user = User(
            user_id="User",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=self.stop1, on=[user], off=[]),
            StopTime(stop=self.stop2, on=[], off=[user])
        ]))

        expected = [
            timedelta()
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_delayed_by_the_time_the_buses_move_in(self):
        user = User(
            user_id="User",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=self.stop2, on=[user], off=[]),
            StopTime(stop=self.stop1, on=[], off=[user])
        ]))

        expected = [
            timedelta(minutes=30)
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_two_users_with_same_org_and_dst(self):
        user1 = User(
            user_id="User1",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime + timedelta(minutes=10),
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=self.stop1, on=[user1, user2], off=[]),
            StopTime(stop=self.stop2, on=[], off=[user1, user2])
        ]))

        expected = [
            timedelta(minutes=10), timedelta()
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)

    def test_two_users(self):
        user1 = User(
            user_id="User1",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime + timedelta(minutes=10),
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime + timedelta(minutes=40),
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        actual = Delay(car=self.mobility, plan=Route(stop_times=[
            StopTime(stop=self.stop1, on=[user1], off=[]),
            StopTime(stop=self.stop2, on=[user2], off=[user1]),
            StopTime(stop=self.stop1, on=[], off=[user2])
        ]))

        expected = [
            timedelta(), timedelta(minutes=20)
        ]

        self.assertEqual(expected, actual.values)
        self.assertEqual(sum(expected, timedelta()), actual.value)


class PlanningTestCase(TestCase):
    def setUp(self):
        self.base_datetime = datetime(year=2022, month=1, day=1)
        self.board_time = 10
        self.max_delay_time = 30
        self.stop1 = Stop(stop_id="S001", name=..., lat=..., lng=...)
        self.stop2 = Stop(stop_id="S002", name=..., lat=..., lng=...)
        self.stop3 = Stop(stop_id="S003", name=..., lat=..., lng=...)
        self.network = Network()
        self.network.add_edge(self.stop1.stop_id, self.stop2.stop_id, 30, with_rev=True)
        self.network.add_edge(self.stop1.stop_id, self.stop3.stop_id, 40, with_rev=True)
        self.network.add_edge(self.stop2.stop_id, self.stop3.stop_id, 50, with_rev=True)

    def test_plan_the_ideal_route(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=...,
                stop=self.stop1
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        user = User(
            user_id="User",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        actual = manager.minimum_delay(user)

        expected = [
            StopTime(stop=self.stop1, on=[user], off=[]),
            StopTime(stop=self.stop2, on=[], off=[user]),
        ]

        self.assertEqual(expected, actual.stop_times)

    def test_plan_a_route_requested_by_two_users(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=...,
                stop=self.stop1
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time,
        )
        user1 = User(
            user_id="User1",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime + timedelta(minutes=30),
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        manager.mobilities["M001"]._waiting_users.update({user1.user_id: user1})
        actual = manager.minimum_delay(user2)

        expected = [
            StopTime(stop=self.stop1, on=[user1], off=[]),
            StopTime(stop=self.stop2, on=[user2], off=[user1]),
            StopTime(stop=self.stop1, on=[], off=[user2]),
        ]

        self.assertEqual(expected, actual.stop_times)

    def test_plan_a_route_requested_by_two_users_when_two_buses(self):
        manager = CarManager(
            network=self.network,
            event_queue=Mock(env=Environment(self.base_datetime)),
            settings=[CarSetting(
                mobility_id="M001",
                capacity=1,
                trip=...,
                stop=self.stop1
            ), CarSetting(
                mobility_id="M002",
                capacity=1,
                trip=...,
                stop=self.stop2
            )],
            board_time=self.board_time,
            max_delay_time=self.max_delay_time
        )
        user1 = User(
            user_id="User1",
            org=self.stop1,
            dst=self.stop2,
            desired=self.base_datetime,
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )
        user2 = User(
            user_id="User2",
            org=self.stop2,
            dst=self.stop1,
            desired=self.base_datetime + timedelta(minutes=30),
            ideal=timedelta(minutes=self.network.duration(self.stop1.stop_id, self.stop2.stop_id) + self.board_time * 2)
        )

        manager.mobilities["M001"]._waiting_users.update({user1.user_id: user1})
        actual = manager.minimum_delay(user2)

        expected = [
            StopTime(stop=self.stop2, on=[user2], off=[]),
            StopTime(stop=self.stop1, on=[], off=[user2]),
        ]

        self.assertEqual(expected, actual.stop_times)
