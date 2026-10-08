# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from enum import Enum

from mblib.jschema.events import DepartEvent, ReserveEvent
from pydantic import AnyHttpUrl, BaseModel, Field, conlist, constr, model_validator


class RouteCalculationMethod(str, Enum):
    EQUAL_INTERVAL = "equal_interval"
    BRUTE_FORCE = "brute_force"


class Planner(BaseModel):
    endpoint: AnyHttpUrl


class Mobility(BaseModel):
    capacity: int
    speed: float = Field(default=350.0, gt=0, allow_inf_nan=False)  # [m/min]


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def check_exist_either(self):
        if self.filename or self.fetch_url:
            return self
        raise ValueError("specified neither filename nor fetch_url")


class Setup(BaseModel):
    reference_time: constr(min_length=8, max_length=8)
    simulation_start_time: constr(pattern=r"^\d{2}:\d{2}$") = "00:00"
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    mobility: Mobility
    route_calculation_method: RouteCalculationMethod = (
        RouteCalculationMethod.EQUAL_INTERVAL
    )
    planner: Planner | None = None

    @model_validator(mode="after")
    def require_planner_for_brute_force(self):
        if (
            self.route_calculation_method == RouteCalculationMethod.BRUTE_FORCE
            and self.planner is None
        ):
            raise ValueError("planner is required for brute_force calculation")
        return self


# Note: OtherEvent must be described at the end
TriggeredEvent = ReserveEvent | DepartEvent
