# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field, model_validator


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class HistoricalDemandSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    time: float | None = Field(None, description="Time to reserve mobilities")
    dept: float = Field(..., description="Time to start move from org to dst")
    service: str | None = None
    user_id: str | None = None
    demand_id: str | None = None
    user_type: str | None = None

    @model_validator(mode="after")
    def check_exist_time(self):
        if self.dept is None and self.arrv is None:
            raise ValueError("not specified both dept and arrv")
        if self.time is None:
            self.time = self.dept
        return self


class Setup(BaseModel):
    trips: list[HistoricalDemandSetting]
    userIDFormat: str = "U_%d"
    demandIDFormat: str = "D_%d"
