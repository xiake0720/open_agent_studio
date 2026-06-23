import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.exceptions import register_exception_handlers
from backend.app.core.logging import setup_logging

logger = logging.getLogger("open_agent_studio")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期。

    后续可以在这里做：
    1. 初始化数据库
    2. 初始化模型配置
    3. 初始化工具注册表
    4. 关闭资源连接
    """
    setup_logging()
    logger.info(
        "应用启动 | name=%s | env=%s",
        settings.APP_NAME,
        settings.APP_ENV,
    )

    yield

    logger.info("应用关闭 | name=%s", settings.APP_NAME)


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用。

    main.py 只负责应用装配：
    1. CORS
    2. 异常处理
    3. 请求日志
    4. API 路由
    """

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="OpenAgent Studio",
        debug=settings.APP_DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "请求完成 | method=%s | path=%s | status=%s | duration=%sms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    app.include_router(
        api_router,
        prefix=settings.API_PREFIX,
    )

    return app


app = create_app()