# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing

from pydantic import BaseModel, Field

from jschema.events import Event


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class CommuterSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    deptOut: float = Field(description="Time to start move from org to dst")
    deptIn: float = Field(description="Time to start move from dst to org")
    service: str | None = None
    user_type: str | None = None


class Setup(BaseModel):
    commuters: typing.Mapping[str, CommuterSetting]  # key indicates User ID


TriggeredEvent = Event
