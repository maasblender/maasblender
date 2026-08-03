# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from enum import Enum

from pydantic import AnyHttpUrl, BaseModel, conlist, constr, model_validator


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def check_exist_either(self):
        if self.filename or self.fetch_url:
            return self
        raise ValueError("specified neither filename nor fetch_url")


class OTPDetails(BaseModel):
    input_files: list[InputFilesItem]


class ServiceFileType(str, Enum):
    GBFS = "gbfs"
    GTFS = "gtfs"
    GTFS_FLEX = "gtfs_flex"


class NetworkSetting(BaseModel):
    type: ServiceFileType = ServiceFileType.GTFS
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    agency_id: str | None = None  # equivalent to system_id for GBFS file


class TransportMode(BaseModel):
    mode: str
    qualifier: str | None = None


class TransportModes(BaseModel):
    modes: conlist(TransportMode, min_length=1)


class Setup(BaseModel):
    otp_config: OTPDetails
    networks: dict[str, NetworkSetting]
    reference_time: constr(min_length=8, max_length=8)
    modes: conlist(TransportModes, min_length=1) = None
    walking_meters_per_minute: float | None = (
        None  # get from router_config.json, if None
    )
    timezone: int = +9
