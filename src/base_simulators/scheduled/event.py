# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing


from core import EventType, Mobility, User
from environment import Environment


class TriggerEvent:
    """ 発火するイベント

    イベントを発火させて他のサービスに通知するために利用する。"""

    def __init__(self, env: Environment, event_type: EventType):
        self.event_type = event_type
        self.env = env

    def dumps(self) -> typing.Dict:
        return {
            "eventType": self.event_type,
            "time": self.env.now
        }


class ReservedEvent(TriggerEvent):
    def __init__(
            self,
            env: Environment,
            user: User,
            mobility: Mobility,
    ):
        super().__init__(env, EventType.RESERVED)
        self.user = user
        self.mobility = mobility

    def dumps(self):
        return super().dumps() | {
            "details": {
                "success": True,
                "userId": self.user.user_id,
                "mobilityId": self.mobility.mobility_id if self.mobility else None,
                "org": {
                    "locationId": self.user.path.org.stop_id,
                    "lat": self.user.path.org.lat,
                    "lng": self.user.path.org.lng,
                },
                "dst": {
                    "locationId": self.user.path.dst.stop_id,
                    "lat": self.user.path.dst.lat,
                    "lng": self.user.path.dst.lng,
                },
                "dept": self.env.elapsed(self.user.path.departure),
                "arrv": self.env.elapsed(self.user.path.arrival)
            }
        }


class ReserveFailedEvent(TriggerEvent):
    def __init__(
            self,
            env: Environment,
            user_id: str
    ):
        super().__init__(env, EventType.RESERVED)
        self.user_id = user_id

    def dumps(self):
        return super().dumps() | {
            "details": {
                "success": False,
                "userId": self.user_id
            }
        }


class DepartedArrivedEvent(TriggerEvent):
    def __init__(self, env: Environment, event_type: EventType, mobility: Mobility, user: User = None):
        super().__init__(env, event_type)
        self.user = user
        self.mobility = mobility

    def dumps(self):
        return super().dumps() | {
            "details": {
                "userId": self.user.user_id if self.user else None,
                "mobilityId": self.mobility.mobility_id,
                "location": {
                    "locationId": self.mobility.stop.stop_id,
                    "lat": self.mobility.stop.lat,
                    "lng": self.mobility.stop.lng,
                }
            }
        }


class DepartedEvent(DepartedArrivedEvent):
    def __init__(
            self,
            env: Environment,
            mobility: Mobility,
            user: User = None
    ):
        super().__init__(env, EventType.DEPARTED, mobility, user)


class ArrivedEvent(DepartedArrivedEvent):
    def __init__(
            self,
            env: Environment,
            mobility: Mobility,
            user: User = None
    ):
        super().__init__(env, EventType.ARRIVED, mobility, user)


class EventQueue:
    def __init__(self):
        self._events: typing.List[typing.Dict] = []

    @property
    def events(self):
        events = self._events
        self._events = []
        return events

    def enqueue(self, event: TriggerEvent):
        self._events.append(event.dumps())
