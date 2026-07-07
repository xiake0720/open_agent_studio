from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AppException
from backend.app.models.model_config import ModelConfig


async def list_model_configs(
    db: AsyncSession,
    enabled_only: bool = True,
) -> list[ModelConfig]:
    """
    查询模型配置列表。

    enabled_only=True 时，只返回启用的模型。
    """

    stmt = select(ModelConfig)

    if enabled_only:
        stmt = stmt.where(ModelConfig.enabled.is_(True))

    stmt = stmt.order_by(
        ModelConfig.provider.asc(),
        ModelConfig.display_name.asc(),
    )

    result = await db.execute(stmt)

    return list(result.scalars().all())


async def get_model_config(
    db: AsyncSession,
    model_config_id: str,
) -> ModelConfig:
    """
    根据 ID 查询单个模型配置。

    如果不存在，抛出业务异常。
    """
    stmt = select(ModelConfig).where(ModelConfig.model_id == model_config_id)
    model_config = await db.scalar(stmt)

    if model_config is None:
        raise AppException(
            message="模型配置不存在",
            code=40404,
            data={"model_config_id": model_config_id},
        )

    return model_config

async def get_default_model_config(
    db: AsyncSession,
) -> ModelConfig:
    """
    获取默认可用模型。

    当前规则：
    1. 只查 enabled=True
    2. 优先 support_streaming=True
    3. 按 provider/display_name 排序取第一个
    """

    stmt = (
        select(ModelConfig)
        .where(ModelConfig.enabled.is_(True))
        .order_by(
            ModelConfig.provider.asc(),
            ModelConfig.display_name.asc(),
        )
        .limit(1)
    )

    result = await db.execute(stmt)
    model_config = result.scalar_one_or_none()

    if model_config is None:
        raise AppException(
            message="没有可用的模型配置",
            code=40405,
        )

    return model_config