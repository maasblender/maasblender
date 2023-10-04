# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
from pprint import pformat

import aiohttp
import fastapi

logger = logging.getLogger(__name__)
LoggerType = logging.Logger | logging.LoggerAdapter


async def error_log(response: aiohttp.ClientResponse, logger_: LoggerType = logger):
    request = response.request_info
    message = f"{request.method} {request.url} [status={response.status}]"
    try:
        content = await response.json()
        match response.status:
            case fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY:
                text = pformat(content)
            case _:
                text = pformat(content, width=200)
        logger_.error("%s:\n%s", message, text)
    except:
        try:
            text = await response.text()
            logger_.error("%s: %s", message, text)
        except:  # ignore error
            logger_.error("%s: cannot read response", message)
    return message


def check_limit_file_size(data: bytes, *, limit=0):
    """if data size over limit, raise fastapi.HTTPException"""
    if limit:
        file_size = len(data)
        if file_size > limit:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail=f"file size limit over: {file_size} > {limit}",
            )


async def check_response(response: aiohttp.ClientResponse, *, limit=0):
    """if error response, raise exception and output error log"""
    if not response.ok:
        message = await error_log(response)
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message,
        )
    elif limit:
        check_limit_file_size(await response.read(), limit=limit)
