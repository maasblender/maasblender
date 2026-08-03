# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import typing

import aiohttp
from engine import Event, Runner
from mblib.io import httputil
from mblib.jschema.spec import SpecificationResponse

logger = logging.getLogger(__name__)


class HttpRunner(Runner):
    def __init__(self, name: str, endpoint: str):
        super().__init__(name=name)
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession()

    def __str__(self):
        return f"HttpRunner({self.name}, {self._endpoint})"

    async def _get(self, method: str, params: typing.Mapping | None = None):
        async with self._session.get(
            self._endpoint + method,
            params=params if params else {},
        ) as response:
            await httputil.check_response(response)
            return await response.json()

    async def _post(
        self,
        method: str,
        data: typing.Any = None,
        params: typing.Mapping | None = None,
        timeout_seconds=300,
    ):
        async with self._session.post(
            self._endpoint + method,
            json=data,
            params=params if params else {},
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as response:
            await httputil.check_response(response)
            return await response.json()

    async def spec(self) -> SpecificationResponse:
        response = await self._get("spec")
        result = SpecificationResponse.model_validate(response)
        return result

    async def setup(self, setting: typing.Mapping):
        await self._post("setup", data=setting, timeout_seconds=3600)

    async def start(self):
        await self._post("start")

    async def peek(self):
        response = await self._get("peek")
        return response["next"] if response["next"] >= 0 else float("inf")

    async def step(self):
        response = await self._post("step")
        return response["now"], [Event.parse_obj(event) for event in response["events"]]

    async def triggered(self, event: Event):
        await self._post("triggered", data=event.model_dump())

    async def finish(self):
        await self._post("finish")
        await self._session.close()

    async def reservable(self, org: str, dst: str):
        response = await self._get("reservable", {"org": org, "dst": dst})
        return response["reservable"]
