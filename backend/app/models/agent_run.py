from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class AgentRun(Base):
    """
    Agent 运行记录表。

    一次用户请求，对应一次 AgentRun。
    后续 run_events、tool_calls 都会关联到这里。
    """

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Agent运行ID",
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )

    user_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="本次运行对应的用户消息ID",
    )

    model_config_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("model_configs.id", ondelete="SET NULL"),
        nullable=True,
        comment="模型配置ID",
    )

    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Agent名称",
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="实际模型ID",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
        comment="运行状态：running / completed / failed",
    )

    input_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户输入",
    )

    final_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最终输出",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="运行耗时毫秒",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="开始时间",
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="结束时间",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )