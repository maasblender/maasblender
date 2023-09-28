# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import typing
from dataclasses import dataclass
from logging import getLogger
from collections import defaultdict

import simpy

from location import Station
from mobility import Scooter, ScooterParameter
from event import ReservedEvent, ReserveFailedEvent, DepartedEvent, ArrivedEvent, EventQueue
from operation.reduce_fluctuations import Manager, OperatedStation, Operator, OperatorParameter

logger = getLogger(__name__)


@dataclass(frozen=True)
class Reservation:
    user_id: str
    mobility: Scooter
    org: Station
    dst: Station


class Simulation:
    def __init__(self):
        self.env = simpy.Environment()
        self.queue = EventQueue(env=self.env)
        self.operation = Manager(env=self.env)
        self.stations: typing.Dict[str, Station] = {}
        self._reservations: typing.Dict[str, Reservation] = {}

    def setup(self, station_information: typing.List[typing.Dict], free_bike_status: typing.List[typing.Dict],
              scooter_params: ScooterParameter, operator_params: OperatorParameter):
        mobilities: typing.Dict[str, typing.List[Scooter]] = defaultdict(list)
        for bike in free_bike_status:
            mobilities[bike["station_id"]].append(Scooter(
                env=self.env,
                id_=bike["bike_id"],
                params=scooter_params,
                current_range_meters=bike["current_range_meters"]
            ))

        self.stations.update({
            station["station_id"]: Station(
                id_=station["station_id"],
                name=station["station_id"],
                lat=station["lat"],
                lng=station["lon"],
                capacity=station["capacity"],
                is_charging=station["is_charging_station"],
                mobilities=mobilities[station["station_id"]]
            ) for station in station_information
        })

        operated_stations = [
            OperatedStation(
                station=station,
                proper_upper=len(station.reservable_mobilities) + 1,
                proper_lower=len(station.reservable_mobilities) - 1
            ) for station in self.stations.values()
        ]

        self.operation.setup(operated_stations, {
            Operator(
                env=self.env,
                queue=self.queue,
                params=operator_params,
                location=operated_stations[0],
            )
        }, operator_params)

    def start(self):
        self.env.process(self.operation.run())

    def peek(self):
        return self.env.peek()

    def step(self):
        self.env.step()
        return self.env.now, self.queue.events

    def reservable(self, org: str, dst: str):
        org = self.stations[org]
        dst = self.stations[dst]
        return org.any_reservable_mobility and dst.any_reservable_dock

    def reserve(self, user_id: str, org: str, dst: str, dept: float):
        self.env.process(self._reserve(user_id, self.stations[org], self.stations[dst], dept))

    def depart(self, user_id: str):
        self.env.process(self._depart(user_id))

    def _reserve(self, user_id: str, org: Station, dst: Station, dept: float):
        yield self.env.timeout(0)
        assert user_id not in self._reservations, user_id
        if not self.reservable(org.location_id, dst.location_id):
            self.queue.enqueue(ReserveFailedEvent(user_id=user_id))
            return
        mobility = org.reserve_mobility()
        dst.reserve_dock(mobility)
        self._reservations[user_id] = Reservation(user_id, mobility, org, dst)
        self.queue.enqueue(ReservedEvent(
            user_id=user_id,
            mobility=mobility,
            org=org,
            dst=dst,
            dept=dept,
            arrv=dept + mobility.duration(org, dst)
        ))

    def _depart(self, user_id: str):
        yield self.env.timeout(0)
        # ToDo: Since the same user may make multiple reservations,
        #  it is better to use the identifier of the reservation rather than the user ID.
        assert user_id in self._reservations, user_id
        reservation = self._reservations.pop(user_id, None)

        reservation.org.pick(reservation.mobility)
        self.queue.enqueue(DepartedEvent(
            user_id=user_id,
            mobility=reservation.mobility,
            location=reservation.org
        ))

        yield self.env.process(reservation.mobility.move(reservation.org, reservation.dst))

        reservation.dst.park(reservation.mobility)
        self.queue.enqueue(ArrivedEvent(
            user_id=user_id,
            mobility=reservation.mobility,
            location=reservation.dst
        ))
