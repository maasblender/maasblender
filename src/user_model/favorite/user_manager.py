# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import dataclasses
import itertools
import logging

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
from jschema.query import SortType, UserType
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
        # modify expected arrival if the departure is changed
        arrv = dept + (self.arrv - self.dept) if self.arrv else None
        self.event_manager.enqueue(
            ReserveEvent(
                service=self.service,
                user_id=user.user_id,
                org=self.org,
                dst=self.dst,
                dept=dept,
                arrv=arrv,
                now=dept,
            )
        )
        event: ReservedEvent = yield self.event_manager.event(
            ReservedEvent(source=self.service, user_id=user.user_id)
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
                now=self.event_manager.env.now,
            )
        )
        # not yield, only wait arrived event here.
        self.event_manager.event(
            DepartedEvent(source=self.service, user_id=user.user_id, location=self.org)
        )

        yield self.event_manager.event(
            ArrivedEvent(source=self.service, user_id=user.user_id, location=self.dst)
        )


@dataclasses.dataclass(frozen=True)
class RouteFilter:
    def __call__(self, plans: list[Route]) -> list[Route]:
        plans = [plan for plan in self._sorted(plans) if self._check(plan)]
        assert plans, "no user_favorite_plans"
        return plans

    def _sorted(self, plans: list[Route]):
        return plans

    def _check(self, plan: Route) -> bool:
        # everything pass
        return True


@dataclasses.dataclass(frozen=True)
class SortTypeRouteFilter(RouteFilter):
    sort_type: SortType | None

    @staticmethod
    def _debug_route(plans: list[Route]):
        logger.debug(f"arrvs {[p.arrv for p in plans]}")
        logger.debug(f"walking_time {[p.walking_time for p in plans]}")

    def _sorted(self, plans: list[Route]):
        self._debug_route(plans)
        if self.sort_type is None:
            return plans
        match self.sort_type:
            case SortType.BY_ARRIVAL_TIME:
                sorted_plans = sorted(plans, key=lambda x: x.arrv)
            case SortType.BY_WALKING_TIME:
                sorted_plans = sorted(plans, key=lambda x: x.walking_time)
            case _:
                raise ValueError(f"Invalid sort type {self.sort_type}")
        self._debug_route(sorted_plans)
        return sorted_plans


@dataclasses.dataclass(frozen=True)
class FavoriteRouteFilter(RouteFilter):
    favorite_service: set[str] | None
    walking_time_limit_min: float

    def _check(self, plan: Route) -> bool:
        if plan.is_walking_only():  # only walking routes remain
            return True
        return self._check_service(plan) and self._check_walking_limit(plan)

    def _check_service(self, plan: Route) -> bool:
        if self.favorite_service is None:
            return True
        if self.favorite_service == {"walking"}:
            return False
        services = set(t.service for t in plan.trips)
        return bool(self.favorite_service & services)

    def _check_walking_limit(self, plan: Route) -> bool:
        walking_time = sum(
            t.arrv - t.dept for t in plan.trips if t.service == "walking"
        )
        return walking_time <= self.walking_time_limit_min


@dataclasses.dataclass(frozen=True)
class FavoriteSortedRouteFilter(SortTypeRouteFilter, FavoriteRouteFilter):
    pass


class Wait(Task):
    """
    waiting for departure
    """

    def __init__(self, manager: EventManager, dept: float):
        self.event_manager = manager
        self.dept = dept

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, _: User):
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
                org=self.route.trips[1].org,
                dst=self.route.trips[1].dst,
                dept=self.route.trips[1].dept,
                now=self.event_manager.env.now,
            )
        )
        event: ReservedEvent = yield self.event_manager.event(
            ReservedEvent(source=self.service, user_id=user.user_id)
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
                now=self.event_manager.env.now,
            )
        )

        # not yield, only wait arrived event here.
        self.event_manager.event(
            DepartedEvent(source=self.service, user_id=user.user_id, location=self.org)
        )

        yield self.event_manager.event(
            ArrivedEvent(source=self.service, user_id=user.user_id, location=self.dst)
        )


def filter_plans_by_fixed_service(
    plans: list[Route], fixed_service: str
) -> list[Route]:
    if fixed_service == "walking":  # select walk-only route
        return [plan for plan in plans if plan.is_walking_only()]
    else:  # select route containing the service
        result = [
            plan
            for plan in plans
            if fixed_service in {trip.service for trip in plan.trips}
        ]
        if result:
            return result
        else:
            logger.warning(
                f"The designated transportation service '{fixed_service}' cannot be used to trip "
                f"from the origin '{plans[0].org}' to the destination '{plans[0].dst}'."
                f"This is independent of the reservation conditions."
            )
            logger.warning(
                f"ignore fixed service, because of no plan using {fixed_service=}"
            )
            return plans


class UserManager(Runner):
    _event_manager: EventManager
    _route_filter: dict[str, RouteFilter]  # key: userId
    route_planner: Planner | None
    confirmed_services: list[str]

    def __init__(
        self,
        user_params: dict[str, UserType | None],
        confirmed_services: list[str] = None,
    ):
        super().__init__()
        self._event_manager = EventManager(env=self.env)
        self._route_filter = {
            k: FavoriteSortedRouteFilter(
                favorite_service=v.favorite_service,
                walking_time_limit_min=v.walking_time_limit_min,
                sort_type=v.sort_type,
            )
            if v
            else RouteFilter()
            for k, v in user_params.items()
        }
        self.route_planner = None
        self.confirmed_services = confirmed_services or []

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
        org: Location,
        dst: Location,
        dept: float | None,
        fixed_service: str | None,
    ):
        """Add the mobility demand of the user.

        Select a route where fixed_service is used.
        If fixed_service is not specified, select the first result of the route search.
        """
        dept = dept if dept else self.env.now

        route_plans = await self.route_planner.plan(org, dst, dept)

        import pprint

        logger.debug(f"plans_from_otp_planner num={len(route_plans)}")
        for rp in route_plans:
            logger.debug(pprint.pformat(rp))

        assert user_id in self._route_filter, f"{user_id=} not includes on users"
        route_filter = self._route_filter[user_id]
        tasks = self.plans_to_trips(route_plans, fixed_service, route_filter)
        user = User(
            id_=user_id,
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

    def plans_to_trips(
        self, plans: list[Route], fixed_service: str | None, route_filter: RouteFilter
    ):
        if fixed_service:  # check for each DEMAND event
            plans = filter_plans_by_fixed_service(plans, fixed_service)
        else:  # check for each user
            plans = route_filter(plans)

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
