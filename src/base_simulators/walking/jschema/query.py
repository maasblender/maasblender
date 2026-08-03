# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0

from mblib.jschema.events import DepartEvent, ReserveEvent
from pydantic import BaseModel


class Setup(BaseModel):
    walking_meters_per_minute: float = 80.0  # (m/min)


TriggeredEvent = ReserveEvent | DepartEvent
