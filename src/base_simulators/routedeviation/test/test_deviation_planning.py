# SPDX-FileCopyrightText: 2026 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core import Service, Stop, StopTime, TripLocation
from mblib.jschema.events import Location
from mobility import Car
from routing import EqualIntervalRouter, RoadDistanceRouter
from simulation import Simulation
from trip import SingleTrip


class DeviationPlanningTestCase(unittest.IsolatedAsyncioTestCase):
    def create_simulation(self, router=None, capacity=2):
        day = date(2022, 1, 1)
        self.day = day
        self.origin = Stop("origin", "Origin", 36, 137)
        self.destination = Stop("destination", "Destination", 36.1, 137.1)
        self.end = Stop("end", "End", 36.2, 137.2)
        return Simulation(
            start_time=datetime.combine(day, datetime.min.time()),
            capacity=capacity,
            router=router,
            trips={
                "car": SingleTrip(
                    route=None,
                    service=Service(
                        day, day + timedelta(days=1), saturday=True, sunday=True
                    ),
                    stop_times_with=[
                        StopTime(self.origin, departure=timedelta(hours=9)),
                        TripLocation(
                            "flex", timedelta(hours=9), timedelta(hours=9, minutes=10)
                        ),
                        StopTime(
                            self.destination, arrival=timedelta(hours=9, minutes=10)
                        ),
                        TripLocation(
                            "flex2",
                            timedelta(hours=9, minutes=10),
                            timedelta(hours=9, minutes=20),
                        ),
                        StopTime(self.end, arrival=timedelta(hours=9, minutes=20)),
                    ],
                )
            },
        )

    async def reserve(self, sim, user="user", dst="destination", dept=0, lat=36.05):
        await sim.reserve_user(
            user,
            f"demand-{user}",
            Location(locationId="flex", lat=lat, lng=137.05),
            Location(locationId=dst, lat=36.1, lng=137.1),
            dept,
        )

    async def test_default_router_stores_equal_interval_plan(self):
        sim = self.create_simulation()
        car = sim.car_manager.mobilities["car"]
        self.assertIsInstance(car.router, EqualIntervalRouter)
        await self.reserve(sim)
        plan = car.deviation_plans[(self.day, "flex")]
        self.assertEqual(1, len(plan))
        self.assertEqual(
            sim.env.start_time + timedelta(hours=9, minutes=5), plan[0].arrival
        )
        self.assertEqual(car.users["user"].path.pick_up_stop, plan[0].stop)

    async def test_movement_uses_saved_plan_without_recalculating(self):
        router = EqualIntervalRouter()
        router.plan = AsyncMock(wraps=router.plan)
        sim = self.create_simulation(router)
        await self.reserve(sim)
        router.plan.assert_awaited_once()
        sim.dept_user("user")
        sim.start()
        triggered = []
        while sim.peek() < 561:
            sim.step()
            triggered.extend(sim.event_queue.events)
        departures = [
            event
            for event in triggered
            if event["eventType"] == "DEPARTED" and event["details"]["userId"] == "user"
        ]
        self.assertEqual([545], [event["time"] for event in departures])
        self.assertEqual({}, sim.car_manager.mobilities["car"].users)
        router.plan.assert_awaited_once()

    async def test_additional_reservation_replans_existing_stops(self):
        sim = self.create_simulation()
        await self.reserve(sim, "first")
        await self.reserve(sim, "second", lat=36.06)
        car = sim.car_manager.mobilities["car"]
        plan = car.deviation_plans[(self.day, "flex")]
        self.assertEqual(
            [car.users[user].path.pick_up_stop for user in ("first", "second")],
            [stop.stop for stop in plan],
        )
        self.assertEqual(
            [
                sim.env.start_time + timedelta(hours=9, minutes=i * 10 / 3)
                for i in (1, 2)
            ],
            [stop.arrival for stop in plan],
        )

    async def test_rejected_plan_preserves_existing_reservation_and_plan(self):
        router = EqualIntervalRouter()
        sim = self.create_simulation(router)
        await self.reserve(sim, "first")
        car = sim.car_manager.mobilities["car"]
        saved = dict(car.deviation_plans)
        router.plan = AsyncMock(return_value=None)
        await self.reserve(sim, "second")
        self.assertEqual({"first"}, set(car.users))
        self.assertEqual(saved, car.deviation_plans)
        sim.env.run(until=1)
        self.assertFalse(sim.event_queue.events[-1]["details"]["success"])

    async def test_two_deviation_areas_are_committed_atomically(self):
        router = EqualIntervalRouter()
        equal_interval_plan = router.plan
        calls = 0

        async def reject_second(**kwargs):
            nonlocal calls
            calls += 1
            return await equal_interval_plan(**kwargs) if calls == 1 else None

        router.plan = AsyncMock(side_effect=reject_second)
        sim = self.create_simulation(router)
        await self.reserve(sim, dst="flex2")
        self.assertEqual(2, router.plan.await_count)
        car = sim.car_manager.mobilities["car"]
        self.assertEqual({}, car.users)
        self.assertEqual({}, car.deviation_plans)

    async def test_plans_are_separate_for_each_service_date(self):
        sim = self.create_simulation()
        await self.reserve(sim, "today")
        await self.reserve(sim, "tomorrow", dept=1440)
        car = sim.car_manager.mobilities["car"]
        for day, user in (
            (self.day, "today"),
            (self.day + timedelta(days=1), "tomorrow"),
        ):
            plan = car.deviation_plans[(day, "flex")]
            self.assertEqual(
                [car.users[user].path.pick_up_stop], [stop.stop for stop in plan]
            )
            self.assertEqual(
                datetime.combine(day, datetime.min.time())
                + timedelta(hours=9, minutes=5),
                plan[0].arrival,
            )

    async def test_capacity_rejection_does_not_call_router(self):
        router = EqualIntervalRouter()
        router.plan = AsyncMock(wraps=router.plan)
        sim = self.create_simulation(router, capacity=1)
        await self.reserve(sim, "first")
        router.plan.reset_mock()
        await self.reserve(sim, "second")
        router.plan.assert_not_awaited()
        self.assertEqual({"first"}, set(sim.car_manager.mobilities["car"].users))

    async def test_reservation_after_deviation_departure_is_rejected(self):
        router = EqualIntervalRouter()
        router.plan = AsyncMock(wraps=router.plan)
        sim = self.create_simulation(router)
        sim.env.run(until=540)
        await self.reserve(sim, dept=540)
        router.plan.assert_not_awaited()
        self.assertEqual({}, sim.car_manager.mobilities["car"].users)

    async def test_rejected_candidate_falls_back_to_another_vehicle(self):
        sim = self.create_simulation()
        first = sim.car_manager.mobilities["car"]
        first.router.plan = AsyncMock(return_value=None)
        second = Car(sim.env, sim.event_queue, "other", 2, first.trip(self.day))
        sim.car_manager.mobilities["other"] = second
        await self.reserve(sim)
        first.router.plan.assert_awaited_once()
        self.assertEqual({}, first.users)
        self.assertEqual({}, first.deviation_plans)
        self.assertIn("user", second.users)
        self.assertIn((self.day, "flex"), second.deviation_plans)

    async def test_fixed_stop_reservation_does_not_require_deviation_planning(self):
        router = EqualIntervalRouter()
        router.plan = AsyncMock(wraps=router.plan)
        sim = self.create_simulation(router)
        await sim.reserve_user(
            "user",
            "demand",
            Location(locationId="origin", lat=36, lng=137),
            Location(locationId="destination", lat=36.1, lng=137.1),
            0,
        )
        router.plan.assert_not_awaited()
        car = sim.car_manager.mobilities["car"]
        self.assertIn("user", car.users)
        self.assertEqual({}, car.deviation_plans)

    async def test_brute_force_reservation_and_equal_interval_inquiry(self):
        response = MagicMock()
        response.json = AsyncMock(
            return_value={"matrix": [[0, 400, 1000], [400, 0, 600], [1000, 600, 0]]}
        )
        request = MagicMock()
        request.__aenter__ = AsyncMock(return_value=response)
        session = MagicMock()
        session.post.return_value = request
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        sim = self.create_simulation(RoadDistanceRouter("http://planner", 100))
        with patch("routing.aiohttp.ClientSession", return_value=client) as factory:
            self.assertIs(True, await sim.reservable("flex", "destination"))
            factory.assert_not_called()
            await self.reserve(sim)
            car = sim.car_manager.mobilities["car"]
            self.assertEqual(
                sim.env.start_time + timedelta(hours=9, minutes=4),
                car.deviation_plans[(self.day, "flex")][0].arrival,
            )
            sim.dept_user("user")
            sim.start()
            triggered = []
            while sim.peek() < 561:
                sim.step()
                triggered.extend(sim.event_queue.events)
            departures = [
                event["time"]
                for event in triggered
                if event["eventType"] == "DEPARTED"
                and event["details"]["userId"] == "user"
            ]
            self.assertEqual([544], departures)
            self.assertEqual({}, car.users)
            session.post.assert_called_once()
