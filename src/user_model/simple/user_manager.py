# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import itertools
import logging

from jschema.query import PreferenceMode
from core import Runner, User, Task, Location, Route
from event import (
    Manager as EventManager,
    EventIdentifier,
    ReserveEvent,
    ReservedEvent,
    DepartEvent,
    DepartedEvent,
    ArrivedEvent,
)
from planner import Planner

logger = logging.getLogger(__name__)


class Trip(Task):
    def __init__(
        self,
        manager: EventManager,
        org: Location,
        dst: Location,
        service: str,
        dept: float,
        arrv: float | None = None,
        fail: list[Task] = None,
    ):
        self.event_manager = manager
        self.service = service
        self.org = org
        self.dst = dst
        self.dept = dept
        self.arrv = arrv
        self.fail = fail or []

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, user: User):
        dept = self.event_manager.env.now
        arrv = (
            dept + (self.arrv - self.dept) if self.arrv else None
        )  # modify expected arrival if the depature is changed
        self.event_manager.enqueue(
            ReserveEvent(
                service=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                org=self.org,
                dst=self.dst,
                dept=dept,
                arrv=arrv,
                now=dept,
            )
        )
        event: ReservedEvent = yield self.event_manager.event(
            ReservedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
            )
        )
        if not event.success:
            if not self.fail:
                logger.warning(
                    f"Ignore the user's, {event.user_id}, events "
                    f"because the {event.source} service could not be reserved and the fail-process was not configured."
                )
            return self.fail

        self.event_manager.enqueue(
            DepartEvent(
                service=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                now=self.event_manager.env.now,
            )
        )
        # not yield, only wait arrived event here.
        self.event_manager.event(
            DepartedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                location=self.org,
            )
        )

        yield self.event_manager.event(
            ArrivedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                location=self.dst,
            )
        )


class Wait(Task):
    """
    waiting for departure
    """

    def __init__(self, manager: EventManager, dept: float):
        self.event_manager = manager
        self.dept = dept

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, user: User):
        if self.dept > self.event_manager.env.now:
            yield self.event_manager.env.timeout(self.dept - self.event_manager.env.now)


class Reserve(Task):
    """
    (pre)reserve mobility before trip
    """

    def __init__(self, manager: EventManager, route: Route, fail: list[Task] = None):
        assert len(route.trips) == 3
        self.event_manager = manager
        self.route = route
        self.service = route.trips[1].service
        self.org = route.trips[0].org
        self.dst = route.trips[-1].dst
        self.fail = fail if fail else []

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, user: User):
        self.event_manager.enqueue(
            ReserveEvent(
                service=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                org=self.route.trips[1].org,
                dst=self.route.trips[1].dst,
                dept=self.route.trips[1].dept,
                now=self.event_manager.env.now,
            )
        )
        event: ReservedEvent = yield self.event_manager.event(
            ReservedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
            )
        )
        # wait for departure from pre-reserve time
        if self.route.trips[0].dept > self.event_manager.env.now:
            yield self.event_manager.env.timeout(
                self.route.trips[0].dept - self.event_manager.env.now
            )
        if not event.success:
            if not self.fail:
                logger.warning(
                    f"Ignore the user's, {event.user_id}, events "
                    f"because the {event.source} service could not be reserved and the fail-process was not configured."
                )
            return self.fail

        if len(event.route.trips) > 1 and event.route.trips[0].service == "walking":
            # add pre walking trip from event
            pre_dst = event.route.trips[0].dst  # maybe org of mobility
            pre_arrv = event.route.trips[0].arrv
            mobility_trip = event.route.trips[1]
        else:
            pre_dst = self.route.trips[0].dst
            pre_arrv = self.route.trips[0].arrv
            mobility_trip = event.route.trips[0]
        post_span = self.route.trips[2].arrv - self.route.trips[2].dept
        if len(event.route.trips) > 1 and event.route.trips[-1].service == "walking":
            # add post walking trip from event
            post_org = event.route.trips[-1].org  # maybe dst of mobility
            post_dept = event.route.trips[-1].dept
            post_arrv = event.route.trips[-1].arrv + post_span
        else:
            post_org = self.route.trips[2].org
            post_dept = mobility_trip.arrv
            post_arrv = post_dept + post_span

        return [
            Trip(
                self.event_manager,
                org=self.org,
                dst=pre_dst,
                service=self.route.trips[0].service,  # walking
                dept=self.route.trips[0].dept,
                arrv=pre_arrv,
            ),
            ReservedTrip(
                self.event_manager,
                org=mobility_trip.org,
                dst=mobility_trip.dst,
                service=self.route.trips[1].service,
                dept=mobility_trip.dept,
            ),
            Trip(
                self.event_manager,
                org=post_org,  # maybe dst of mobility
                dst=self.dst,
                service=self.route.trips[2].service,
                dept=post_dept,
                arrv=post_arrv,
            ),
        ]


class ReservedTrip(Task):
    """
    (pre)Reserved trip
    """

    def __init__(
        self,
        manager: EventManager,
        org: Location,
        dst: Location,
        service: str,
        dept: float,
    ):
        self.event_manager = manager
        self.service = service
        self.org = org
        self.dst = dst
        self.dept = dept

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, user: User):
        # do not wait (dept is for mobility, not for user)
        self.event_manager.enqueue(
            DepartEvent(
                service=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                now=self.event_manager.env.now,
            )
        )

        # not yield, only wait arrived event here.
        self.event_manager.event(
            DepartedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                location=self.org,
            )
        )

        yield self.event_manager.event(
            ArrivedEvent(
                source=self.service,
                user_id=user.user_id,
                demand_id=user.demand_id,
                location=self.dst,
            )
        )


