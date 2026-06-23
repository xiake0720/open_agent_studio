from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ModelConfig(Base):
    """
    模型配置表。

    注意：
    不直接保存 API Key 明文，只保存环境变量名称 api_key_env。
    """

    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="模型配置ID",
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="模型供应商，例如 glm / qwen / minimax / nvidia",
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="前端展示名称",
    )

    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="实际请求模型ID",
    )

    base_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="OpenAI-compatible base_url",
    )

    api_key_env: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="API Key 对应的环境变量名",
    )

    api_shape: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="chat_completions",
        comment="API 形态：chat_completions / responses / image",
    )

    support_streaming: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否支持流式输出",
    )

    support_tools: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否支持工具调用",
    )

    support_image: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否支持图片生成",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )

    extra_body_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="第三方模型额外参数，JSON字符串",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )