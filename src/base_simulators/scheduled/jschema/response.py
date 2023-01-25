# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel


class EventType(str, Enum):
    RESERVED = 'RESERVED'
    DEPARTED = 'DEPARTED'
    ARRIVED = 'ARRIVED'


class Event(BaseModel):
    eventType: EventType
    time: float


class LocationDetails(BaseModel):
    locationId: str
    lat: float
    lng: float


class ReservedEventDetails(BaseModel):
    success: typing.Literal[True]
    userId: str
    mobilityId: str
    org: LocationDetails
    dst: LocationDetails
    dept: float
    arrv: float


class ReserveFailedEventDetails(BaseModel):
    success: typing.Literal[False]
    userId: str


class ReservedEvent(Event):
    eventType: typing.Literal[EventType.RESERVED] = EventType.RESERVED
    details: typing.Union[ReservedEventDetails, ReserveFailedEventDetails]


class EventDetails(BaseModel):
    userId: typing.Optional[str]
    mobilityId: str
    location: LocationDetails


class DepartedEvent(Event):
    eventType: typing.Literal[EventType.DEPARTED] = EventType.DEPARTED
    details: EventDetails


class ArrivedEvent(Event):
    eventType: typing.Literal[EventType.ARRIVED] = EventType.ARRIVED
    details: EventDetails


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: typing.List[typing.Union[ReservedEvent, DepartedEvent, ArrivedEvent]]


class ReservableStatus(BaseModel):
    reservable: bool
