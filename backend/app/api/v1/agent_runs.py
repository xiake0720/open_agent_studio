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

router = APIRouter(
    prefix="/agent-runs",
    tags=["AgentRuns"],
)

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