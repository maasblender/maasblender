# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing

import simpy

from core import EventType, Mobility

from location import Location


class Event:
    def __init__(self, event_type: EventType):
        self.event_type = event_type

    def dumps(self) -> typing.Dict:
        return {
            "eventType": self.event_type
        }


class ReservedEvent(Event):
    def __init__(
            self,
            user_id: str,
            mobility: Mobility,
            org: Location, dst: Location,
            dept: float, arrv: float,
    ):
        super().__init__(EventType.RESERVED)
        self.user_id = user_id
        self.mobility = mobility
        self.org = org
        self.dst = dst
        self.dept = dept
        self.arrv = arrv

    def dumps(self):
        return super().dumps() | {
            "details": {
                "userId": self.user_id,
                "mobilityId": self.mobility.id,
                "success": True,
                "route": [{
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
                    "dept": self.dept,
                    "arrv": self.arrv
                }]
            }}


class ReserveFailedEvent(Event):
    def __init__(self, user_id: str):
        super().__init__(EventType.RESERVED)
        self.user_id = user_id

    def dumps(self):
        return super().dumps() | {
            "details": {
                "success": False,
                "userId": self.user_id
            }
        }


class DepartedArrivedEvent(Event):
    def __init__(self, event_type: typing.Union[EventType.DEPARTED, EventType.ARRIVED],
                 mobility: Mobility, location: Location, user_id: str = None):
        super().__init__(event_type=event_type)
        self.user_id = user_id
        self.mobility = mobility
        self.location = location

    def dumps(self):
        return super().dumps() | {
            "details": {
                "userId": self.user_id,
                "mobilityId": self.mobility.id,
                "location": {
                    "locationId": self.location.location_id,
                    "lat": self.location.lat,
                    "lng": self.location.lng
                }
            }}


class DepartedEvent(DepartedArrivedEvent):
    def __init__(self, mobility: Mobility, location: Location, user_id: str = None):
        super().__init__(EventType.DEPARTED, mobility, location, user_id)


class ArrivedEvent(DepartedArrivedEvent):
    def __init__(self, mobility: Mobility, location: Location, user_id: str = None):
        super().__init__(EventType.ARRIVED, mobility, location, user_id)


class EventQueue:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self._events: list[dict] = []

    @property
    def events(self):
        events = self._events
        self._events = []
        return events

    def enqueue(self, event: Event):
        self._events.append({"time": self.env.now} | event.dumps())
