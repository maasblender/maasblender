# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import typing
import logging
from enum import Enum

from geopy.distance import geodesic

logger = logging.getLogger("mmsim")


class Location:
    def __init__(self, id_, lat: float, lng: float):
        self.location_id = id_
        self.lat = lat
        self.lng = lng

    def __repr__(self):
        return f"Location({self.location_id}, {self.lat}, {self.lng})"

    def __str__(self):
        return self.location_id

    def distance(self, other: Location) -> float:
        """ 地点間の直線距離(m) """
        return geodesic([self.lat, self.lng], [other.lat, other.lng]).meters


class EventType(str, Enum):
    Reserved = "RESERVED"
    Departed = "DEPARTED"
    Arrived = "ARRIVED"


class TriggeredEvent:
    """ simpy.events.Event の識別子 """

    def __init__(self, event_type: EventType):
        self.event_type = event_type

    def dumps(self) -> typing.Dict:
        return {
            "eventType": self.event_type,
        }


class ReservedEvent(TriggeredEvent):
    def __init__(
            self,
            user_id: str,
            org: Location,
            dst: Location,
            dept: float,
            arrv: float
    ):
        super().__init__(EventType.Reserved)
        self.user_id = user_id
        self.org = org
        self.dst = dst
        self.dept = dept
        self.arrv = arrv

    def dumps(self):
        return super().dumps() | {
            "details": {
                "userId": self.user_id,
                "success": True,
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
            }
        }


class DepartedArrivedEvent(TriggeredEvent):
    def __init__(
            self,
            event_type: EventType,
            location: Location,
            user_id: typing.Optional[str],
    ):
        super().__init__(event_type)
        self.location = location
        self.subject_id = user_id
        self.user_id = user_id

    def dumps(self):
        return super().dumps() | {
            "details": {
                "subjectId": self.subject_id,
                "userId": self.user_id,
                "mobilityId": None,
                "location": {
                    "locationId": self.location.location_id,
                    "lat": self.location.lat,
                    "lng": self.location.lng
                }
            }
        }


class DepartedEvent(DepartedArrivedEvent):
    def __init__(
            self,
            location: Location,
            user_id: str
    ):
        super().__init__(EventType.Departed, location=location, user_id=user_id)


class ArrivedEvent(DepartedArrivedEvent):
    def __init__(
            self,
            location: Location,
            user_id: str
    ):
        super().__init__(EventType.Arrived, location=location, user_id=user_id)
