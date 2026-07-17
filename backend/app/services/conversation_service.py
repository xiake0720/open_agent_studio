from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AppException
from backend.app.models.conversation import Conversation
from backend.app.schemas.conversation import ConversationCreate

async def create_conversation(
    db: AsyncSession,
    payload: ConversationCreate,
    user_id: str,
) -> Conversation:
    """
    创建会话。
    """
    conversation = Conversation(
        title=payload.title,
        agent_mode=payload.agent_mode,
        default_model=payload.default_model,
        user_id=user_id,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return conversation

async def list_conversations(
    db: AsyncSession,
    user_id: str,
) -> list[Conversation]:
    """
    查询会话列表。

    按更新时间倒序排列，最近使用的会话排在前面。
    """

    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_conversation(
    db: AsyncSession,
    conversation_id: str,
    user_id: str | None = None,
) -> Conversation:
    """
    查询单个会话。

    如果不存在，抛出业务异常。
    """

    stmt = select(Conversation).where(Conversation.id == conversation_id)
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    conversation = await db.scalar(stmt)

    if conversation is None:
        raise AppException(
            message="会话不存在",
            code=40401,
            data={"conversation_id": conversation_id},
        )

    return conversation


async def delete_conversation(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
) -> None:
    """
    删除会话。

    Conversation 和 Message 已经配置 cascade="all, delete-orphan"，
    后续删除会话时，对应消息也会一起删除。
    """

    conversation = await get_conversation(db, conversation_id, user_id)

    await db.delete(conversation)
    await db.commit()
