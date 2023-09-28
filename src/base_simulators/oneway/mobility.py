# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import dataclasses
import typing
from logging import getLogger

import simpy

from core import Location, Mobility

logger = getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ScooterParameter:
    mobility_speed: float  # [m/min]
    charging_speed: float  # [/min]
    discharging_speed: float  # [/min]

    @property
    def max_range_meters(self):
        return -1.0 / self.discharging_speed * self.mobility_speed


class Battery:
    def __init__(self, env: simpy.Environment, params: ScooterParameter, fuel_percent: float):
        self.env = env
        self._soc = fuel_percent
        self._last_checked = env.now
        self._standby: typing.Callable[[float], float] = lambda duration: 0.0
        self._charging: typing.Callable[[float], float] = lambda duration: params.charging_speed * duration
        self._running: typing.Callable[[float], float] = lambda duration: params.discharging_speed * duration
        self._status = self._standby

    @property
    def soc(self):
        """ The current charge state

         ranges from 0 (empty) - 100 (full) """

        self._update()
        return self._soc

    def _update(self):
        self._soc += self._status(self.env.now - self._last_checked)
        self._soc = min(max(0.0, self._soc), 1.0)
        self._last_checked = self.env.now

    def charge(self):
        self._update()
        self._status = self._charging

    def run(self):
        self._update()
        self._status = self._running

    def get_standby(self):
        self._update()
        self._status = self._standby


class Scooter(Mobility):
    """ Rechargeable Mobility """

    def __init__(self, env: simpy.Environment, id_: str, params: ScooterParameter, current_range_meters: float):
        super().__init__(id_, params.mobility_speed)
        self.env = env
        self._max_range_meters = params.max_range_meters
        self.battery = Battery(env, params, fuel_percent=current_range_meters / self._max_range_meters)

    @property
    def current_range_meters(self):
        return self.battery.soc * self._max_range_meters

    def move(self, org: Location, dst: Location):
        self.battery.run()
        yield self.env.timeout(self.duration(org, dst))
        self.battery.get_standby()

    def charge(self):
        self.battery.charge()

    def discharge(self):
        self.battery.get_standby()
