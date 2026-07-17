from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Conversation(Base):
    """
    会话表。

    一条 conversation 对应左侧会话列表中的一个会话。
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="会话ID",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="新会话",
        comment="会话标题",
    )

    agent_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        comment="当前会话默认 Agent 模式",
    )

    default_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="当前会话默认模型",
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

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属用户ID；旧数据迁移期间允许为空",
    )
