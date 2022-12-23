# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import aiohttp

from engine import Runner

logger = logging.getLogger("broker")


class HttpRunner(Runner):
    """ モビリティシミュレータコントローラーの汎用的な実装 """
    def __init__(self, name: str, endpoint: str):
        super().__init__(name=name)
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession(raise_for_status=True)

    async def _get(self, method: str, params: typing.Mapping = None):
        try:
            async with self._session.get(
                self._endpoint + "/" + method,
                params=params if params else {},
            ) as response:
                return await response.json()
        except Exception as ex:
            logger.error("%s -- HttpRunner(name=%s)._get(%s, %s)", str(ex), self.name, method, params)
            raise

    async def _post(self, method: str, data: typing.Mapping = None, params: typing.Mapping = None):
        try:
            async with self._session.post(
                self._endpoint + "/" + method,
                json=data if data else {},
                params=params if params else {},
            ) as response:
                return await response.json()
        except Exception as ex:
            logger.error("%s -- HttpRunner(name=%s)._post(%s, %s, %s)", str(ex), self.name, method, data, params)
            raise

    async def setup(self, setting: typing.Mapping):
        await self._post("setup", data=setting)

    async def start(self):
        await self._post("start")

    async def peek(self):
        response = await self._get("peek")
        return response["next"] if response["next"] >= 0 else float('inf')

    async def step(self):
        response = await self._post("step")
        return response["now"], [event for event in response["events"]]

    async def triggered(self, event: typing.Mapping):
        await self._post("triggered", data=event)

    async def finish(self):
        await self._post("finish")
        await self._session.close()

    async def reservable(self, org: str, dst: str):
        response = await self._get("reservable", {"org": org, "dst": dst})
        return response["reservable"]
