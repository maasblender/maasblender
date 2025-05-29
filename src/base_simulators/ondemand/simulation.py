# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from datetime import datetime, timedelta
from logging import getLogger

from environment import Environment
from core import Network, User, Trip
from event import EventQueue
from mobility import CarManager, CarSetting

logger = getLogger(__name__)


class Simulation:
    def __init__(
        self,
        start_time: datetime,
        network: Network,
        enable_ortools: bool,
        board_time: float,
        max_delay_time: float,
        trips: dict[str, Trip],
        settings: typing.Collection[CarSetting],
        max_calculation_seconds: int = 30,
        max_calculation_stop_times_length: int = 10,
    ):
        self.env = Environment(start_time=start_time)
        self.event_queue = EventQueue(self.env)
        self.network = network
        self.board_time = board_time
        self.stops = {
            location.stop_id: location
            for trip in trips.values()
            for location in trip.stop_time.group.locations
        }
        if enable_ortools and board_time > 0:
            self.board_time = 0
            logger.warning("board_time is ignored when enable_ortools is true")
        self.car_manager = CarManager(
            network=self.network,
            event_queue=self.event_queue,
            enable_ortools=enable_ortools,
            board_time=board_time,
            max_delay_time=max_delay_time,
            max_calculation_seconds=max_calculation_seconds,
            max_calculation_stop_times_length=max_calculation_stop_times_length,
            settings=settings,
        )

    def start(self):
        pass

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        return self.env.now

    def reservable(self, org: str, dst: str, dept: float = None):
        org = self.stops[org]
        dst = self.stops[dst]
        return bool(
            self.car_manager.minimum_delay(
                User(
                    user_id=...,
                    demand_id=...,
                    org=org,
                    dst=dst,
                    desired=self.env.datetime_from(dept)
                    if dept
                    else self.env.datetime_now,
                    ideal=timedelta(
                        minutes=self.network.duration(org.stop_id, dst.stop_id)
                        + self.board_time * 2
                    ),
                )
            )
        )

    def reserve_user(
        self, user_id: str, demand_id: str, org: str, dst: str, dept: float
    ):
        org = self.stops[org]
        dst = self.stops[dst]
        self.car_manager.reserve(
            User(
                user_id=user_id,
                demand_id=demand_id,
                org=org,
                dst=dst,
                desired=self.env.datetime_from(dept),
                ideal=timedelta(
                    minutes=self.network.duration(org.stop_id, dst.stop_id)
                    + self.board_time * 2
                ),
            )
        )

    def ready_to_depart(self, user_id: str):
        """Notify the on-demand bus that the user has arrived at the departure station and is ready to get on the bus
        when the bus arrives.

        Without the notification, the user cannot get on the bus.
        """

        if user := self.car_manager.depart(user_id):
            return user
        else:
            logger.warning(
                f"User '{user_id}' has been notified that the user is ready to depart, but the corresponding "
                f"reservation cannot be found. The reservation may have failed or the user may have already departed."
            )
