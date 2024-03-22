# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import math

from pydantic import BaseModel, AnyHttpUrl, model_validator
from enum import Enum

from jschema.events import (
    DemandEvent,
    ReservedEvent,
    DepartedEvent,
    ArrivedEvent,
    Event as OtherEvent,
)


class PlannerSetting(BaseModel):
    endpoint: AnyHttpUrl


class SortType(str, Enum):
    BY_WALKING_TIME = "byWalkingTime"
    BY_ARRIVAL_TIME = "byArrivalTime"


class UserType(BaseModel):
    walking_time_limit_min: float = math.inf
    favorite_service: set[str] | None = None
    sort_type: SortType | None = None


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def check_exist_either(self):
        if self.filename or self.fetch_url:
            return self
        raise ValueError("specified neither filename nor fetch_url")


class Setup(BaseModel):
    planner: PlannerSetting
    confirmed_services: list[str] = []
    users: list[InputFilesItem]
    userTypes: dict[str, UserType] = {}


# Note: OtherEvent must be described at the end
TriggeredEvent = DemandEvent | ReservedEvent | DepartedEvent | ArrivedEvent | OtherEvent
