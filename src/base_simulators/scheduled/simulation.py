# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from datetime import datetime
from logging import getLogger

from environment import Environment
from core import Trip
from event import EventQueue, ReserveFailedEvent
from mobility import CarManager, CarSetting

logger = getLogger("schedsim")


class Simulation:
    def __init__(self, start_time: datetime, capacity: int, trips: typing.Dict[str, Trip]) -> None:
        self.env = Environment(start_time=start_time)
        self.event_queue = EventQueue()
        self.car_manager = CarManager(
            env=self.env,
            event_queue=self.event_queue,
            settings=[
                CarSetting(
                    mobility_id=trip_id,
                    capacity=capacity,  # ToDo: All trips may not have the same capacity.
                    trip=trip
                ) for trip_id, trip in trips.items()
            ]
        )
        self.stops = {
            stop_time.stop.stop_id: stop_time.stop
            for trip in trips.values() for stop_time in trip.stop_times()
        }

    def start(self):
        self.car_manager.run()

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        return self.env.now

    def reservable(self, org: str, dst: str):
        org = self.stops[org]
        dst = self.stops[dst]
        if mobility := self.car_manager.earliest_mobility(org, dst, self.env.now):
            return mobility.is_reservable(mobility.earliest_path(org, dst, self.env.now))
        return False

    def reserve_user(self, user_id: str, org: str, dst: str, dept: float):
        """ 利用者が車両の乗車予約をする。"""

        org = self.stops[org]
        dst = self.stops[dst]
        if mobility := self.car_manager.earliest_mobility(org, dst, dept):
            earliest_path = mobility.earliest_path(org, dst, dept)
            if mobility.is_reservable(earliest_path):
                mobility.reserve(user_id, earliest_path)
                return

        self.env.process(self._failed_to_reserve(user_id))

    def _failed_to_reserve(self, user_id: str):
        yield self.env.timeout(0)
        self.event_queue.enqueue(ReserveFailedEvent(
            env=self.env,
            user_id=user_id,
        ))

    def dept_user(self, user_id: str):
        """ 利用者が予約した車両を利用して目的地に向かう。

        利用者は出発地で待機する。予約した車両が来たら乗車して目的地に向かう。"""

        user = self.car_manager.find_user(user_id)
        assert user
        user.wait()

        return user
