# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from datetime import date, datetime, time, timedelta
from itertools import chain
from logging import getLogger

from core import (
    AbstractStopTimeWithDateTime,
    DeviatedStopTimeWithDateTime,
    Mobility,
    Path,
    StopLike,
    StopTimeWithDateTime,
    Trip,
    TripLocation,
    User,
    UserStatus,
)
from environment import Environment
from event import ArrivedEvent, DepartedEvent, EventQueue, ReservedEvent
from routing import EqualIntervalRouter, Router

logger = getLogger(__name__)


class Car(Mobility):
    env: Environment
    events: EventQueue
    _capacity: int
    _stop: StopLike | None
    users: dict[
        str, User
    ]  # 車両を予約している/停車駅に待機している/車両に乗車している すべての利用者

    def __init__(
        self,
        env: Environment,
        queue: EventQueue,
        mobility_id: str,
        capacity: int,
        trip: Trip,
        router: Router | None = None,
    ):
        super().__init__(mobility_id=mobility_id, trip=trip)
        self.env = env
        self.events = queue
        self._capacity = capacity
        self._stop = None
        self.users = {}
        self.router = router if router is not None else EqualIntervalRouter()
        self.deviation_plans: dict[
            tuple[date, str], list[DeviatedStopTimeWithDateTime]
        ] = {}

    @property
    def stop(self):
        return self._stop

    @property
    def current_datetime(self):
        return self.env.datetime_from(self.env.now)

    def _get_users_of(self, status: UserStatus):
        return [user for user in self.users.values() if user.status == status]

    @property
    def reserved_users(self):
        return self._get_users_of(UserStatus.RESERVED)

    @property
    def waiting_users(self):
        return self._get_users_of(UserStatus.WAITING)

    @property
    def passengers(self):
        return self._get_users_of(UserStatus.RIDING)

    async def is_reservable(self, path: Path, *, router: Router | None = None) -> bool:
        return await self.plan_reservation(path, router=router) is not None

    async def plan_reservation(
        self, path: Path, *, router: Router | None = None
    ) -> dict[tuple[date, str], list[DeviatedStopTimeWithDateTime]] | None:
        # Include the new request alongside all existing reservations.
        # Occupancy can increase only at a departure, so check every departure.
        # Count each timetable interval as [departure, arrival): a passenger
        # arriving at this instant leaves before another passenger boards.
        paths = [user.path for user in self.users.values()] + [path]
        for reservation in paths:
            departure = reservation.departure
            passengers = sum(
                other.departure <= departure < other.arrival for other in paths
            )
            if passengers > self._capacity:
                return None

        # Replan only the deviation areas used by this pickup or drop-off.
        at_date = path.pick_up.reference_date
        stops = [
            stop for stop in (path.pick_up_stop, path.drop_off_stop) if stop is not None
        ]
        if not stops:
            return {}
        router = router if router is not None else self.router
        stop_times = list(self.trip(at_date).iter_stop_times_at(at_date))
        result = {}
        for index, stop_time in enumerate(stop_times):
            if not isinstance(stop_time, TripLocation):
                continue
            location_id = stop_time.location_id
            added = [stop for stop in stops if stop.location.location_id == location_id]
            if not added:
                continue
            # Each deviation area lies between two fixed timetable stops.
            # After its departure time, its movement plan cannot be changed.
            origin = stop_times[index - 1]
            destination = stop_times[index + 1]
            if origin.departure < self.current_datetime:
                return None
            # Include existing pickup/drop-off points for the same service date
            # and area, so the router produces a plan for all affected users.
            existing = [
                stop
                for user in self.users.values()
                if user.path.pick_up.reference_date == at_date
                for stop in (user.path.pick_up_stop, user.path.drop_off_stop)
                if stop is not None and stop.location.location_id == location_id
            ]
            # The router orders and times these stops within the timetable window.
            plan = await router.plan(
                origin=origin.stop,
                destination=destination.stop,
                temporary_stops=[*existing, *added],
                departure=origin.departure,
                arrival=destination.arrival,
            )
            if plan is None:
                return None
            result[(at_date, location_id)] = plan
        # Return all plans together; reserve() saves them only after success.
        return result

    def _get_on(self):
        assert self.stop

        for user in self.waiting_users:
            # 現在地が予定とおりの乗車駅である場合、乗客を乗車させる。
            if (
                user.path.org == self.stop
                and user.path.departure <= self.current_datetime
            ):
                self.events.enqueue(
                    DepartedEvent(env=self.env, mobility=self, user=user)
                )
                user.ride()

        assert len(self.passengers) <= self._capacity

    def _get_off(self):
        assert self.stop

        for user in self.passengers:
            # 現在地が予定とおりの降車駅である場合、乗客を降車させる。
            if user.path.dst == self.stop:
                self.events.enqueue(
                    ArrivedEvent(env=self.env, mobility=self, user=user)
                )
                self.users.pop(user.user_id)

    def _arrive(self, stop: StopLike):
        self._stop = stop
        self.events.enqueue(ArrivedEvent(env=self.env, mobility=self))
        self._get_off()

    def _departure(self):
        self._get_on()
        self.events.enqueue(DepartedEvent(env=self.env, mobility=self))
        self._stop = None

    def _iter_movement_plans(
        self, trip: Trip, at_date: date
    ) -> typing.Iterator[AbstractStopTimeWithDateTime]:
        for stop_time in trip.iter_stop_times_at(at_date):
            match stop_time:
                case StopTimeWithDateTime():
                    yield stop_time
                case TripLocation(location_id=location_id):
                    yield from self.deviation_plans.get((at_date, location_id), [])

    def run(self):
        while True:
            if trip := self.trip():
                stop_times = trip.stop_times_at(self.operation_date)
                if stop_times and stop_times[0].arrival < self.current_datetime:
                    raise ValueError(
                        "simulation start time is in the middle of an operation day: "
                        f"mobility_id={self.mobility_id}, "
                        f"start_time={self.env.start_time.isoformat()}, "
                        f"current_time={self.current_datetime.isoformat()}, "
                        f"first_departure_time={stop_times[0].arrival.isoformat()}"
                    )

                # 時刻表に従って順番に停車駅に移動する。
                for plan in self._iter_movement_plans(trip, self.operation_date):
                    yield self.env.timeout_until(plan.arrival)
                    self._arrive(plan.stop)
                    yield self.env.timeout_until(plan.departure)
                    self._departure()

                assert not self.passengers, f"remain users on end: {self}"

            else:
                # If there is no operation for the day, wait until the next day.
                yield self.env.timeout_until(
                    datetime.combine(
                        self.current_datetime.date() + timedelta(days=1), time()
                    )
                )

    def __str__(self):
        data = {
            "now": self.env.now,
            "mobility_id": self.mobility_id,
            "trip": self._trip,
            "stop": self.stop,
            "users": tuple(self.users.values()),
        }
        return f"Car({data})"

    def reserve(
        self,
        user_id: str,
        demand_id: str,
        path: Path,
        plans: dict[tuple[date, str], list[DeviatedStopTimeWithDateTime]],
    ):
        assert user_id not in self.users
        user = User(user_id, demand_id, path)
        self.deviation_plans.update(plans)
        self.users[user_id] = user
        self.env.process(self._reserved(user))

    def _reserved(self, user: User):
        yield self.env.timeout(0)
        self.events.enqueue(
            ReservedEvent(
                env=self.env,
                mobility=self,
                user=user,
            )
        )

    def earliest_path(self, org: StopLike, dst: StopLike, dept: float) -> Path | None:
        """Returns the shortest path from the `org` point to the `dst` point

        Returns `None` if no route can be found"""

        dept_datetime = self.env.datetime_from(dept)

        # Search for paths for one day before or after the day of operation, including the day of operation.
        for path in chain(
            self.paths(org, dst, at=dept_datetime.date() - timedelta(days=1)),
            self.paths(org, dst, at=dept_datetime.date()),
            self.paths(org, dst, at=dept_datetime.date() + timedelta(days=1)),
        ):
            # This route is available for boarding.
            if dept_datetime <= path.departure:
                return path
        return None


