# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel


class Mobility(BaseModel):
    capacity: int


class GTFSDetails(BaseModel):
    fetch_url: str


class Setup(BaseModel):
    reference_time: str
    gtfs: GTFSDetails
    mobility: Mobility


class EventType(str, Enum):
    DEMAND = 'DEMAND'
    RESERVE = 'RESERVE'
    RESERVED = 'RESERVED'
    DEPART = 'DEPART'
    DEPARTED = 'DEPARTED'
    ARRIVED = 'ARRIVED'


class Event(BaseModel):
    eventType: typing.Union[
        typing.Literal[EventType.DEMAND],
        typing.Literal[EventType.RESERVED],
        typing.Literal[EventType.DEPARTED],
        typing.Literal[EventType.ARRIVED]
    ]
    time: float
    details: typing.Any


class Location(BaseModel):
    locationId: str
    lat: float
    lng: float


class ReserveEventDetails(BaseModel):
    userId: str
    org: Location
    dst: Location
    dept: float


class ReserveEvent(BaseModel):
    eventType: typing.Literal[EventType.RESERVE]
    time: float
    details: ReserveEventDetails


class DepartEventDetails(BaseModel):
    userId: str


class DepartEvent(BaseModel):
    eventType: typing.Literal[EventType.DEPART]
    time: float
    details: DepartEventDetails
