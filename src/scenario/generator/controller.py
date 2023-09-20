# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import math

import fastapi

from config import env
from generator import DemandGenerator
from jschema import query, response

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="scenario (for probability)",
    description="make probabilistically DEMAND events",
    # version="0.1.0",
    # docs_url="/docs"
    # redoc_url="/redoc",
)


@app.on_event("startup")
def startup():
    class MultilineLogFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            message = super().format(record)
            return message.replace("\n", "\t\n")  # indicate continuation line by trailing tab

    formatter = MultilineLogFormatter(env.log_format)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=env.log_level, handlers=[handler])

    # replace logging formatter for uvicorn
    for handler in logging.getLogger("uvicorn").handlers:
        handler.setFormatter(formatter)

    logger.debug("configuration: %s", env.json())


@app.exception_handler(Exception)
def exception_callback(request: fastapi.Request, exc: Exception):
    from fastapi.responses import PlainTextResponse
    # omitted traceback here, because uvicorn outputs traceback as ASGI Exception
    logger.error("failed process called at %s", request.url)
    return PlainTextResponse(str(exc), status_code=500)


scenario: DemandGenerator | None = None


@app.post("/setup", response_model=response.Message)
def setup(settings: query.Setup):
    global scenario
    scenario = DemandGenerator()
    scenario.setup(settings)
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
    if events:
        logger.info(f"now {now}  events {events}")
    return {"now": now, "events": events}


@app.post("/triggered")
def triggered(_: query.TriggeredEvent):
    pass


@app.post("/finish", response_model=response.Message)
def finish():
    global scenario
    scenario = None
    return response.Message(message="successfully finished.")
