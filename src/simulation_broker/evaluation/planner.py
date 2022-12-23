# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import dataclasses
import aiohttp


class Location(typing.NamedTuple):
    id_: str
    lat: float
    lng: float


class Trip(typing.NamedTuple):
    org: Location
    dst: Location
    dept: float
    arrv: float
    service: str


@dataclasses.dataclass
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

    @property
    def service(self):
        return self.trips[1].service if len(self.trips) > 1 else self.trips[0].service


class Planner:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession(raise_for_status=True)

    async def plan(self, org: Location, dst: Location, dept: float) -> typing.List[Route]:
        async with self._session.post(
            url=self._endpoint,
            params={
              "dept": dept
            },
            json={
                "org": {
                    "locationId": org.id_,
                    "lat": org.lat,
                    "lng": org.lng
                },
                "dst": {
                    "locationId": dst.id_,
                    "lat": dst.lat,
                    "lng": dst.lng
                }
            }
        ) as response:
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
