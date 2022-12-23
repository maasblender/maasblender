# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import random
from itertools import count

import simpy

import jschema.query
from engine import Runner
from scenario.core import Location, DemandEvent

logger = logging.getLogger("generator")

UNIT_TIME = 1.0  # min


class TenDemand(typing.NamedTuple):
    dept: float
    org: Location
    dst: Location


class SenDemand(typing.NamedTuple):
    begin: float
    end: float
    org: Location
    dst: Location
    expected_demands: float

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
        """ ある事象が単位時間に発生する確率を返却する

        単位時間はモジュールのトップレベルで定義された UNIT_TIME が使用される。
        ある事象が begin から end の間に発生する回数の頻度はポアソン分布に従う。
        """

        if (p := self.expected_demands / (self.period / UNIT_TIME)) > 0.1:
            logger.warning(
                f"The probability: {p} of the event occurring in unit time: {UNIT_TIME} may not be small enough. "
                f"Consider a smaller unit time."
            )
        return p

    def generate_demands(self) -> typing.Iterator[TenDemand]:
        for i in range(int(self.period // UNIT_TIME)):
            elapsed = i * UNIT_TIME
            if random.random() < self.probability:
                yield TenDemand(self.begin + elapsed, self.org, self.dst)


class DemandGenerator(Runner):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.env = simpy.Environment()
        self.count = count(1)
        self.sen: typing.List[SenDemand] = []
        self._events: typing.List[typing.Union[DemandEvent]] = []

    async def setup(self, setting: jschema.query.DemandGeneratorDetails):
        random.seed(setting.seed)
        self.sen = [
            SenDemand(
                begin=sen.begin,
                end=sen.end,
                org=Location(
                    id_=sen.org.locationId,
                    lat=sen.org.lat,
                    lng=sen.org.lng,
                ),
                dst=Location(
                    id_=sen.dst.locationId,
                    lat=sen.dst.lat,
                    lng=sen.dst.lng,
                ),
                expected_demands=sen.expected_demands
            )
            for sen in setting.demands
        ]

    async def start(self):
        for sen in self.sen:
            for ten in sen.generate_demands():
                self.env.process(
                    self._demand(
                        dept=ten.dept,
                        org=ten.org,
                        dst=ten.dst
                    ))

    async def peek(self):
        return self.env.peek()

    async def step(self):
        self.env.step()
        events = self._events
        self._events = []
        return self.env.now, [event.dumps() for event in events]

    async def triggered(self, event: typing.Mapping):
        pass

    def _demand(self, dept, org: Location, dst: Location):
        yield self.env.timeout(dept)
        self._events.append(DemandEvent(
            user_id=f"U_{next(self.count)}",
            org=org,
            dst=dst,
        ))
