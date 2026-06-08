# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import itertools
import typing
from dataclasses import dataclass

import simpy

from core import DemandEvent, DemandInfo, Location
from jschema.query import CommuterSetting


@dataclass(frozen=True)
class Commuter:
    env: simpy.Environment
    user_id: str
    org: Location
    dst: Location
    dept_out: float | None
    dept_in: float | None
    arrv_out: float | None
    arrv_in: float | None
    lead_time: float
    service: str | None
    user_type: str | None
    demand: typing.Callable[[str, str, DemandInfo], None]

    def out_daily(self, day, demand_id_gen: typing.Iterator[str]):
        if self.dept_out is not None:
            timeout = self.dept_out
            dept = self.dept_out + 1440.0 * day
            arrv = None
        else:
            timeout = self.arrv_out - self.lead_time
            dept = None
            arrv = self.arrv_out + 1440.0 * day
        yield self.env.timeout(timeout)
        self.demand(
            self.user_id,
            next(demand_id_gen),
            DemandInfo(
                self.org,
                self.dst,
                dept,
                arrv,
                self.service,
                self.user_type,
            ),
        )

    def in_daily(self, day, demand_id_gen: typing.Iterator[str]):
        if self.dept_in is not None:
            timeout = self.dept_in
            dept = self.dept_in + 1440.0 * day
            arrv = None
        else:
            timeout = self.arrv_in - self.lead_time
            dept = None
            arrv = self.arrv_in + 1440.0 * day
        yield self.env.timeout(timeout)
        self.demand(
            self.user_id,
            next(demand_id_gen),
            DemandInfo(
                self.dst,
                self.org,
                dept,
                arrv,
                self.service,
                self.user_type,
            ),
        )


class CommuterScenario:
    def __init__(self):
        self.env = simpy.Environment()
        self.commuters: list[Commuter] = []
        self._events: list[DemandEvent] = []
        self._demand_id_gen: typing.Iterator[str] | None = None

    def setup(
        self,
        commuters: typing.Mapping[str, CommuterSetting],
        demand_id_format: str,
    ):
        self.commuters = [
            Commuter(
                env=self.env,
                user_id=user_id,
                org=Location(setting.org.locationId, setting.org.lat, setting.org.lng),
                dst=Location(setting.dst.locationId, setting.dst.lat, setting.dst.lng),
                dept_out=setting.deptOut,
                dept_in=setting.deptIn,
                arrv_out=setting.arrvOut,
                arrv_in=setting.arrvIn,
                lead_time=setting.leadTime,
                service=setting.service,
                user_type=setting.user_type,
                demand=self._demand,
            )
            for user_id, setting in commuters.items()
        ]
        self._demand_id_gen = (demand_id_format % i for i in itertools.count(1))

    def users(self):
        return [
            {
                "userId": commuter.user_id,
                "userType": commuter.user_type,
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
            {"time": self.env.now} | event.dumps() for event in events
        ]

    def _run(self):
        assert self._demand_id_gen is not None
        demand_id_gen = self._demand_id_gen
        day = 0
        while True:
            for commuter in self.commuters:
                self.env.process(commuter.out_daily(day, demand_id_gen))
                self.env.process(commuter.in_daily(day, demand_id_gen))
            yield self.env.timeout(1440)  # repeat daily
            day += 1

    def _demand(self, user_id: str, demand_id: str, info: DemandInfo):
        self._events.append(
            DemandEvent(user_id=user_id, demand_id=demand_id, info=info)
        )