def filter_plans_by_fixed_service(
    plans: list[Route], fixed_service: str
) -> list[Route]:
    if fixed_service == "walking":
        # select walk-only route
        return [plan for plan in plans if plan.is_walking_only()]
    else:
        # select route containing the service
        if result := [
            plan
            for plan in plans
            if fixed_service in {trip.service for trip in plan.trips}
        ]:
            return result
        else:
            return filter_plans_by_fixed_service(plans, "walking")


def sort_plans_by_prefer_service(
    plans: list[Route], prefer_service: str
) -> list[Route]:
    plans.sort(
        key=lambda plan: prefer_service not in {trip.service for trip in plan.trips}
    )
    return plans


class UserManager(Runner):
    _event_manager: EventManager
    route_planner: Planner | None
    confirmed_services: list[str]

    def __init__(
        self, preference_mode: PreferenceMode, confirmed_services: list[str] = None
    ):
        super().__init__()
        self._event_manager = EventManager(env=self.env)
        self.route_planner = None
        self.confirmed_services = confirmed_services or []
        self.preference = (
            filter_plans_by_fixed_service
            if preference_mode == PreferenceMode.fixed
            else sort_plans_by_prefer_service
        )

    async def close(self):
        if self.route_planner:
            await self.route_planner.close()

    @property
    def triggered_events(self):
        events = self._event_manager.dequeue()
        return events

    def setup_planner(self, endpoint: str):
        self.route_planner = Planner(endpoint=endpoint)

    async def demand(
        self,
        user_id: str,
        demand_id: str,
        org: Location,
        dst: Location,
        dept: float | None,
        service: str | None,
    ):
        """Add the mobility demand of the user.

        Select a route where fixed_service is used.
        If fixed_service is not specified, select the first result of the route search.
        """
        dept = dept if dept else self.env.now

        route_plans = await self.route_planner.plan(org, dst, dept)

        tasks = self.plans_to_trips(route_plans, service)
        user = User(
            user_id=user_id,
            demand_id=demand_id,
            org=org,
            dst=dst,
            dept=dept,
            tasks=self.wait_for_departure(dept, tasks),  # add waiting task
        )
        self.env.process(user.run())

    def trigger(self, event: EventIdentifier):
        self._event_manager.trigger(event)

    def wait_for_departure(self, dept: float, tasks: list[Task]):
        """
        add task of waiting for departure
        """
        task = tasks[0]
        if isinstance(task, Trip) and self.env.now < dept:
            return [Wait(self._event_manager, dept=dept), *tasks]
        else:
            return tasks

    def plans_to_trips(self, plans: list[Route], service: str | None):
        if service:  # check for each DEMAND event
            plans = self.preference(plans, service)

        # ToDo: Unclear criteria for determining walking plan
        # No alternative plan
        if len(plans) == 1:
            return self.trips_with_walking_in_case_of_failure(
                self._plan_to_trips(plans[0])
            )

        # ToDo: Consider whether the planner is responsible for returning the walking route.
        return self.trips_with_subsequent_in_case_of_failure(
            self._plan_to_trips(plans[0]),
            self._plan_to_trips(plans[1]),
        )

    def trips_with_walking_in_case_of_failure(self, trips: list[Reserve] | list[Trip]):
        for trip in trips:
            if len(trip.fail) == 0:
                if isinstance(trip, Reserve):
                    trip.fail = [
                        Trip(
                            self._event_manager,
                            org=trip.org,
                            dst=trip.dst,
                            dept=trip.route.dept,
                            service="walking",
                        )
                    ]
                else:
                    assert isinstance(trip, Trip)
                    # never fail to reservation walking
                    if trip.service != "walking":
                        trip.fail = [
                            Trip(
                                self._event_manager,
                                org=trip.org,
                                dst=trips[-1].dst,
                                dept=trip.dept,
                                service="walking",
                            )
                        ]
        return trips

    def trips_with_subsequent_in_case_of_failure(
        self,
        primary_trips: list[Reserve] | list[Trip],
        secondary_trips: list[Reserve] | list[Trip],
    ):
        # If the primary plan is on foot
        if all(trip.service == "walking" for trip in primary_trips):
            return primary_trips

        # If the secondary plan is on foot
        if all(trip.service == "walking" for trip in secondary_trips):
            return self.trips_with_walking_in_case_of_failure(primary_trips)

        # If the secondary plan is confirmed service
        if isinstance(secondary_trips[0], Reserve):
            return self.trips_with_walking_in_case_of_failure(primary_trips)

        # Set up second plan, as recovery plan for the (first) mobility trip
        # ToDo: secondary trips on might not always be suitable.
        if isinstance(primary_trips[0], Reserve):
            primary_trips[0].fail = self.trips_with_walking_in_case_of_failure(
                secondary_trips
            )
        else:
            assert isinstance(secondary_trips[0], Trip)
            mobility_trip = next(
                itertools.dropwhile(lambda e: e.service == "walking", primary_trips)
            )
            recovery_trips = list(
                itertools.dropwhile(lambda e: e.service == "walking", secondary_trips)
            )
            mobility_trip.fail = [
                Trip(
                    self._event_manager,
                    org=mobility_trip.org,
                    dst=recovery_trips[0].org,
                    dept=recovery_trips[0].dept,
                    service="walking",
                ),
                *self.trips_with_walking_in_case_of_failure(recovery_trips),
            ]
        return self.trips_with_walking_in_case_of_failure(primary_trips)

    def _plan_to_trips(self, route: Route):
        if len(route.trips) == 3 and route.trips[1].service in self.confirmed_services:
            return [Reserve(self._event_manager, route)]
        else:
            return [
                Trip(
                    self._event_manager,
                    org=trip.org,
                    dst=trip.dst,
                    dept=trip.dept,
                    service=trip.service,
                )
                for trip in route
            ]
