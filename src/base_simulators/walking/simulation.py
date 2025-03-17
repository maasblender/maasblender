# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
from dataclasses import dataclass

import simpy
from geopy.distance import geodesic

from core import Location
from event import ReservedEvent, DepartedEvent, ArrivedEvent

logger = logging.getLogger(__name__)
MIN_DURATION = 0.0


@dataclass(frozen=True)
class Reservation:
    user_id: str
    org: Location
    dst: Location
    dept: float
    arrv: float


def calc_distance(src: Location, dst: Location) -> float:
    return geodesic([src.lat, src.lng], [dst.lat, dst.lng]).meters


class Simulation:
    def __init__(self, walking_meters_per_minute: float):
        super().__init__()
        self.env = simpy.Environment()
        self.queue = EventQueue(env=self.env)
        self.velocity = walking_meters_per_minute
        self._reservations: dict[str, Reservation] = {}

    def setup(self):
        pass

    def start(self):
        pass

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        return self.env.now, self.queue.pop_all()

    def run(self, until: float):
        if self.env.now < until:
            self.env.run(until=until)

    def reserve(
        self,
        user_id: str,
        demand_id: str,
        org: Location,
        dst: Location,
        dept: float,
        arrv: float | None,
    ):
        self.env.process(self._reserve(user_id, demand_id, org, dst, dept, arrv))

    def _reserve(
        self,
        user_id: str,
        demand_id: str,
        org: Location,
        dst: Location,
        dept: float,
        arrv: float | None,
    ):
        # This user only needs to reserve a vehicle just before departure, so it must not be reserved at this time.
        assert user_id not in self._reservations, user_id

        arrv = arrv if arrv and arrv > dept else dept + self._duration(org, dst)

        yield self.env.timeout(0)
        self._reservations[user_id] = Reservation(user_id, org, dst, dept, arrv)
        self.queue.enqueue(
            ReservedEvent(
                user_id=user_id,
                demand_id=demand_id,
                org=org,
                dst=dst,
                dept=dept,
                arrv=arrv,
            )
        )

    def _duration(self, org: Location, dst: Location):
        duration = calc_distance(org, dst) / self.velocity
        return max(duration, MIN_DURATION)

    def depart(self, user_id: str, demand_id: str):
        self.env.process(self._depart(user_id, demand_id))

    def _depart(self, user_id: str, demand_id: str):
        # This user only needs to reserve a vehicle just before departure, so it must not be reserved at this time.
        assert user_id in self._reservations, (
            f"departing user must be reserved: {user_id=}, {self._reservations=}"
        )
        reservation = self._reservations.pop(user_id)
        assert (
            reservation.dept >= self.env.now
        )  # Always fulfill if the vehicle is reserved just before departure.

        yield self.env.timeout(reservation.dept - self.env.now)
        self.queue.enqueue(
            DepartedEvent(
                user_id=user_id,
                demand_id=demand_id,
                location=reservation.org,
            )
        )

        yield self.env.timeout(reservation.arrv - self.env.now)
        self.queue.enqueue(
            ArrivedEvent(
                user_id=user_id,
                demand_id=demand_id,
                location=reservation.dst,
            )
        )


class EventQueue:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self._events: list[dict] = []

    def pop_all(self):
        events = self._events
        self._events = []
        return events

    def enqueue(self, event: ReservedEvent | DepartedEvent | ArrivedEvent):
        self._events.append({"time": self.env.now} | event.dumps())
