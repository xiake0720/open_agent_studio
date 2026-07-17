from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.api.dependencies import get_current_user
from backend.app.models.user import User
from backend.app.schemas.message import MessageCreate, MessageResponse
from backend.app.schemas.response import success
from backend.app.services.message_service import (
    create_message,
    list_messages,
)

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["Messages"],
)


@router.get("")
async def list_messages_api(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    查询某个会话下的消息列表。

    前端进入某个会话时调用。
    """

    messages = await list_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=user.id,
    )

    data = [
        MessageResponse.model_validate(item).model_dump(mode="json")
        for item in messages
    ]

    return success(data)


@router.post("")
async def create_message_api(
    conversation_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    创建消息。

    Day 5 阶段用于手动测试消息保存。
    后续接入 Agent 后，用户消息和助手消息也会复用 service 层保存。
    """

    message = await create_message(
        db=db,
        conversation_id=conversation_id,
        payload=payload,
        user_id=user.id,
    )

    return success(
        MessageResponse.model_validate(message).model_dump(mode="json")
    )
