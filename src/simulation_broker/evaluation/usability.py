# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import json
import typing
import logging
import aiohttp

from engine import Runner
from evaluation.planner import Location, Route, Planner

logger = logging.getLogger("broker")


class UsabilityEvaluator(Runner):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.logger = logging.getLogger("evaluation")
        self.planner: typing.Optional[Planner] = None
        self._endpoint = ""
        self._session = aiohttp.ClientSession(raise_for_status=True)

    async def setup(self, setting):
        self._endpoint = setting["reservable"]["endpoint"]
        self.planner = Planner(endpoint=setting["planner"]["endpoint"])

    async def peek(self):
        return float("inf")

    async def step(self):
        raise NotImplementedError()

    async def triggered(self, event: typing.Mapping):
        if event["eventType"] == "DEMAND":
            time = event["time"]
            plans = await self._plan(
                org=Location(
                    id_=event["details"]["org"]["locationId"],
                    lat=event["details"]["org"]["lat"],
                    lng=event["details"]["org"]["lng"]
                ),
                dst=Location(
                    id_=event["details"]["dst"]["locationId"],
                    lat=event["details"]["dst"]["lat"],
                    lng=event["details"]["dst"]["lng"]
                ),
                dept=time,
            )
            await self._evaluate(plans, actual=event["details"]["service"], time=time)

    def _plan(self, org: Location, dst: Location, dept: float):
        return self.planner.plan(org, dst, dept)

    async def _check_reservable(self, service: str, org: str, dst: str) -> bool:
        async with self._session.get(
            url=self._endpoint,
            params={"service": service, "org": org, "dst": dst},
        ) as response:
            return (await response.json())["reservable"]

    async def _evaluate(self, plans: typing.List[Route], actual: typing.Optional[str], time: float):
        org = plans[0].org
        dst = plans[0].dst
        assert all(plan.org == org for plan in plans)
        assert all(plan.dst == dst for plan in plans)

        self.logger.info(json.dumps({
            "org": org.id_,
            "dst": dst.id_,
            "time": time,
            "actual_service": actual,
            "plans": [
                {
                    "org": plan.trips[1].org.id_ if len(plan.trips) > 1 else plan.trips[0].org.id_,
                    "dst": plan.trips[1].dst.id_ if len(plan.trips) > 1 else plan.trips[0].dst.id_,
                    "dept": [trip.dept for trip in plan.trips],
                    "arrv": [trip.arrv for trip in plan.trips],
                    "service": plan.service,
                    "reservable": await self._check_reservable(
                        service=plan.service,
                        org=plan.trips[1].org.id_ if len(plan.trips) > 1 else plan.trips[0].org.id_,
                        dst=plan.trips[1].dst.id_ if len(plan.trips) > 1 else plan.trips[0].dst.id_,
                    ) if plan.service != "walking" else True
                } for plan in plans
            ]
        }))
