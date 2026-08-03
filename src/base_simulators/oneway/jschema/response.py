# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing

from mblib.jschema import response
from mblib.jschema.events import ArrivedEvent, DepartedEvent, ReservedEvent
from pydantic import BaseModel

Message = response.Message
Peek = response.Peek
StepEvent: typing.TypeAlias = ReservedEvent | DepartedEvent | ArrivedEvent
Step = response.Step[StepEvent]


class ReservableStatus(BaseModel):
    reservable: bool
