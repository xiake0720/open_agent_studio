from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.agent_run import AgentRun
from backend.app.schemas.agent_run import (
    AgentRunCreateRequest,
    AgentRunResponse,
)
from backend.app.schemas.response import success
from backend.app.services.agent_service import (
    create_stream_agent_run,
    stream_agent_run,
)
from backend.app.services.run_event_service import list_run_events
from backend.app.services.tool_call_service import list_tool_calls


router = APIRouter(
    prefix="/agent-runs",
    tags=["AgentRuns"],
)

@router.get("/{run_id}/tool-calls")
async def list_agent_run_tool_calls_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    查询一次 AgentRun 的工具调用记录。
    """

    run = await db.get(AgentRun, run_id)

    if run is None:
        raise AppException(
            message="Agent运行记录不存在",
            code=40406,
            data={"run_id": run_id},
        )

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
):
    """
    查询一次 AgentRun 的完整执行事件。
    """

    run = await db.get(AgentRun, run_id)

    if run is None:
        raise AppException(
            message="Agent运行记录不存在",
            code=40406,
            data={"run_id": run_id},
        )

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
):
    """
    创建一次流式 Agent 运行。

    前端先调用这个接口拿到 run_id 和 stream_url。
    然后再用 EventSource 连接 stream_url。
    """

    result = await create_stream_agent_run(
        db=db,
        payload=payload,
    )

    return success(result.model_dump(mode="json"))

@router.get("/{run_id}/stream")
async def stream_agent_run_api(
    run_id: str,
):
    """
    流式执行 AgentRun。

    返回 text/event-stream。
    """

    return StreamingResponse(
        stream_agent_run(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/{run_id}")
async def get_agent_run_api(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(AgentRun, run_id)

    if run is None:
        raise AppException(
            message="Agent运行记录不存在",
            code=40406,
            data={"run_id": run_id},
        )

    return success(
        AgentRunResponse.model_validate(run).model_dump(mode="json")
    )