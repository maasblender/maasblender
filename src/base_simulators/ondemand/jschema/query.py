# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field, AnyHttpUrl, model_validator, constr

from mblib.jschema.events import ReserveEvent, DepartEvent


class Mobility(BaseModel):
    mobility_id: str
    trip_id: str
    capacity: int
    stop: str


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
    input_files: list[InputFilesItem] = Field(..., min_items=1, max_items=2)
    network: InputFilesItem
    enable_ortools: bool = True
    board_time: float | None
    max_delay_time: float | None
    mobility_speed: float = 20.0 * 1000 / 60  # [m/min]
    max_calculation_seconds: int = 30
    max_calculation_stop_times_length: int = 10
    mobilities: list[Mobility]


# Note: OtherEvent must be described at the end
TriggeredEvent = ReserveEvent | DepartEvent
