# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import asyncio
import datetime
import logging
import re
import typing
import pprint

import aiohttp

import httputil
from core import Location, Path, Trip, calc_distance
from jschema.response import DistanceMatrix

logger = logging.getLogger(__name__)


class AsyncClient:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint
        self._session = aiohttp.ClientSession()
        self._semaphore = asyncio.Semaphore(8)

    async def get(self, method: str, params: typing.Mapping[str, str] = None, *, suppress_log=False):
        url = self._endpoint + "/" + method
        async with self._semaphore:
            async with self._session.get(url, params=params) as response:
                await httputil.check_response(response)
                if not suppress_log:
                    logger.debug("%s response: %s", url, await response.text())
                return await response.json()

    async def close(self):
        await self._session.close()


pattern = re.compile(r".+:(.*)")


def get_id_from_dict(raw: typing.Mapping, key: str, *keys: str) -> str:
    """Get id or name"""
    if value := raw.get(key):
        # remove prefix for unique descent across the GTFSs
        return pattern.match(value).groups()[0]
    else:
        for key in keys:
            if value := raw.get(key):
                return value
        else:
            raise KeyError(key)


class OpenTripPlanner:
    def __init__(self, endpoint: str, ref_datetime: datetime.datetime,
                 walking_meters_per_minute: float, modes: list[str],
                 services: typing.Mapping[str, str]):
        super().__init__()
        self.client = AsyncClient(endpoint)
        self.ref_datetime = ref_datetime
        self.walking_velocity = walking_meters_per_minute
        self.modes = modes
        self.services = services  # key: agency_id, value: service名

        # ToDo: overwrite otp default walking velocity to self.walking_velocity

    async def close(self):
        await self.client.close()

    def _elapsed(self, timestamp: str):
        return (datetime.datetime.fromtimestamp(int(timestamp) / 1000).astimezone() - self.ref_datetime) \
               / datetime.timedelta(minutes=1)

    async def health(self):
        try:
            response = await self.client.get("otp/actuators/health")
            return response == {"status": "UP"}
        except aiohttp.ClientConnectionError:
            return False

    async def meters_for_all_stops_combinations(self, stops: list[Location], base: datetime.datetime):
        failed_stops = set()
        stop_id_map = {
            get_id_from_dict(e, "id"): e["id"]
            for e in await self.client.get(method="otp/routers/default/index/stops")
        }

        async def _distance(org: Location, dst: Location):
            org_id = stop_id_map.get(org.id_)
            dst_id = stop_id_map.get(dst.id_)
            if org_id is None or dst_id is None:
                return -1
            if org_id == dst_id:
                return 0
            if org_id in failed_stops or dst_id in failed_stops:
                return -1

            try:
                response = await self.client.get(
                    method="otp/routers/default/plan",
                    params={
                        "mode": 'CAR',
                        "fromPlace": org_id,
                        # "fromPlace": f"{org.lng},{org.lng}",
                        "toPlace": dst_id,
                        # "toPlace": f"{dst.lng},{dst.lng}",
                        "time": f"{base.time()}",
                        "date": f"{base.date()}",
                    },
                    suppress_log=True,
                )
                assert "plan" in response, f"no plan in response: {response}"
                if not response["plan"]["itineraries"]:
                    return 0
                distance = response["plan"]["itineraries"][0]["walkDistance"]
                if distance < 0:
                    logger.error("illegal response from OTP: %s", response)
                    raise ValueError("illegal response from OTP, distance = %s", distance)
                return distance
            except Exception as e:
                logger.warning(f"failed to calculate the distance between {org.id_} and {dst.id_}. Error: {e}.")
                failed_stops.add(dst.id_)
                return -1

        matrix: list[list[float]] = []
        for stop_a in stops:
            vals = await asyncio.gather(*[
                _distance(org=stop_a, dst=stop_b)
                for stop_b in stops
            ])
            matrix.append(list(vals))
        return DistanceMatrix(stops=[stop.id_ for stop in stops], matrix=matrix)

    async def plan(self, org: Location, dst: Location, dept: float) -> list[Path]:
        paths: list[Path] = []
        for mode in self.modes:
            async for path in self._plan(mode=mode, org=org, dst=dst, dept=dept):
                if path not in paths:  # ignore duplicated walking path
                    paths.append(path)
        paths.sort(key=lambda e: e.arrv)
        if not any(all(trip.service == "walking" for trip in path.trips) for path in paths):
            # ToDo: Discuss again who should determine the means of transit if no route can be found.
            # If any routes are not found, return the walking route.
            walk_path = self.get_walk_path(org, dst, dept)
            logger.warning("no plan by OTP, and return walk path: %s", walk_path)
            paths.append(walk_path)
        return paths

    def get_walk_path(self, org: Location, dst: Location, dept: float) -> Path:
        return Path([
            Trip(
                org=org,
                dst=dst,
                dept=dept,
                arrv=dept + calc_distance(org, dst) / self.walking_velocity,
                service="walking",
            )],
            walking_time_minutes=calc_distance(org, dst) / self.walking_velocity)

    async def _plan(self, mode: str, org: Location, dst: Location, dept: float):
        dept_datetime = self.ref_datetime + datetime.timedelta(minutes=dept)

        response = await self.client.get(
            method="otp/routers/default/plan",
            params={
                "mode": mode,
                "fromPlace": f"{org.lat},{org.lng}",
                "toPlace": f"{dst.lat},{dst.lng}",
                "time": f"{dept_datetime.time()}",
                "date": f"{dept_datetime.date()}"
            }
        )

        # return shortest route
        assert "plan" in response, f"no plan in response: {response}"
        for itinerary in response["plan"]["itineraries"]:
            # The OTP fixes the departure and arrival names to "Origin" and "Destination".
            # correct them to their original names.
            # (The named POI will have that name, so the assert statement is disabled)
            # assert itinerary["legs"][0]["from"]["name"] == "Origin", itinerary["legs"][0]["from"]["name"]
            # assert itinerary["legs"][-1]["to"]["name"] == "Destination", itinerary["legs"][-1]["from"]["name"]
            itinerary["legs"][0]["from"]["name"] = org.id_
            itinerary["legs"][-1]["to"]["name"] = dst.id_
            logger.debug(pprint.pformat(itinerary))
            yield Path(
                trips=[self._leg_to_trip(leg) for leg in itinerary["legs"]],
                walking_time_minutes=itinerary["walkTime"] / 60)
        # else:
        #     return []

    def _get_service(self, leg: typing.Mapping):
        mode = leg.get("mode", "").upper()
        rented_bike = leg.get("rentedBike", False)
        if mode == "WALK":
            service = "walking"
        elif rented_bike:
            if mode not in ["BICYCLE", "CAR", "MOPED", "SCOOTER", "OTHER"]:
                logger.warning("unknown mode with rentedBike: %s", mode)
            networks = leg.get("from", {}).get("networks")
            assert networks, "no networks data in leg"
            for agency in networks:
                if service := self.services.get(agency):
                    break
            else:
                raise KeyError(f"unknown service with rentedBike: {networks} (not in {list(self.services)})")
        else:
            agency = get_id_from_dict(leg, "agencyId", "agencyName")
            service = self.services.get(agency)
            if not service:
                raise KeyError(f"unknown agency: {agency} (not in {self.services})")
        return service

    def _leg_to_trip(self, leg: typing.Mapping) -> Trip:
        service = self._get_service(leg)
        return Trip(
            org=Location(
                id_=get_id_from_dict(leg["from"], "stopId", "bikeShareId", "name"),
                lat=leg["from"]["lat"],
                lng=leg["from"]["lon"]
            ),
            dst=Location(
                id_=get_id_from_dict(leg["to"], "stopId", "bikeShareId", "name"),
                lat=leg["to"]["lat"],
                lng=leg["to"]["lon"]
            ),
            dept=self._elapsed(leg["from"]["departure"]),
            arrv=self._elapsed(leg["to"]["arrival"]),
            service=service,
        )
