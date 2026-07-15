from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ToolCall(Base):
    """
    工具调用记录表。

    一次 AgentRun 中可能发生多次工具调用。
    """

    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="工具调用记录ID",
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属AgentRun ID",
    )

    sdk_tool_call_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="SDK原始工具调用ID",
    )

    seq: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="本次运行中的事件顺序",
    )

    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="工具名称",
    )

    arguments_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="工具参数JSON",
    )

    output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="工具输出",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
        comment="running / success / error",
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="工具调用耗时",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )