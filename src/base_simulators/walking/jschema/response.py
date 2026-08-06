# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from mblib.jschema.events import ArrivedEvent, DepartedEvent, ReservedEvent
from pydantic import BaseModel


class Message(BaseModel):
    message: str


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: list[ReservedEvent | DepartedEvent | ArrivedEvent]


class ReservableStatus(BaseModel):
    reservable: bool


StepEvent = ReservedEvent | DepartedEvent | ArrivedEvent
