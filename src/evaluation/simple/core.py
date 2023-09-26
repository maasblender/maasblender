# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Location:
    location_id: str
    lat: float
    lng: float

    def __str__(self):
        return self.location_id

    def dumps(self):
        return {
            "locationId": self.location_id,
            "lat": self.lat,
            "lng": self.lng,
        }
