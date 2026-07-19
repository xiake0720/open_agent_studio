from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user
from backend.app.core.agent_run_status import AgentRunStatus
from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.agent_run import AgentRun
from backend.app.models.user import User
from backend.app.schemas.agent_run import (
    AgentRunCancelResponse,
    AgentRunCreateRequest,
    AgentRunResponse,
)
from backend.app.schemas.response import success
from backend.app.services.agent_service import (
    create_stream_agent_run,
    stream_agent_run,
)
from backend.app.services.agent_run_service import (
    finalize_requested_cancellation,
    request_agent_run_cancel,
)
from backend.app.services.model_compare_service import (
    cancel_model_compare,
    get_model_compare,
    get_model_compare_response,
)
from backend.app.services.run_event_service import create_run_event, list_run_events
from backend.app.services.run_runtime import cancellation_registry
from backend.app.services.tool_call_service import list_tool_calls
from backend.app.services.conversation_service import get_conversation


router = APIRouter(
    prefix="/agent-runs",
    tags=["AgentRuns"],
)


async def get_owned_run(db: AsyncSession, run_id: str, user_id: str) -> AgentRun:
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise AppException(
            message="Agent运行记录不存在",
            code=40406,
            data={"run_id": run_id},
        )
    await get_conversation(db, run.conversation_id, user_id)
    return run


@router.get("/{run_id}/compare-results")
async def get_agent_run_compare_results_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_owned_run(db, run_id, user.id)
    result = await get_model_compare_response(db, run_id)
    return success(result.model_dump(mode="json"))


@router.get("/{run_id}/tool-calls")
async def list_agent_run_tool_calls_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    查询一次 AgentRun 的工具调用记录。
    """

    await get_owned_run(db, run_id, user.id)

    tool_calls = await list_tool_calls(
        db=db,
        run_id=run_id,
    )

    return success([
        item.model_dump(mode="json")
        for item in tool_calls
    ])


@router.get("/{run_id}/events")
async def list_agent_run_events_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    查询一次 AgentRun 的完整执行事件。
    """

    await get_owned_run(db, run_id, user.id)

    events = await list_run_events(
        db=db,
        run_id=run_id,
    )

    return success([
        event.model_dump(mode="json")
        for event in events
    ])


@router.post("")
async def create_agent_run_api(
    payload: AgentRunCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    创建一次流式 Agent 运行。

    前端先调用这个接口拿到 run_id 和 stream_url。
    然后再用 EventSource 连接 stream_url。
    """

    result = await create_stream_agent_run(
        db=db,
        payload=payload,
        user_id=user.id,
    )

    return success(result.model_dump(mode="json"))


@router.get("/{run_id}/stream")
async def stream_agent_run_api(
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    流式执行 AgentRun。

    返回 text/event-stream。
    """

    await get_owned_run(db, run_id, user.id)
    try:
        after_seq = max(0, int(last_event_id or "0"))
    except ValueError:
        after_seq = 0
    return StreamingResponse(
        stream_agent_run(run_id, user.id, last_event_id=after_seq),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{run_id}/cancel")
async def cancel_agent_run_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await get_owned_run(db, run_id, user.id)
    transition = await request_agent_run_cancel(db, run_id)
    run = transition.run

    if not transition.idempotent:
        await create_run_event(
            db,
            run_id=run.id,
            event_type="run.cancel.requested",
            payload={
                "run_id": run.id,
                "status": run.status,
                "cancel_requested_at": (
                    run.cancel_requested_at.isoformat() if run.cancel_requested_at else None
                ),
            },
        )

        if transition.previous_status is AgentRunStatus.PENDING:
            await create_run_event(
                db,
                run_id=run.id,
                event_type="run.cancelled",
                payload={
                    "run_id": run.id,
                    "status": run.status,
                    "cancelled_at": run.cancelled_at.isoformat() if run.cancelled_at else None,
                    "partial_output": run.partial_output or "",
                },
            )
        else:
            # Let the task persist its last token chunk; DB finalization below is the fallback.
            await cancellation_registry.cancel_and_wait(run.id)
            finalized = await finalize_requested_cancellation(db, run.id)
            if finalized is not None:
                run = finalized
                await create_run_event(
                    db,
                    run_id=run.id,
                    event_type="run.cancelled",
                    payload={
                        "run_id": run.id,
                        "status": run.status,
                        "cancelled_at": (
                            run.cancelled_at.isoformat() if run.cancelled_at else None
                        ),
                        "partial_output": run.partial_output or "",
                    },
                )
            else:
                refreshed = await db.get(AgentRun, run.id, populate_existing=True)
                if refreshed is not None:
                    run = refreshed

    compare = await get_model_compare(db, run.id)
    if compare is not None and compare.status not in {"completed", "cancelled"}:
        await cancel_model_compare(db, compare, "cancelled")

    return success(
        AgentRunCancelResponse(
            run_id=run.id,
            status=run.status,
            cancel_requested_at=run.cancel_requested_at,
            cancelled_at=run.cancelled_at,
            idempotent=transition.idempotent,
        ).model_dump(mode="json")
    )


@router.get("/{run_id}")
async def get_agent_run_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await get_owned_run(db, run_id, user.id)

    return success(
        AgentRunResponse.model_validate(run).model_dump(mode="json")
    )
