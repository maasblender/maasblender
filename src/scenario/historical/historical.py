# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import typing
import itertools

from dataclasses import dataclass

import simpy

import jschema.query
from core import Location, DemandEvent, DemandInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoricalDemand:
    time: float
    user_id: str
    info: DemandInfo


class HistoricalScenario:
    def __init__(self):
        self.env = simpy.Environment()
        self._demands: list[HistoricalDemand] = []
        self._events: list[DemandEvent] = []
        self._user_types = {}

    def setup(
        self,
        settings: typing.Collection[jschema.query.HistoricalDemandSetting],
        user_id_format: str,
        demand_id_format: str,
    ):
        # append user_id
        user_id_gen = (user_id_format % i for i in itertools.count(1))
        demand_id_gen = (demand_id_format % i for i in itertools.count(1))
        for setting in settings:
            if not setting.user_id:
                setting.user_id = next(user_id_gen)
            if not setting.demand_id:
                setting.demand_id = next(demand_id_gen)

        # make user table with user_type
        for setting in settings:
            if setting.user_type:
                self._user_types[setting.user_id] = setting.user_type
            elif setting.user_id not in self._user_types:
                self._user_types[setting.user_id] = None
            else:
                assert not self._user_types[setting.user_id]

        self._demands = [
            HistoricalDemand(
                time=setting.time,
                user_id=setting.user_id,
                info=DemandInfo(
                    org=Location(
                        setting.org.locationId, setting.org.lat, setting.org.lng
                    ),
                    dst=Location(
                        setting.dst.locationId, setting.dst.lat, setting.dst.lng
                    ),
                    dept=setting.dept,
                    service=setting.service,
                    demand_id=setting.demand_id,
                    user_type=self._user_types[setting.user_id],
                ),
            )
            for setting in settings
        ]

    def users(self):
        return [
            {
                "userId": user_id,
                "userType": user_type,
            }
            for user_id, user_type in self._user_types.items()
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
            {"time": self.env.now} | event.dumps() for event in events
        ]

    def _demand(self, demand: HistoricalDemand):
        yield self.env.timeout(demand.time)
        self._events.append(DemandEvent(user_id=demand.user_id, info=demand.info))
