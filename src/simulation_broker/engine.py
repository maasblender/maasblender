# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import typing

from pydantic import BaseModel, Extra

from common.result import ResultWriter

logger = logging.getLogger(__name__)


class Event(BaseModel, extra=Extra.allow):
    eventType: str
    source: str | None = None
    time: float
    service: str | None = None
    details: typing.Any


class Runner:
    def __init__(self, name: str):
        self.name = name

    async def setup(self, setting: typing.Mapping) -> None:
        pass

    async def start(self) -> None:
        pass

    async def peek(self) -> int | float:
        raise NotImplementedError()

    async def step(self) -> tuple[int | float, list[Event]]:
        raise NotImplementedError()

    async def triggered(self, event: Event) -> None:
        raise NotImplementedError()

    async def finish(self) -> None:
        pass

    async def reservable(self, org: str, dst: str) -> bool:
        pass


class RunnerEngine:
    def __init__(self, writer: ResultWriter):
        self._writer = writer
        self._runners: dict[str, Runner] = {}

    @property
    def runners(self):
        yield from self._runners.values()

    def setup_runners(self, runners: typing.Mapping[str, Runner]):
        for name, runner in runners.items():
            self._runners[name] = runner

    async def start(self):
        for runner in self.runners:
            await runner.start()

    async def peek(self):
        return min(await asyncio.gather(*[runner.peek() for runner in self.runners]))

    async def step(self, until: int | float = None) -> int | float:
        peeks = await asyncio.gather(*[runner.peek() for runner in self.runners])

        # step the simulator with the lowest peek() value
        runner, min_peek = min(zip(self.runners, peeks), key=lambda e: e[1])
        # If the next event is after the value of until, returns the scheduled time of it
        if until and min_peek > until:
            return min_peek

        now, events = await runner.step()

        for event in events:
            event.source = runner.name
            await self._writer.write_json(event.dict(exclude_none=True))

            # sync triggered events with the other runners
            if service := event.service:
                await self._runners[service].triggered(event)
            else:
                for each in self.runners:
                    await each.triggered(event)
        return now

    async def finish(self):
        for runner in self.runners:
            await runner.finish()

    async def reservable(self, service: str, org: str, dst: str):
        if runner := self._runners.get(service, None):
            return await runner.reservable(org, dst)
        else:
            msg = f"service: {service} was not found. (services: {list(self._runners.keys())})"
            raise KeyError(msg)
