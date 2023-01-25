# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import sys
import traceback
import zipfile
import io

import aiohttp
import fastapi

from jschema.query import EventType, Event, ReserveEvent, DepartEvent, Setup
from jschema.response import Peek, Step, ReservableStatus
from gbfs import GbfsFiles
from simulation import Simulation

logger: logging.Logger
sim: Simulation
gbfs_files: GbfsFiles

app = fastapi.FastAPI(debug=True)


@app.on_event("startup")
async def startup():
    global logger
    logger = logging.getLogger('owmsim')

    _handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


@app.exception_handler(Exception)
async def exception_callback(_: fastapi.Request, exc: Exception):
    global logger

    logger.error(f"Unexpected Error {exc.args} \n {traceback.format_exc()}")


@app.post("/gbfs")
async def upload_gbfs(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file = upload_file.file
        if not zipfile.is_zipfile(file):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="GBFS files are limited to 1 MB",
            )

        if file_size := file.tell() > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GBFS files are {file_size} bytes, but limited to 1 MB",
            )
        file.seek(0)

        with zipfile.ZipFile(io.BytesIO(file.read())) as archive:
            global gbfs_files
            gbfs_files = GbfsFiles(archive)

    finally:
        upload_file.file.close()

    return {}


@app.post("/setup")
async def setup(settings: Setup):
    global gbfs_files
    gbfs_url = settings.gbfs.fetch_url
    if gbfs_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(gbfs_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GBFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            gbfs_files = GbfsFiles(archive)

    global sim
    sim = Simulation()
    sim.setup(
        station_information=gbfs_files.station_information["data"]["stations"],
        free_bike_status=gbfs_files.free_bike_status["data"]["bikes"]
    )

    return {}


@app.post("/start")
async def start():
    global sim

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
    global sim

    now, events = sim.step()
    return {
        "now": now,
        "events": events
    }


@app.post("/triggered")
async def triggered(event: typing.Union[Event, ReserveEvent, DepartEvent]):
    global sim

    # just let time forward to expect nothing to happen.
    if sim.env.now < event.time:
        sim.env.run(until=event.time)

    if event.eventType == EventType.RESERVE:
        sim.reserve(
            user_id=event.details.userId,
            org=event.details.org.locationId,
            dst=event.details.dst.locationId,
            dept=event.details.dept,
        )
    elif event.eventType == EventType.DEPART:
        sim.depart(
            user_id=event.details.userId,
        )


@app.get("/reservable", response_model=ReservableStatus)
async def reservable(org: str, dst: str):
    return {
        "reservable": sim.reservable(org, dst)
    }


@app.post("/finish")
async def finish():
    global sim
    global gbfs_files

    sim = None
    gbfs_files = None

    return {
        "message": "successfully finished."
    }
