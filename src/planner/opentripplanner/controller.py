# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextlib
import datetime
import io
import json
import logging
import pathlib
import subprocess
import typing
import zipfile
from copy import deepcopy
from urllib.parse import urljoin

import aiohttp
import fastapi

import httputil
from config import env
from core import Location, Path
from jschema import query, response
from route_planner import OpenTripPlanner

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="planner (use OpenTripPlanner)",
    description="provide itinerary plans for various services",
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


file_table = httputil.FileManager(limit=env.FILE_SIZE_LIMIT)  # osm.pbf ファイル対応として大きめのlimit
planner: OpenTripPlanner | None = None
proc: subprocess.Popen | None = None


@app.on_event("shutdown")
async def shutdown_event():
    global planner
    if planner:
        await planner.close()
        planner = None
    if proc:
        proc.kill()


@app.get("/gbfs/{zipname}/{filename}")
def get_gbfs(zipname: str, filename: str):
    fpath = env.OPENTRIPPLANNER_GBFS_DIR / zipname / filename
    logger.debug("download %s", fpath)
    return fastapi.responses.FileResponse(fpath)


@app.post("/upload", response_model=response.Message)
def upload(upload_file: fastapi.UploadFile = fastapi.File(...)):
    try:
        file_table.put(upload_file)
    finally:
        upload_file.file.close()
    return {
        "message": f"successfully uploaded. {upload_file.filename}"
    }


@contextlib.contextmanager
def open_json_file_for_update(path: pathlib.Path):
    if path.exists():
        with path.open("r") as f:
            data = json.load(f)
    else:
        data = {}
    yield data
    with path.open("w") as f:
        json.dump(data, f, indent=2)
    logger.info("%s: %s", path, json.dumps(data, ensure_ascii=False, indent=2))


def update_config_files_for_gbfs(url_base: str):
    default_updater = {
        "type": "bike-rental",
        # "network": "electricScooter",
        # "language": "en",
        "frequencySec": 5,
        "sourceType": "gbfs",
        # "allowKeepingRentedBicycleAtDestination": False,
        "url": "",
    }

    path_json = env.OPENTRIPPLANNER_VOLUME_DIR / "router-config.json"
    with open_json_file_for_update(path_json) as router_config:
        updaters: list[dict[str, typing.Any]] = router_config.setdefault("updaters", [])

        # Clear the original gbfs.json URL setting
        for updater in updaters:
            updater["url"] = ""
        for path_gbfs_json in env.OPENTRIPPLANNER_GBFS_DIR.glob("*/gbfs.json"):
            dir_gbfs = path_gbfs_json.parent
            # Get gbfs.json file path and URL
            gbfsname = dir_gbfs.relative_to(env.OPENTRIPPLANNER_GBFS_DIR)
            url = urljoin(url_base, f"/gbfs/{gbfsname}/gbfs.json")

            # Set URL to gbfs.json for updaters element in router-config.json
            for updater in updaters:
                # If there are any URLs that have not been set, set them there.
                if not updater.get("url"):
                    updater["url"] = url
                    break
            else:
                logger.warning(f"fill in updater element in router-config.json with default values")
                # If there is no URL, add a new one.
                updater = deepcopy(default_updater)
                updater["url"] = url
                updaters.append(updater)

            # Set feed URL in each gbfs.json file
            with open_json_file_for_update(path_gbfs_json) as gbfs:
                for language, item in gbfs["data"].items():
                    for feed in item["feeds"]:
                        name = feed["name"]
                        path_json = dir_gbfs / f"{name}.json"
                        if not path_json.is_file():
                            msg = f"not exist {path_json} pointed by {path_gbfs_json}"
                            raise fastapi.HTTPException(fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR, msg)
                        url = urljoin(url_base, f"/gbfs/{gbfsname}/{name}.json")
                        feed["url"] = url


async def get_walking_speed(setting: query.Setup):
    walking_meters_per_minute = setting.walking_meters_per_minute
    if walking_meters_per_minute is None:
        walk_speed = 1.33
        try:
            with open(env.OPENTRIPPLANNER_VOLUME_DIR / "router-config.json", "r") as fd:
                config = json.load(fd)
            walk_speed = config.get("routingDefaults", {}).get("walkSpeed", walk_speed)
        except:  # Default value if the file cannot be read
            logger.warning(f"failed to read {env.OPENTRIPPLANNER_VOLUME_DIR}/router-config.json")
        walking_meters_per_minute = walk_speed * 60  # [m/秒] -> [m/分]
    return walking_meters_per_minute