class CarSetting(typing.NamedTuple):
    mobility_id: str
    capacity: int
    trip: Trip
    router: Router | None = None


class CarManager:
    """Manage multiple transit buses"""

    def __init__(
        self,
        env: Environment,
        event_queue: EventQueue,
        settings: typing.Collection[CarSetting],
    ):
        self.env = env
        self.event_queue = event_queue
        self.mobilities: dict[str, Car] = {
            setting.mobility_id: Car(
                env=self.env,
                queue=self.event_queue,
                mobility_id=setting.mobility_id,
                capacity=setting.capacity,
                trip=setting.trip,
                router=setting.router,
            )
            for setting in settings
        }

    def find_user(self, user_id: str):
        for mobility in self.mobilities.values():
            if user_id in mobility.users:
                return mobility.users[user_id]
        return None

    def run(self):
        for car in self.mobilities.values():
            self.env.process(car.run())

    def earliest_mobility(
        self, org: StopLike, dst: StopLike, dept: float
    ) -> Car | None:
        """Return the vehicle that arrives at the destination earliest.

        Returns `None` If there is no vehicle available"""

        car_arrivals = {
            k: v.arrival
            for k, v in {
                car: car.earliest_path(org, dst, dept)
                for car in self.mobilities.values()
            }.items()
            if v
        }

        if not len(car_arrivals):
            return None

        return min(car_arrivals.items(), key=lambda x: x[1])[0]
