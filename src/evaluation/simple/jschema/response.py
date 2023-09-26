# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Status(BaseModel):
    success: bool


class Message(BaseModel):
    message: str


class Peek(BaseModel):
    next: float


class Step(BaseModel):
    now: float
    events: list | None = []


class ReservableStatus(BaseModel):
    reservable: bool
