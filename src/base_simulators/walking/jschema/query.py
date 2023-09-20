# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel

from jschema.events import ReserveEvent, DepartEvent, Event as OtherEvent


class Setup(BaseModel):
    walking_meters_per_minute = 80.0  # (m/min)


# Note: OtherEvent must be described at the end
TriggeredEvent = ReserveEvent | DepartEvent | OtherEvent
