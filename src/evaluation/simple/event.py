# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses

from simpy import Environment

from core import Location


@dataclasses.dataclass(frozen=True)
class DemandEvent:
    env: Environment
    event_time: float
    dept: float
    org: Location
    dst: Location
    service: str | None
    user_id: str | None


class EventQueue:
    def __init__(self, env: Environment):
        self._env = env
        self._events: list[DemandEvent] = []

    @property
    def env(self) -> Environment:
        return self._env

    @property
    def events(self):
        events = self._events
        self._events = []
        return events

    def demand(self, event: DemandEvent):
        self._events.append(event)
