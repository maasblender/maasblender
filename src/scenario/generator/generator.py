# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import random
import typing

import simpy

import jschema.query
from core import Location, DemandEvent, DemandInfo

logger = logging.getLogger(__name__)

UNIT_TIME = 1.0  # min


class Demand(typing.NamedTuple):
    time: float | None  # reserving time in case of advance reservation
    dept: float
    user_id: str
    info: DemandInfo


class TenDemand(typing.NamedTuple):
    time: float | None  # reserving time in case of advance reservation
    dept: float
    info: DemandInfo


class SenDemand(typing.NamedTuple):
    begin: float
    end: float
    expected_demands: float
    time: float | None  # reserving time in case of advance reservation
    info: DemandInfo

    @property
    def period(self):
        period = self.end - self.begin

        assert period > 0
        if remainder := period % UNIT_TIME:
            logger.warning(
                f"Period: {self.begin} - {self.end} was not divisible by the unit time: {UNIT_TIME}"
                f"The remainder {remainder} was rounded down."
            )
        return period

    @property
    def probability(self):
        """ Return the probability of an event occurring in a unit of time

        UNIT_TIME defined at the top level of the module is used as the unit time.
        The frequency of the number of times an event occurs between begin and end follows a Poisson distribution.
        """

        if (p := self.expected_demands / (self.period / UNIT_TIME)) > 0.1:
            logger.warning(
                f"The probability: {p} of the event occurring in unit time: {UNIT_TIME} may not be small enough. "
                f"Consider a smaller unit time."
            )
        return p

    def generate_demands(self):
        for i in range(int(self.period // UNIT_TIME)):
            elapsed = i * UNIT_TIME
            if random.random() < self.probability:
                yield TenDemand(self.time, self.begin + elapsed, self.info)


def make_demands(setting: jschema.query.Setup):
    sen = (
            SenDemand(
                begin=sen.begin,
                end=sen.end,
                expected_demands=sen.expected_demands,
                time=sen.resv,
                info=DemandInfo(
                    org=Location(
                        location_id=sen.org.locationId,
                        lat=sen.org.lat,
                        lng=sen.org.lng,
                    ),
                    dst=Location(
                        location_id=sen.dst.locationId,
                        lat=sen.dst.lat,
                        lng=sen.dst.lng,
                    ),
                    user_type=sen.user_type,
                    service=sen.service,
                ),
            )
            for sen in setting.demands
    )
    ten = sorted(
        (e for sen in sen for e in sen.generate_demands()),
        key=lambda e: (e.time, e.dept),
    )
    demands = [
        Demand(time=e.time, dept=e.dept, user_id=setting.userIDFormat % i, info=e.info)
        for i, e in enumerate(ten, 1)
    ]

    return demands


class DemandGenerator:
    def __init__(self):
        self.env = simpy.Environment()
        self._demands: list[Demand] = []
        self._events: list[DemandEvent] = []

    def setup(self, setting: jschema.query.Setup):
        random.seed(setting.seed)
        self._demands = make_demands(setting)

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

    def _demand(self, demand: Demand):
        if demand.time is None:  # immediate reservation
            yield self.env.timeout(demand.dept)  # wait for departure time
            self._events.append(DemandEvent(user_id=demand.user_id, dept=None, info=demand.info))
        else:  # advance reservation
            yield self.env.timeout(demand.time)  # wait for reservation time
            self._events.append(DemandEvent(user_id=demand.user_id, dept=demand.dept, info=demand.info))
