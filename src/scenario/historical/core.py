# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from enum import Enum


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
    dept: float
    service: str | None
    demand_id: str
    user_type: str | None


@dataclass(frozen=True)
class DemandEvent:
    user_id: str
    info: DemandInfo

    def dumps(self) -> dict:
        info = self.info
        return {
            "eventType": EventType.Demand.value,
            "details": {
                "userId": self.user_id,
                "userType": self.info.user_type,
                "demandId": self.info.demand_id,
                "dept": self.info.dept,
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
