import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.run_event import RunEvent
from backend.app.schemas.run_event import RunEventResponse


async def create_run_event(
    db: AsyncSession,
    run_id: str,
    seq: int,
    event_type: str,
    payload: dict[str, Any],
    event_name: str | None = None,
) -> RunEvent:
    """
    保存一条 Agent 执行事件。
    """

    run_event = RunEvent(
        run_id=run_id,
        seq=seq,
        event_type=event_type,
        event_name=event_name,
        payload_json=json.dumps(
            payload,
            ensure_ascii=False,
        ),
    )

    try:
        db.add(run_event)
        await db.commit()
        await db.refresh(run_event)
        return run_event
    except Exception:
        await db.rollback()
        raise


async def list_run_events(
    db: AsyncSession,
    run_id: str,
) -> list[RunEventResponse]:
    """
    按事件顺序查询一次 AgentRun 的全部事件。
    """

    statement = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(
            RunEvent.seq.asc(),
            RunEvent.created_at.asc(),
        )
    )

    result = await db.execute(statement)
    rows = result.scalars().all()

    return [
        RunEventResponse(
            id=row.id,
            run_id=row.run_id,
            seq=row.seq,
            event_type=row.event_type,
            event_name=row.event_name,
            payload_json=parse_payload(row.payload_json),
            created_at=row.created_at,
        )
        for row in rows
    ]


def parse_payload(raw: str) -> dict[str, Any]:
    """
    把数据库中的 JSON 字符串转换成 Python 字典。
    """

    try:
        value = json.loads(raw)

        if isinstance(value, dict):
            return value

        return {"value": value}

    except json.JSONDecodeError:
        return {"raw": raw}