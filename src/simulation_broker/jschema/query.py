# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing

from pydantic import BaseModel, Field


class LocationSetting(BaseModel):
    locationId: str
    lat: float
    lng: float


class CommuterSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    deptOut: float = Field(description="org から dst に移動を開始する時刻")
    deptIn: float = Field(description="dst から org に移動を開始する時刻")


class CommuterScenarioSetting(BaseModel):
    type: typing.Literal["commuter"]
    details: typing.Mapping[str, CommuterSetting] = Field(description="key は User ID を示す.")


class HistoricalDemandSetting(BaseModel):
    org: LocationSetting
    dst: LocationSetting
    dept: float = Field(description="org から dst に移動を開始する時刻")
    service: str


class HistoricalScenarioSetting(BaseModel):
    type: typing.Literal["historical"]
    details: typing.List[HistoricalDemandSetting]


class SenDemandsSetting(BaseModel):
    begin: float
    end: float
    org: LocationSetting
    dst: LocationSetting
    expected_demands: float


class DemandGeneratorDetails(BaseModel):
    seed: int
    demands: typing.List[SenDemandsSetting]


class DemandGeneratorSetting(BaseModel):
    type: typing.Literal["generator"]
    details: DemandGeneratorDetails


class WalkingSimulatorSetting(BaseModel):
    type: typing.Literal["walking"]
    details: typing.Mapping


class ExternalSetting(BaseModel):
    type: typing.Literal["http"]
    endpoint: str
    details: typing.Mapping


class PlannerSetting(BaseModel):
    type: typing.Literal["planner"]
    endpoint: str
    details: typing.Mapping


class EvaluateSetting(BaseModel):
    type: typing.Literal["evaluate"]
    details: typing.Mapping


class ResultWriterSetting(BaseModel):
    endpoint: str


class BrokerSettingDetails(BaseModel):
    writer: ResultWriterSetting


class BrokerSetting(BaseModel):
    type: typing.Literal["broker"]
    details: BrokerSettingDetails


SettingType = typing.Union[
    BrokerSetting,
    WalkingSimulatorSetting,
    CommuterScenarioSetting,
    HistoricalScenarioSetting,
    DemandGeneratorSetting,
    EvaluateSetting,
    PlannerSetting,
    ExternalSetting
]

SettingMapType = typing.Mapping[str, SettingType]
