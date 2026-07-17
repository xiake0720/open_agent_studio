from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base
from backend.app.db.session import AsyncSessionLocal, engine

# 关键：导入所有模型，确保 Base.metadata 能收集到表结构。
from backend.app import models  # noqa: F401


from backend.app.db.seed import seed_model_configs


def migrate_legacy_sqlite(sync_conn) -> None:
    """create_all 不会修改旧表，这里只做当前版本所需的兼容迁移。"""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    if "conversations" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("conversations")}
    if "user_id" not in columns:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN user_id VARCHAR(36)"))
    sync_conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id)")
    )


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
        await conn.run_sync(migrate_legacy_sqlite)

    async with AsyncSessionLocal() as db:
        await seed_model_configs(db)

    logger.info("数据库初始化完成 | url=%s", settings.DATABASE_URL)
