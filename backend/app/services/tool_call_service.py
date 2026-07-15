import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.tool_call import ToolCall
from backend.app.schemas.tool_call import ToolCallResponse


def dump_json(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False)


def parse_json_or_text(raw: str | None) -> Any | None:
    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def create_tool_call(
    db: AsyncSession,
    run_id: str,
    tool_name: str,
    arguments: Any,
    sdk_tool_call_id: str | None = None,
    seq: int | None = None,
) -> ToolCall:
    tool_call = ToolCall(
        run_id=run_id,
        sdk_tool_call_id=sdk_tool_call_id,
        seq=seq,
        tool_name=tool_name,
        arguments_json=dump_json(arguments),
        status="running",
    )

    db.add(tool_call)
    await db.commit()
    await db.refresh(tool_call)

    return tool_call


async def complete_tool_call(
    db: AsyncSession,
    tool_call: ToolCall,
    output: Any,
    started_at_perf: float | None = None,
) -> ToolCall:
    tool_call.output = dump_json(output)
    tool_call.status = "success"

    if started_at_perf is not None:
        tool_call.duration_ms = round((time.perf_counter() - started_at_perf) * 1000)

    await db.commit()
    await db.refresh(tool_call)

    return tool_call


async def list_tool_calls(
    db: AsyncSession,
    run_id: str,
) -> list[ToolCallResponse]:
    stmt = (
        select(ToolCall)
        .where(ToolCall.run_id == run_id)
        .order_by(ToolCall.created_at.asc())
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        ToolCallResponse(
            id=row.id,
            run_id=row.run_id,
            sdk_tool_call_id=row.sdk_tool_call_id,
            seq=row.seq,
            tool_name=row.tool_name,
            arguments_json=parse_json_or_text(row.arguments_json),
            output=row.output,
            status=row.status,
            duration_ms=row.duration_ms,
            created_at=row.created_at,
            finished_at=row.finished_at,
        )
        for row in rows
    ]