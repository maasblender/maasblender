# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import json

from simpy import Environment

from mblib.io.result import ResultWriter
from planner import Location, Route, Planner, ReservableChecker
from event import EventQueue, DemandEvent
from jschema.query import EvaluationTiming


def near_locations(loc1: Location, loc2: Location, *, delta: float):
    return all(
        [
            abs(loc1.lat - loc2.lat) < delta,
            abs(loc1.lng - loc2.lng) < delta,
        ]
    )


class UsabilityEvaluator:
    logger: ResultWriter
    planner: Planner
    reserver: ReservableChecker
    timing: EvaluationTiming

    def __init__(
        self,
        logger: ResultWriter,
        planner: str,
        reservable: str,
        timing: EvaluationTiming,
    ):
        self.logger = logger
        self.planner = Planner(planner)
        self.reserver = ReservableChecker(reservable)
        self.timing = timing
        self.env = Environment()
        self.event_queue = EventQueue(self.env)

    async def close(self):
        if self.planner:
            await self.planner.close()
        if self.reserver:
            await self.reserver.close()

    def demand(
        self,
        event_time: float,
        dept: float,
        org: Location,
        dst: Location,
        service: str | None,
        demand_id: str | None,
    ):
        """
        enqueue DEMAND event at dept
        """
        self.env.process(
            self._demand(
                DemandEvent(
                    env=self.env,
                    event_time=event_time,
                    dept=dept,
                    org=org,
                    dst=dst,
                    service=service,
                    demand_id=demand_id,
                )
            )
        )

    def _demand(self, demand: DemandEvent):
        match self.timing:
            case EvaluationTiming.ON_DEPARTURE:
                yield self.env.timeout(demand.dept - self.env.now)
            case EvaluationTiming.ON_DEMAND:
                yield self.env.timeout(0)
        self.event_queue.demand(demand)

    async def step(self):
        self.env.step()
        # dequeue DEMAND event and evaluate output
        for demand in self.event_queue.events:
            await self.evaluate(demand)
        return self.env.now

    async def evaluate(self, demand: DemandEvent):
        plans = await self.planner.plan(
            org=demand.org, dst=demand.dst, dept=demand.dept
        )
        result = await self._evaluate(
            plans,
            actual=demand.service,
            event_time=demand.event_time,
            dept=demand.dept,
            demand_id=demand.demand_id,
        )
        await self.logger.write_json(result)

    async def _evaluate(
        self,
        plans: list[Route],
        actual: str | None,
        event_time: float,
        dept: float,
        demand_id: str,
    ):
        org = plans[0].org
        dst = plans[0].dst
        assert all(near_locations(plan.org, org, delta=1e-4) for plan in plans), (
            json.dumps(
                [dataclasses.asdict(plan) for plan in plans],
                ensure_ascii=False,
                indent=2,
            )
        )
        assert all(near_locations(plan.dst, dst, delta=1e-4) for plan in plans), (
            json.dumps(
                [dataclasses.asdict(plan) for plan in plans],
                ensure_ascii=False,
                indent=2,
            )
        )

        return {
            "demand_id": demand_id,
            "time": dept,
            "event_time": event_time,  # for compatibility
            "org": org.location_id,
            "dst": dst.location_id,
            "actual_service": actual,
            "plans": [
                [
                    {
                        "org": trip.org.location_id,
                        "dst": trip.dst.location_id,
                        "dept": trip.dept,
                        "arrv": trip.arrv,
                        "service": trip.service,
                        "reservable": await self.reserver.reservable(
                            service=trip.service,
                            org=trip.org.location_id,
                            dst=trip.dst.location_id,
                        )
                        if trip.service != "walking"
                        else True,
                    }
                    for trip in plan.trips
                ]
                for plan in plans
            ],
        }
