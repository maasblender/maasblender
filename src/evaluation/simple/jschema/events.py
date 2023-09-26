# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel, Extra


class EventType(str, Enum):
    DEMAND = "DEMAND"
    RESERVE = "RESERVE"
    RESERVED = "RESERVED"
    DEPART = "DEPART"
    DEPARTED = "DEPARTED"
    ARRIVED = "ARRIVED"


class Event(BaseModel):
    eventType: EventType
    source: str | None = None  # not included within API response '/step', and set by broker
    time: float


class Location(BaseModel):
    locationId: str
    lat: float
    lng: float


class DemandEventDetails(BaseModel, extra=Extra.allow):
    userId: str
    org: Location
    dst: Location
    service: str | None = None
    dept: float | None = None  # immediate depature demand or arrive-by demand if None
    arrv: float | None = None  # arrive-by demand if not None


class DemandEvent(Event):
    eventType: typing.Literal[EventType.DEMAND]
    details: DemandEventDetails


class ReserveEventDetails(BaseModel, extra=Extra.allow):
    userId: str
    org: Location
    dst: Location
    dept: float
    arrv: float | None = None


class ReserveEvent(Event):
    eventType: typing.Literal[EventType.RESERVE]
    service: str
    details: ReserveEventDetails


class Trip(BaseModel, extra=Extra.allow):
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str | None = None


class ReservedEventDetails(BaseModel, extra=Extra.allow):
    success: bool
    userId: str
    route: list[Trip] = []


class ReservedEvent(Event):
    eventType: typing.Literal[EventType.RESERVED]
    details: ReservedEventDetails


class DepartEventDetails(BaseModel, extra=Extra.allow):
    userId: str


class DepartEvent(Event):
    eventType: typing.Literal[EventType.DEPART]
    service: str
    details: DepartEventDetails


class DepartedEventDetails(BaseModel, extra=Extra.allow):
    userId: str | None
    location: Location


class DepartedEvent(Event):
    eventType: typing.Literal[EventType.DEPARTED]
    details: DepartedEventDetails


class ArrivedEventDetails(BaseModel, extra=Extra.allow):
    userId: str | None
    location: Location


class ArrivedEvent(Event):
    eventType: typing.Literal[EventType.ARRIVED]
    details: ArrivedEventDetails
