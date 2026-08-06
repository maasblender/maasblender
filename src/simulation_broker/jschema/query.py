# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from enum import Enum

from pydantic import AnyHttpUrl, BaseModel, RootModel


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


class ValidationSetting(BaseModel):
    ignore_feature: bool = False
    ignore_schema: bool = False
    ignore_in_process: bool = False


class BrokerSettingDetails(BaseModel):
    writer: ResultWriterSetting = ResultWriterSetting()
    validation: ValidationSetting | None = None


class BrokerSetting(BaseSetting):
    type: typing.Literal[ModuleType.broker]
    details: BrokerSettingDetails


class Setup(RootModel[dict[str, BrokerSetting | PlannerSetting | ExternalSetting]]):
    # dict-like accessors
    def __getattr__(self, name: str):
        if name in ["get", "keys", "values", "items"]:
            return getattr(self.root, name)

    def __getitem__(self, key: str):
        return self.root.__getitem__(key)

    def __contains__(self, key: str):
        return self.root.__contains__(key)
