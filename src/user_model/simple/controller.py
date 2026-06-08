# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging

import fastapi

from core import Location, Route, Trip
from event import ReservedEvent, DepartedEvent, ArrivedEvent
from jschema import query, response
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
    builder.set_feature(events.EventType.DEMAND, required=["demand_id", "pre_reserve"])
    builder.set_feature(events.EventType.RESERVE, declared=["demand_id"])
    builder.set_feature(events.EventType.DEPART, declared=["demand_id"])
    builder.set_feature(
        events.EventType.RESERVED, declared=["demand_id"], required=["pre_reserve"]
    )
    builder.set_feature(events.EventType.DEPARTED, declared=["demand_id"])
    builder.set_feature(events.EventType.ARRIVED, declared=["demand_id"])
    return builder.get_specification_response(version=events.VERSION_1)


@app.get("/spec/schema")
def get_event_schema_all() -> dict[str, spec.JsonSchemaValue | None]:
    builder = spec.EventSpecificationBuilder(
        step=response.StepEvent, triggered=query.TriggeredEvent
    )
    return builder.schemas


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    global manager

    manager = UserManager(
        preference_mode=settings.preference_mode,
        confirmed_services=settings.confirmed_services,
    )
    manager.setup_planner(endpoint=settings.planner.endpoint.unicode_string())

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
                arrv=event.details.arrv,
                service=event.details.service,
            )
        case query.ReservedEvent():
            manager.trigger(
                ReservedEvent(
                    source=event.source,
                    success=event.details.success,
                    user_id=event.details.userId,
                    demand_id=event.details.demandId,
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
