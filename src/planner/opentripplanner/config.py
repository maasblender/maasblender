# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import pathlib

from mblib.io.log import LogConfig


class Configuration(LogConfig, frozen=True):
    """environment variable"""

    OPENTRIPPLANNER_PORT: int = 8080  # port number of OpenTripPlanner core
    OPENTRIPPLANNER_STARTUP_TIMEOUT: int = (
        180  # time out (seconds) to start up OpenTripPlanner core
    )
    FILE_SIZE_LIMIT: int = 0  # file size limit for each input file
    # data directory for OpenTripPlanner core
    OPENTRIPPLANNER_EXECUTABLE: pathlib.Path = pathlib.Path("/var/otp/otp-shaded.jar")
    OPENTRIPPLANNER_VOLUME_DIR: pathlib.Path = pathlib.Path("/var/otp/volume")
    OPENTRIPPLANNER_GBFS_DIR: pathlib.Path = pathlib.Path("/var/otp/volume/gbfs")


env = Configuration()
