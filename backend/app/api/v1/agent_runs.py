from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.agent_run import AgentRun
from backend.app.schemas.agent_run import AgentRunResponse
from backend.app.schemas.response import success


router = APIRouter(
    prefix="/agent-runs",
    tags=["AgentRuns"],
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