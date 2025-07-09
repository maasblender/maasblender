# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import math
import pathlib

import fastapi

from core import Location
from jschema import query, response
from mblib.io.log import init_logger
from mblib.io.result import ResultWriter, HTTPResultWriter, FileResultWriter
from mblib.jschema import events, spec
from usability import UsabilityEvaluator

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="evaluation",
    description="generate evaluation logs by DEMAND event",
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


@app.on_event("shutdown")
async def shutdown_event():
    await finish()


manager: UsabilityEvaluator | None = None
writer: ResultWriter | None = None


@app.get(
    "/spec", response_model=spec.SpecificationResponse, response_model_exclude_none=True
)
def get_specification():
    builder = spec.EventSpecificationBuilder(triggered=query.TriggeredEvent)
    builder.set_feature(events.EventType.DEMAND)
    return builder.get_specification_response(version=events.VERSION_1)


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    global manager, writer
    if settings.writer.endpoint:
        writer = HTTPResultWriter(f"{settings.writer.endpoint}/result/evaluation/")
    else:
        writer = FileResultWriter(pathlib.Path("evaluation.txt"))
    manager = UsabilityEvaluator(
        writer,
        planner=str(settings.planner.endpoint),
        reservable=str(settings.reservable.endpoint),
        timing=settings.evaluation_timing,
    )
    return response.Message(message="successfully configured.")


@app.post("/start", response_model=response.Message)
def start():
    return response.Message(message="successfully started.")


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = manager.env.peek()
    next_ = peek_time if math.isfinite(peek_time) else -1
    return response.Peek(next=next_)


@app.post("/step", response_model=response.Step)
async def step():
    now = await manager.step()
    return response.Step(now=now, events=[])


@app.post("/triggered")
def triggered(event: query.TriggeredEvent | events.Event):
    match event:
        case query.DemandEvent():
            manager.demand(
                event_time=event.time,
                dept=event.details.dept if event.details.dept else event.time,
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
                service=event.details.service,
                demand_id=event.details.demandId,
            )


@app.post("/finish", response_model=response.Message)
async def finish():
    global manager, writer
    if manager:
        await manager.close()
        manager = None
    if writer:
        await writer.close()
    return response.Message(message="successfully finished.")


@app.get("/evaluation")
def evaluation():
    if isinstance(writer, FileResultWriter):
        return fastapi.responses.FileResponse(path=writer.filepath)
    else:
        msg = "must be retrieved from jobmanager"
        raise fastapi.HTTPException(fastapi.status.HTTP_404_NOT_FOUND, msg)
