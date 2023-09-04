# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field, AnyHttpUrl, root_validator, constr

from jschema.events import ReserveEvent, DepartEvent, Event as OtherEvent


class Mobility(BaseModel):
    mobility_id: str
    trip_id: str
    capacity: int
    stop: str


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @root_validator
    def check_exist_either(cls, values):
        if values.get("filename") or values.get("fetch_url"):
            return values
        raise ValueError("specified neither filename nor fetch_url")


class Setup(BaseModel):
    reference_time: constr(min_length=8, max_length=8)
    input_files: list[InputFilesItem] = Field(..., min_items=1, max_items=1)
    network: InputFilesItem
    board_time: float | None
    max_delay_time: float | None
    mobility_speed: float = 20.0 * 1000 / 60  # [m/min]
    mobilities: list[Mobility]


# Note: OtherEvent must be described at the end
TriggeredEvent = ReserveEvent | DepartEvent | OtherEvent
