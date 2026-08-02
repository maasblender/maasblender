# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import math

import fastapi
from core import Location
from jschema import query, response
from mblib.io.log import init_logger
from mblib.jschema import events, spec
from simulation import Simulation

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="walking mobility simulator",
    description="simulate travelling on foot",
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


sim: Simulation | None = None


@app.get(
    "/spec", response_model=spec.SpecificationResponse, response_model_exclude_none=True
)
def get_specification():
    builder = spec.EventSpecificationBuilder(
        step=response.StepEvent, triggered=query.TriggeredEvent
    )
    builder.set_feature(
        events.EventType.RESERVED, declared=["demand_id", "pre_reserve"]
    )
    builder.set_feature(events.EventType.DEPARTED, declared=["demand_id"])
    builder.set_feature(events.EventType.ARRIVED, declared=["demand_id"])
    builder.set_feature(events.EventType.RESERVE, required=["demand_id"])
    builder.set_feature(events.EventType.DEPART, required=["demand_id"])
    return builder.get_specification_response(version=events.VERSION_1)


@app.post("/setup", response_model=response.Message)
def setup(settings: query.Setup):
    global sim
    sim = Simulation(settings.walking_meters_per_minute)
    sim.setup()
    return response.Message(message="successfully configured.")


@app.post("/start", response_model=response.Message)
def start():
    sim.start()
    return response.Message(message="successfully started.")


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = sim.peek()
    next_ = peek_time if math.isfinite(peek_time) else -1
    return response.Peek(next=next_)


@app.post("/step", response_model=response.Step)
def step():
    now, events = sim.step()
    return response.Step(now=now, events=events)


@app.post("/triggered")
def triggered(event: query.TriggeredEvent | events.Event):
    # just let time forward to expect nothing to happen.
    sim.run(until=event.time)

    match event:
        case query.ReserveEvent():
            sim.reserve(
                user_id=event.details.userId,
                demand_id=event.details.demandId,
                org=Location(
                    location_id=event.details.org.locationId,
                    lat=event.details.org.lat,
                    lng=event.details.org.lng,
                ),
                dst=Location(
                    location_id=event.details.dst.locationId,
                    lat=event.details.dst.lat,
                    lng=event.details.dst.lng,
                ),
                dept=event.details.dept,
                arrv=event.details.arrv,
            )
        case query.DepartEvent():
            sim.depart(
                user_id=event.details.userId,
                demand_id=event.details.demandId,
            )


@app.get("/reservable", response_model=response.ReservableStatus)
def reservable(_org: str, _dst: str):
    return response.ReservableStatus(reservable=True)


@app.post("/finish", response_model=response.Message)
def finish():
    global sim
    sim = None
    return response.Message(message="successfully finished.")
