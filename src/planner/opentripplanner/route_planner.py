# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import asyncio
import datetime
import logging
import re
import typing

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
import aiohttp

from core import Location, Path, Trip, calc_distance
from jschema.response import DistanceMatrix

logger = logging.getLogger(__name__)
pattern = re.compile(r".+:(.*)")


def id_from_gtfs_id(gtfs_id: str) -> str:
    return pattern.match(gtfs_id).groups()[0]


class OpenTripPlanner:
    def __init__(
        self,
        endpoint: str,
        ref_datetime: datetime.datetime,
        walking_meters_per_minute: float,
        transport_modes: list[list[typing.Mapping]],
        services: typing.Mapping[str, str],
    ):
        super().__init__()
        self.endpoint = endpoint
        self.client = Client(
            transport=AIOHTTPTransport(
                url=f"{endpoint}/otp/routers/default/index/graphql"
            ),
            fetch_schema_from_transport=True,
        )
        self.ref_datetime = ref_datetime
        self.walking_velocity = walking_meters_per_minute
        self.transport_modes = (
            transport_modes
            if transport_modes
            else [
                [
                    {"mode": "WALK"},
                    {"mode": "TRANSIT"},
                ],
                [{"mode": "WALK"}, {"mode": "FLEX", "qualifier": "DIRECT"}],
            ]
        )
        self.services = services  # key: agency_id, value: service name

        # ToDo: overwrite otp default walking velocity to self.walking_velocity

    async def close(self):
        await self.client.close_async()

    def _elapsed(self, timestamp: str):
        return (
            datetime.datetime.fromtimestamp(int(timestamp) / 1000).astimezone()
            - self.ref_datetime
        ) / datetime.timedelta(minutes=1)

    async def health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.endpoint}/otp/actuators/health") as resp:
                    result = await resp.json()
            return result == {"status": "UP"}
        except aiohttp.ClientConnectionError:
            return False

    async def meters_for_all_stops_combinations(
        self, stops: list[str], base: datetime.datetime
    ):
        stops_org = stops
        stop_id_map = {
            id_from_gtfs_id(stop["gtfsId"]): stop["gtfsId"]
            for stop in await self.stops()
        }
        stops = [stop_id_map[stop] for stop in stops]

        matrix: list[list[float]] = []
        async with self.client as session:
            for stop_a in stops:
                vals = await asyncio.gather(
                    *[
                        self.distance(
                            session,
                            org=stop_a,
                            dst=stop_b,
                            date=f"{base.date()}",
                            time=f"{base.time()}",
                        )
                        for stop_b in stops
                    ]
                )
                matrix.append(list(vals))
        return DistanceMatrix(stops=stops_org, matrix=matrix)

    async def plan(self, org: Location, dst: Location, dept: float) -> list[Path]:
        paths: list[Path] = []
        for modes in self.transport_modes:
            async for path in self._plan_query(
                modes=modes, org=org, dst=dst, dept=dept
            ):
                if path not in paths:  # ignore duplicated walking path
                    paths.append(path)
        paths.sort(key=lambda e: e.arrv)

        if not any(
            all(trip.service == "walking" for trip in path.trips) for path in paths
        ):
            # If a walking route is not found, append a walking route.
            walk_path = self.straight_walk_path(org, dst, dept)
            paths.append(walk_path)
            if not paths:
                logger.warning("no plan by OTP, and return straight walk path.")
            else:
                logger.warning(
                    "no walking plan found by OTP, and appended a walking path: %s",
                    walk_path,
                )

        return paths

    def straight_walk_path(self, org: Location, dst: Location, dept: float) -> Path:
        return Path(
            trips=[
                Trip(
                    org=org,
                    dst=dst,
                    dept=dept,
                    arrv=dept + calc_distance(org, dst) / self.walking_velocity,
                    service="walking",
                )
            ],
            walking_time_minutes=calc_distance(org, dst) / self.walking_velocity,
        )

    async def stops(self) -> list[typing.Mapping[str, str]]:
        query = gql("""
        query Stops {
          stops {
            gtfsId
          }
        }
        """)

        response = await self.client.execute_async(query)
        return response["stops"]

    async def distance(self, session, org: str, dst: str, date: str, time: str) -> int:
        query = gql("""
        query PlanQuery($from: String, $to: String, $date: String, $time: String) {
          plan(
            fromPlace: $from
            toPlace: $to
            date: $date
            time: $time
            transportModes: [{ mode: CAR }]
            numItineraries: 1
            maxTransfers: 1
          ) {
            itineraries {
              walkDistance 
            }
          }
        }
        """)

        response = await session.execute(
            query,
            variable_values={
                "date": date,
                "time": time,
                "from": org,
                "to": dst,
            },
        )

        if response["plan"]["itineraries"]:
            return response["plan"]["itineraries"][0]["walkDistance"]
        else:
            return 0

    async def _plan_query(
        self, modes: list[typing.Mapping], org: Location, dst: Location, dept: float
    ):
        query = gql("""
    query PlanQuery($modes: [TransportMode], $from: InputCoordinates, $to: InputCoordinates, $date: String, $time: String) {
      plan(
        from: $from
        to: $to
        date: $date
        time: $time
        transportModes: $modes
        numItineraries: 3
        maxTransfers: 4
      ) {
        itineraries {
          walkTime
          legs {
            mode
            agency {
              gtfsId
            }
            from {
              name
              lat
              lon
              stop {
                gtfsId
              }
              departureTime
            }
            to {
              name
              lat
              lon
              stop {
                gtfsId
              }
              arrivalTime
            }
          }
        }
      }
    }
            """)

        dept_datetime = self.ref_datetime + datetime.timedelta(minutes=dept)
        response = await self.client.execute_async(
            query,
            variable_values={
                "modes": modes,
                "date": f"{dept_datetime.date()}",
                "time": f"{dept_datetime.time()}",
                "from": {"lat": org.lat, "lon": org.lng},
                "to": {"lat": dst.lat, "lon": dst.lng},
            },
        )

        for itinerary in response["plan"]["itineraries"]:
            itinerary["legs"][0]["from"]["name"] = org.id_
            itinerary["legs"][-1]["to"]["name"] = dst.id_
            yield Path(
                trips=[self._leg_to_trip(leg) for leg in itinerary["legs"]],
                walking_time_minutes=itinerary["walkTime"] / 60,
            )

    def _leg_to_trip(self, leg: typing.Mapping) -> Trip:
        service = (
            "walking"
            if leg["mode"] == "WALK"
            else self.services.get(id_from_gtfs_id(leg["agency"]["gtfsId"]))
        )
        if not service:
            raise KeyError(
                f"unknown agency: {leg['agency']['gtfsId']} (not in {self.services.keys()})"
            )

        org = leg["from"]
        dst = leg["to"]
        return Trip(
            service=service,
            org=Location(
                id_=id_from_gtfs_id(org["stop"]["gtfsId"])
                if org.get("stop")
                else org["name"],
                lat=org["lat"],
                lng=org["lon"],
            ),
            dst=Location(
                id_=id_from_gtfs_id(dst["stop"]["gtfsId"])
                if dst.get("stop")
                else dst["name"],
                lat=dst["lat"],
                lng=dst["lon"],
            ),
            dept=self._elapsed(org["departureTime"]),
            arrv=self._elapsed(dst["arrivalTime"]),
        )
