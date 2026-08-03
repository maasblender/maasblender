# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import logging
import urllib.parse
from pprint import pformat

import aiohttp
import fastapi
import pydantic
from pydantic_settings import BaseSettings

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
    except:  # noqa: E722, In general, too broad exception is not appropriate, but here the purpose is to log all exceptions, so E722 is ignored.
        try:
            text = await response.text()
            logger_.error("%s: %s", message, text)
        except:  # noqa: E722, In general, too broad exception is not appropriate, but here the purpose is to log all exceptions, so E722 is ignored.
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


def check_upload_filename(upload_file: fastapi.UploadFile):
    filename = urllib.parse.unquote(upload_file.filename)
    if filename != upload_file.filename:
        logger.warning(
            "upload file with urlencoded filename: %s, raw: %s",
            filename,
            upload_file.filename,
        )
    return filename


class FileManagerConfig(BaseSettings, frozen=True):
    """environment variable"""

    FILE_SIZE_LIMIT: int = 0  # file size limit for each input file


@dataclasses.dataclass(frozen=True)
class FileManager:
    env: FileManagerConfig = dataclasses.field(default_factory=FileManagerConfig)
    table: dict[str, bytes] = dataclasses.field(default_factory=dict)

    @property
    def limit(self):
        return self.env.FILE_SIZE_LIMIT

    def put(self, upload_file: fastapi.UploadFile):
        data = upload_file.file.read()
        check_limit_file_size(data, limit=self.limit)
        filename = check_upload_filename(upload_file)
        self.table[filename] = data

    async def _fetch(self, session: aiohttp.ClientSession, url: str):
        async with session.get(url) as resp:
            await check_response(resp, limit=self.limit)
            data = await resp.read()
            return resp.content_disposition.filename, data

    async def pop(
        self,
        session: aiohttp.ClientSession,
        *,
        url: str | pydantic.AnyHttpUrl = None,
        filename: str | None = None,
    ) -> tuple[str, bytes]:
        if url:
            if not isinstance(url, str):
                url = str(url)
            return await self._fetch(session, url)
        elif filename:
            data = self.table.pop(filename)
            return filename, data
        else:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="exists directory in GBFS zip file",  # ToDo: correct message?
            )

    def clear(self):
        self.table.clear()
