# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
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
    def distance(self, other: 'Location'):
        """ 地点間の直線距離(m) """

        # Remarks: self.distance(other) may not equal other.distance(self)
        return great_circle([self.lat, self.lng], [other.lat, other.lng]).meters


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


class MobilityNetwork:
    def shortest_path(self, org: Location, dst: Location, dept: float) -> Path:
        raise NotImplementedError()


class WalkingNetwork(MobilityNetwork):
    def __init__(self, service: str, walking_meters_per_minute: float):
        self.service = service
        self.walking_velocity = walking_meters_per_minute

    def shortest_path(self, org: Location, dst: Location, dept: float) -> Path:
        return Path(trips=[Trip(
            org=org,
            dst=dst,
            dept=dept,
            arrv=dept + org.distance(dst) / self.walking_velocity,
            service=self.service
        )])
