# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import typing
import logging
from dataclasses import dataclass

import simpy
from geopy.distance import geodesic

logger = logging.getLogger("user")


class Location:
    def __init__(self, id_, lat: float, lng: float):
        self.location_id = id_
        self.lat = lat
        self.lng = lng

    def __repr__(self):
        return f"Location({self.location_id}, {self.lat}, {self.lng})"

    def __str__(self):
        return self.location_id

    def distance(self, other: Location) -> float:
        """ 地点間の直線距離(m) """
        return geodesic([self.lat, self.lng], [other.lat, other.lng]).meters


class Runner:
    """ イベントコントローラー """

    def __init__(self):
        self._env = simpy.Environment()

    @property
    def env(self):
        return self._env

    def start(self):
        pass

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        return self.env.now


class Task:
    def __call__(self, user: User) -> simpy.Event:
        raise NotImplementedError()


class User:
    """ 地点間を複数のモビリティサービスを利用しながら移動する動体 """
    def __init__(self, id_: str, org: Location, dst: Location, tasks: typing.List[Task]):
        self.user_id = id_
        self.org = org  # （旅程全体の）出発地
        self.dst = dst  # （旅程全体の）目的地
        self.task: typing.Optional[Task] = None  # 移動中の旅程
        self.tasks: typing.List[Task] = tasks  # 未来の旅程

    def run(self):
        """ 行動プロセス """
        while True:
            if not len(self.tasks):
                return
            self.task = self.tasks.pop(0)
            failed = yield self.task(self)
            if failed:
                self.tasks = failed


@dataclass(frozen=True)
class Trip:
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


@dataclass(frozen=True)
class Route:
    trips: typing.List[Trip]

    @property
    def org(self):
        return self.trips[0].org

    @property
    def dst(self):
        return self.trips[-1].dst

    @property
    def dept(self):
        return self.trips[0].dept

    @property
    def arrv(self):
        return self.trips[-1].arrv

    def __iter__(self):
        return iter(self.trips)


