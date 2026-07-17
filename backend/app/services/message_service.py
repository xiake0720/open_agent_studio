from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.schemas.message import MessageCreate
from backend.app.services.conversation_service import get_conversation


async def list_messages(
        db: AsyncSession,
        conversation_id: str,
        user_id: str | None = None,
) -> list[Message]:
    """
    查询某个会话下的消息列表。

    按 sequence_no 正序排列，保证前端按真实聊天顺序展示。
    """

    # 先确认会话存在。
    # 如果不存在，get_conversation 会抛出 AppException。
    await get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.is_visible.is_(True),
        )
        .order_by(Message.sequence_no.asc(), Message.created_at.asc())
    )

    result = await db.execute(stmt)

    return list(result.scalars().all())


async def get_next_sequence_no(
        db: AsyncSession,
        conversation_id: str,
) -> int:
    """
    计算当前会话下一条消息的 sequence_no。

    如果当前会话没有消息，则返回 1。
    如果已有最大 sequence_no = 5，则返回 6。
    """

    stmt = select(func.max(Message.sequence_no)).where(
        Message.conversation_id == conversation_id
    )

    result = await db.execute(stmt)
    max_sequence_no = result.scalar_one_or_none()

    if max_sequence_no is None:
        return 1

    return int(max_sequence_no) + 1


async def create_message(
        db: AsyncSession,
        conversation_id: str,
        payload: MessageCreate,
        user_id: str | None = None,
) -> Message:
    """
    创建一条消息。
    """

    # 先确认会话存在。
    await get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    sequence_no = await get_next_sequence_no(
        db=db,
        conversation_id=conversation_id,
    )

    message = Message(
        conversation_id=conversation_id,
        role=payload.role,
        content=payload.content,
        model=payload.model,
        agent_name=payload.agent_name,
        sequence_no=sequence_no,
    )

    db.add(message)

    # 新增消息后，更新会话 updated_at。
    # 这样左侧会话列表按 updated_at 排序时，最近聊天的会话会排在前面。
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=func.now())
    )

    await db.commit()
    await db.refresh(message)

    return message
