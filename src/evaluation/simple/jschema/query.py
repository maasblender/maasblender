# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from enum import Enum
from pydantic import BaseModel, AnyHttpUrl, Field

from mblib.jschema.events import DemandEvent


class ResultWriterSetting(BaseModel):
    endpoint: AnyHttpUrl | None = None


class PlannerSetting(BaseModel):
    endpoint: AnyHttpUrl


class ReservableSetting(BaseModel):
    endpoint: AnyHttpUrl


class EvaluationTiming(str, Enum):
    ON_DEPARTURE = 'departure'
    ON_DEMAND = 'demand'


class Setup(BaseModel):
    writer: ResultWriterSetting = ResultWriterSetting()
    planner: PlannerSetting
    reservable: ReservableSetting
    evaluation_timing: EvaluationTiming = Field(default=EvaluationTiming.ON_DEPARTURE)


TriggeredEvent = DemandEvent
