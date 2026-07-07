from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.model_config import ModelConfig
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.message import MessageCreate
from backend.app.services.conversation_service import get_conversation
from backend.app.services.message_service import create_message
from backend.app.services.model_config_service import (
    get_default_model_config,
    get_model_config,
)
from backend.app.services.model_factory import build_chat_model


GENERAL_AGENT_NAME = "GeneralAgent"


async def resolve_model_config(
    db: AsyncSession,
    model_config_id: str | None,
    conversation_default_model: str | None,
) -> ModelConfig:
    """
    解析本次聊天使用哪个模型。

    优先级：
    1. 请求中传入 model_config_id
    2. 会话 default_model
    3. 系统默认启用模型
    """

    if model_config_id:
        return await get_model_config(db, model_config_id)

    if conversation_default_model:
        return await get_model_config(db, conversation_default_model)

    return await get_default_model_config(db)


async def run_general_chat(
    db: AsyncSession,
    payload: ChatRequest,
) -> ChatResponse:
    """
    执行一次普通 Agent 聊天。
    """

    conversation = await get_conversation(
        db=db,
        conversation_id=payload.conversation_id,
    )

    model_config = await resolve_model_config(
        db=db,
        model_config_id=payload.model_config_id,
        conversation_default_model=conversation.default_model,
    )

    built_model = build_chat_model(model_config)

    user_message = await create_message(
        db=db,
        conversation_id=payload.conversation_id,
        payload=MessageCreate(
            role="user",
            content=payload.content,
            model=None,
            agent_name=None,
        ),
    )

    agent = Agent(
        name=GENERAL_AGENT_NAME,
        instructions=(
            "你是 OpenAgent Studio 中的通用中文助手。"
            "回答要准确、清晰、结构化。"
            "如果用户问技术问题，请尽量给出可执行步骤。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
    )

    result = await Runner.run(
        agent,
        payload.content,
    )

    final_output = str(result.final_output)

    assistant_message = await create_message(
        db=db,
        conversation_id=payload.conversation_id,
        payload=MessageCreate(
            role="assistant",
            content=final_output,
            model=model_config.model_id,
            agent_name=GENERAL_AGENT_NAME,
        ),
    )

    return ChatResponse(
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        model_config_id=model_config.id,
        model=model_config.model_id,
        agent_name=GENERAL_AGENT_NAME,
        final_output=final_output,
    )