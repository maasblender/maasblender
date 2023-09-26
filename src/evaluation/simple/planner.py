# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import dataclasses

import aiohttp

from common import httputil
from core import Location


@dataclasses.dataclass(frozen=True)
class Trip:
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


@dataclasses.dataclass(frozen=True)
class Route:
    trips: list[Trip]

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

    @property
    def service(self):
        return self.trips[1].service if len(self.trips) > 1 else self.trips[0].service


class Planner:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession()

    async def close(self):
        await self._session.close()

    async def plan(self, org: Location, dst: Location, dept: float) -> list[Route]:
        async with self._session.post(
                url=self._endpoint,
                params={"dept": dept},
                json={"org": org.dumps(), "dst": dst.dumps()},
        ) as response:
            await httputil.check_response(response)
            routes = await response.json()
            return [
                Route([
                    Trip(
                        org=Location(trip["org"]["id_"], lat=trip["org"]["lat"], lng=trip["org"]["lng"]),
                        dst=Location(trip["dst"]["id_"], lat=trip["dst"]["lat"], lng=trip["dst"]["lng"]),
                        dept=trip["dept"],
                        arrv=trip["arrv"],
                        service=trip["service"]
                    ) for trip in route["trips"]
                ]) for route in routes
            ]


class ReservableChecker:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession()

    async def close(self):
        await self._session.close()

    async def reservable(self, service: str, org: str, dst: str) -> bool:
        async with self._session.get(
                url=self._endpoint,
                params={"service": service, "org": org, "dst": dst},
        ) as response:
            await httputil.check_response(response)
            return (await response.json())["reservable"]
