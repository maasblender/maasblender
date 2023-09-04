# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel

from jschema.events import ReservedEvent, DepartedEvent, ArrivedEvent


class Message(BaseModel):
    message: str


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: list[ReservedEvent | DepartedEvent | ArrivedEvent]


class ReservableStatus(BaseModel):
    reservable: bool
