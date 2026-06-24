from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)
from backend.app.schemas.response import success
from backend.app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post("")
async def create_conversation_api(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建会话。

    前端点击“新建会话”时调用。
    """

    conversation = await create_conversation(
        db=db,
        payload=payload,
    )

    return success(
        ConversationResponse.model_validate(conversation).model_dump(mode="json")
    )


@router.get("")
async def list_conversations_api(
    db: AsyncSession = Depends(get_db),
):
    """
    查询会话列表。

    前端左侧会话列表使用。
    """

    conversations = await list_conversations(db)

    data = [
        ConversationResponse.model_validate(item).model_dump(mode="json")
        for item in conversations
    ]

    return success(data)


@router.get("/{conversation_id}")
async def get_conversation_api(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    查询单个会话详情。
    """

    conversation = await get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    return success(
        ConversationResponse.model_validate(conversation).model_dump(mode="json")
    )


@router.delete("/{conversation_id}")
async def delete_conversation_api(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    删除会话。
    """

    await delete_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    return success(True)