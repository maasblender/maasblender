# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses

from core import Location, EventType


@dataclasses.dataclass
class Event:
    event_type: EventType

    def dumps(self) -> dict:
        return {
            "eventType": self.event_type,
        }


@dataclasses.dataclass
class ReservedEvent(Event):
    user_id: str
    org: Location
    dst: Location
    dept: float
    arrv: float

    def __init__(self, user_id: str, org: Location, dst: Location, dept: float, arrv: float):
        super().__init__(EventType.RESERVED)
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
                "route": [{
                    "org": self.org.dumps(),
                    "dst": self.dst.dumps(),
                    "dept": self.dept,
                    "arrv": self.arrv,
                }]
            }
        }


@dataclasses.dataclass
class DepartedArrivedEvent(Event):
    location: Location
    user_id: str

    def __init__(self, event_type: EventType, location: Location, user_id: str):
        super().__init__(event_type)
        self.location = location
        self.user_id = user_id

    @property
    def subject_id(self):
        return self.user_id

    def dumps(self):
        return super().dumps() | {
            "details": {
                "subjectId": self.subject_id,
                "userId": self.user_id,
                "mobilityId": None,
                "location": self.location.dumps(),
            }
        }


@dataclasses.dataclass
class DepartedEvent(DepartedArrivedEvent):
    def __init__(self, location: Location, user_id: str):
        super().__init__(EventType.DEPARTED, location, user_id)


@dataclasses.dataclass
class ArrivedEvent(DepartedArrivedEvent):
    def __init__(self, location: Location, user_id: str):
        super().__init__(EventType.ARRIVED, location, user_id)
