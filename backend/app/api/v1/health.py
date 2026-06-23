from datetime import datetime

from fastapi import APIRouter

from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.schemas.response import success

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check():
    """
    健康检查接口。

    前端和部署平台都可以用这个接口判断后端是否启动成功。
    """
    return success(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
    )


@router.get("/ping")
async def ping():
    return success("pong")


@router.get("/error")
async def test_error():
    """
    测试统一业务异常。

    Day 2 可以先保留，方便验证异常处理是否正常。
    后面正式版本可以删除或只在 dev 环境开放。
    """
    raise AppException("这是一个测试业务异常", code=40001)