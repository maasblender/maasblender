# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import typing
from dataclasses import dataclass

import simpy

import jschema.query
from core import Location, DemandEvent, DemandInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoricalDemand:
    dept: float
    user_id: str
    info: DemandInfo


class HistoricalScenario:
    def __init__(self):
        self.env = simpy.Environment()
        self._demands: list[HistoricalDemand] = []
        self._events: list[DemandEvent] = []

    def setup(self, settings: typing.Collection[jschema.query.HistoricalDemandSetting],
              user_id_format: str, offset_time=0.0):
        if offset_time:
            logger.info("offset time: %s", offset_time)
        self._demands = [
            HistoricalDemand(
                dept=setting.dept - offset_time,
                user_id=user_id_format % i,
                info=DemandInfo(
                    org=Location(setting.org.locationId, setting.org.lat, setting.org.lng),
                    dst=Location(setting.dst.locationId, setting.dst.lat, setting.dst.lng),
                    service=setting.service,
                    user_type=setting.user_type,
                ),
            )
            for i, setting in enumerate(settings, 1)
            if setting.dept - offset_time >= 0
        ]

    def users(self):
        return [
            {
                "userId": demand.user_id,
                "userType": demand.info.user_type,
            }
            for demand in self._demands
        ]

    def start(self):
        for demand in self._demands:
            self.env.process(self._demand(demand))

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        events, self._events = self._events, []
        return self.env.now, [
            {"time": self.env.now} | event.dumps()
            for event in events
        ]

    def _demand(self, demand: HistoricalDemand):
        yield self.env.timeout(demand.dept)
        self._events.append(DemandEvent(user_id=demand.user_id, info=demand.info))
