# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from datetime import datetime
from logging import getLogger

from environment import Environment
from event import EventQueue, ReserveFailedEvent
from mobility import CarManager, CarSetting
from trip import SingleTrip, BlockTrip

logger = getLogger(__name__)


class Simulation:
    def __init__(
        self,
        start_time: datetime,
        capacity: int,
        trips: typing.Dict[str, SingleTrip] = None,
        blocks: typing.Dict[str, list[SingleTrip]] = None,
    ) -> None:
        trips = trips or {}
        blocks = blocks or {}

        self.env = Environment(start_time=start_time)
        self.event_queue = EventQueue()
        self.car_manager = CarManager(
            env=self.env,
            event_queue=self.event_queue,
            # ToDo: All trips may not have the same capacity.
            settings=[
                CarSetting(
                    mobility_id=trip_id,
                    capacity=capacity,
                    trip=trip,
                )
                for trip_id, trip in trips.items()
            ]
            + [
                CarSetting(
                    mobility_id=block_id,
                    capacity=capacity,
                    trip=BlockTrip(
                        trips=sorted(trips, key=lambda x: x.stop_times[0].departure)
                    ),
                )
                for block_id, trips in blocks.items()
            ],
        )
        self.stops = {
            stop.stop_id: stop for trip in trips.values() for stop in trip.stops
        } | {
            stop.stop_id: stop
            for block in blocks.values()
            for trip in block
            for stop in trip.stops
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
            return mobility.is_reservable(
                mobility.earliest_path(org, dst, self.env.now)
            )
        return False

    def reserve_user(
        self, user_id: str, demand_id: str, org: str, dst: str, dept: float
    ):
        org = self.stops[org]
        dst = self.stops[dst]
        if mobility := self.car_manager.earliest_mobility(org, dst, dept):
            earliest_path = mobility.earliest_path(org, dst, dept)
            if mobility.is_reservable(earliest_path):
                mobility.reserve(user_id, demand_id, earliest_path)
                return

        self.env.process(self._failed_to_reserve(user_id, demand_id))

    def _failed_to_reserve(self, user_id: str, demand_id: str):
        yield self.env.timeout(0)
        self.event_queue.enqueue(
            ReserveFailedEvent(
                env=self.env,
                user_id=user_id,
                demand_id=demand_id,
            )
        )

    def dept_user(self, user_id: str):
        """A user uses the vehicle reserved by him/her self to go to the destination.

        A user waits at the departure point. When the reserved vehicle arrives,
        the user boards the vehicle and heads for the destination."""

        user = self.car_manager.find_user(user_id)
        assert user
        user.wait()

        return user
