# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
from itertools import count

import simpy

import jschema.query
from engine import Runner
from scenario.core import Location, DemandEvent

logger = logging.getLogger("historical")


class HistoricalDemand(typing.NamedTuple):
    org: Location
    dst: Location
    dept: float
    service: str


class HistoricalScenario(Runner):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.count = count(1)
        self.env = simpy.Environment()
        self._demands: typing.List[HistoricalDemand] = []
        self._events: typing.List[typing.Union[DemandEvent]] = []

    async def setup(self, settings: typing.Collection[jschema.query.HistoricalDemandSetting]):
        self._demands = [
            HistoricalDemand(
                org=Location(setting.org.locationId, setting.org.lat, setting.org.lng),
                dst=Location(setting.dst.locationId, setting.dst.lat, setting.dst.lng),
                dept=setting.dept,
                service=setting.service
            )
            for setting in settings
        ]

    async def start(self):
        for demand in self._demands:
            self.env.process(self._demand(demand.org, demand.dst, demand.dept, demand.service))

    async def peek(self):
        return self.env.peek()

    async def step(self):
        self.env.step()
        events = self._events
        self._events = []
        return self.env.now, [event.dumps() for event in events]

    async def triggered(self, event: typing.Mapping):
        pass

    def _demand(self, org: Location, dst: Location, dept: float, service: str):
        yield self.env.timeout(dept)
        self._events.append(DemandEvent(
            user_id=f"U_{next(self.count)}",
            org=org,
            dst=dst,
            service=service
        ))
