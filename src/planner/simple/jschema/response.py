# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Message(BaseModel):
    message: str