# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import aiohttp

from jschema.query import LocationSetting


logger = logging.getLogger("planner")


class Location(typing.NamedTuple):
    id_: str
    lat: float
    lng: float


class Trip(typing.NamedTuple):
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


Path = typing.List[Trip]


class Planner:
    def __init__(self, name: str, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession(raise_for_status=True)

    async def _get(self, method: str, params: typing.Mapping = None):
        async with self._session.get(
                self._endpoint + "/" + method,
                params=params if params else {},
        ) as response:
            return await response.json()

    async def _post(self, method: str, data: typing.Mapping = None, params: typing.Mapping = None):
        async with self._session.post(
                self._endpoint + "/" + method,
                json=data if data else {},
                params=params if params else {},
        ) as response:
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
