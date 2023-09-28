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


def calc_distance(src: Location, dst: Location) -> float:
    return geodesic([src.lat, src.lng], [dst.lat, dst.lng]).meters


class Mobility:
    """Mobility interface for representing a chargeable electric-vehicle."""

    def __init__(self, id_: str, velocity: float):
        self.id = id_
        self.velocity = velocity  # (m/min)
        self.reserved = False

    def duration(self, org: Location, dst: Location):
        return calc_distance(org, dst) / self.velocity
