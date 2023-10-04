# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import BaseModel, AnyHttpUrl


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class ModuleType(str, Enum):
    broker = "broker"
    planner = "planner"
    http = "http"


class BaseSetting(BaseModel):
    type: ModuleType


class ExternalSetting(BaseSetting):
    type: typing.Literal[ModuleType.http]
    endpoint: AnyHttpUrl
    details: typing.Mapping


class PlannerSetting(BaseSetting):
    type: typing.Literal[ModuleType.planner]
    endpoint: AnyHttpUrl
    details: typing.Any


class ResultWriterSetting(BaseModel):
    endpoint: AnyHttpUrl | None = None


class BrokerSettingDetails(BaseModel):
    writer: ResultWriterSetting = ResultWriterSetting()


class BrokerSetting(BaseSetting):
    type: typing.Literal[ModuleType.broker]
    details: BrokerSettingDetails


Setup = typing.Mapping[str, BrokerSetting | PlannerSetting | ExternalSetting]
