# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import logging
import typing

import aiohttp

from common import httputil
from jschema.query import LocationSetting

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Location:
    id_: str
    lat: float
    lng: float


@dataclasses.dataclass(frozen=True)
class Trip:
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


@dataclasses.dataclass(frozen=True)
class Path:
    trips: typing.List[Trip]
    walking_time_minutes: float


class Planner:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession()

    async def finish(self):
        await self._session.close()

    async def _get(self, method: str, params: typing.Mapping = None):
        async with self._session.get(
                self._endpoint + "/" + method,
                params=params if params else {},
        ) as response:
            await httputil.check_response(response)
            return await response.json()

    async def _post(self, method: str, data: typing.Mapping = None, params: typing.Mapping = None):
        async with self._session.post(
                self._endpoint + "/" + method,
                json=data if data else {},
                params=params if params else {},
        ) as response:
            await httputil.check_response(response)
            return await response.json()

    async def setup(self, setting: typing.Mapping):
        await self._post("setup", data=setting)

    async def plan(self, org: LocationSetting, dst: LocationSetting, dept: float):
        response = await self._post(
            method="plan",
            data={"org": org.dict(), "dst": dst.dict()},
            params={"dept": dept}
        )
        return response
