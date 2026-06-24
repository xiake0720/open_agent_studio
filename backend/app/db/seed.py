from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.model_config import ModelConfig


DEFAULT_MODEL_CONFIGS = [
    {
        "provider": "glm",
        "display_name": "GLM-5.1",
        "model_id": "glm-5.1",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "GLM_API_KEY",
        "api_shape": "chat_completions",
        "support_streaming": True,
        "support_tools": True,
        "support_image": False,
        "enabled": True,
        "extra_body_json": '{"thinking":{"type":"disabled"}}',
    },
    {
        "provider": "qwen",
        "display_name": "Qwen Plus",
        "model_id": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "QWEN_API_KEY",
        "api_shape": "chat_completions",
        "support_streaming": True,
        "support_tools": True,
        "support_image": False,
        "enabled": True,
        "extra_body_json": None,
    },
    {
        "provider": "custom",
        "display_name": "自定义模型网关 GLM-5.1",
        "model_id": "glm-5.1",
        "base_url": "https://ai-clawbot.shuwenda.com/v1",
        "api_key_env": "CUSTOM_MODEL_API_KEY",
        "api_shape": "chat_completions",
        "support_streaming": True,
        "support_tools": True,
        "support_image": False,
        "enabled": True,
        "extra_body_json": None,
    },
    {
        "provider": "flux",
        "display_name": "Flux Image",
        "model_id": "flux",
        "base_url": "https://your-image-api.example.com/v1",
        "api_key_env": "IMAGE_MODEL_API_KEY",
        "api_shape": "image",
        "support_streaming": False,
        "support_tools": False,
        "support_image": True,
        "enabled": False,
        "extra_body_json": None,
    },
]


async def seed_model_configs(db: AsyncSession) -> None:
    """
    初始化默认模型配置。

    注意：
    1. 不保存真实 API Key。
    2. 只保存 api_key_env，也就是环境变量名称。
    3. 如果 provider + model_id 已存在，则跳过，避免重复插入。
    """

    created_count = 0

    for item in DEFAULT_MODEL_CONFIGS:
        stmt = select(ModelConfig).where(
            ModelConfig.provider == item["provider"],
            ModelConfig.model_id == item["model_id"],
        )

        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            continue

        model_config = ModelConfig(**item)
        db.add(model_config)
        created_count += 1

    if created_count > 0:
        await db.commit()

    logger.info("默认模型配置初始化完成 | created=%s", created_count)