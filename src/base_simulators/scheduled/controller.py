# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import sys
import io
import traceback
import logging
import datetime
import zipfile

import aiohttp
import fastapi

import jschema.query
import gtfs
from jschema.response import Peek, Step, ReservableStatus
from simulation import Simulation
from core import Trip

logger: logging.Logger
sim: Simulation
trips: typing.Dict[str, Trip]

app = fastapi.FastAPI(debug=True)


@app.on_event("startup")
async def startup():
    global logger
    logger = logging.getLogger('schedsim')
    _handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


@app.exception_handler(Exception)
async def exception_callback(_: fastapi.Request, exc: Exception):
    logger.error(f"Unexpected Error {exc.args} \n {traceback.format_exc()}")


@app.post("/gtfs")
async def upload_gtfs(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file = upload_file.file
        if not zipfile.is_zipfile(file):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="GTFS archive is not zip",
            )

        if file_size := file.tell() > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        file.seek(0)

        with zipfile.ZipFile(io.BytesIO(file.read())) as archive:
            gtfs_files = gtfs.GtfsFilesReader(archive)

        global trips
        trips = gtfs_files.trips

    finally:
        upload_file.file.close()

    return {}


@app.post("/setup")
async def setup(settings: jschema.query.Setup):
    global trips
    gtfs_url = settings.gtfs.fetch_url
    if gtfs_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(gtfs_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            gtfs_files = gtfs.GtfsFilesReader(archive)
        trips = gtfs_files.trips

    start_time = datetime.datetime.strptime(settings.reference_time, '%Y%m%d')
    capacity = settings.mobility.capacity
    global sim
    # ToDo: trips may be not defined.
    sim = Simulation(start_time=start_time, capacity=capacity, trips=trips)

    return {
        "message": "successfully configured."
    }


@app.post("/start")
async def start():
    sim.start()
    return {}


@app.get("/peek", response_model=Peek)
async def peek():
    global sim

    peek_time = sim.peek()
    return {
        "next": peek_time if peek_time < float('inf') else -1
    }


@app.post("/step", response_model=Step)
async def step():
    return {
        "now": sim.step(),
        "events": sim.event_queue.events
    }


@app.post("/triggered")
async def triggered(event: typing.Union[jschema.query.Event, jschema.query.ReserveEvent, jschema.query.DepartEvent]):

    # expect nothing to happen. just let time forward.
    if sim.env.now < event.time:
        sim.env.run(until=event.time)

    if event.eventType == jschema.query.EventType.RESERVE:
        sim.reserve_user(
            user_id=event.details.userId,
            org=event.details.org.locationId,
            dst=event.details.dst.locationId,
            dept=event.details.dept
        )
    elif event.eventType == jschema.query.EventType.DEPART:
        sim.dept_user(
            user_id=event.details.userId
        )


@app.get("/reservable", response_model=ReservableStatus)
async def reservable(org: str, dst: str):
    return {
        "reservable": sim.reservable(org, dst)
    }


@app.post("/finish")
async def finish():
    global sim
    global trips

    sim = None
    trips = None

    return {
        "message": "successfully finished."
    }
