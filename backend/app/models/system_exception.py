from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SystemException(Base):
    __tablename__ = "system_exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="error", index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="system", index=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
