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

logger = getLogger("schedsim")


class Car(Mobility):
    """ 移動体

    時刻表とおりに停車地を移動する。停車地では乗客が昇降できる。"""

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
        """ 乗客の乗車処理 """

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
        """ 乗客の降車処理 """

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
        """ 運行プロセス """
        while True:
            if trip := self.trip():

                # 時刻表に従って順番に停車駅に移動する。
                for plan in trip.stop_times_at(self.operation_date):
                    yield self.env.timeout_until(plan.arrival)
                    self._arrive(plan.stop)
                    yield self.env.timeout_until(plan.departure)
                    self._departure()

                # ToDo: 将来的に未来の予約もする場合は `not len(self.passengers)` を検討する。
                assert not len(self.users)

            else:
                # 運行がない場合は次の日まで待機する。
                yield self.env.timeout_until(
                    datetime.combine(self.current_datetime.date() + timedelta(days=1), time())
                )

    def reserve(self, user_id: str, path: Path):
        """ 乗車予約をする """

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
        """ 出発地から目的地に移動する最短経路を返す

        移動できない場合は None を返す。"""

        dept_datetime = self.env.datetime_from(dept)

        # 運行日が当日を含む前後1日の経路を探索する。
        for path in chain(
            self.paths(org, dst, at=dept_datetime.date() - timedelta(days=1)),
            self.paths(org, dst, at=dept_datetime.date()),
            self.paths(org, dst, at=dept_datetime.date() + timedelta(days=1))
        ):
            # 乗車できる
            if dept_datetime < path.departure:
                return path
        return None


class CarSetting(typing.NamedTuple):
    mobility_id: str
    capacity: int
    trip: Trip


class CarManager:
    """ 複数の乗合バスを管理する """

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
        """ 最も早く目的地に到着する車両を返す

        乗車予約できる車両がない場合は None を返す。"""

        car_arrivals = {
            k: v.arrival for k, v in {
                car: car.earliest_path(org, dst, dept)
                for car in self.mobilities.values()
            }.items() if v
        }

        if not len(car_arrivals):
            return None

        return sorted(car_arrivals.items(), key=lambda x: x[1])[0][0]
