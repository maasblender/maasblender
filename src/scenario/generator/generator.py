# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import itertools
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
    dept: float | None  # desired departure time
    arrv: float | None  # desired arrival time (arrive-by)
    user_id: str
    demand_id: str
    info: DemandInfo


class TenDemand(typing.NamedTuple):
    time: float | None  # reserving time in case of advance reservation
    dept: float | None  # desired departure time
    arrv: float | None  # desired arrival time (arrive-by)
    info: DemandInfo


class SenDemand(typing.NamedTuple):
    begin: float
    end: float
    expected_demands: float
    time: float | None  # reserving time in case of advance reservation
    arrive_by: bool
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
        """Return the probability of an event occurring in a unit of time

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
                if self.arrive_by:
                    yield TenDemand(self.time, None, self.begin + elapsed, self.info)
                else:
                    yield TenDemand(self.time, self.begin + elapsed, None, self.info)


def make_demands(setting: jschema.query.Setup):
    sen = (
        SenDemand(
            begin=sen.begin,
            end=sen.end,
            expected_demands=sen.expected_demands,
            time=sen.resv,
            arrive_by=sen.arrive_by,
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
    user_id_gen = (setting.userIDFormat % i for i in itertools.count(1))
    demand_id_gen = (setting.demandIDFormat % i for i in itertools.count(1))
    demands = [
        Demand(
            time=e.time,
            dept=e.dept,
            arrv=e.arrv,
            user_id=next(user_id_gen),
            demand_id=next(demand_id_gen),
            info=e.info,
        )
        for e in ten
    ]

    return demands


class DemandGenerator:
    def __init__(self):
        self.env = simpy.Environment()
        self._demands: list[Demand] = []
        self._events: list[DemandEvent] = []
        self._user_types = {}

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
            {"time": self.env.now} | event.dumps() for event in events
        ]

    def _demand(self, demand: Demand):
        # depart-at: emit the demand at the reservation time,
        # or at ``dept`` when the demand is not pre-reserved.
        if demand.dept and demand.arrv is None:
            demand_time = demand.time if demand.time else demand.dept
            dept = demand.dept if demand.time else None
        # arrive-by: emit the demand at the reservation time,
        # or immediately when no reservation time is provided.
        elif demand.arrv and demand.dept is None:
            demand_time = demand.time if demand.time else 0.0
            dept = None
        # Exactly one of ``dept`` or ``arrv`` must be set.
        else:
            raise ValueError("a demand must define exactly one of `dept` or `arrv`")

        yield self.env.timeout(demand_time)
        self._events.append(
            DemandEvent(
                user_id=demand.user_id,
                demand_id=demand.demand_id,
                dept=dept,
                arrv=demand.arrv,
                info=demand.info,
            )
        )
