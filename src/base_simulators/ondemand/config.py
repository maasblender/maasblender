# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseSettings


class LogConfiguration(BaseSettings, frozen=True):
    """environment variable for logger"""
    DEBUG: bool = False  # debug log flag

    @property
    def log_level(self):
        import logging
        return logging.DEBUG if self.DEBUG else logging.INFO

    @property
    def log_format(self):
        if self.DEBUG:
            fmt = "[%(levelname).3s] %(name)s - %(message)s"
        else:
            fmt = "[%(levelname).3s] %(message)s"
        return fmt


class Configuration(LogConfiguration, frozen=True):
    """environment variable"""
    FILE_SIZE_LIMIT: int = 0  # file size limit for each input file


env = Configuration()
