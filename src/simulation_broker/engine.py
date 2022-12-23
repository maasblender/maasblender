# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import json
import asyncio
from functools import reduce

logger = logging.getLogger("broker")


class Runner:
    """ イベントコントローラーの基底クラス """
    def __init__(self, name: str):
        self.name = name

    async def setup(self, setting):
        pass

    async def start(self):
        pass

    async def peek(self) -> typing.Union[int, float]:
        raise NotImplementedError()

    async def step(self) -> typing.Tuple[typing.Union[int, float], typing.List[typing.Dict]]:
        raise NotImplementedError()

    async def triggered(self, event: typing.Mapping):
        raise NotImplementedError()

    async def finish(self):
        pass

    async def reservable(self, org: str, dst: str) -> bool:
        pass


class RunnerEngine:
    """ エベント駆動エンジン """

    def __init__(self, event_logger: logging.Logger):
        self._logger = event_logger
        self._runners: typing.Dict[str, Runner] = {}
        self.error = False

    @property
    def runners(self):
        yield from self._runners.values()

    def setup_runners(self, runners: typing.Mapping[str, Runner]):
        for name, runner in runners.items():
            self._runners[name] = runner

    async def start(self):
        self.error = False
        for runner in self.runners:
            await runner.start()

    async def peek(self):
        if len([*self.runners]) == 0:
            logger.error("No runners.")
            return float('inf')
        return min(await asyncio.gather(*[runner.peek() for runner in self.runners]))

    async def step(self, until: typing.Union[int, float] = None) -> typing.Union[int, float]:
        peeks = await asyncio.gather(*[runner.peek() for runner in self.runners])

        # If the next event is after the value of until, returns the scheduled time of it
        if until and min(peeks) > until:
            return min(peeks)

        # step the simulator with the lowest peek() value
        runner = reduce(
            lambda a, b: a if a[1] <= b[1] else b,
            ((runner, peek) for runner, peek in zip(self.runners, peeks))
        )[0]
        now, events = await runner.step()

        for event in events:
            event = event | {
                "time": now,
                "source": runner.name
            }
            self._logger.info(json.dumps(event))

            # sync triggered events with the other runners
            if service := event.get("service"):
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
            logger.error(f"service: {service} was not found.")
            raise RuntimeError(f"service: {service} was not found.")

