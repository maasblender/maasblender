# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import dataclasses
import logging
import time
import typing
from datetime import datetime, timedelta
import itertools
import functools

from .core import Trip, Stop, Network, User, Mobility
from .event import EventQueue


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Schedule:
    current: typing.Optional[StopTime] = None
    stop_times: typing.Sequence[StopTime] = dataclasses.field(default_factory=list)

    def __bool__(self):
        return bool(self.stop_times)

    def update(self, stop_times: typing.Sequence[StopTime]):
        self.stop_times = stop_times

        if not self.current or self.current.stop == self.stop_times[0].stop:
            self.pop()
        else:
            self.current.on = []
            self.current.off = []

        return self

    def pop(self):
        if self:
            self.current = self.stop_times[0]
            self.stop_times = self.stop_times[1:]
        else:
            self.current = None
            self.stop_times: typing.List[StopTime] = []
        return self.current


@dataclasses.dataclass
class TimeoutWatchDog:
    name: str
    limit: int  # [sec]
    interval: int = 10  # [sec]
    start_time: float = dataclasses.field(default_factory=time.perf_counter)
    count: int = 0

    def check(self, car: Car, user: User, route: Route):
        elapsed = time.perf_counter() - self.start_time
        # warning log at every interval
        if elapsed >= self.interval + self.interval * self.count:
            if self.count == 0:
                logger.info("%s: elapsed=%s[sec], car=%s, user=%s, route=%s",
                            self.name, elapsed, car, user.user_id, route.stop_times)
            else:
                logger.info("%s: elapsed=%s[sec]", self.name, elapsed)
            self.count += 1
        if elapsed < self.limit:
            return True
        else:
            logger.warning("abort calculation %s: elapsed=%s[sec], car=%s, user=%s, route=%s",
                           self.name, elapsed, car, user.user_id, route.stop_times)
            return False


