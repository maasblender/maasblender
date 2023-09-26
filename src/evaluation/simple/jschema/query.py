# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, AnyHttpUrl

from jschema.events import DemandEvent, Event as OtherEvent


class ResultWriterSetting(BaseModel):
    endpoint: AnyHttpUrl | None = None


class PlannerSetting(BaseModel):
    endpoint: AnyHttpUrl


class ReservableSetting(BaseModel):
    endpoint: AnyHttpUrl


class Setup(BaseModel):
    writer: ResultWriterSetting = ResultWriterSetting()
    planner: PlannerSetting
    reservable: ReservableSetting


TriggeredEvent = DemandEvent | OtherEvent
