# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typing
from logging import getLogger
from functools import reduce

from core import Location
from mobility import Scooter


logger = getLogger("owmsim")


class Dock:
    """ Entity that stores a mobility """

    def __init__(self, mobility: Scooter = None):
        self.reserved: typing.Optional[Scooter] = None
        self.mobility: typing.Optional[Scooter] = mobility

    @property
    def is_available(self):
        assert not (self.mobility and self.reserved)
        return not (self.mobility or self.reserved)

    def pick(self):
        assert self.mobility and self.mobility.reserved
        mobility = self.mobility
        self.mobility = None
        mobility.reserved = False
        return mobility

    def park(self):
        assert self.reserved
        self.mobility = self.reserved
        self.reserved = None


class Station(Location):
    """ Entity that stores docks """

    def __init__(
            self, id_: str, name: str, lat: float, lng: float, mobilities: typing.Iterable[Scooter],
            capacity=0, is_charging=False
    ):
        mobilities = list(mobilities)
        assert len(mobilities) <= capacity
        super().__init__(id_, lat=lat, lng=lng)
        self.name = name
        self.is_charging = is_charging
        self._docks: typing.Set[Dock] = {
            Dock(mobility) for mobility in mobilities
        } | {
            Dock() for _ in range(capacity - len(mobilities))
        }

    @property
    def reservable_mobilities(self):
        return [dock.mobility for dock in self._docks if dock.mobility and not dock.mobility.reserved]

    @property
    def any_reservable_mobility(self):
        return any(dock.mobility and not dock.mobility.reserved for dock in self._docks)

    @property
    def any_reservable_dock(self):
        return any(dock.is_available for dock in self._docks)

    def reserve_mobility(self):
        mobilities_available = [dock.mobility for dock in self._docks if dock.mobility and not dock.mobility.reserved]
        if not len(mobilities_available):
            assert False

        def mobility_max_soc(a: Scooter, b: Scooter):
            return a if a.current_range_meters > b.current_range_meters else b

        mobility = reduce(mobility_max_soc, mobilities_available)
        mobility.reserved = True
        return mobility

    def reserve_dock(self, mobility: Scooter):
        for dock in self._docks:
            if dock.is_available:
                dock.reserved = mobility
                return dock
        assert False

    def pick(self, mobility: Scooter):
        """ pick the reserved mobility """
        for dock in self._docks:
            if dock.mobility == mobility:
                return dock.pick()
        assert False

    def park(self, mobility: Scooter):
        """ park the mobility at the reserved dock """

        for dock in self._docks:
            if dock.reserved == mobility:
                dock.park()
                # ToDo: yield env.timeout(5)?
                # mobility disable -> available
                return
        assert False
