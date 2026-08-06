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
    dept: float | None = Field(None, description="Time to start move from org to dst")
    arrv: float | None = Field(None, description="Time to arrive at dst")
    service: str | None = None
    user_id: str | None = None
    demand_id: str | None = None
    user_type: str | None = None
    actual_duration: float | None = None

    @model_validator(mode="after")
    def check_exist_time(self):
        if self.dept is None and self.arrv is None:
            raise ValueError("either dept or arrv must be specified")
        if self.dept is not None and self.arrv is not None:
            raise ValueError("dept and arrv cannot both be specified")
        if self.time is None:
            self.time = self.dept if self.dept else 0.0
        return self


class Setup(BaseModel):
    trips: list[HistoricalDemandSetting]
    userIDFormat: str = "U_%d"
    demandIDFormat: str = "D_%d"