@app.post("/setup", response_model=response.Message)
async def setup(request: fastapi.Request, setting: query.Setup):
    network_types = set()
    async with aiohttp.ClientSession() as session:
        for ref in setting.otp_config.input_files:
            filename, data = await file_table.pop(session, filename=ref.filename, url=ref.fetch_url)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                archive.extractall(env.OPENTRIPPLANNER_VOLUME_DIR)
        for service, network in setting.networks.items():
            for ref in network.input_files:
                network_types.add(network.type)
                if network.type in ["gtfs", "gtfs_flex"]:
                    filename, data = await file_table.pop(session, filename=ref.filename, url=ref.fetch_url)
                    (env.OPENTRIPPLANNER_VOLUME_DIR / filename).write_bytes(data)
                elif network.type in ["gbfs"]:
                    filename, data = await file_table.pop(session, filename=ref.filename, url=ref.fetch_url)
                    # Place the unzipped file in the Static folder for GBFS
                    # Separate the files from other GBFS files by using a zip file name.
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        archive.extractall(env.OPENTRIPPLANNER_GBFS_DIR / filename)
                else:
                    msg = f"not supported network type: {network.type}"
                    raise fastapi.HTTPException(fastapi.status.HTTP_501_NOT_IMPLEMENTED, msg)
    if not (network_types & {"gtfs", "gtfs_flex"}):
        msg = "OTP requires at least one GTFS (or GTFS FLEX) file"
        raise fastapi.HTTPException(fastapi.status.HTTP_501_NOT_IMPLEMENTED, msg)
    if "gbfs" in network_types:
        url_base = f"http://localhost:{request.url.port}"
        update_config_files_for_gbfs(url_base)

    walking_meters_per_minute = await get_walking_speed(setting)
    logger.info("walking_meters_per_minute: %s", walking_meters_per_minute)

    global planner
    planner = OpenTripPlanner(
        endpoint=f"http://localhost:{env.OPENTRIPPLANNER_PORT}",
        ref_datetime=datetime.datetime.strptime(setting.reference_time, "%Y%m%d").replace(
            # ToDo: Consider the proper handling of time zone
            tzinfo=datetime.timezone(datetime.timedelta(hours=setting.timezone))
        ),
        walking_meters_per_minute=walking_meters_per_minute,
        modes=setting.modes,
        services={
            details.agency_id or service: service
            for service, details in setting.networks.items()
        },
    )

    global proc
    command = [
        "java", "-Xmx5G", "-jar", "/root/otp/otp-2.2.0-shaded.jar", "--build",
        "--port", str(env.OPENTRIPPLANNER_PORT), "--serve", env.OPENTRIPPLANNER_VOLUME_DIR,
    ]
    proc = subprocess.Popen(command)
    try:
        await asyncio.wait_for(planner_up(interval=5), timeout=env.OPENTRIPPLANNER_STARTUP_TIMEOUT)
    except asyncio.TimeoutError:
        msg = "Failed to configure; unable to start OTP process."
        raise fastapi.HTTPException(fastapi.status.HTTP_408_REQUEST_TIMEOUT, msg)
    return {
        "message": "successfully configured."
    }


async def planner_up(interval: float):
    while not await planner.health():
        await asyncio.sleep(interval)
        rc = proc.poll()
        if rc is not None:
            msg = f"failed to start OpenTripPlanner: returncode={rc}"
            raise fastapi.HTTPException(fastapi.status.HTTP_408_REQUEST_TIMEOUT, msg)
    logger.info("Open Trip Planner status changed to UP.")


@app.post("/matrix", response_model=response.DistanceMatrix)
async def meters_for_all_stops_combinations(stops: list[str]):
    return await planner.meters_for_all_stops_combinations(stops, planner.ref_datetime)


@app.post("/plan", response_model=list[Path])
async def plan(org: query.LocationSetting, dst: query.LocationSetting, dept: float):
    org = Location(id_=org.locationId, lat=org.lat, lng=org.lng)
    dst = Location(id_=dst.locationId, lat=dst.lat, lng=dst.lng)
    return await planner.plan(org, dst, dept)
