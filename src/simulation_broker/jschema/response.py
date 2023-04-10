# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Status(BaseModel):
    success: bool


class Message(BaseModel):
    message: str


class Peek(Status):
    next: float


class Step(Status):
    now: float


class ReservableStatus(BaseModel):
    reservable: bool
