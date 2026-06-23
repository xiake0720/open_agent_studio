from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings


def create_app() -> FastAPI:
    """
    创建FaseApi应用

    后续会在这里挂载
    1、会话窗口
    2、消息窗口
    3、模型配置窗口
    4、Agent流式接口
    5、图片生成接口
    :return:
    """

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="OpenAgent Studio",
        debug=settings.APP_DEBUG
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health_check():
        """
        健康检查接口

        前端和部署平台都可以用这个接口判断后端是否启动成功
        :return:
        """
        return {
            "ok":True,
            "app":settings.APP_NAME,
            "env":settings.APP_ENV,
            "time": datetime.now().isoformat(timespec="seconds")
        }

    return app

app = create_app()