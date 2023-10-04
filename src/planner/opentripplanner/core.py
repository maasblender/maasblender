# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import typing
from functools import cache

from geopy.distance import great_circle


@dataclasses.dataclass(frozen=True)
class Location:
    id_: str
    lat: float
    lng: float


@cache
def calc_distance(src: Location, dst: Location) -> float:
    return great_circle([src.lat, src.lng], [dst.lat, dst.lng]).meters


@dataclasses.dataclass(frozen=True)
class Trip:
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


@dataclasses.dataclass(frozen=True)
class Path:
    trips: typing.List[Trip]
    walking_time_minutes: float

    @property
    def org(self):
        return self.trips[0].org

    @property
    def dst(self):
        return self.trips[-1].dst

    @property
    def dept(self):
        return self.trips[0].dept

    @property
    def arrv(self):
        return self.trips[-1].arrv
