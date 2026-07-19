from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.core.config import BASE_DIR, settings
from backend.app.core.logging import logger
from backend.app.db.base import Base
from backend.app.db.session import AsyncSessionLocal, engine

# 关键：导入所有模型，确保 Base.metadata 能收集到表结构。
from backend.app import models  # noqa: F401


from backend.app.db.seed import seed_admin_user, seed_model_configs


def run_alembic_upgrade(sync_conn) -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.attributes["connection"] = sync_conn
    command.upgrade(config, "head")


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

    create_all 只负责补齐全新或缺失的表；字段升级由 Alembic 管理。
    """
    ensure_sqlite_dir()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(run_alembic_upgrade)

    async with AsyncSessionLocal() as db:
        await seed_model_configs(db)
        await seed_admin_user(db)

    logger.info("数据库初始化完成 | url=%s", settings.DATABASE_URL)