class Car(Mobility):
    """ On-Demand Bus

    mobility that transport multiple users from a stop to another stop and operate to meet their requests.
    """

    def __init__(self, network: Network, queue: EventQueue, mobility_id: str, capacity: int, trip: Trip,
                 stop: Stop, board_time: timedelta, max_delay_time: timedelta):
        super().__init__(mobility_id=mobility_id, trip=trip)
        self.network = network
        self.events = queue
        self.capacity = capacity
        self.schedule = Schedule()
        self._last_arrival_time = self.env.datetime_now
        self._initial_stop = stop
        self._stop: typing.Optional[Stop] = stop
        self._board_time: timedelta = board_time
        self._max_delay_time: timedelta = max_delay_time
        self._reserved_users: typing.Dict[str, User] = {}
        self._waiting_users: typing.Dict[str, User] = {}
        self._passengers: typing.Dict[str, User] = {}
        _, end_window = self.window()
        self.env.process(self._move_to_initial_stop(end_window)) # move to initial stop at end_window

    def __str__(self):
        reserved = [e.user_id for e in self._reserved_users.values()]
        waiting = [e.user_id for e in self._waiting_users.values()]
        passenger = [e.user_id for e in self._passengers.values()]
        return f"Car[{self.mobility_id}] with users({reserved=}, {waiting=}, {passenger=})"

    def __repr__(self):
        fields = [
            f"network={self.network}",
            f"queue={self.events}",
            f"capacity={self.capacity}",
            f"trip={self._trip}",
            f"stop={self.stop}",
            f"board_time={self._board_time}",
            f"max_delay_time={self._max_delay_time}",
            f"schedule={self.schedule}",
            f"_last_arrival_time={self._last_arrival_time}",
            f"_reserved_users={self._reserved_users}",
            f"_waiting_users={self._waiting_users}",
            f"_passengers={self._passengers}",
        ]
        return "Car(" + ", ".join(fields) + ")"

    @property
    def env(self):
        return self.events.env

    @property
    def users(self):
        return (self._reserved_users | self._waiting_users | self._passengers).values()

    @property
    def waiting_users(self):
        return self._waiting_users.values()

    @property
    def passengers(self):
        return self._passengers.values()

    @property
    def stop(self):
        return self._stop

    @property
    def board_time(self):
        return self._board_time

    @property
    def moving(self):
        return self.schedule.current if not self.stop else None

    def find_reserved_user(self, user_id: str):
        return self._reserved_users.get(user_id, None)

    def user_ready(self, user: User):
        self._reserved_users.pop(user.user_id)
        self._waiting_users.update({user.user_id: user})

    def arrived(self):
        if users := [user for user in self.passengers if user.dst == self.stop]:
            yield self.env.timeout(self.board_time.total_seconds() / 60)
            for user in users:
                self._passengers.pop(user.user_id)
                self.events.arrived(mobility=self, user=user)

        self._last_arrival_time = self.env.datetime_now

        if self.schedule:
            self.env.process(self.departed())
        else:
            self.schedule.pop()
            assert not len(self.passengers)
            assert not len(self.waiting_users)
            _, end_window = self.window()
            if end_window < self.env.datetime_now:
                # move to initial after end window (fail-safe: avoid arrival after end window in reserve)
                self.env.process(self._move_to_initial_stop())

    def departed(self):
        # wait until the scheduled arrival time
        if users := self.schedule.current.on:
            if (latest_arrival_time := max(user.desired_dept for user in users)) > self.env.datetime_now:
                yield self.env.timeout_until(latest_arrival_time)

        while users := [user for user in self.schedule.current.on if user in self.waiting_users]:
            assert self.schedule.current.stop == self.stop, (
                f"illegal current schedule of mobility={self.mobility_id}"
                f" with users={[e.user_id for e in users]} at {self.env.now=}:"
                f" {self.schedule.current.stop=} != {self.stop=}"
                f"\n  car={repr(self)}"
            )
            for user in users:
                assert user.org == self.stop
                self.events.departed(mobility=self, user=user)
                self._waiting_users.pop(user.user_id)
                self._passengers.update({user.user_id: user})
            yield self.env.timeout(self.board_time.total_seconds() / 60)

            assert len(self.passengers) <= self.capacity, (
                f"capacity over of mobility={self.mobility_id} on stop={self.stop}"
                f" with users={[e.user_id for e in users]} at {self.env.now=}:"
                f" len({[e.user_id for e in self.passengers]=}) > {self.capacity=}"
                f"\n  car={repr(self)}"
            )

        self.env.process(self.move(self.schedule.pop().stop))

    def _move_to_initial_stop(self, end: datetime | None = None):
        if end:
            yield self.env.timeout_until(end)
            # next timing for moving to the initial stop
            self.env.process(self._move_to_initial_stop(end + timedelta(days=1)))
        if self.moving or self.schedule or len(self.passengers) > 0:
            # moving to the initial stop after another schedule or drop all passengers
            return 
        if self._stop != self._initial_stop:
            self.env.process(self.move(self._initial_stop)) 

    def move(self, to: Stop):
        assert self.stop

        duration = self.network.duration(self.stop.stop_id, to.stop_id)

        self.events.departed(mobility=self)
        if not self.schedule.current:
            # non-scheduled move (for move to initial stop)
            self.schedule.current = StopTime(stop=to, arrival=self.env.datetime_from(self.env.now + duration))
        self._stop = None
        yield self.env.timeout(duration)
        self._stop = to
        self.events.arrived(mobility=self)

        self.env.process(self.arrived())

    def routes_appended_new_user(self, user: User):
        watchdog = TimeoutWatchDog(f"routes_appended_new_user(user={user.user_id})",
                                   limit=30, interval=5)  # calculation timeout
        routes = [
            Route(stop_times=[
                StopTime(stop=passenger.dst, off=[passenger])
                for passenger in passengers
            ])
            for passengers in itertools.permutations(self.passengers)
        ]
        for user_ in (self._waiting_users | self._reserved_users | {user.user_id: user}).values():
            new_routes = []
            for route in routes:
                for i, k in itertools.combinations_with_replacement(range(len(route.stop_times) + 1), 2):
                    if not watchdog.check(self, user_, route):
                        return []
                    stop_times = [
                        StopTime(stop=stop_time.stop, on=stop_time.on, off=stop_time.off)
                        for stop_time in route.stop_times
                    ]
                    stop_times.insert(k, StopTime(stop=user_.dst, off=[user_]))
                    stop_times.insert(i, StopTime(stop=user_.org, on=[user_]))

                    r = Route(stop_times)
                    # exclude the duplicated pattern
                    if r in new_routes:
                        continue
                    # exclude the obviously inefficient pattern
                    if r.inefficient(self.passengers):
                        continue
                    # exclude the pattern that exceeds capacity
                    if len(self.passengers) + r.max_passengers > self.capacity:
                        continue
                    # exclude the pattern that exceeds max delay
                    if any(value > self._max_delay_time for value in Delay(self, r).values):
                        continue
                    new_routes.append(r)

            routes = list(new_routes)

        return routes

    def reserve(self, user: User, schedule: typing.List[StopTime]):
        assert user.user_id not in self.users

        if not self.schedule.current:
            next_stop = schedule[0].stop
            # If the bus has stopped and there's no next stop, operations begin according to the new schedule.
            self.env.process(
                self.move(next_stop)
                if self.stop != next_stop else
                self.departed()
            )

        self.schedule.update(schedule)
        self._reserved_users.update({user.user_id: user})

    def window(self) -> typing.Tuple[datetime | None, datetime | None]:
        now = self.env.datetime_now
        today = datetime(year=now.year, month=now.month, day=now.day)
        if trip := self.trip(today.date() - timedelta(days=1)):
            # yesterday's after midnight
            start_window = today
            end_window = today + trip.stop_time.end_window - timedelta(days=1)
            if now < end_window:
                return start_window, end_window
        if trip := self.trip(today.date()):
            start_window = today + trip.stop_time.start_window
            end_window = today + trip.stop_time.end_window
            if now < end_window:
                return start_window, end_window
        if trip := self.trip(today.date() + timedelta(days=1)):
            # today's after midnight, maybe long time delay
            start_window = today + trip.stop_time.start_window + timedelta(days=1)
            end_window = today + trip.stop_time.end_window + timedelta(days=1)
            return start_window, end_window
        return None, None


