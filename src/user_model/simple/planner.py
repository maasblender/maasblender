# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import typing
import aiohttp

from core import Location, Route, Trip


class Planner:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._session = aiohttp.ClientSession(raise_for_status=True)

    async def close(self):
        await self._session.close()

    async def plan(self, org: Location, dst: Location, dept: float) -> typing.List[Route]:
        response = self.query(org, dst, dept)
        return [
            Route([
                Trip(
                    org=Location(trip["org"]["id_"], lat=trip["org"]["lat"], lng=trip["org"]["lng"]),
                    dst=Location(trip["dst"]["id_"], lat=trip["dst"]["lat"], lng=trip["dst"]["lng"]),
                    dept=trip["dept"],
                    arrv=trip["arrv"],
                    service=trip["service"]
                ) for trip in route["trips"]
            ]) for route in await response
        ]

    async def query(self, org: Location, dst: Location, dept: float):
        async with self._session.post(
            url=self.endpoint,
            params={
                "dept": dept
            },
            json={
                "org": {
                    "locationId": org.location_id,
                    "lat": org.lat,
                    "lng": org.lng
                },
                "dst": {
                    "locationId": dst.location_id,
                    "lat": dst.lat,
                    "lng": dst.lng
                }
            }
        ) as response:
            return await response.json()
