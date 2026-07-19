import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.agent_run import AgentRun
from backend.app.models.run_event import RunEvent
from backend.app.schemas.run_event import RunEventResponse


async def create_run_event(
    db: AsyncSession,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    event_name: str | None = None,
    seq: int | None = None,
) -> RunEvent:
    """Atomically allocate the next persisted event sequence and save the event."""

    if seq is None:
        statement = (
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(event_seq=AgentRun.event_seq + 1)
            .returning(AgentRun.event_seq)
        )
        seq = (await db.execute(statement)).scalar_one()

    run_event = RunEvent(
        run_id=run_id,
        seq=seq,
        event_type=event_type,
        event_name=event_name,
        payload_json=json.dumps(payload, ensure_ascii=False),
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
    *,
    after_seq: int = 0,
) -> list[RunEventResponse]:
    statement = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
        .order_by(RunEvent.seq.asc(), RunEvent.created_at.asc())
    )
    rows = (await db.execute(statement)).scalars().all()
    return [to_response(row) for row in rows]


def to_response(row: RunEvent) -> RunEventResponse:
    return RunEventResponse(
        id=row.id,
        run_id=row.run_id,
        seq=row.seq,
        event_type=row.event_type,
        event_name=row.event_name,
        payload_json=parse_payload(row.payload_json),
        created_at=row.created_at,
    )


def parse_payload(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        return {"raw": raw}
