# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from logging import getLogger
from itertools import chain
from datetime import datetime, time, timedelta

from core import Path, Trip, Stop, UserStatus, User, Mobility
from environment import Environment
from event import EventQueue, DepartedEvent, ArrivedEvent, ReservedEvent

logger = getLogger(__name__)


class Car(Mobility):
    def __init__(self, env: Environment, queue: EventQueue,
                 mobility_id: str, capacity: int, trip: Trip):
        super().__init__(mobility_id=mobility_id, trip=trip)
        self.env = env
        self.events = queue
        self._capacity = capacity
        self._stop: typing.Optional[Stop] = None
        self.users: typing.Dict[str, User] = {}  # 車両を予約している/停車駅に待機している/車両に乗車している すべての利用者

    @property
    def stop(self):
        return self._stop

    @property
    def current_datetime(self):
        return self.env.datetime_from(self.env.now)

    @property
    def reserved_users(self):
        return [user for user in self.users.values() if user.status == UserStatus.RESERVED]

    @property
    def waiting_users(self):
        return [user for user in self.users.values() if user.status == UserStatus.WAITING]

    @property
    def passengers(self):
        return [user for user in self.users.values() if user.status == UserStatus.RIDING]

    def is_reservable(self, reservation: Path):
        paths = [user.path for user in self.users.values()] + [reservation]
        for path in paths:
            departure = path.departure
            if len([path for path in paths if path.departure <= departure < path.arrival]) > self._capacity:
                return False
        return True

    def _get_on(self):
        assert self.stop

        for user in self.waiting_users:
            # 現在地が予定とおりの乗車駅である場合、乗客を乗車させる。
            if user.path.org == self.stop and user.path.departure == self.current_datetime:
                self.events.enqueue(DepartedEvent(
                    env=self.env,
                    mobility=self,
                    user=user
                ))
                user.ride()

        assert len(self.passengers) <= self._capacity

    def _get_off(self):
        assert self.stop

        for user in self.passengers:
            # 現在地が予定とおりの降車駅である場合、乗客を降車させる。
            if user.path.dst == self.stop:
                assert user.path.arrival == self.current_datetime
                self.events.enqueue(ArrivedEvent(
                    env=self.env,
                    mobility=self,
                    user=user
                ))
                self.users.pop(user.user_id)

    def _arrive(self, stop: Stop):
        self._stop = stop
        self.events.enqueue(ArrivedEvent(env=self.env, mobility=self))
        self._get_off()

    def _departure(self):
        self._get_on()
        self.events.enqueue(DepartedEvent(env=self.env, mobility=self))
        self._stop = None

    def run(self):
        while True:
            if trip := self.trip():

                # 時刻表に従って順番に停車駅に移動する。
                for plan in trip.stop_times_at(self.operation_date):
                    yield self.env.timeout_until(plan.arrival)
                    self._arrive(plan.stop)
                    yield self.env.timeout_until(plan.departure)
                    self._departure()

                assert not self.passengers, f"remain users on end: {self}"

            else:
                # If there is no operation for the day, wait until the next day.
                yield self.env.timeout_until(
                    datetime.combine(self.current_datetime.date() + timedelta(days=1), time())
                )

    def __str__(self):
        data = dict(
            now=self.env.now,
            mobility_id=self.mobility_id,
            trip=self._trip,
            stop=self.stop,
            users=tuple(self.users.values()),
        )
        return f"Car({data})"

    def reserve(self, user_id: str, path: Path):
        assert user_id not in self.users
        self.users.update({user_id: User(user_id, path)})
        self.env.process(self._reserved(self.users[user_id]))

    def _reserved(self, user: User):
        yield self.env.timeout(0)
        self.events.enqueue(ReservedEvent(
            env=self.env,
            mobility=self,
            user=user,
        ))

    def earliest_path(self, org: Stop, dst: Stop, dept: float):
        """ Returns the shortest path from the `org` point to the `dst` point

        Returns `None` if no route can be found"""

        dept_datetime = self.env.datetime_from(dept)

        # Search for paths for one day before or after the day of operation, including the day of operation.
        for path in chain(
            self.paths(org, dst, at=dept_datetime.date() - timedelta(days=1)),
            self.paths(org, dst, at=dept_datetime.date()),
            self.paths(org, dst, at=dept_datetime.date() + timedelta(days=1))
        ):
            # This route is available for boarding.
            if dept_datetime < path.departure:
                return path
        return None


class CarSetting(typing.NamedTuple):
    mobility_id: str
    capacity: int
    trip: Trip


class CarManager:
    """ Manage multiple transit buses """

    def __init__(self, env: Environment, event_queue: EventQueue, settings: typing.Collection[CarSetting]):
        self.env = env
        self.event_queue = event_queue
        self.mobilities: typing.Dict[str, Car] = {
            setting.mobility_id: Car(
                env=self.env,
                queue=self.event_queue,
                mobility_id=setting.mobility_id,
                capacity=setting.capacity,
                trip=setting.trip
            ) for setting in settings
        }

    def find_user(self, user_id: str):
        for mobility in self.mobilities.values():
            if user_id in mobility.users:
                return mobility.users[user_id]
        return None

    def run(self):
        for car in self.mobilities.values():
            self.env.process(car.run())

    def earliest_mobility(self, org: Stop, dst: Stop, dept: float) -> typing.Optional[Car]:
        """ Return the vehicle that arrives at the destination earliest.

        Returns `None` If there is no vehicle available """

        car_arrivals = {
            k: v.arrival for k, v in {
                car: car.earliest_path(org, dst, dept)
                for car in self.mobilities.values()
            }.items() if v
        }

        if not len(car_arrivals):
            return None

        return sorted(car_arrivals.items(), key=lambda x: x[1])[0][0]
