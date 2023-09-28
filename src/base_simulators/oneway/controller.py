# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import io
import logging
import zipfile

import aiohttp
import fastapi

import httputil
from config import env
from gbfs import GbfsFiles
from jschema import query, response
from mobility import ScooterParameter
from operation.reduce_fluctuations import OperatorParameter
from simulation import Simulation

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="mobility simulator for oneway mobility",
    description="simulate shared cycles, etc. using GBFS",
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


file_table = httputil.FileManager(limit=env.FILE_SIZE_LIMIT)
sim: Simulation | None = None


@app.post("/upload", response_model=response.Message)
def upload(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file_table.put(upload_file)
    finally:
        upload_file.file.close()
    return {
        "message": f"successfully uploaded. {upload_file.filename}"
    }


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    async with aiohttp.ClientSession() as session:
        ref = settings.input_files[0]
        filename, data = await file_table.pop(session, filename=ref.filename, url=ref.fetch_url)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            gbfs_files = GbfsFiles(archive)

    global sim
    sim = Simulation()
    sim.setup(
        station_information=gbfs_files.station_information["data"]["stations"],
        free_bike_status=gbfs_files.free_bike_status["data"]["bikes"],
        scooter_params=ScooterParameter(settings.mobility_speed, settings.charging_speed, settings.discharging_speed),
        operator_params=OperatorParameter(
            settings.operator_start_time, settings.operator_end_time, settings.operator_interval,
            settings.operator_speed, settings.operator_loading_time, settings.operator_capacity,
        ),
    )
    return {
        "message": "successfully configured."
    }


@app.post("/start", response_model=response.Message)
def start():
    sim.start()
    return {
        "message": "successfully started."
    }


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = sim.peek()
    return {
        "next": peek_time if peek_time < float('inf') else -1
    }


@app.post("/step", response_model=response.Step)
def step():
    now, events = sim.step()
    return {
        "now": now,
        "events": events
    }


@app.post("/triggered")
def triggered(event: query.TriggeredEvent):
    # just let time forward to expect nothing to happen.
    if sim.env.now < event.time:
        sim.env.run(until=event.time)

    match event:
        case query.ReserveEvent():
            sim.reserve(
                user_id=event.details.userId,
                org=event.details.org.locationId,
                dst=event.details.dst.locationId,
                dept=event.details.dept,
            )
        case query.DepartEvent():
            sim.depart(
                user_id=event.details.userId,
            )


@app.get("/reservable", response_model=response.ReservableStatus)
def reservable(org: str, dst: str):
    return {
        "reservable": sim.reservable(org, dst)
    }


@app.post("/finish", response_model=response.Message)
def finish():
    global sim
    sim = None
    file_table.clear()
    return {
        "message": "successfully finished."
    }
