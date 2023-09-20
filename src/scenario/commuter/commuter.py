# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
from dataclasses import dataclass

import simpy

import jschema.query
from core import Location, DemandInfo, DemandEvent

@dataclass(frozen=True)
class Commuter:
    env: simpy.Environment
    user_id: str
    dept_out: float
    dept_in: float
    info: DemandInfo
    demand: typing.Callable[[str, DemandInfo], None]

    def run(self):
        # dept out
        yield self.env.timeout(self.dept_out)
        self.demand(self.user_id, self.info)

        # dept in
        yield self.env.timeout(self.dept_in - self.dept_out)
        self.demand(self.user_id, self.info.reverse)


class CommuterScenario:
    def __init__(self):
        self.env = simpy.Environment()
        self.commuters: list[Commuter] = []
        self._events: list[DemandEvent] = []

    def setup(self, commuters: typing.Mapping[str, jschema.query.CommuterSetting]):
        self.commuters = [
            Commuter(
                env=self.env,
                user_id=user_id,
                dept_out=setting.deptOut,
                dept_in=setting.deptIn,
                info=DemandInfo(
                    org=Location(setting.org.locationId, setting.org.lat, setting.org.lng),
                    dst=Location(setting.dst.locationId, setting.dst.lat, setting.dst.lng),
                    user_type=setting.user_type,
                    service=setting.service,
                ),
                demand=self._demand,
            )
            for user_id, setting in commuters.items()
        ]

    def users(self):
        return [
            {
                "userId": commuter.user_id,
                "userType": commuter.info.user_type,
            }
            for commuter in self.commuters
        ]

    def start(self):
        self.env.process(self._run())

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        events, self._events = self._events, []
        return self.env.now, [
            {"time": self.env.now} | event.dumps()
            for event in events
        ]

    def _run(self):
        while True:
            for commuter in self.commuters:
                self.env.process(commuter.run())
            yield self.env.timeout(1440)  # repeat daily

    def _demand(self, user_id: str, info: DemandInfo):
        self._events.append(DemandEvent(user_id=user_id, info=info))
