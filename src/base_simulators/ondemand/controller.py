# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import contextlib
import io
import typing
import sys
from io import StringIO
import traceback
import logging
import datetime
import zipfile
import csv
import codecs

import aiohttp
import fastapi

import jschema.query
from jschema.response import Peek, Step, ReservableStatus
from gtfs import GtfsFlexFilesReader
from simulation import Simulation
from core import Stop, Trip, Network

logger: logging.Logger
sim: Simulation
network: Network | None = None
stops: typing.Dict[str, Stop] | None = None
trips: typing.Dict[str, Trip] | None = None

app = fastapi.FastAPI(debug=True)

CAR_SPEED = 20.0 * 1000 / 60  # km/h -> [meter/分]


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


@contextlib.contextmanager
def open_zip_archive(file: typing.BinaryIO, file_type: str, limit=1 * 1024 * 1024) -> zipfile.ZipFile:
    if not zipfile.is_zipfile(file):
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=f"{file_type} archive is not zip",
        )
    if file_size := file.tell() > limit:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=f"{file_type} files are {file_size} bytes, but limited to 1 MB",
        )
    file.seek(0)
    with zipfile.ZipFile(io.BytesIO(file.read())) as archive:
        yield archive


@app.post("/gtfs_flex")
async def upload_gtfs_flex(upload_file: fastapi.UploadFile = fastapi.File(...)):
    file = upload_file.file
    try:
        with open_zip_archive(file, "GTFS FLEX") as archive:
            reader = GtfsFlexFilesReader().read(archive)
        global stops, trips
        trips = reader.trips
        stops = reader.stops
    finally:
        file.close()
    return {
        "message": "successfully uploaded gtfs flex files."
    }


@app.post("/network")
async def configure_network(upload_file: fastapi.UploadFile = fastapi.File(...)):
    file = upload_file.file
    try:
        if file_size := file.tell() > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        file.seek(0)

        global network
        network = Network()

        reader = csv.DictReader(codecs.iterdecode(file, 'utf-8'))
        for rows in reader:
            stop_a = reader.fieldnames[reader.line_num - 2]
            for stop_b in reader.fieldnames:
                if stop_a == stop_b:
                    continue
                network.add_edge(stop_a, stop_b, float(rows[stop_b]))

    finally:
        upload_file.file.close()

    return {
        "message": "successfully uploaded network file."
    }


@app.post("/setup")
async def setup(settings: jschema.query.Setup):
    global stops, trips

    if gtfs_url := settings.gtfs_flex.fetch_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(gtfs_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            reader = GtfsFlexFilesReader().read(archive)
        trips = reader.trips
        stops = reader.stops

    if not trips:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="GTFS files were not properly configured."
        )

    global network
    if not network:
        if network_url := settings.network.fetch_url:
            async with aiohttp.ClientSession(raise_for_status=True) as session:
                data = [
                    jschema.query.Location(locationId=e.stop_id, lat=e.lat, lng=e.lng).dict()
                    for e in sorted(stops.values(), key=lambda e: e.stop_id)
                ]
                async with session.post(network_url, json=data) as resp:
                    text = await resp.text("utf-8-sig")
            logger.info("fetch %s, result:\n%s", network_url, text)
            network = Network()
            reader = csv.DictReader(StringIO(text))
            for rows in reader:
                stop_a = reader.fieldnames[reader.line_num - 2]
                for stop_b in reader.fieldnames:
                    if stop_a == stop_b:
                        continue
                    distance = float(rows[stop_b])
                    assert distance >= 0, f"distance must not negative: {rows[stop_b]}, {stop_a} -> {stop_b}"
                    network.add_edge(stop_a, stop_b, distance / CAR_SPEED)
        else:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Stop-Stop Network was not properly configured."
            )

    global sim
    sim = Simulation(
        start_time=datetime.datetime.strptime(settings.reference_time, '%Y%m%d'),
        network=network,
        trips=trips,
        board_time=settings.board_time,
        max_delay_time=settings.max_delay_time,
        settings={mobility.mobility_id: mobility for mobility in settings.mobilities},
    )

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
        sim.ready_to_depart(
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
