import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.system_exception import SystemException


async def record_system_exception(
    db: AsyncSession,
    *,
    message: str,
    category: str = "system",
    level: str = "error",
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    error_code: int | None = None,
    detail: Any = None,
    traceback_text: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> SystemException:
    detail_text = None
    if detail is not None:
        detail_text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, default=str)
    item = SystemException(
        message=message,
        category=category,
        level=level,
        method=method,
        path=path,
        status_code=status_code,
        error_code=error_code,
        detail=detail_text,
        traceback_text=traceback_text,
        user_id=user_id,
        run_id=run_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


def mark_exception_resolved(item: SystemException, resolved: bool) -> None:
    item.resolved = resolved
    item.resolved_at = datetime.now(timezone.utc) if resolved else None
