# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import traceback
import datetime
import io
import zipfile

import aiohttp
import fastapi
from fastapi.responses import StreamingResponse

from jschema.query import LocationSetting
import jschema.response
from core import Location, MobilityNetwork, WalkingNetwork
from route_planner import Planner, DirectPathPlanner
from gtfs.reader import FilesReader as GtfsFiles
from gtfs.network import Network as GtfsNetwork
from gtfs_flex.reader import FilesReader as GtfsFlexFiles
from gtfs_flex.network import Network as GtfsFlexNetwork
from gbfs.reader import FilesReader as GbfsFiles
from gbfs.network import Network as GbfsNetwork


logger: logging.Logger
app = fastapi.FastAPI()
gtfs_files: GtfsFiles
gtfs_flex_files: GtfsFlexFiles
gbfs_files: GbfsFiles
planner: Planner


@app.on_event("startup")
async def startup():
    global logger
    logger = logging.getLogger('planner')
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
            global gtfs_files
            gtfs_files = GtfsFiles(archive)

    finally:
        upload_file.file.close()

    return {}


@app.post("/gtfs_flex")
async def upload_gtfs_flex(upload_file: fastapi.UploadFile = fastapi.File(...)):
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
            global gtfs_flex_files
            gtfs_flex_files = GtfsFlexFiles(archive)

    finally:
        upload_file.file.close()

    return {}


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


@app.post("/setup", response_model=jschema.response.Message)
async def setup(settings: jschema.query.Setup):
    if settings.gtfs and settings.gtfs.fetch_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(settings.gtfs.fetch_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            global gtfs_files
            gtfs_files = GtfsFiles(archive)
    if settings.gtfs_flex and settings.gtfs_flex.fetch_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(settings.gtfs_flex.fetch_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GTFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            global gtfs_flex_files
            gtfs_flex_files = GtfsFlexFiles(archive)
    if settings.gbfs and settings.gbfs.fetch_url:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(settings.gbfs.fetch_url) as resp:
                data = await resp.read()
        if file_size := len(data) > 1 * 1024 * 1024:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"GBFS files are {file_size} bytes, but limited to 1 MB",
            )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            global gbfs_files
            gbfs_files = GbfsFiles(archive)

    networks: typing.List[MobilityNetwork] = [
        WalkingNetwork("walking", walking_meters_per_minute=settings.walking_meters_per_minute)
    ]
    for name, setting in settings.networks.items():
        if setting.type == "gbfs":
            network = GbfsNetwork(
                service=name,
                walking_meters_per_minute=settings.walking_meters_per_minute,
                mobility_meters_per_minute=setting.mobility_meters_per_minute
            )
            network.setup(gbfs_files.stations.values())
        elif setting.type == "gtfs":
            network = GtfsNetwork(
                service=name,
                start_time=datetime.datetime.strptime(setting.reference_time, '%Y%m%d'),
                walking_meters_per_minute=settings.walking_meters_per_minute,
                max_waiting_bus_time=setting.max_waiting_time
            )
            network.setup(gtfs_files.trips.values())
        elif setting.type == "gtfs_flex":
            network = GtfsFlexNetwork(
                service=name,
                start_time=datetime.datetime.strptime(setting.reference_time, '%Y%m%d'),
                walking_meters_per_minute=settings.walking_meters_per_minute,
                mobility_meters_per_minute=setting.mobility_meters_per_minute,
                expected_waiting_time=setting.expected_waiting_time,
            )
            network.setup(gtfs_flex_files.trips.values())
        else:
            raise NotImplementedError(f"{setting.type} is not implemented.")

        networks.append(network)

    global planner
    planner = DirectPathPlanner(networks)

    return {
        "message": "successfully configured."
    }


@app.post("/matrix")
async def meters_for_all_stops_combinations(stops: list[LocationSetting]):
    return StreamingResponse(planner.meters_for_all_stops_combinations([
        Location(e.locationId, e.lat, e.lng) for e in stops
    ]))


@app.post("/plan")
async def plan(org: LocationSetting, dst: LocationSetting, dept: float):
    return planner.plan(
        org=Location(id_=org.locationId, lat=org.lat, lng=org.lng),
        dst=Location(id_=dst.locationId, lat=dst.lat, lng=dst.lng),
        dept=dept
    )
