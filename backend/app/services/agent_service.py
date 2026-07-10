import json
import time
from collections.abc import AsyncGenerator

from agents import Agent, Runner
from openai.types.responses import ResponseTextDeltaEvent
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import AsyncSessionLocal
from backend.app.models import ModelConfig
from backend.app.models.agent_run import AgentRun
from backend.app.schemas.agent_run import AgentRunCreateRequest, AgentRunCreateResponse
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.message import MessageCreate
from backend.app.services.agent_run_service import (
    complete_agent_run,
    create_agent_run,
    fail_agent_run,
)
from backend.app.services.conversation_service import get_conversation
from backend.app.services.event_normalizer import normalize_stream_event
from backend.app.services.message_service import create_message
from backend.app.services.model_config_service import (
    get_default_model_config,
    get_model_config,
)
from backend.app.services.model_factory import build_chat_model

from typing import Any

from backend.app.services.run_event_service import create_run_event

GENERAL_AGENT_NAME = "GeneralAgent"

def format_sse_event(event: str, data: dict) -> str:
    """
    把 Python 字典格式化成 SSE 事件字符串。

    SSE 格式要求：
    event: 事件名
    data: JSON字符串
    空行结尾
    """

    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )

async def create_stream_agent_run(
    db: AsyncSession,
    payload: AgentRunCreateRequest,
) -> AgentRunCreateResponse:
    """
    创建一次流式 Agent 运行。

    这个函数只做三件事：
    1. 保存用户消息
    2. 创建 agent_runs 记录
    3. 返回 stream_url

    注意：
    这里不调用模型。
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

    if not model_config.support_streaming:
        raise ValueError(f"当前模型不支持流式输出：{model_config.display_name}")

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

    return AgentRunCreateResponse(
        run_id=agent_run.id,
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
        model=model_config.model_id,
        agent_name=GENERAL_AGENT_NAME,
        stream_url=f"/api/agent-runs/{agent_run.id}/stream",
    )

async def stream_agent_run(
    run_id: str,
) -> AsyncGenerator[str, None]:
    """
    执行一次流式 Agent 运行，并不断 yield SSE 字符串。

    这里是 Day 10 核心函数。
    """

    start_time = time.perf_counter()
    final_output_parts: list[str] = []
    event_seq = 0

    async with AsyncSessionLocal() as db:

        async def persist_event(
                event_type: str,
                data: dict[str, Any],
                event_name: str | None = None,
        ) -> str:
            """
            保存事件，并返回可直接发送给前端的 SSE 字符串。
            """

            nonlocal event_seq

            event_seq += 1

            await create_run_event(
                db=db,
                run_id=run.id,
                seq=event_seq,
                event_type=event_type,
                event_name=event_name,
                payload=data,
            )

            return format_sse_event(
                event_type,
                data,
            )

        run = await db.get(AgentRun, run_id)

        if run is None:
            yield format_sse_event(
                "run.error",
                {
                    "run_id": run_id,
                    "message": "Agent运行记录不存在",
                },
            )
            return

        try:
            if run.model_config_id is None:
                raise ValueError("AgentRun 缺少 model_config_id")

            model_config = await get_model_config(
                db=db,
                model_config_id=run.model_config_id,
            )

            built_model = build_chat_model(model_config)

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

            started_data = {
                "run_id": run.id,
                "agent_name": GENERAL_AGENT_NAME,
                "model": model_config.model_id,
            }

            yield await persist_event(
                event_type="run.started",
                data=started_data,
            )

            result = Runner.run_streamed(
                agent,
                input=run.input_text,
            )

            async for event in result.stream_events():
                normalized = normalize_stream_event(
                    event=event,
                    run_id=run.id,
                )

                if normalized is None:
                    continue

                if normalized.event_type == "token.delta":
                    delta = str(normalized.data.get("delta") or "")

                    if delta:
                        final_output_parts.append(delta)

                if normalized.persist:
                    yield await persist_event(
                        event_type=normalized.event_type,
                        event_name=normalized.event_name,
                        data=normalized.data,
                    )
                else:
                    yield format_sse_event(
                        normalized.event_type,
                        normalized.data,
                    )

            if result.run_loop_exception:
                raise result.run_loop_exception

            final_output = str(result.final_output or "".join(final_output_parts))
            duration_ms = round((time.perf_counter() - start_time) * 1000)

            await complete_agent_run(
                db=db,
                run=run,
                final_output=final_output,
                duration_ms=duration_ms,
            )

            await create_message(
                db=db,
                conversation_id=run.conversation_id,
                payload=MessageCreate(
                    role="assistant",
                    content=final_output,
                    model=model_config.model_id,
                    agent_name=GENERAL_AGENT_NAME,
                ),
            )

            completed_data = {
                "run_id": run.id,
                "final_output": final_output,
                "duration_ms": duration_ms,
            }

            yield await persist_event(
                event_type="run.completed",
                data=completed_data,
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000)

            await fail_agent_run(
                db=db,
                run=run,
                error_message=str(exc),
                duration_ms=duration_ms,
            )

            error_data = {
                "run_id": run.id,
                "message": str(exc),
                "duration_ms": duration_ms,
            }

            yield await persist_event(
                event_type="run.error",
                data=error_data,
            )

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