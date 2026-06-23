from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Message(Base):
    """
    消息表。

    保存用户消息、助手消息、工具消息和系统消息。
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="消息ID",
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="消息角色：user / assistant / tool / system",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容",
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="生成该消息使用的模型",
    )

    agent_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="生成该消息的 Agent 名称",
    )

    sequence_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="消息顺序号",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )