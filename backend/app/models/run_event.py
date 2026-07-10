from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class RunEvent(Base):
    """
    Agent 执行事件表。

    一次 AgentRun 可以包含多条事件，例如：
    1. run.started
    2. agent.updated
    3. tool.called
    4. tool.output
    5. message.completed
    6. run.completed
    """

    __tablename__ = "run_events"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "seq",
            name="uq_run_events_run_id_seq",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="事件ID",
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属AgentRun ID",
    )

    seq: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="事件在本次运行中的顺序",
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="标准化事件类型",
    )

    event_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="SDK原始事件名称",
    )

    payload_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="事件数据JSON",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="事件创建时间",
    )