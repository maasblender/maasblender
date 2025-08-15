# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import json

from event import DemandEvent, EventQueue
from mblib.io.result import ResultWriter
from simpy import Environment

from planner import Location, Planner, ReservableChecker, Route


def near_locations(loc1: Location, loc2: Location, *, delta: float):
    return all(
        [
            abs(loc1.lat - loc2.lat) < delta,
            abs(loc1.lng - loc2.lng) < delta,
        ]
    )


class UsabilityEvaluator:
    logger: ResultWriter
    planner: Planner | None
    reserver: ReservableChecker | None

    def __init__(self, logger: ResultWriter, planner: str, reservable: str):
        self.logger = logger
        self.planner = Planner(planner)
        self.reserver = ReservableChecker(reservable)
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
        demand = DemandEvent(
            env=self.env,
            event_time=event_time,
            dept=dept,
            org=org,
            dst=dst,
            service=service,
            demand_id=demand_id,
        )
        self.env.process(self._demand(demand))

    def _demand(self, demand: DemandEvent):
        yield self.env.timeout(demand.dept - self.env.now)
        self.event_queue.demand(demand)

    async def step(self):
        self.env.step()
        # dequeue DEMAND event and evaluate output
        for demand in self.event_queue.events:
            await self.evaluate(demand)
        return self.env.now

    async def evaluate(self, demand: DemandEvent):
        plans = await self._plan(org=demand.org, dst=demand.dst, dept=demand.dept)
        result = await self._evaluate(
            plans,
            actual=demand.service,
            event_time=demand.event_time,
            dept=demand.dept,
            demand_id=demand.demand_id,
        )
        await self.logger.write_json(result)

    def _plan(self, org: Location, dst: Location, dept: float):
        return self.planner.plan(org, dst, dept)

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

        result = {
            "org": org.location_id,
            "dst": dst.location_id,
            "event_time": event_time,  # for compatibility
            "time": dept,
            "actual_service": actual,
            "plans": [await self._evaluate_plan(plan) for plan in plans],
            "demand_id": demand_id,
        }
        return result

    async def _evaluate_plan(self, plan: Route):
        if len(plan.trips) > 1:
            # assume second trip as mobility
            trip = plan.trips[1]
        else:
            trip = plan.trips[0]
        return {
            "org": trip.org.location_id,
            "dst": trip.dst.location_id,
            "dept": [trip.dept for trip in plan.trips],
            "arrv": [trip.arrv for trip in plan.trips],
            "service": plan.service,
            "reservable": await self.reserver.reservable(
                service=plan.service,
                org=trip.org.location_id,
                dst=trip.dst.location_id,
            )
            if plan.service != "walking"
            else True,
        }
