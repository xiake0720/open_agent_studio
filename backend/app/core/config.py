from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 当前文件：
# backend/app/core/config.py
#
# parents[0] = backend/app/core
# parents[1] = backend/app
# parents[2] = backend
# parents[3] = 项目根目录 open_agent_studio
BASE_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env"

# 关键：把 .env 里的所有变量加载进 os.environ
# 这样 os.getenv("GLM_API_KEY") 才能拿到值
load_dotenv(ENV_FILE, override=False)


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

    AUTH_COOKIE_NAME: str = "oas_session"
    AUTH_SESSION_DAYS: int = 7
    LOGIN_CAPTCHA_AFTER_FAILURES: int = 3
    LOGIN_CAPTCHA_TTL_SECONDS: int = 300

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
