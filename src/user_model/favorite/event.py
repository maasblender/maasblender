# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
from enum import Enum

import simpy
from core import Location, Route

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    RESERVE = "RESERVE"
    DEPART = "DEPART"
    RESERVED = "RESERVED"
    ARRIVED = "ARRIVED"
    DEPARTED = "DEPARTED"


class TriggerEvent:
    def __init__(self, event_type: EventType, time: float):
        self.event_type = event_type
        self.time = time

    def dumps(self) -> dict:
        return {"eventType": self.event_type, "time": self.time}


class ReserveEvent(TriggerEvent):
    def __init__(
        self,
        service: str,
        user_id: str,
        demand_id: str,
        org: Location,
        dst: Location,
        dept: float,
        now: float,
        arrv: float | None = None,
    ):
        super().__init__(EventType.RESERVE, time=now)
        self.service = service
        self.user_id = user_id
        self.demand_id = demand_id
        self.org = org
        self.dst = dst
        self.dept = dept
        self.arrv = arrv

    def dumps(self):
        return super().dumps() | {
            "service": self.service,
            "details": {
                "userId": self.user_id,
                "demandId": self.demand_id,
                "org": {
                    "locationId": self.org.location_id,
                    "lat": self.org.lat,
                    "lng": self.org.lng,
                },
                "dst": {
                    "locationId": self.dst.location_id,
                    "lat": self.dst.lat,
                    "lng": self.dst.lng,
                },
                "dept": self.dept,
                "arrv": self.arrv,
            },
        }


class DepartEvent(TriggerEvent):
    def __init__(self, service: str, user_id: str, demand_id: str, now: float):
        super().__init__(EventType.DEPART, time=now)
        self.service = service
        self.user_id = user_id
        self.demand_id = demand_id

    def dumps(self):
        return super().dumps() | {
            "service": self.service,
            "details": {
                "userId": self.user_id,
                "demandId": self.demand_id,
            },
        }


class EventIdentifier:
    """identify a simpy.events.Event to be succeeded"""

    def __init__(self, event_type: EventType, source: str):
        self.type = event_type
        self.source = source

    def __eq__(self, other):
        return isinstance(other, type(self)) and all(
            (self.type == other.type, self.source == other.source)
        )

    def __hash__(self):
        return hash((self.type, self.source))


# ToDo: It can be dangerous to identity a reserved event based on it's userId and source alone.
class ReservedEvent(EventIdentifier):
    def __init__(
        self,
        source: str,
        user_id: str,
        success: bool = True,
        route: Route | None = None,
    ):
        super().__init__(EventType.RESERVED, source=source)
        self.user_id = user_id
        self.success = success
        self.route = route

    def __eq__(self, other):
        return super().__eq__(other) and all((self.user_id == other.user_id,))

    def __hash__(self):
        return hash(
            (
                super().__hash__(),
                self.user_id,
            )
        )


class DepartedArrivedEvent(EventIdentifier):
    def __init__(
        self,
        event_type: EventType,
        source: str,
        location: Location,
        user_id: str,
        demand_id: str,
    ):
        super().__init__(event_type, source=source)
        self.location = location
        self.user_id = user_id
        self.demand_id = demand_id

    def __eq__(self, other):
        return super().__eq__(other) and all(
            (
                self.location.location_id == other.location.location_id,
                self.user_id == other.user_id,
            )
        )

    def __hash__(self):
        return hash((super().__hash__(), self.location.location_id, self.user_id))


class DepartedEvent(DepartedArrivedEvent):
    def __init__(self, source: str, location: Location, user_id: str, demand_id: str):
        super().__init__(
            EventType.DEPARTED,
            source=source,
            location=location,
            user_id=user_id,
            demand_id=demand_id,
        )


class ArrivedEvent(DepartedArrivedEvent):
    def __init__(self, source: str, location: Location, user_id: str, demand_id: str):
        super().__init__(
            EventType.ARRIVED,
            source=source,
            location=location,
            user_id=user_id,
            demand_id=demand_id,
        )


class Manager:
    def __init__(self, env: simpy.Environment):
        self._env: simpy.Environment = env
        self._queue: list[TriggerEvent] = []
        self._events: dict[EventIdentifier, simpy.Event] = {}

    @property
    def env(self) -> simpy.Environment:
        return self._env

    def dequeue(self):
        events = self._queue
        self._queue = []
        return events

    def enqueue(self, event: TriggerEvent):
        self._queue.append(event)

    def trigger(self, identifier: EventIdentifier):
        """identifies and fires simpy.events.Event from EventIdentifier"""
        if event := self._events.pop(identifier, None):
            event.succeed(value=identifier)

    def event(self, identifier: EventIdentifier):
        """identifies and returns simpy.events.Event from EventIdentifier"""
        if identifier not in self._events:
            self._events[identifier] = self.env.event()

        return self._events[identifier]