class Route:
    def __init__(self, stop_times: typing.List[StopTime]):
        def _normalize(a: typing.List[StopTime], b: StopTime):
            return a[:-1] + [a[-1] + b] if a and a[-1].stop == b.stop else a + [b]
        self.stop_times = functools.reduce(_normalize, stop_times, [])

    def __eq__(self, other):
        if not isinstance(other, Route):
            return False
        return self.stop_times == other.stop_times

    # def __hash__(self):
    #     return hash(tuple(self.stop_times))

    @property
    def max_passengers(self):
        return max(itertools.accumulate(
            len(stop_time.on) - len(stop_time.off)
            for stop_time in self.stop_times
        ))

    def inefficient(self, passengers: typing.Collection[User]):
        passengers = set(passengers)
        for stop_time in self.stop_times:
            for user in passengers:
                # clearly inefficient for a passenger not to get off where he/she is scheduled to get off
                if user.dst == stop_time.stop and user not in stop_time.off:
                    return True
            passengers |= set(stop_time.on)
            passengers -= set(stop_time.off)
        return False


@dataclasses.dataclass
class StopTime:
    stop: Stop
    arrival: datetime = None
    departure: datetime = None
    on: typing.List[User] = dataclasses.field(default_factory=list)
    off: typing.List[User] = dataclasses.field(default_factory=list)

    def __eq__(self, other):
        if not isinstance(other, StopTime):
            return False
        return all((
            self.stop == other.stop,
            set(self.on) == set(other.on),
            set(self.off) == set(other.off)
        ))

    # def __hash__(self):
    #     return hash((self.stop, frozenset(self.on), frozenset(self.off)))

    def __add__(self, other: StopTime):
        assert self.stop is other.stop, (self.stop, other.stop)
        return StopTime(
            stop=self.stop,
            on=sorted(set(self.on + other.on), key=(self.on + other.on).index),
            off=sorted(set(self.off + other.off), key=(self.off + other.off).index),
        )


