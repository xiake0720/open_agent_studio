import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.schemas.response import fail

logger = logging.getLogger("open_agent_studio")


class AppException(Exception):
    """
    业务异常。

    用于主动抛出的可预期错误，例如：
    - 会话不存在
    - 模型配置不存在
    - 参数不合法
    - 工具调用失败
    """

    def __init__(
        self,
        message: str,
        code: int = 400,
        data: Optional[Any] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.data = data
        super().__init__(message)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    logger.warning(
        "业务异常 | path=%s | code=%s | message=%s",
        request.url.path,
        exc.code,
        exc.message,
    )

    return JSONResponse(
        status_code=200,
        content=fail(
            code=exc.code,
            message=exc.message,
            data=exc.data,
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "参数校验失败 | path=%s | errors=%s",
        request.url.path,
        exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content=fail(
            code=422,
            message="请求参数校验失败",
            data=exc.errors(),
        ).model_dump(),
    )


async def global_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "系统异常 | path=%s | error=%s",
        request.url.path,
        str(exc),
    )

    message = str(exc) if settings.APP_DEBUG else "服务器内部错误"

    return JSONResponse(
        status_code=500,
        content=fail(
            code=500,
            message=message,
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)