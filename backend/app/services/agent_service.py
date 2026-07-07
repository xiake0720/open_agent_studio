import time

from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import ModelConfig
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.message import MessageCreate
from backend.app.services.agent_run_service import (
    complete_agent_run,
    create_agent_run,
    fail_agent_run,
)
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

    agent_run = await create_agent_run(
        db=db,
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
        agent_name=GENERAL_AGENT_NAME,
        model=model_config.model_id,
        input_text=payload.content,
    )

    start_time = time.perf_counter()

    try:
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
        duration_ms = round((time.perf_counter() - start_time) * 1000)

        await complete_agent_run(
            db=db,
            run=agent_run,
            final_output=final_output,
            duration_ms=duration_ms,
        )

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
            run_id=agent_run.id,
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            model_config_id=model_config.id,
            model=model_config.model_id,
            agent_name=GENERAL_AGENT_NAME,
            final_output=final_output,
        )

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000)

        await fail_agent_run(
            db=db,
            run=agent_run,
            error_message=str(exc),
            duration_ms=duration_ms,
        )

        raise