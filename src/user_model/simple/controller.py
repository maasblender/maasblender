# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging

import sys
import traceback

from fastapi import FastAPI, Request

import jschema.query
import jschema.response
from core import Location
from event import ReservedEvent, DepartedEvent, ArrivedEvent
from user_manager import UserManager

logger: logging.Logger
manager: typing.Optional[UserManager] = None

app = FastAPI(debug=True)


@app.on_event("startup")
async def startup():
    global logger
    logger = logging.getLogger('user')
    _handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(_handler)

    _handler = logging.FileHandler("log.txt")
    logger.addHandler(_handler)


@app.exception_handler(Exception)
async def exception_callback(_: Request, exc: Exception):
    logger.error(f"Unexpected Error {exc.args} \n {traceback.format_exc()}")


@app.post("/setup", response_model=jschema.response.Message)
async def setup(settings: jschema.query.Setup):
    global manager

    manager = UserManager()
    manager.setup_planer(endpoint=settings.planner.endpoint)

    return {
        "message": "successfully configured."
    }


@app.post("/start", response_model=jschema.response.Message)
async def start():
    global manager

    manager.start()
    return {
        "message": "successfully started."
    }


@app.get("/peek", response_model=jschema.response.Peek)
async def peek():
    global manager

    peek_time = manager.peek()

    return {
        "next": peek_time if peek_time < float('inf') else -1
    }


@app.post("/step", response_model=jschema.response.Step)
async def step():
    now = manager.step()
    events = [event.dumps() for event in manager.triggered_events]
    return {
        "now": now,
        "events": events
    }


@app.post("/triggered")
async def triggered(event: typing.Union[
    jschema.query.Event,
    jschema.query.DemandEvent,
    jschema.query.ReservedEvent,
    jschema.query.DepartedEvent,
    jschema.query.ArrivedEvent
]):
    # expect nothing to happen. just let time forward.
    if manager.env.now < event.time:
        manager.env.run(until=event.time)

    if event.eventType == jschema.query.EventType.DEMAND:
        await manager.demand(
            user_id=event.details.userId,
            org=Location(
                id_=event.details.org.locationId,
                lat=event.details.org.lat,
                lng=event.details.org.lng
            ),
            dst=Location(
                id_=event.details.dst.locationId,
                lat=event.details.dst.lat,
                lng=event.details.dst.lng
            ),
            fixed_service=event.details.service
        )
    elif event.eventType == jschema.query.EventType.RESERVED:
        manager.trigger(ReservedEvent(
            source=event.source,
            success=event.details.success,
            user_id=event.details.userId
        ))
    elif event.eventType == jschema.query.EventType.DEPARTED:
        manager.trigger(DepartedEvent(
            source=event.source,
            user_id=event.details.userId,
            location=Location(
                id_=event.details.location.locationId,
                lat=event.details.location.lat,
                lng=event.details.location.lng
            )
        ))
    elif event.eventType == jschema.query.EventType.ARRIVED:
        manager.trigger(ArrivedEvent(
            source=event.source,
            user_id=event.details.userId,
            location=Location(
                id_=event.details.location.locationId,
                lat=event.details.location.lat,
                lng=event.details.location.lng
            )
        ))


@app.post("/finish", response_model=jschema.response.Message)
async def finish():
    global manager

    if manager:
        await manager.close()
        manager = None
    return {
        "message": "successfully finished."
    }
