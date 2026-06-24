from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    系统配置类

    配置来源：
    1、默认值
    2、.env文件
    3、系统环境变量
    """

    APP_NAME: str = "OpenAgent Studio"
    APP_ENV: str = "dev"
    APP_DEBUG: bool = True

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 9099

    API_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/open_agent_studio.db"

    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        """
        把 .env 中的逗号分隔字符串转成列表。

        示例：
        BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
        """
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """
    使用缓存，避免每次读取配置都重新解析 .env。
    """
    return Settings()


settings = get_settings()