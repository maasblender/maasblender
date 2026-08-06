# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0

from mblib.jschema import response
from mblib.jschema.events import DepartEvent, ReserveEvent

Message = response.Message
Peek = response.Peek

StepEvent = ReserveEvent | DepartEvent
Step = response.Step[StepEvent]
