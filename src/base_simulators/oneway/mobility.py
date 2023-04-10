# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from logging import getLogger

import simpy

from core import Location, Mobility


logger = getLogger("owmsim")


class Battery:
    def __init__(self, env: simpy.Environment, fuel_percent: float):
        self.env = env
        self._soc = fuel_percent
        self._last_checked = env.now
        self._standby: typing.Callable[[float], float] = lambda duration: 0.0
        self._charging: typing.Callable[[float], float] = lambda duration: 0.003333 * duration
        self._running: typing.Callable[[float], float] = lambda duration: -0.004386 * duration
        self._status = self._standby

    @property
    def soc(self):
        """ 現在の充電率を返す

        充電率は 0 - 100 のいずれかの値"""

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
    """充電可能なモビリティ"""

    def __init__(self, env: simpy.Environment, id_: str, current_range_meters: float):
        super().__init__(id_)
        self.env = env
        self._max_range_meters = 1.0 / 0.004386 * self.velocity
        self.battery = Battery(env, fuel_percent=current_range_meters / self._max_range_meters)

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
