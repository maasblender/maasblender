# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
from enum import Enum
from dataclasses import dataclass


logger = logging.getLogger("mmsim")


class Location:
    def __init__(self, id_, lat: float, lng: float):
        self.location_id = id_
        self.lat = lat
        self.lng = lng

    def __repr__(self):
        return f"Location({self.location_id}, {self.lat}, {self.lng})"

    def __str__(self):
        return self.location_id


class EventType(str, Enum):
    Demand = "DEMAND"


@dataclass(frozen=True)
class DemandEvent:
    user_id: str
    org: Location
    dst: Location
    service: typing.Optional[str] = None

    def dumps(self) -> typing.Dict:
        return {
            "eventType": EventType.Demand,
            "details": {
                "userId": self.user_id,
                "org": {
                    "locationId": self.org.location_id,
                    "lat": self.org.lat,
                    "lng": self.org.lng
                },
                "dst": {
                    "locationId": self.dst.location_id,
                    "lat": self.dst.lat,
                    "lng": self.dst.lng
                },
                "service": self.service
            }
        }
