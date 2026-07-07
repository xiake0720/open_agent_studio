from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.response import success
from backend.app.services.agent_service import run_general_chat


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("")
async def chat_api(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    普通 Agent 聊天接口。

    Day 8 暂时返回完整结果，不做流式。
    """

    result: ChatResponse = await run_general_chat(
        db=db,
        payload=payload,
    )

    return success(result.model_dump(mode="json"))