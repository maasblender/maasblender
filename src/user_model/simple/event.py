# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
from enum import Enum

import simpy

from core import Location

logger = logging.getLogger("user")


class EventType(str, Enum):
    RESERVE = "RESERVE"
    DEPART = "DEPART"
    RESERVED = "RESERVED"
    ARRIVED = "ARRIVED"
    DEPARTED = "DEPARTED"


class TriggerEvent:
    """ 発火するイベント

    イベントを発火させて他のサービスに通知するために利用する。"""

    def __init__(self, event_type: EventType, time: float):
        self.event_type = event_type
        self.time = time

    def dumps(self) -> typing.Dict:
        return {
            "eventType": self.event_type,
            "time": self.time
        }


class ReserveEvent(TriggerEvent):
    def __init__(self, service: str, user_id: str, org: Location, dst: Location, dept: float, now: float):
        super().__init__(EventType.RESERVE, time=now)
        self.service = service
        self.user_id = user_id
        self.org = org
        self.dst = dst
        self.dept = dept

    def dumps(self):
        return super().dumps() | {
            "service": self.service,
            "details": {
                "userId": self.user_id,
                "org": {
                    "locationId": self.org.location_id,
                    "lat": self.org.lat,
                    "lng": self.org.lng
                },
                "dst": {
                    "locationId": self.dst.location_id,
                    "lat": self.dst.lat,
                    "lng": self.dst.lng
                },
                "dept": self.dept
            }
        }


class DepartEvent(TriggerEvent):
    def __init__(self, service: str, user_id: str, now: float):
        super().__init__(EventType.DEPART, time=now)
        self.service = service
        self.user_id = user_id

    def dumps(self):
        return super().dumps() | {
            "service": self.service,
            "details": {
                "userId": self.user_id,
            }
        }


class EventIdentifier:
    """ simpy.events.Event の識別子

     triggered event を受け取って simpy.events.Event を succeed するために利用する。 """

    def __init__(self, event_type: EventType, source: str):
        self.type = event_type
        self.source = source

    def __eq__(self, other):
        return isinstance(other, type(self)) and all((
            self.type == other.type,
            self.source == other.source
        ))

    def __hash__(self):
        return hash((
            self.type,
            self.source
        ))


# ToDo: userId と source だけで判断するのは危険かもしれない。
class ReservedEvent(EventIdentifier):
    def __init__(self, source: str, user_id: str, success=True):
        super().__init__(EventType.RESERVED, source=source)
        self.user_id = user_id
        self.success = success

    def __eq__(self, other):
        return super().__eq__(other) and all((
            self.user_id == other.user_id,
        ))

    def __hash__(self):
        return hash((
            super().__hash__(),
            self.user_id,
        ))


class DepartedArrivedEvent(EventIdentifier):
    def __init__(
            self,
            event_type: EventType,
            source: str,
            location: Location,
            user_id: str,
    ):
        super().__init__(event_type, source=source)
        self.location = location
        self.user_id = user_id

    def __eq__(self, other):
        return super().__eq__(other) and all((
            self.location.location_id == other.location.location_id,
            self.user_id == other.user_id
        ))

    def __hash__(self):
        return hash((
            super().__hash__(),
            self.location.location_id,
            self.user_id
        ))


class DepartedEvent(DepartedArrivedEvent):
    def __init__(self, source: str, location: Location, user_id: str):
        super().__init__(EventType.DEPARTED, source=source, location=location, user_id=user_id)


class ArrivedEvent(DepartedArrivedEvent):
    def __init__(self, source: str, location: Location, user_id: str):
        super().__init__(EventType.ARRIVED, source=source, location=location, user_id=user_id)


class Manager:
    """ すべてのモビリティシミュレータのイベントを一括管理する """

    def __init__(self, env: simpy.Environment):
        self._env = env
        self._queue: typing.List[TriggerEvent] = []
        self._events: typing.Dict[EventIdentifier, simpy.Event] = {}

    @property
    def env(self):
        return self._env

    def dequeue(self):
        events = self._queue
        self._queue = []
        return events

    def enqueue(self, event: TriggerEvent):
        self._queue.append(event)

    def trigger(self, identifier: EventIdentifier):
        """ EventIdentifier から simpy.events.Event を特定して発火する """
        if event := self._events.pop(identifier, None):
            event.succeed(value=identifier)

    def event(self, identifier: EventIdentifier):
        """ EventIdentifier から simpy.events.Event を特定して返す """
        if identifier not in self._events:
            self._events[identifier] = self.env.event()

        return self._events[identifier]
