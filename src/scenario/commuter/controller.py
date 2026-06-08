# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import math

import fastapi

from commuter import CommuterScenario
from jschema.query import Setup
from jschema.response import Message, Peek, Step, StepEvent, User
from mblib.io.log import init_logger
from mblib.jschema import events, spec

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="scenario (for commuter)",
    description="make outbound and inbound DEMAND events",
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


scenario: CommuterScenario | None = None


@app.get(
    "/spec", response_model=spec.SpecificationResponse, response_model_exclude_none=True
)
def get_specification():
    builder = spec.EventSpecificationBuilder(step=StepEvent)
    builder.set_feature(
        events.EventType.DEMAND, declared=["demand_id", "pre_reserve", "arrive_by"]
    )
    return builder.get_specification_response(version=events.VERSION_1)


@app.post("/setup", response_model=Message)
def setup(settings: Setup):
    global scenario
    scenario = CommuterScenario()
    scenario.setup(settings.commuters, settings.demandIDFormat)
    return Message(message="successfully configured.")


@app.get("/users", response_model=list[User], response_model_exclude_none=True)
def get_users():
    return scenario.users()


@app.post("/start", response_model=Message)
def start():
    scenario.start()
    return Message(message="successfully started.")


@app.get("/peek", response_model=Peek)
def peek():
    peek_time = scenario.peek()
    next_ = peek_time if math.isfinite(peek_time) else -1
    return Peek(next=next_)


@app.post("/step", response_model=Step, response_model_exclude_none=True)
def step():
    now, events = scenario.step()
    return {"now": now, "events": events}


@app.post("/triggered")
def triggered(_: events.Event):
    pass


@app.post("/finish", response_model=Message)
def finish():
    global scenario
    scenario = None
    return Message(message="successfully finished.")
