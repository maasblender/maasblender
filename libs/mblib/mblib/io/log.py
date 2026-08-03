# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import typing

import aiohttp
from pydantic_settings import BaseSettings

from . import httputil

logger = logging.getLogger(__name__)


class AsyncHttpSeqnoHandler(logging.Handler):
    _instances: typing.ClassVar[list[AsyncHttpSeqnoHandler]] = []
    _url: str
    _session: aiohttp.ClientSession
    _count: itertools.count
    _records: asyncio.Queue[logging.LogRecord]
    _task: asyncio.Task | None
    _closed: bool

    @classmethod
    async def shutdown(cls):
        for instance in cls._instances:
            await instance.close_async()
        cls._instances.clear()

    @classmethod
    def get_queue_size(cls) -> int:
        return sum(instance._records.qsize() for instance in cls._instances)

    @classmethod
    async def wait_queue_size(cls, qsize: int, interval: int):
        while cls.get_queue_size() > qsize:
            logger.warning(
                "wait_queue_size: queue_size=%s > %s", cls.get_queue_size(), qsize
            )
            await asyncio.sleep(interval)

    def __init__(self, url: str):
        super().__init__()
        self._url = url
        self._session = aiohttp.ClientSession()
        self._count = itertools.count()
        self._records = asyncio.Queue()
        self._task = None
        self._closed = False
        AsyncHttpSeqnoHandler._instances.append(self)

    def emit(self, record):
        if self._task is None and not self._closed:
            self._task = asyncio.create_task(self._polling())
        self._records.put_nowait(record)

    def close(self):
        self._closed = True
        super().close()

    async def close_async(self):
        if self._task:
            if self._records.empty():
                self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._session.close()

    async def _pop_records(self, nowait: bool):
        if not nowait and self._records.empty():
            yield await self._records.get()
        for _ in range(self._records.qsize()):
            yield self._records.get_nowait()

    async def _post(self, data: list[typing.Mapping]):
        async with self._session.post(url=self._url, json=data) as response:
            await httputil.check_response(response)
            return await response.json()

    async def _send_records(self, nowait=False):
        data = [
            {"seqno": next(self._count), "data": json.loads(record.getMessage())}
            async for record in self._pop_records(nowait)
        ]
        if data:
            await self._post(data=data)

    async def _polling(self):
        while not self._closed:
            await self._send_records()
        # after close(), process records until the queue becomes empty
        if not self._records.empty():
            logger.info("remaining qsize: %s", self._records.qsize())
            await self._send_records(nowait=True)


class LogConfig(BaseSettings, frozen=True):
    """environment variable for logger"""

    DEBUG: bool = False  # debug log flag
    LOG_FORMAT_DEBUG: str = "[%(levelname).3s] %(name)s - %(message)s"
    LOG_FORMAT: str = "[%(levelname).3s] %(message)s"

    @property
    def log_level(self) -> int:
        import logging

        return logging.DEBUG if self.DEBUG else logging.INFO

    @property
    def log_format(self) -> str:
        return self.LOG_FORMAT_DEBUG if self.DEBUG else self.LOG_FORMAT


class MultilineLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return message.replace(
            "\n", "\t\n"
        )  # indicate continuation line by trailing tab


def init_logger() -> None:
    env = LogConfig()
    formatter = MultilineLogFormatter(env.log_format)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=env.log_level, handlers=[handler])

    # replace logging formatter for uvicorn
    for handler in logging.getLogger("uvicorn").handlers:
        handler.setFormatter(formatter)
