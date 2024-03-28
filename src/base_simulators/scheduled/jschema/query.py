# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, AnyHttpUrl, model_validator, conlist, constr

from mblib.jschema.events import ReserveEvent, DepartEvent


class Mobility(BaseModel):
    capacity: int


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
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    mobility: Mobility


# Note: OtherEvent must be described at the end
TriggeredEvent = ReserveEvent | DepartEvent