# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from enum import Enum
from functools import cached_property


@dataclass(frozen=True)
class Location:
    location_id: str
    lat: float
    lng: float

    def __str__(self):
        return self.location_id


class EventType(str, Enum):
    Demand = "DEMAND"


@dataclass(frozen=True)
class DemandInfo:
    """parameters for demand event by setting"""

    org: Location
    dst: Location
    dept: float | None = None
    arrv: float | None = None
    service: str | None = None
    user_type: str | None = None

    @cached_property
    def reverse(self):
        """return path"""
        return DemandInfo(
            org=self.dst,
            dst=self.org,
            dept=self.dept,
            arrv=self.arrv,
            service=self.service,
            user_type=self.user_type,
        )


@dataclass(frozen=True)
class DemandEvent:
    user_id: str
    demand_id: str
    info: DemandInfo

    def dumps(self) -> dict:
        info = self.info
        return {
            "eventType": EventType.Demand.value,
            "details": {
                "userId": self.user_id,
                "userType": self.info.user_type,
                "demandId": self.demand_id,
                "dept": self.info.dept,
                "arrv": self.info.arrv,
                "org": {
                    "locationId": info.org.location_id,
                    "lat": info.org.lat,
                    "lng": info.org.lng,
                },
                "dst": {
                    "locationId": info.dst.location_id,
                    "lat": info.dst.lat,
                    "lng": info.dst.lng,
                },
                "service": info.service,
            },
        }
