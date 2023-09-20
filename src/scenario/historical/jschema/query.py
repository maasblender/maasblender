# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field

from jschema.events import Event


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class HistoricalDemandSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    dept: float = Field(..., description="Time to start move from org to dst")
    service: str | None = None
    user_type: str | None = None


class Setup(BaseModel):
    trips: list[HistoricalDemandSetting]
    userIDFormat: str = "U_%d"
    offset_time: float = 0.0


TriggeredEvent = Event
