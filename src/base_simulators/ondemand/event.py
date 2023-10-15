# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import datetime
import typing

from .core import EventType, Mobility, User
from .environment import Environment


class TriggerEvent:
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
            departure: datetime.datetime,
            arrival: datetime.datetime
    ):
        super().__init__(env, EventType.RESERVED)
        self.user = user
        self.mobility = mobility
        self.departure = departure
        self.arrival = arrival

    def dumps(self):
        return super().dumps() | {
            "details": {
                "success": True,
                "userId": self.user.user_id,
                "mobilityId": self.mobility.mobility_id if self.mobility else None,
                "route": [{
                    "org": {
                        "locationId": self.user.org.stop_id,
                        "lat": self.user.org.lat,
                        "lng": self.user.org.lng,
                    },
                    "dst": {
                        "locationId": self.user.dst.stop_id,
                        "lat": self.user.dst.lat,
                        "lng": self.user.dst.lng,
                    },
                    "dept": self.env.elapsed(self.departure),
                    "arrv": self.env.elapsed(self.arrival)
                }],
            }
        }


class ReserveFailedEvent(TriggerEvent):
    def __init__(self, env: Environment, user_id: str):
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
    def __init__(self, env: Environment):
        self._env = env
        self._events: typing.List[typing.Dict] = []

    def __repr__(self):
        return f"EventQueue(env=Environment({self.env.datetime_now}), events={self._events})"

    @property
    def env(self):
        return self._env

    @property
    def events(self):
        events = self._events
        self._events = []
        return events

    def _enqueue(self, event: TriggerEvent):
        self._events.append(event.dumps())

    def departed(self, mobility: Mobility, user: User = None):
        self._enqueue(DepartedEvent(
            env=self._env,
            mobility=mobility,
            user=user
        ))

    def arrived(self, mobility: Mobility, user: User = None):
        self._enqueue(ArrivedEvent(
            env=self._env,
            mobility=mobility,
            user=user
        ))

    def reserved(
        self,
        user: User,
        mobility: Mobility,
        departure: datetime.datetime,
        arrival: datetime.datetime
    ):
        self._enqueue(ReservedEvent(
            env=self._env,
            user=user,
            mobility=mobility,
            departure=departure,
            arrival=arrival
        ))

    def reserve_failed(self, user_id: str):
        self._enqueue(ReserveFailedEvent(
            env=self._env,
            user_id=user_id
        ))
