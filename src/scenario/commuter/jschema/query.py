# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing

from pydantic import BaseModel, Field, model_validator


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class CommuterSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    deptOut: float | None = Field(
        None, description="Departure time from org to dst (depart-at mode)"
    )
    deptIn: float | None = Field(
        None, description="Departure time from dst to org (depart-at mode)"
    )
    arrvOut: float | None = Field(
        None, description="Target arrival time at dst (arrive-by mode)"
    )
    arrvIn: float | None = Field(
        None, description="Target arrival time at org (arrive-by mode)"
    )
    leadTime: float = Field(
        15.0,
        ge=0,
        description="Minutes before arrival time to emit arrive-by demand",
    )
    service: str | None = None
    user_type: str | None = None

    @model_validator(mode="after")
    def check_timing_fields(self):
        # Each leg must choose exactly one of depart-at or arrive-by.
        if self.deptOut is not None and self.arrvOut is not None:
            raise ValueError("Cannot specify both deptOut and arrvOut")
        if self.deptIn is not None and self.arrvIn is not None:
            raise ValueError("Cannot specify both deptIn and arrvIn")
        if self.deptOut is None and self.arrvOut is None:
            raise ValueError("Either deptOut or arrvOut must be specified")
        if self.deptIn is None and self.arrvIn is None:
            raise ValueError("Either deptIn or arrvIn must be specified")

        out_emit = (
            self.deptOut if self.deptOut is not None else self.arrvOut - self.leadTime
        )
        in_emit = (
            self.deptIn if self.deptIn is not None else self.arrvIn - self.leadTime
        )
        if out_emit > in_emit:
            raise ValueError(
                "outbound demand must be emitted earlier than or equal to inbound"
            )

        return self


class Setup(BaseModel):
    commuters: typing.Mapping[str, CommuterSetting]  # key indicates User ID
    demandIDFormat: str = "D_%d"
