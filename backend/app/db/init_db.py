from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base
from backend.app.db.session import engine

# 关键：导入所有模型，确保 Base.metadata 能收集到表结构。
from backend.app import models  # noqa: F401


def ensure_sqlite_dir() -> None:
    """
    确保 SQLite 数据库目录存在。

    当前默认数据库路径：
    sqlite+aiosqlite:///./data/open_agent_studio.db
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    """
    初始化数据库。

    Day 3 阶段先使用 create_all。
    后续如果表结构复杂起来，再引入 Alembic 做迁移。
    """
    ensure_sqlite_dir()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("数据库初始化完成 | url=%s", settings.DATABASE_URL)