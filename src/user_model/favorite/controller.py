# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging

import aiohttp
import fastapi

from core import Location, Route, Trip
from event import ReservedEvent, DepartedEvent, ArrivedEvent
from jschema import query, response
from mblib.io import httputil
from mblib.io.log import init_logger
from mblib.jschema import spec, events
from user_manager import UserManager

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="user manager",
    description="simulate selection and use of mobility based on DEMAND events",
    # version="0.1.0",
    # docs_url="/docs"
    # redoc_url="/redoc",
)


@app.on_event("startup")
def startup():
    init_logger()


@app.exception_handler(Exception)
def exception_callback(request: fastapi.Request, exc: Exception):
    from fastapi.responses import PlainTextResponse

    # omitted traceback here, because uvicorn outputs traceback as ASGI Exception
    logger.error("failed process called at %s", request.url)
    return PlainTextResponse(str(exc), status_code=500)


manager: UserManager | None = None


@app.on_event("shutdown")
async def shutdown_event():
    await finish()


@app.get(
    "/spec", response_model=spec.SpecificationResponse, response_model_exclude_none=True
)
def get_specification():
    builder = spec.EventSpecificationBuilder(
        step=response.StepEvent, triggered=query.TriggeredEvent
    )
    builder.set_feature(
        events.EventType.DEMAND,
        declared=["user_type"],
        required=["demand_id", "pre_reserve"],
    )
    builder.set_feature(events.EventType.RESERVE, declared=["demand_id"])
    builder.set_feature(events.EventType.DEPART, declared=["demand_id"])
    builder.set_feature(
        events.EventType.RESERVED, declared=["demand_id"], required=["pre_reserve"]
    )
    builder.set_feature(events.EventType.DEPARTED, declared=["demand_id"])
    builder.set_feature(events.EventType.ARRIVED, declared=["demand_id"])
    return builder.get_specification_response(version=events.VERSION_1)


def convert(
    user: dict[str, str], user_types: dict[str, query.UserType]
) -> tuple[str, query.UserType | None]:
    """convert from user infomation to parameters about user favorite"""
    user_id = user["userId"]
    if user_type := user.get("userType"):
        if param := user_types.get(user_type):
            return user_id, param
        else:
            logger.warning("no userType=%s parameter of user_id=%s", user_type, user_id)
    else:
        logger.info("no userType of user_id=%s", user_id)
    return user_id, None


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    users: list[dict[str, str]] = []
    async with aiohttp.ClientSession() as session:
        for e in settings.users:
            async with session.get(str(e.fetch_url)) as resp:
                await httputil.check_response(resp)
                users.extend(await resp.json())

    global manager
    if settings.userTypes:
        user_params = dict(convert(user, settings.userTypes) for user in users)
    else:
        logger.warning("user.userTypes setting is not defined")
        user_params = {user["userId"]: None for user in users}
    manager = UserManager(user_params, confirmed_services=settings.confirmed_services)
    manager.setup_planner(endpoint=settings.planner.endpoint)

    return {"message": "successfully configured."}


@app.post("/start", response_model=response.Message)
def start():
    global manager

    manager.start()
    return {"message": "successfully started."}


@app.get("/peek", response_model=response.Peek)
def peek():
    global manager

    peek_time = manager.peek()

    return {"next": peek_time if peek_time < float("inf") else -1}


@app.post("/step", response_model=response.Step)
def step():
    now = manager.step()
    events = [event.dumps() for event in manager.triggered_events]
    return {"now": now, "events": events}


@app.post("/triggered")
async def triggered(event: query.TriggeredEvent | events.Event):
    # expect nothing to happen. just let time forward.
    if manager.env.now < event.time:
        manager.env.run(until=event.time)

    match event:
        case query.DemandEvent():
            await manager.demand(
                user_id=event.details.userId,
                demand_id=event.details.demandId,
                org=Location(
                    id_=event.details.org.locationId,
                    lat=event.details.org.lat,
                    lng=event.details.org.lng,
                ),
                dst=Location(
                    id_=event.details.dst.locationId,
                    lat=event.details.dst.lat,
                    lng=event.details.dst.lng,
                ),
                dept=event.details.dept,
                fixed_service=event.details.service,
            )
        case query.ReservedEvent():
            manager.trigger(
                ReservedEvent(
                    source=event.source,
                    success=event.details.success,
                    user_id=event.details.userId,
                    route=Route(
                        [
                            Trip(
                                org=Location(
                                    id_=trip.org.locationId,
                                    lat=trip.org.lat,
                                    lng=trip.org.lng,
                                ),
                                dst=Location(
                                    id_=trip.dst.locationId,
                                    lat=trip.dst.lat,
                                    lng=trip.dst.lng,
                                ),
                                dept=trip.dept,
                                arrv=trip.arrv,
                                # reserved mobility trip if service is None
                                service=trip.service if trip.service else event.source,
                            )
                            for trip in event.details.route
                        ]
                    ),
                )
            )
        case query.DepartedEvent():
            manager.trigger(
                DepartedEvent(
                    source=event.source,
                    user_id=event.details.userId,
                    demand_id=event.details.demandId,
                    location=Location(
                        id_=event.details.location.locationId,
                        lat=event.details.location.lat,
                        lng=event.details.location.lng,
                    ),
                )
            )
        case query.ArrivedEvent():
            manager.trigger(
                ArrivedEvent(
                    source=event.source,
                    user_id=event.details.userId,
                    demand_id=event.details.demandId,
                    location=Location(
                        id_=event.details.location.locationId,
                        lat=event.details.location.lat,
                        lng=event.details.location.lng,
                    ),
                )
            )


@app.post("/finish", response_model=response.Message)
async def finish():
    global manager

    if manager:
        await manager.close()
        manager = None
    return {"message": "successfully finished."}
