# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel
import typing

from mblib.jschema import response
from mblib.jschema.events import ReservedEvent, DepartedEvent, ArrivedEvent

Message = response.Message
Peek = response.Peek
StepEvent: typing.TypeAlias = ReservedEvent | DepartedEvent | ArrivedEvent
Step = response.Step[StepEvent]


class ReservableStatus(BaseModel):
    reservable: bool
