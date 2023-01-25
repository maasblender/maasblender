# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel


class Message(BaseModel):
    message: str


class EventType(str, Enum):
    RESERVE = 'RESERVE'
    DEPART = 'DEPART'


class Event(BaseModel):
    eventType: EventType
    service: str
    time: float


class LocationDetails(BaseModel):
    locationId: str
    lat: float
    lng: float


class ReserveEventDetails(BaseModel):
    userId: str
    org: LocationDetails
    dst: LocationDetails
    dept: float


class ReserveEvent(Event):
    eventType: typing.Literal[EventType.RESERVE]
    details: ReserveEventDetails


class DepartEventDetails(BaseModel):
    userId: str


class DepartEvent(Event):
    eventType: typing.Literal[EventType.DEPART]
    details: DepartEventDetails


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: typing.List[typing.Union[ReserveEvent, DepartEvent]]

