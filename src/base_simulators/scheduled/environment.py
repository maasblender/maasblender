# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from logging import getLogger
from datetime import datetime, timedelta

from simpy import Environment as Original

logger = getLogger(__name__)


class Environment(Original):
    def __init__(self, start_time: datetime):
        super().__init__()
        self.start_time = start_time

    def datetime_from(self, elapsed: float):
        return self.start_time + timedelta(minutes=elapsed)

    def elapsed(self, date_time: datetime):
        return (date_time - self.start_time).total_seconds() / 60

    def timeout_until(self, date_time: datetime):
        return self.timeout(self.elapsed(date_time) - self.now)
