# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import datetime
import json
import io
import logging
import zipfile

import aiohttp
import fastapi

from core import Network
from gtfs import GtfsFlexFilesReader
from jschema import query, response
from mblib.io import httputil
from mblib.io.log import init_logger
from mblib.jschema import spec, events
from simulation import Simulation, CarSetting

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="mobility simulator for on-demand mobility",
    description="simulate on-demand bus, etc. using GTFS FLEX",
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


file_table = httputil.FileManager()
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


@app.post("/upload", response_model=response.Message)
def upload(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file_table.put(upload_file)
    finally:
        upload_file.file.close()
    return {"message": f"successfully uploaded. {upload_file.filename}"}


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    async with aiohttp.ClientSession() as session:
        ref = settings.input_files[0]
        filename, data = await file_table.pop(
            session, filename=ref.filename, url=ref.fetch_url
        )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            reader = GtfsFlexFilesReader().read(archive)
        trips = reader.trips
        stops = reader.stops

        if network_url := settings.network.fetch_url:
            stops_req = [
                events.Location(locationId=e.stop_id, lat=e.lat, lng=e.lng).model_dump()
                for e in sorted(stops.values(), key=lambda e: e.stop_id)
            ]
            async with session.post(
                str(network_url),
                json=stops_req,
                timeout=aiohttp.ClientTimeout(total=3600),
            ) as resp:
                await httputil.check_response(resp)
                matrix = await resp.json()
            network = Network()
            for stop_a, row in zip(matrix["stops"], matrix["matrix"]):
                for stop_b, distance in zip(matrix["stops"], row):
                    if stop_a == stop_b:
                        continue
                    assert distance >= 0, (
                        f"distance must not negative: {distance}, {stop_a} -> {stop_b}"
                    )
                    network.add_edge(stop_a, stop_b, distance / settings.mobility_speed)
        elif settings.network.filename:
            ref = settings.input_files[1]
            _, data = await file_table.pop(
                session, filename=ref.filename, url=ref.fetch_url
            )
            matrix = json.loads(data)
            network = Network()
            for stop_a, row in zip(matrix["stops"], matrix["matrix"]):
                for stop_b, distance in zip(matrix["stops"], row):
                    if stop_a == stop_b:
                        continue
                    assert distance >= 0, (
                        f"distance must not negative: {distance}, {stop_a} -> {stop_b}"
                    )
                    network.add_edge(stop_a, stop_b, distance / settings.mobility_speed)
        else:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Stop-Stop Network was not properly configured.",
            )

    global sim
    sim = Simulation(
        start_time=datetime.datetime.strptime(settings.reference_time, "%Y%m%d"),
        network=network,
        trips=trips,
        enable_ortools=settings.enable_ortools,
        board_time=settings.board_time,
        max_delay_time=settings.max_delay_time,
        max_calculation_seconds=settings.max_calculation_seconds,
        max_calculation_stop_times_length=settings.max_calculation_stop_times_length,
        settings=[
            CarSetting(
                mobility_id=mobility.mobility_id,
                capacity=mobility.capacity,
                trip=trips[mobility.trip_id],
                stop=stops[mobility.stop],
            )
            for mobility in settings.mobilities
        ],
    )

    return {"message": "successfully configured."}


@app.post("/start", response_model=response.Message)
def start():
    sim.start()
    return {"message": "successfully started."}


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = sim.peek()
    return {"next": peek_time if peek_time < float("inf") else -1}


@app.post("/step", response_model=response.Step)
def step():
    return {"now": sim.step(), "events": sim.event_queue.events}


@app.post("/triggered")
def triggered(event: query.TriggeredEvent | events.Event):
    # expect nothing to happen. just let time forward.
    if sim.env.now < event.time:
        sim.env.run(until=event.time)

    match event:
        case events.ReserveEvent():
            sim.reserve_user(
                user_id=event.details.userId,
                demand_id=event.details.demandId,
                org=event.details.org.locationId,
                dst=event.details.dst.locationId,
                dept=event.details.dept,
            )
        case events.DepartEvent():
            sim.ready_to_depart(user_id=event.details.userId)


@app.get("/reservable", response_model=response.ReservableStatus)
def reservable(org: str, dst: str):
    return {"reservable": sim.reservable(org, dst)}


@app.post("/finish", response_model=response.Message)
def finish():
    global sim
    sim = None
    file_table.clear()
    return {"message": "successfully finished."}
