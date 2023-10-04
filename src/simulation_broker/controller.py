# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import asyncio
import dataclasses
import logging
import math
import pathlib
import typing

import fastapi

from common.result import ResultWriter, FileResultWriter, HTTPResultWriter
from config import env
from engine import RunnerEngine
from jschema import query, response
from route_planner import Planner, Path
from runner import HttpRunner

logger = logging.getLogger(__name__)
app = fastapi.FastAPI(
    title="broker",
    description="integrate and run each simulation module",
    # version="0.1.0",
    # docs_url="/docs"
    # redoc_url="/redoc",
)


@app.on_event("startup")
def startup():
    class MultilineLogFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            message = super().format(record)
            return message.replace("\n", "\t\n")  # indicate continuation line by trailing tab

    formatter = MultilineLogFormatter(env.log_format)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=env.log_level, handlers=[handler])

    # replace logging formatter for uvicorn
    for handler in logging.getLogger("uvicorn").handlers:
        handler.setFormatter(formatter)

    logger.debug("configuration: %s", env.json())


@app.exception_handler(Exception)
def exception_callback(request: fastapi.Request, exc: Exception):
    from fastapi.responses import PlainTextResponse
    # omitted traceback here, because uvicorn outputs traceback as ASGI Exception
    logger.error("failed process called at %s", request.url)
    return PlainTextResponse(str(exc), status_code=500)


@dataclasses.dataclass
class SetupParser:
    settings: query.Setup

    @property
    def broker(self) -> tuple[str, query.BrokerSetting]:
        for name, setting in self.settings.items():
            if setting.type == query.ModuleType.broker:
                return name, setting
        raise KeyError(f"no broker setting")

    @property
    def planners(self) -> typing.Iterator[tuple[str, query.PlannerSetting]]:
        for name, setting in self.settings.items():
            if setting.type == query.ModuleType.planner:
                yield name, setting

    @staticmethod
    def _order(name: str):
        keys = ["historical", "generator", "commuter", "scenario", "walk", "evaluat", "user"]
        for i, key in enumerate(keys):
            if name.startswith(key):
                return i
        return 99

    @property
    def externals(self) -> list[tuple[str, query.ExternalSetting]]:
        names = sorted(self.settings.keys(), key=self._order)
        # fix order for some modules by _order function
        return [
            (name, self.settings[name])
            for name in names
            if self.settings[name].type == query.ModuleType.http
        ]


@dataclasses.dataclass
class Manager:
    # main simulation engine
    engine: RunnerEngine | None = None
    # manager to communicate planner
    planners: list[Planner] = dataclasses.field(default_factory=list)
    # writer to send simulation result to jobmanager
    writer: ResultWriter | None = None
    # running state of engine
    running = False
    # error state on engine
    error: Exception | None = None

    @property
    def success(self):
        return not self.error

    async def setup_planner(self, endpoint: str, setting: typing.Mapping):
        planner = Planner(endpoint=endpoint)
        await planner.setup(setting)
        self.planners.append(planner)

    async def setup_external(self, name: str, endpoint: str, setting: typing.Mapping):
        runner = HttpRunner(name, endpoint=endpoint)
        await runner.setup(setting)
        self.engine.setup_runners({name: runner})

    def run(self, until: int | float | None, background_tasks: fastapi.BackgroundTasks):
        self.running = True
        background_tasks.add_task(self._run, until)
        # asyncio.create_task(_run(until))
        return {
            "message": "successfully run."
        }

    async def _run(self, until: int | float):
        now = 0.0
        while now <= until and self.success:
            try:
                now = await self.engine.step(until)
            except fastapi.HTTPException as ex:
                self.error = ex
                logger.error("error on running: %s", repr(ex))
            except Exception as ex:
                self.error = ex
                logger.exception("error on running: %s", repr(ex))
        self.running = False

    async def finish(self):
        if self.engine:
            await self.engine.finish()
            self.engine = None
        for planner in self.planners:
            await planner.finish()
        self.planners.clear()
        if self.writer:
            await self.writer.close()
        self.running = False
        self.error = None


manager = Manager()


@app.post("/setup", response_model=response.Message)
async def setup(settings: query.Setup):
    parser = SetupParser(settings)

    name, broker_setting = parser.broker
    if endpoint := broker_setting.details.writer.endpoint:
        manager.writer = HTTPResultWriter(f"{endpoint}/result/events/")
    else:
        manager.writer = FileResultWriter(pathlib.Path("events.txt"))

    manager.engine = RunnerEngine(writer=manager.writer)
    for _, planner_setting in parser.planners:
        await manager.setup_planner(planner_setting.endpoint, planner_setting.details)
    for name, external_setting in parser.externals:
        await manager.setup_external(name, external_setting.endpoint, external_setting.details)

    return {
        "message": "successfully configured."
    }


@app.post("/start", response_model=response.Message)
async def start():
    await manager.engine.start()
    return {
        "message": "successfully started."
    }


@app.get("/peek", response_model=response.Peek)
async def peek():
    peek_time = await manager.engine.peek()
    return {
        "success": manager.success,
        "next": peek_time if math.isfinite(peek_time) else -1,
        "running": manager.running,
    }


@app.post("/step", response_model=response.Step)
async def step():
    """run only one step (usually for debugging)"""
    step_time = await manager.engine.step()
    return {
        "success": manager.success,
        "now": step_time if math.isfinite(step_time) else -1,
    }


@app.post("/run", response_model=response.Message)
def run(until: int | float | None, background_tasks: fastapi.BackgroundTasks):
    manager.run(until, background_tasks)
    return {
        "message": "successfully run."
    }


@app.post("/plan", response_model=list[Path])
async def plan(org: query.LocationSetting, dst: query.LocationSetting, dept: float):
    plans = await asyncio.gather(*[planner.plan(org, dst, dept) for planner in manager.planners])
    return [path for plan_ in plans for path in plan_]  # flatten


@app.get("/reservable", response_model=response.ReservableStatus)
async def reservable(service: str, org: str, dst: str):
    return {
        "reservable": await manager.engine.reservable(service, org, dst)
    }


@app.post("/finish", response_model=response.Message)
async def finish():
    await manager.finish()
    return {
        "message": "successfully finished."
    }


@app.get("/events")
def events():
    if isinstance(manager.writer, FileResultWriter):
        return fastapi.responses.FileResponse(path=manager.writer.filepath)
    else:
        msg = "must be retrieved from jobmanager"
        raise fastapi.HTTPException(fastapi.status.HTTP_404_NOT_FOUND, msg)
