# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Message(BaseModel):
    message: str


class DistanceMatrix(BaseModel):
    stops: list[str]
    matrix: list[list[float]]
