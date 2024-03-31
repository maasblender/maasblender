# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import datetime
import io
import logging
import zipfile

import aiohttp
import fastapi

import gtfs
import httputil
from config import env
from jschema import query, response
from simulation import Simulation

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="mobility simulator for scheduled mobility",
    description="simulate bus and train routes using GTFS",
    # version="0.1.0",
    # docs_url="/docs"
    # redoc_url="/redoc",
)


@app.on_event("startup")
def startup():
    class MultilineLogFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            message = super().format(record)
            return message.replace(
                "\n", "\t\n"
            )  # indicate continuation line by trailing tab

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


@app.post("/upload")
def upload(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file_table.put(upload_file)
    finally:
        upload_file.file.close()
    return {"message": f"successfully uploaded. {upload_file.filename}"}


@app.post("/setup")
async def setup(settings: query.Setup):
    async with aiohttp.ClientSession() as session:
        ref = settings.input_files[0]
        filename, data = await file_table.pop(
            session, filename=ref.filename, url=ref.fetch_url
        )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        gtfs_files = gtfs.GtfsFilesReader(archive)

    trips = gtfs_files.trips
    # ToDo: handle gtfs_files.blocks

    global sim
    sim = Simulation(
        start_time=datetime.datetime.strptime(settings.reference_time, "%Y%m%d"),
        capacity=settings.mobility.capacity,
        trips=trips,
    )

    return {"message": "successfully configured."}


@app.post("/start")
def start():
    sim.start()
    return {}


@app.get("/peek", response_model=response.Peek)
def peek():
    peek_time = sim.peek()
    return {"next": peek_time if peek_time < float("inf") else -1}


@app.post("/step", response_model=response.Step)
def step():
    return {"now": sim.step(), "events": sim.event_queue.events}


@app.post("/triggered")
def triggered(event: query.TriggeredEvent):
    # expect nothing to happen. just let time forward.
    if sim.env.now < event.time:
        sim.env.run(until=event.time)

    match event:
        case query.ReserveEvent():
            sim.reserve_user(
                user_id=event.details.userId,
                org=event.details.org.locationId,
                dst=event.details.dst.locationId,
                dept=event.details.dept,
            )
        case query.DepartEvent():
            sim.dept_user(user_id=event.details.userId)


@app.get("/reservable", response_model=response.ReservableStatus)
def reservable(org: str, dst: str):
    return {"reservable": sim.reservable(org, dst)}


@app.post("/finish", response_model=response.Message)
def finish():
    global sim
    sim = None
    file_table.clear()
    return {"message": "successfully finished."}
