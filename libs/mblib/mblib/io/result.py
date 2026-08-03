# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION
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
from pydantic_settings import BaseSettings

from . import httputil

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


class ResultWriterConfig(BaseSettings, frozen=True):
    """environment variable"""

    RESULT_WRITER_QUEUE_SIZE: int = 500  # queue size limit for result writer buffer
    RESULT_WRITER_OVER_INTERVAL: int = (
        1  # check interval time (seconds) over queue size limit
    )


@dataclasses.dataclass
class HTTPResultWriter:
    url: str
    env: ResultWriterConfig = dataclasses.field(default_factory=ResultWriterConfig)
    _session: aiohttp.ClientSession = dataclasses.field(
        default_factory=aiohttp.ClientSession
    )
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
        while self._records.qsize() > self.env.RESULT_WRITER_QUEUE_SIZE:
            logger.warning(
                "wait_queue_size: queue_size=%s > %s",
                self._records.qsize(),
                self.env.RESULT_WRITER_QUEUE_SIZE,
            )
            await asyncio.sleep(self.env.RESULT_WRITER_OVER_INTERVAL)

    async def _polling(self):
        while not self._closed:
            await self._send_records()
        # after close(), process records until the queue becomes empty
        if not self._records.empty():
            logger.info("remaining qsize: %s", self._records.qsize())
            await self._send_records(nowait=True)

    async def _send_records(self, nowait=False):
        data = [
            {"seqno": next(self._count), "data": record}
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
