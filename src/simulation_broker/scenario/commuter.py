# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
from dataclasses import dataclass

import simpy

import jschema.query
from engine import Runner
from scenario.core import Location, DemandEvent

logger = logging.getLogger("commuter")


@dataclass(frozen=True)
class Commuter:
    env: simpy.Environment
    user_id: str
    org: Location
    dst: Location
    dept_out: float
    dept_in: float
    demand: typing.Callable[[str, Location, Location], None]

    def run(self):
        # dept out
        yield self.env.timeout(self.dept_out)
        self.demand(self.user_id, self.org, self.dst)

        # dept in
        yield self.env.timeout(self.dept_in - self.dept_out)
        self.demand(self.user_id, self.dst, self.org)


class CommuterScenario(Runner):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.env = simpy.Environment()
        self.commuters: typing.List[Commuter] = []
        self._events: typing.List[typing.Union[DemandEvent]] = []

    async def setup(self, commuters: typing.Mapping[str, jschema.query.CommuterSetting]):
        self.commuters = [
            Commuter(
                env=self.env,
                user_id=user_id,
                org=Location(setting.org.locationId, setting.org.lat, setting.org.lng),
                dst=Location(setting.dst.locationId, setting.dst.lat, setting.dst.lng),
                dept_out=setting.deptOut,
                dept_in=setting.deptIn,
                demand=self._demand,
            )
            for user_id, setting in commuters.items()
        ]

    async def start(self):
        self.env.process(self.run())

    async def peek(self):
        return self.env.peek()

    async def step(self):
        self.env.step()
        events = self._events
        self._events = []
        return self.env.now, [event.dumps() for event in events]

    async def triggered(self, event: typing.Mapping):
        pass

    def run(self):
        while True:
            for commuter in self.commuters:
                self.env.process(commuter.run())
            yield self.env.timeout(1440)

    def _demand(self, user_id: str, org: Location, dst: Location):
        self._events.append(DemandEvent(
            user_id=user_id,
            org=org,
            dst=dst,
        ))
