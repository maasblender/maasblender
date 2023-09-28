# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, AnyHttpUrl, root_validator

from jschema.events import ReserveEvent, DepartEvent, Event as OtherEvent


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @root_validator
    def check_exist_either(cls, values):
        if values.get("filename") or values.get("fetch_url"):
            return values
        raise ValueError("specified neither filename nor fetch_url")


class Setup(BaseModel):
    input_files: list[InputFilesItem]
    charging_speed = 0.003333  # [/min] (1 / 0.003333 = 300 min = 5h)
    discharging_speed = -0.004386  # [/min] (1 / -0.004386 = 228 min = 3h38min)
    mobility_speed = 200.0  # [m/min] (200 m/min = 12km/h)
    operator_start_time = 360.0  # [min] (360 = am 6:00)
    operator_end_time = 720.0  # [min] (720 = am 12:00)
    operator_interval = 15.0  # [min]
    operator_speed = 1000.0  # [m/min] (1000 m/min = 60km/h)
    operator_loading_time: int = 1  # (min/mobilities)
    operator_capacity: int = 4


TriggeredEvent = ReserveEvent | DepartEvent | OtherEvent
