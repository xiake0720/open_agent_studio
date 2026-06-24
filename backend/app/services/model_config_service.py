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

    model_config = await db.get(ModelConfig, model_config_id)

    if model_config is None:
        raise AppException(
            message="模型配置不存在",
            code=40404,
            data={"model_config_id": model_config_id},
        )

    return model_config