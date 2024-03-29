# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import math

import fastapi

from historical import HistoricalScenario
from jschema import query, response
from mblib.io.log import init_logger
from mblib.jschema import events, spec

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="scenario (for historical)",
    description="make DEMAND events by departure time, origin, and destination",
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


scenario: HistoricalScenario | None = None


@app.get("/spec", response_model=spec.SpecificationResponse, response_model_exclude_none=True)
def get_specification():
    builder = spec.EventSpecificationBuilder(step=response.StepEvent)
    builder.set_feature(events.EventType.DEMAND, declared=["demand_id", "pre_reserve"])
    return builder.get_specification_response(version=events.VERSION_1)


@app.post("/setup", response_model=response.Message)
def setup(settings: query.Setup):
    global scenario
    scenario = HistoricalScenario()
    scenario.setup(settings.trips, settings.userIDFormat, settings.demandIDFormat, settings.offset_time)
    return response.Message(message="successfully configured.")


@app.get("/users", response_model=list[response.User], response_model_exclude_none=True)
def get_users():
    return scenario.users()


@app.post("/start", response_model=response.Message)
def start():
    scenario.start()
    return response.Message(message="successfully started.")


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = scenario.peek()
    next_ = peek_time if math.isfinite(peek_time) else -1
    return response.Peek(next=next_)


@app.post("/step", response_model=response.Step, response_model_exclude_none=True)
def step():
    now, events = scenario.step()
    return {"now": now, "events": events}


@app.post("/triggered")
def triggered(_: events.Event):
    pass


@app.post("/finish", response_model=response.Message)
def finish():
    global scenario
    scenario = None
    return response.Message(message="successfully finished.")
