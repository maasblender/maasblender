# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel

from jschema.events import DemandEvent


class Message(BaseModel):
    message: str


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: list[DemandEvent]


class User(BaseModel):
    userId: str
    userType: str | None