class Delay:
    def __init__(self, car: Car, plan: Route):
        self.car = car
        self.stop_times = plan.stop_times

        start_window, end_window = car.window()
        if start_window is None:
            # unavailable
            self.values = [self.car._max_delay_time]
            self.value = self.car._max_delay_time
            return

        # If on the move, set to the next stop-time.
        # If not on, set to the current stop and time.
        if to := self.car.moving:
            previous = StopTime(stop=to.stop, departure=to.arrival)
        else:
            now = self.car.env.datetime_now
            if now >= start_window:
                previous = StopTime(stop=car.stop, departure=now)
            else:
                # wait till start time
                previous = StopTime(stop=car.stop, departure=start_window)

        for previous, stop_time in zip([previous] + plan.stop_times, plan.stop_times):
            stop_time.arrival = previous.departure + timedelta(
                minutes=self.car.network.duration(previous.stop.stop_id, stop_time.stop.stop_id)
            )
            stop_time.departure = max(
                [stop_time.arrival + self.car.board_time * bool(stop_time.off) + self.car.board_time * bool(stop_time.on)] +
                [user.desired_dept + self.car.board_time for user in stop_time.on]
            )

        if plan.stop_times[-1].arrival <= end_window:
            self.values = [
                stop_time.arrival - user.desired_dept + self.car.board_time - user.ideal_duration
                for stop_time in plan.stop_times
                for user in stop_time.off
            ]
            self.value = sum(self.values, timedelta())
        else:
            # unavailable
            self.values = [self.car._max_delay_time]
            self.value = self.car._max_delay_time

    def __lt__(self, other):
        return self.value < other.value


class CarSetting(typing.NamedTuple):
    mobility_id: str
    capacity: int
    trip: Trip
    stop: Stop


class CarManager:
    """ responsible for processing across multiple on-demand buses."""

    def __init__(self, network: Network, event_queue: EventQueue,
                 board_time: float, max_delay_time: float, settings: typing.Collection[CarSetting]):
        self.network = network
        self.event_queue = event_queue
        self.board_time: timedelta = timedelta(minutes=board_time)
        self.max_delay_time: timedelta = timedelta(minutes=max_delay_time)
        self.mobilities: typing.Dict[str, Car] = {
            setting.mobility_id: Car(
                network=self.network,
                queue=self.event_queue,
                mobility_id=setting.mobility_id,
                capacity=setting.capacity,
                trip=setting.trip,
                stop=setting.stop,
                board_time=self.board_time,
                max_delay_time=self.max_delay_time,
            ) for setting in settings
        }

    @property
    def env(self):
        return self.event_queue.env

    def depart(self, user_id: str):
        for mobility in self.mobilities.values():
            if user := mobility.find_reserved_user(user_id):
                mobility.user_ready(user)
                return user

    def minimum_delay(self, user: User):
        for delay in sorted(
                Delay(car, route)
                for car in self.mobilities.values()
                for route in car.routes_appended_new_user(user)
        ):
            if all(value < self.max_delay_time for value in delay.values):
                return delay

    def reserve(self, user: User):
        self.env.process(self._reserve(user))

    def _reserve(self, user: User):
        yield self.env.timeout(0)

        if minimum_delay := self.minimum_delay(user):

            departure = None
            for stop_time in minimum_delay.stop_times:
                if user in stop_time.on:
                    departure = stop_time.departure - self.board_time
                if user in stop_time.off:
                    arrival = stop_time.arrival + self.board_time
                    assert departure
                    self.event_queue.reserved(
                        mobility=minimum_delay.car,
                        user=user,
                        departure=departure,
                        arrival=arrival
                    )

                    minimum_delay.car.reserve(
                        user=user,
                        schedule=minimum_delay.stop_times
                    )

        else:
            self.event_queue.reserve_failed(
                user_id=user.user_id
            )
