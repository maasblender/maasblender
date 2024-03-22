# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum
import datetime

from pydantic import BaseModel, AnyHttpUrl, model_validator, conlist, constr


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class InputFilesItem(BaseModel):
    filename: str | None = None
    fetch_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def check_exist_either(cls, values):
        if values.get("filename") or values.get("fetch_url"):
            return values
        raise ValueError("specified neither filename nor fetch_url")


class ServiceFileType(str, Enum):
    GBFS = "gbfs"
    GTFS = "gtfs"
    GTFS_FLEX = "gtfs_flex"
    MAASSIM = "maassim"


class NetworkSetting(BaseModel):
    type: ServiceFileType
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)


class GbfsNetworkSetting(BaseModel):
    type: typing.Literal[ServiceFileType.GBFS]
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    mobility_meters_per_minute: float


class GtfsNetworkSetting(BaseModel):
    type: typing.Literal[ServiceFileType.GTFS]
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    max_waiting_time: float = 0


class GtfsFlexNetworkSetting(BaseModel):
    type: typing.Literal[ServiceFileType.GTFS_FLEX]
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    mobility_meters_per_minute: float
    expected_waiting_time: float


class MaaSSimNetworkSetting(BaseModel):
    type: typing.Literal[ServiceFileType.MAASSIM]
    input_files: conlist(InputFilesItem, min_length=1, max_length=1)
    mobility_meters_per_minute: float
    expected_waiting_time: float
    start_window: datetime.time
    end_window: datetime.time


class Setup(BaseModel):
    walking_meters_per_minute: float
    reference_time: constr(min_length=8, max_length=8)
    networks: typing.Mapping[
        str,
        typing.Union[
            GtfsNetworkSetting,
            GbfsNetworkSetting,
            GtfsFlexNetworkSetting,
            MaaSSimNetworkSetting,
        ],
    ]
