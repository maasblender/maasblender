# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel

from jschema.events import Event


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class SenDemandsSetting(BaseModel):
    begin: float
    end: float
    org: LocationSetting
    dst: LocationSetting
    expected_demands: float
    service: str | None = None
    user_type: str | None = None
    resv: float | None = None


class Setup(BaseModel):
    seed: int
    demands: list[SenDemandsSetting]
    userIDFormat: str = "U_%d"


TriggeredEvent = Event
