# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
from pydantic import BaseModel


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class GbfsNetworkSetting(BaseModel):
    type: typing.Literal["gbfs"]
    mobility_meters_per_minute: float


class GtfsNetworkSetting(BaseModel):
    type: typing.Literal["gtfs"]
    reference_time: str
    max_waiting_time: float = 0


class GtfsFlexNetworkSetting(BaseModel):
    type: typing.Literal["gtfs_flex"]
    reference_time: str
    mobility_meters_per_minute: float
    expected_waiting_time: float


class GTFSDetails(BaseModel):
    fetch_url: str


class GTFSFlexDetails(BaseModel):
    fetch_url: str


class GBFSDetails(BaseModel):
    fetch_url: str


class Setup(BaseModel):
    gtfs: GTFSDetails | None
    gtfs_flex: GTFSFlexDetails | None
    gbfs: GBFSDetails | None
    walking_meters_per_minute: float
    networks: typing.Mapping[str, typing.Union[GtfsNetworkSetting, GbfsNetworkSetting, GtfsFlexNetworkSetting]]
