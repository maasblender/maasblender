# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import logging

from event import Manager as EventManager, \
    EventIdentifier, ReserveEvent, ReservedEvent, DepartEvent, DepartedEvent, ArrivedEvent
from core import Runner, User, Task, Location, Route as RoutePlan
from planner import Planner

logger = logging.getLogger("user")


# ToDo: 抽象度が足りない。
class Trip(Task):
    def __init__(self, manager: EventManager, org: Location, dst: Location, service: str, fail: typing.List['Trip'] = None):
        self.event_manager = manager
        self.service = service
        self.org = org
        self.dst = dst
        self.fail = fail if fail else []

    def __call__(self, user: User):
        return self.event_manager.env.process(self._process(user))

    def _process(self, user: User):
        self.event_manager.enqueue(ReserveEvent(
            service=self.service,
            user_id=user.user_id,
            org=self.org,
            dst=self.dst,
            dept=self.event_manager.env.now,
            now=self.event_manager.env.now
        ))
        event: ReservedEvent = yield self.event_manager.event(ReservedEvent(
            source=self.service,
            user_id=user.user_id
        ))
        if not event.success:
            if not self.fail:
                logger.warning(
                    f"Ignore the user's, {event.user_id}, events "
                    f"because the {event.source} service could not be reserved and the fail-process was not configured."
                )
            return self.fail

        self.event_manager.enqueue(DepartEvent(
            service=self.service,
            user_id=user.user_id,
            now=self.event_manager.env.now
        ))
        yield self.event_manager.event(DepartedEvent(
            source=self.service,
            user_id=user.user_id,
            location=self.org
        ))

        yield self.event_manager.event(ArrivedEvent(
            source=self.service,
            user_id=user.user_id,
            location=self.dst
        ))


class UserManager(Runner):
    def __init__(self):
        super().__init__()
        self.locations = {}
        self._event_manager = EventManager(env=self.env)
        self.route_planner: typing.Optional[Planner] = None

    async def close(self):
        if self.route_planner:
            await self.route_planner.close()

    @property
    def triggered_events(self):
        events = self._event_manager.dequeue()
        return events

    def setup_planer(self, endpoint: str):
        self.route_planner = Planner(endpoint=endpoint)

    async def demand(self, user_id: str, org: Location, dst: Location, fixed_service: typing.Optional[str] = None):
        """ 利用者の移動需要を追加する

        fixed_service が利用される経路を選ぶ。
        fixed_service が指定されない場合は、経路探索の結果の一つ目を選ぶ。
        """

        route_plans = await self.route_planner.plan(org, dst, self.env.now)

        user = User(
            id_=user_id,
            org=org,
            dst=dst,
            tasks=self.plans_to_trips(route_plans, fixed_service)
        )
        self.env.process(user.run())

    def trigger(self, event: EventIdentifier):
        self._event_manager.trigger(event)

    def plans_to_trips(self, plans: typing.List[RoutePlan], fixed_service: typing.Optional[str] = None):
        def first_plan_with(service: str):
            if service == "walking":
                for each in plans:
                    if len(each.trips) == 1 and each.trips[0].service == service:
                        return each
            else:
                for each in plans:
                    for trip in each.trips:
                        if trip.service == service:
                            return each
            logger.warning(
                f"The designated transportation service '{service}' cannot be used to trip "
                f"from the origin '{plans[0].org}' to the destination '{plans[0].dst}'."
                f"This is independent of the reservation conditions."
            )
            return plans[0]

        if fixed_service:
            route = first_plan_with(fixed_service)
            return self.trips_with_walking_in_case_of_failure([*self._plan_to_trips(route)])
        else:
            # If the result of the route search is walking only
            # ToDo: Unclear criteria for determining walking plan
            if len(plans) == 1:
                # never fail to reservation walking
                return [*self._plan_to_trips(plans[0])]

            # ToDo: Consider whether the planner is responsible for returning the walking route.
            return self.trips_with_subsequent_in_case_of_failure(
                [*self._plan_to_trips(plans[0])],
                [*self._plan_to_trips(plans[1])]
            )

    def trips_with_walking_in_case_of_failure(self, trips: typing.List[Trip]):
        for trip in trips:
            if trip.service != "walking" and len(trip.fail) == 0:
                trip.fail = [Trip(
                    self._event_manager,
                    org=trip.org,
                    dst=trips[-1].dst,
                    service="walking"
                )]
        return trips

    def trips_with_subsequent_in_case_of_failure(self, primary_trips: typing.List[Trip], secondary_trips: typing.List[Trip]):

        # If the primary plan is on foot
        if len(primary_trips) == 1 and primary_trips[0].service == "walking":
            return self.trips_with_walking_in_case_of_failure(primary_trips)

        # If the secondary plan is on foot
        if len(secondary_trips) == 1 and secondary_trips[0].service == "walking":
            return self.trips_with_walking_in_case_of_failure(primary_trips)

        assert len(primary_trips) == 3
        assert len(secondary_trips) == 3
        assert len(primary_trips[1].fail) == 0
        # ToDo: secondary trips on might not always be suitable.
        primary_trips[1].fail = [
            Trip(
                self._event_manager,
                org=primary_trips[1].org,
                dst=secondary_trips[1].org,
                service="walking"
            )
        ] + self.trips_with_walking_in_case_of_failure(secondary_trips)[1:]

        return primary_trips

    def _plan_to_trips(self, route: RoutePlan):
        assert route.trips
        for trip in route:
            yield Trip(
                self._event_manager,
                org=self.locations.get(trip.org.location_id, trip.org),  # ToDo: 今の実装に必然性はない気がする。
                dst=self.locations.get(trip.dst.location_id, trip.dst),
                service=trip.service if trip.service else "walking"
            )
