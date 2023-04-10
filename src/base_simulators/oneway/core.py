# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from enum import Enum
from logging import getLogger

from geopy.distance import geodesic


logger = getLogger(__name__)


class EventType(str, Enum):
    DEPARTED = 'DEPARTED'
    ARRIVED = 'ARRIVED'
    RESERVED = 'RESERVED'


class Location:
    """ Base class representing the location's coordinates of an entity """

    def __init__(self, id_, lat: float, lng: float):
        self.location_id = id_
        self.lat = lat
        self.lng = lng

    def __repr__(self):
        return f"Location({self.location_id}, {self.lat}, {self.lng})"

    def __str__(self):
        return self.location_id

    def distance(self, other: Location) -> float:
        """ 地点間の直線距離(m) """
        return geodesic([self.lat, self.lng], [other.lat, other.lng]).meters


class Mobility:
    """Mobility interface for representing a chargeable electric-vehicle."""

    def __init__(self, id_: str):
        self.id = id_
        self.velocity = 200  # (m/min)
        self.reserved = False

    def duration(self, org: Location, dst: Location):
        """ 出発地から目的地までの所要時間を返す """

        return org.distance(dst) / self.velocity
