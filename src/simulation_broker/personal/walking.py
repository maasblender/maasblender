# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
from dataclasses import dataclass

import simpy

from engine import Runner
from personal.core import Location, TriggeredEvent, ReservedEvent, DepartedEvent, ArrivedEvent

logger = logging.getLogger("walking")
MIN_DURATION = 0.1  # = 6秒


@dataclass(frozen=True)
class Reservation:
    user_id: str
    org: Location
    dst: Location
    dept: float


class PersonalSimulator(Runner):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.env = simpy.Environment()
        self.velocity = 80  # (m/min)
        self.factor = 1.0  # 直線距離を 1.4 倍することで疑似的に移動距離に変換している。
        self._events: typing.List[TriggeredEvent] = []
        self._reservations: typing.Dict[str, Reservation] = {}

    async def peek(self):
        return self.env.peek()

    async def step(self):
        self.env.step()
        events = self._events
        self._events = []
        return self.env.now, [event.dumps() for event in events]

    async def triggered(self, event: typing.Mapping):
        now = event.get("time")
        if self.env.now < now:
            # just let time forward to expect nothing to happen.
            self.env.run(until=now)

        if event["eventType"] == "RESERVE":
            self.env.process(self._reserve(
                user_id=event["details"]["userId"],
                org=Location(
                    id_=event["details"]["org"]["locationId"],
                    lat=event["details"]["org"]["lat"],
                    lng=event["details"]["org"]["lng"]
                ),
                dst=Location(
                    id_=event["details"]["dst"]["locationId"],
                    lat=event["details"]["dst"]["lat"],
                    lng=event["details"]["dst"]["lng"]
                ),
                dept=event["details"]["dept"]
            ))
        elif event["eventType"] == "DEPART":
            self.env.process(self._depart(
                user_id=event["details"]["userId"],
            ))

    def _reserve(self, user_id: str, org: Location, dst: Location, dept: float):
        # 出発の直前に予約すればよい。
        assert user_id not in self._reservations, user_id

        yield self.env.timeout(0)
        self._reservations[user_id] = Reservation(user_id, org, dst, dept)
        self._events.append(ReservedEvent(
            user_id=user_id,
            org=org,
            dst=dst,
            dept=dept,
            arrv=dept + self._duration(org, dst)
        ))

    def _duration(self, org: Location, dst: Location):
        duration = org.distance(dst) * self.factor / self.velocity
        return max(duration, MIN_DURATION)

    def _depart(self, user_id: str):
        # 出発の直前に予約すればよい。
        assert user_id in self._reservations, user_id
        reservation = self._reservations.pop(user_id, None)
        assert reservation.dept >= self.env.now  # 直前に予約して出発するとすれば常に満たす。

        yield self.env.timeout(reservation.dept - self.env.now)
        self._events.append(DepartedEvent(
            user_id=user_id,
            location=reservation.org,
        ))

        yield self.env.timeout(self._duration(reservation.org, reservation.dst))
        self._events.append(ArrivedEvent(
            user_id=user_id,
            location=reservation.dst,
        ))
