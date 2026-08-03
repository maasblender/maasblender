# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing

from mblib.jschema.events import Event
from pydantic import BaseModel


class Message(BaseModel):
    message: str


class Peek(BaseModel):
    next: float


T = typing.TypeVar("T", bound=Event)


class Step(BaseModel, typing.Generic[T]):
    now: float
    events: list[T]
