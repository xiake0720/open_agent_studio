from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.model_config import ModelConfig
from backend.app.models.user import User
from backend.app.core.config import settings
from backend.app.services.auth_service import hash_password, username_key


DEFAULT_MODEL_CONFIGS = [
    {
        "provider": "glm",
        "display_name": "GLM-5.1",
        "model_id": "glm-5.1",
        "base_url": "https://ai-clawbot.shuwenda.com/v1",
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
        "display_name": "qwen3.5-397b-a17b",
        "model_id": "qwen/qwen3.5-397b-a17b",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_KEY",
        "api_shape": "chat_completions",
        "support_streaming": True,
        "support_tools": True,
        "support_image": False,
        "enabled": True,
        "extra_body_json": None,
    },
    {
        "provider": "deepseek",
        "display_name": "deepseek-v4-pro",
        "model_id": "deepseek-ai/deepseek-v4-pro",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_KEY",
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


async def seed_admin_user(db: AsyncSession) -> None:
    key = username_key(settings.DEFAULT_ADMIN_USERNAME)
    existing = await db.scalar(select(User).where(User.username_key == key))
    if existing is not None:
        if not existing.is_admin:
            logger.warning("默认管理员用户名已被普通用户占用，未自动提升权限 | username=%s", existing.username)
        return

    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME.strip(),
        username_key=key,
        password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        is_admin=True,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    logger.info("默认管理员已初始化 | username=%s", admin.username)


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
