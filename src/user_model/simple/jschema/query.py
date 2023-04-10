# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class PlannerSetting(BaseModel):
    endpoint: str


class Setup(BaseModel):
    planner: PlannerSetting


class EventType(str, Enum):
    DEMAND = 'DEMAND'
    RESERVE = 'RESERVE'
    RESERVED = 'RESERVED'
    DEPART = 'DEPART'
    DEPARTED = 'DEPARTED'
    ARRIVED = 'ARRIVED'


class Event(BaseModel):
    eventType: typing.Union[typing.Literal[EventType.RESERVE, EventType.DEPART]]
    source: str
    time: float


class DemandEventDetails(BaseModel):
    userId: str
    org: LocationSetting
    dst: LocationSetting
    service: typing.Optional[str]


class DemandEvent(BaseModel):
    eventType: typing.Literal[EventType.DEMAND]
    source: str
    time: float
    details: DemandEventDetails


class SuccessReservedEventDetails(BaseModel):
    userId: str
    success: typing.Literal[True]
    org: LocationSetting
    dst: LocationSetting
    dept: float
    arrv: float


class FailReservedEventDetails(BaseModel):
    userId: str
    success: typing.Literal[False]


class ReservedEvent(BaseModel):
    eventType: typing.Literal[EventType.RESERVED]
    source: str
    time: float
    details: typing.Union[SuccessReservedEventDetails, FailReservedEventDetails]


class DepartedEventDetails(BaseModel):
    userId: typing.Optional[str]
    location: LocationSetting


class DepartedEvent(BaseModel):
    eventType: typing.Literal[EventType.DEPARTED]
    source: str
    time: float
    details: DepartedEventDetails


class ArrivedEventDetails(BaseModel):
    userId: typing.Optional[str]
    location: LocationSetting


class ArrivedEvent(BaseModel):
    eventType: typing.Literal[EventType.ARRIVED]
    source: str
    time: float
    details: ArrivedEventDetails
