from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.agent_run_status import AgentRunStatus
from backend.app.models.agent_run import AgentRun


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CancelTransition:
    run: AgentRun
    previous_status: AgentRunStatus
    idempotent: bool


async def create_agent_run(
    db: AsyncSession,
    conversation_id: str,
    user_message_id: str | None,
    model_config_id: str | None,
    agent_name: str,
    model: str,
    input_text: str,
) -> AgentRun:
    run = AgentRun(
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        model_config_id=model_config_id,
        agent_name=agent_name,
        model=model,
        status=AgentRunStatus.PENDING.value,
        input_text=input_text,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def claim_agent_run(db: AsyncSession, run_id: str, execution_id: str) -> AgentRun | None:
    now = utcnow()
    statement = (
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status == AgentRunStatus.PENDING.value,
        )
        .values(
            status=AgentRunStatus.RUNNING.value,
            execution_id=execution_id,
            claimed_at=now,
            started_at=now,
            version=AgentRun.version + 1,
        )
        .returning(AgentRun.id)
    )
    claimed_id = (await db.execute(statement)).scalar_one_or_none()
    await db.commit()
    if claimed_id is None:
        return None
    return await db.get(AgentRun, run_id)


async def update_partial_output(
    db: AsyncSession,
    *,
    run_id: str,
    execution_id: str,
    partial_output: str,
) -> bool:
    result = await db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.execution_id == execution_id,
            AgentRun.status == AgentRunStatus.RUNNING.value,
        )
        .values(partial_output=partial_output, version=AgentRun.version + 1)
    )
    await db.commit()
    return result.rowcount == 1


async def is_cancel_requested(db: AsyncSession, run_id: str, execution_id: str) -> bool:
    value = await db.scalar(
        select(AgentRun.cancel_requested_at).where(
            AgentRun.id == run_id,
            AgentRun.execution_id == execution_id,
            AgentRun.status == AgentRunStatus.RUNNING.value,
        )
    )
    return value is not None


async def _finish_agent_run(
    db: AsyncSession,
    *,
    run_id: str,
    execution_id: str,
    status: AgentRunStatus,
    duration_ms: int,
    final_output: str | None = None,
    error_message: str | None = None,
    cancelled: bool = False,
) -> AgentRun | None:
    now = utcnow()
    values: dict[str, object] = {
        "status": status.value,
        "duration_ms": duration_ms,
        "finished_at": now,
        "version": AgentRun.version + 1,
    }
    if final_output is not None:
        values["final_output"] = final_output
        values["partial_output"] = final_output
    if error_message is not None:
        values["error_message"] = error_message
    if cancelled:
        values["cancelled_at"] = now

    result = await db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.execution_id == execution_id,
            AgentRun.status == AgentRunStatus.RUNNING.value,
        )
        .values(**values)
    )
    await db.commit()
    if result.rowcount != 1:
        return None
    return await db.get(AgentRun, run_id)


async def complete_agent_run(
    db: AsyncSession,
    run: AgentRun,
    final_output: str,
    duration_ms: int,
    execution_id: str | None = None,
) -> AgentRun:
    resolved_execution_id = execution_id or run.execution_id
    if not resolved_execution_id:
        raise RuntimeError("AgentRun 尚未领取，不能完成")
    updated = await _finish_agent_run(
        db,
        run_id=run.id,
        execution_id=resolved_execution_id,
        status=AgentRunStatus.COMPLETED,
        final_output=final_output,
        duration_ms=duration_ms,
    )
    if updated is None:
        raise RuntimeError("AgentRun 完成状态写入冲突")
    return updated


async def fail_agent_run(
    db: AsyncSession,
    run: AgentRun,
    error_message: str,
    duration_ms: int,
    execution_id: str | None = None,
) -> AgentRun:
    resolved_execution_id = execution_id or run.execution_id
    if not resolved_execution_id:
        raise RuntimeError("AgentRun 尚未领取，不能标记失败")
    updated = await _finish_agent_run(
        db,
        run_id=run.id,
        execution_id=resolved_execution_id,
        status=AgentRunStatus.FAILED,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    if updated is None:
        raise RuntimeError("AgentRun 失败状态写入冲突")
    return updated


async def timeout_agent_run(
    db: AsyncSession,
    run: AgentRun,
    error_message: str,
    duration_ms: int,
    execution_id: str,
) -> AgentRun | None:
    return await _finish_agent_run(
        db,
        run_id=run.id,
        execution_id=execution_id,
        status=AgentRunStatus.TIMEOUT,
        error_message=error_message,
        duration_ms=duration_ms,
    )


async def cancel_agent_run(
    db: AsyncSession,
    run: AgentRun,
    duration_ms: int,
    execution_id: str,
) -> AgentRun | None:
    return await _finish_agent_run(
        db,
        run_id=run.id,
        execution_id=execution_id,
        status=AgentRunStatus.CANCELLED,
        error_message="运行已由用户取消",
        duration_ms=duration_ms,
        cancelled=True,
    )


async def request_agent_run_cancel(db: AsyncSession, run_id: str) -> CancelTransition:
    run = await db.get(AgentRun, run_id, populate_existing=True)
    if run is None:
        raise LookupError(run_id)
    current = AgentRunStatus(run.status)

    if current is AgentRunStatus.PENDING:
        now = utcnow()
        result = await db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.status == AgentRunStatus.PENDING.value,
            )
            .values(
                status=AgentRunStatus.CANCELLED.value,
                cancel_requested_at=now,
                cancelled_at=now,
                finished_at=now,
                error_message="运行在开始前已取消",
                version=AgentRun.version + 1,
            )
        )
        await db.commit()
        if result.rowcount == 1:
            refreshed = await db.get(AgentRun, run_id, populate_existing=True)
            assert refreshed is not None
            return CancelTransition(refreshed, current, False)
        return await request_agent_run_cancel(db, run_id)

    if current is AgentRunStatus.RUNNING:
        if run.cancel_requested_at is not None:
            return CancelTransition(run, current, True)
        now = utcnow()
        result = await db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.status == AgentRunStatus.RUNNING.value,
                AgentRun.cancel_requested_at.is_(None),
            )
            .values(cancel_requested_at=now, version=AgentRun.version + 1)
        )
        await db.commit()
        if result.rowcount == 1:
            refreshed = await db.get(AgentRun, run_id, populate_existing=True)
            assert refreshed is not None
            return CancelTransition(refreshed, current, False)
        return await request_agent_run_cancel(db, run_id)

    return CancelTransition(run, current, True)


async def finalize_requested_cancellation(db: AsyncSession, run_id: str) -> AgentRun | None:
    """Finalize a DB-backed cancellation when the local task has been signalled."""

    now = utcnow()
    result = await db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status == AgentRunStatus.RUNNING.value,
            AgentRun.cancel_requested_at.is_not(None),
        )
        .values(
            status=AgentRunStatus.CANCELLED.value,
            cancelled_at=now,
            finished_at=now,
            error_message="运行已由用户取消",
            version=AgentRun.version + 1,
        )
    )
    await db.commit()
    if result.rowcount != 1:
        return None
    return await db.get(AgentRun, run_id, populate_existing=True)


async def recompute_duration_ms(db: AsyncSession, run_id: str) -> int:
    run = await db.get(AgentRun, run_id)
    if run is None or run.started_at is None:
        return 0
    started = run.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(0, round((utcnow() - started).total_seconds() * 1000))
