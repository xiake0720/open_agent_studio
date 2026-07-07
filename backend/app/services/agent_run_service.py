from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.agent_run import AgentRun


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
        status="running",
        input_text=input_text,
    )

    db.add(run)
    await db.commit()
    await db.refresh(run)

    return run


async def complete_agent_run(
    db: AsyncSession,
    run: AgentRun,
    final_output: str,
    duration_ms: int,
) -> AgentRun:
    run.status = "completed"
    run.final_output = final_output
    run.duration_ms = duration_ms
    run.finished_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)

    return run


async def fail_agent_run(
    db: AsyncSession,
    run: AgentRun,
    error_message: str,
    duration_ms: int,
) -> AgentRun:
    run.status = "failed"
    run.error_message = error_message
    run.duration_ms = duration_ms
    run.finished_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)

    return run