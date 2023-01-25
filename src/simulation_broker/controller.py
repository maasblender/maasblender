# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import sys
import asyncio
import logging
import logging.handlers
import typing
from typing import Union, Optional
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

import jschema.query
import jschema.response
from logger import AsyncHttpSeqnoHandler
from engine import RunnerEngine as Engine, Runner
from runner import HttpRunner
from personal.walking import PersonalSimulator
from scenario.commuter import CommuterScenario
from scenario.historical import HistoricalScenario
from scenario.generator import DemandGenerator
from evaluation.usability import UsabilityEvaluator
from route_planner import Planner


logger = logging.getLogger("broker")
app = FastAPI(debug=True)

engine: Engine
planner: Planner
broker_setting: jschema.query.BrokerSetting


@app.on_event("startup")
async def startup():
    global logger
    logger = logging.getLogger('broker')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(sys.stdout))


@app.exception_handler(Exception)
async def exception_callback(_: Request, exc: Exception):
    logger.error(f"Unexpected Error {exc.args} \n {traceback.format_exc()}")


def aggregate_by_type(settings: jschema.query.SettingMapType):
    groups: dict[str, list[tuple[str, jschema.query.SettingType]]] = {}
    for name, setting in settings.items():
        groups.setdefault(setting.type, []).append((name, setting))
    return groups


@app.post("/setup", response_model=jschema.response.Message)
async def setup(settings: jschema.query.SettingMapType):
    global engine
    engine = Engine(event_logger=logging.getLogger("events"))

    setting_group = aggregate_by_type(settings)

    global broker_setting
    for name, setting in setting_group.pop("broker", []):
        broker_setting = setting
    global planner
    for name, setting in setting_group.pop("planner", []):
        planner = Planner(name=name, endpoint=setting.endpoint)
        await planner.setup(setting.details)

    async def setup_simulator(name_: str, setting_: jschema.query.SettingType, simulator: Runner):
        await simulator.setup(setting_.details)
        engine.setup_runners({name_: simulator})

    for name, setting in setting_group.pop("commuter", []):
        await setup_simulator(name, setting, CommuterScenario(name))
    for name, setting in setting_group.pop("historical", []):
        await setup_simulator(name, setting, HistoricalScenario(name))
    for name, setting in setting_group.pop("generator", []):
        await setup_simulator(name, setting, DemandGenerator(name))
    for name, setting in setting_group.pop("walking", []):
        await setup_simulator(name, setting, PersonalSimulator(name))
    for name, setting in setting_group.pop("evaluate", []):
        await setup_simulator(name, setting, UsabilityEvaluator(name))
    for name, setting in setting_group.pop("http", []):
        await setup_simulator(name, setting, HttpRunner(name, endpoint=setting.endpoint))

    if setting_group:
        NotImplementedError(f"{setting_group.keys()} is not implemented.")

    return {
        "message": "successfully configured."
    }


async def close_logger_handlers():
    for logger_ in [logging.getLogger("events"), logging.getLogger("evaluation")]:
        for handler in logger_.handlers:
            handler.close()
    await AsyncHttpSeqnoHandler.shutdown()


@app.post("/start", response_model=jschema.response.Message)
async def start():
    events_logger = logging.getLogger("events")
    evaluation_logger = logging.getLogger("evaluation")
    events_logger.setLevel(logging.INFO)
    evaluation_logger.setLevel(logging.INFO)

    if url := broker_setting.details.writer.endpoint:
        events_logger.addHandler(AsyncHttpSeqnoHandler(f"{url}/result/events/"))
        evaluation_logger.addHandler(AsyncHttpSeqnoHandler(f"{url}/result/evaluation/"))

    else:
        # re-assign handlers to clear text files
        await close_logger_handlers()

        events_logger.addHandler(logging.FileHandler("log.txt", mode='w'))
        evaluation_logger.addHandler(logging.FileHandler("evaluation.txt", mode='w'))

    await engine.start()
    return {
        "message": "successfully started."
    }


@app.get("/peek", response_model=jschema.response.Peek)
async def peek():
    peek_time = await engine.peek()
    return {
        "success": not engine.error,
        "next": peek_time if peek_time < float('inf') else -1
    }


@app.post("/step", response_model=jschema.response.Step)
async def step():
    step_time = await engine.step()
    return {
        "success": not engine.error,
        "now": step_time if step_time < float('inf') else -1
    }


@app.post("/run", response_model=jschema.response.Message)
async def run(until: Optional[Union[int, float]]):
    asyncio.create_task(_run(until))

    return {
        "message": "successfully run."
    }


async def _run(until: Union[int, float]):
    now = 0.0
    while now <= until and not engine.error:
        if AsyncHttpSeqnoHandler.get_queue_size() >= 500:
            await AsyncHttpSeqnoHandler.wait_queue_size(qsize=100, interval=1)
        try:
            now = await engine.step(until)
        except Exception as exc:
            engine.error = True
            raise exc


@app.post("/finish", response_model=jschema.response.Message)
async def finish():
    await engine.finish()
    await close_logger_handlers()

    return {
        "message": "successfully finished."
    }


@app.get("/events")
async def events():
    return FileResponse(path="log.txt")


@app.get("/evaluation")
async def evaluation():
    return FileResponse(path="evaluation.txt")


@app.post("/plan")
async def plan(org: jschema.query.LocationSetting, dst: jschema.query.LocationSetting, dept: float):
    return await planner.plan(org, dst, dept)


@app.get("/reservable", response_model=jschema.response.ReservableStatus)
async def reservable(service: str, org: str, dst: str):
    return {
        "reservable": await engine.reservable(service, org, dst)
    }
