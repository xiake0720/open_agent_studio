from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.response import success
from backend.app.services.agent_service import run_general_chat
from backend.app.api.dependencies import get_current_user
from backend.app.models.user import User


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("")
async def chat_api(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    普通 Agent 聊天接口。

    Day 8 暂时返回完整结果，不做流式。
    """

    result: ChatResponse = await run_general_chat(
        db=db,
        payload=payload,
        user_id=user.id,
    )

    return success(result.model_dump(mode="json"))
