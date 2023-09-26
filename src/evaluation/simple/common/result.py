# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import dataclasses
import itertools
import json
import logging
import pathlib
import typing

import aiohttp

from common import httputil
from config import env

logger = logging.getLogger(__name__)


class ResultWriter:
    async def close(self):
        raise NotImplementedError()

    async def write_json(self, data: dict):
        raise NotImplementedError()


class FileResultWriter(ResultWriter):
    filepath: pathlib.Path
    _fp: typing.TextIO

    def __init__(self, filepath: pathlib.Path):
        self.filepath = filepath
        self._fp = self.filepath.open("w")

    async def close(self):
        self._fp.close()

    async def write_json(self, data: dict):
        json.dump(data, self._fp, ensure_ascii=False)
        self._fp.write("\n")


@dataclasses.dataclass
class HTTPResultWriter(ResultWriter):
    url: str
    _session: aiohttp.ClientSession = dataclasses.field(default_factory=aiohttp.ClientSession)
    _count: itertools.count = dataclasses.field(default_factory=itertools.count)
    _records: asyncio.Queue[dict] = dataclasses.field(default_factory=asyncio.Queue)
    _task: asyncio.Task | None = None
    _closed: bool = False

    async def close(self):
        self._closed = True
        if self._task:
            if self._records.empty():
                self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._session.close()

    async def write_json(self, record: dict):
        await self._wait_over()
        if self._task is None and not self._closed:
            self._task = asyncio.create_task(self._polling())
        self._records.put_nowait(record)

    async def _wait_over(self):
        while self._records.qsize() > env.RESULT_WRITER_QUEUE_SIZE:
            logger.warning("wait_queue_size: queue_size=%s > %s",
                           self._records.qsize(), env.RESULT_WRITER_QUEUE_SIZE)
            await asyncio.sleep(env.RESULT_WRITER_OVER_INTERVAL)

    async def _polling(self):
        """ Monitor the queue and log output immediately. """
        while not self._closed:
            await self._send_records()
        # until the queue is empty after close()
        if not self._records.empty():
            logger.info("remaining qsize: %s", self._records.qsize())
            await self._send_records(nowait=True)

    async def _send_records(self, nowait=False):
        data = [
            dict(seqno=next(self._count), data=record)
            async for record in self._pop_records(nowait)
        ]
        if data:
            await self._post(data=data)

    async def _pop_records(self, nowait: bool):
        if not nowait and self._records.empty():
            yield await self._records.get()
        for _ in range(self._records.qsize()):
            yield self._records.get_nowait()

    async def _post(self, data: list[typing.Mapping]):
        async with self._session.post(url=self.url, json=data) as response:
            await httputil.check_response(response)
            return await response.json()
