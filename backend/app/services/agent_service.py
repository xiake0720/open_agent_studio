import asyncio
import json
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.factory import AgentFactory
from backend.app.agents.modes import (
    AgentMode,
    agent_name_for_mode,
    mode_from_agent_name,
    resolve_agent_mode,
)
from backend.app.agents.routing import resolve_route_decision
from backend.app.agents.triage_agent import build_triage_agent
from backend.app.core.exceptions import AppException
from backend.app.db.session import AsyncSessionLocal
from backend.app.models import ModelConfig
from backend.app.models.agent_run import AgentRun
from backend.app.models.model_compare import ModelCompare
from backend.app.models.tool_call import ToolCall
from backend.app.schemas.agent_run import AgentRunCreateRequest, AgentRunCreateResponse
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.message import MessageCreate
from backend.app.services.agent_run_service import (
    complete_agent_run,
    create_agent_run,
    fail_agent_run,
)
from backend.app.services.compare_runner import (
    CandidateOutput,
    format_judge_markdown,
    judge_compare_candidates,
    run_compare_candidate,
)
from backend.app.services.conversation_service import get_conversation
from backend.app.services.event_normalizer import normalize_stream_event
from backend.app.services.message_service import create_message
from backend.app.services.model_compare_service import (
    complete_model_compare,
    create_model_compare,
    fail_model_compare,
    get_model_compare,
    mark_compare_running,
    save_compare_result,
)
from backend.app.services.model_config_service import (
    get_default_model_config,
    get_model_config,
    list_model_configs,
)
from backend.app.services.model_factory import build_chat_model
from backend.app.services.run_event_service import create_run_event
from backend.app.services.tool_call_service import complete_tool_call, create_tool_call


def format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def resolve_model_config(
    db: AsyncSession,
    model_config_id: str | None,
    conversation_default_model: str | None,
) -> ModelConfig:
    if model_config_id:
        return await get_model_config(db, model_config_id)
    if conversation_default_model:
        return await get_model_config(db, conversation_default_model)
    return await get_default_model_config(db)


async def resolve_compare_model_configs(
    db: AsyncSession,
    model_config_ids: list[str],
    *,
    use_defaults: bool = False,
) -> list[ModelConfig]:
    distinct_ids = list(dict.fromkeys(item for item in model_config_ids if item))

    if use_defaults and len(distinct_ids) < 2:
        available = await list_model_configs(db=db, enabled_only=True)
        distinct_ids = [
            item.id
            for item in available
            if item.api_shape == "chat_completions"
        ][:3]

    if not 2 <= len(distinct_ids) <= 3:
        raise AppException(
            message="模型对比必须选择 2-3 个不同的文本模型",
            code=40030,
            data={"compare_model_ids": distinct_ids},
        )

    configs = [await get_model_config(db, item) for item in distinct_ids]
    unsupported = [
        item.display_name
        for item in configs
        if not item.enabled or item.api_shape != "chat_completions"
    ]
    if unsupported:
        raise AppException(
            message="模型对比包含不可用的文本模型",
            code=40031,
            data={"models": unsupported},
        )
    return configs


async def create_stream_agent_run(
    db: AsyncSession,
    payload: AgentRunCreateRequest,
    user_id: str,
) -> AgentRunCreateResponse:
    conversation = await get_conversation(
        db=db, conversation_id=payload.conversation_id, user_id=user_id
    )
    model_config = await resolve_model_config(
        db=db,
        model_config_id=payload.primary_model_id,
        conversation_default_model=conversation.default_model,
    )
    agent_mode = resolve_agent_mode(
        requested_mode=payload.agent_mode,
        conversation_mode=conversation.agent_mode,
    )
    entry_agent_name = agent_name_for_mode(agent_mode)

    if agent_mode is not AgentMode.COMPARE and not model_config.support_streaming:
        raise AppException(
            message=f"当前模型不支持流式输出：{model_config.display_name}",
            code=40032,
        )

    compare_configs: list[ModelConfig] = []
    if agent_mode is AgentMode.COMPARE:
        compare_configs = await resolve_compare_model_configs(
            db,
            payload.compare_model_ids,
        )

    user_message = await create_message(
        db=db,
        conversation_id=payload.conversation_id,
        payload=MessageCreate(role="user", content=payload.content, model=None, agent_name=None),
        user_id=user_id,
    )
    agent_run = await create_agent_run(
        db=db,
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
        agent_name=entry_agent_name,
        model=model_config.model_id,
        input_text=payload.content,
    )

    if compare_configs:
        await create_model_compare(
            db=db,
            run_id=agent_run.id,
            model_config_ids=[item.id for item in compare_configs],
        )

    return AgentRunCreateResponse(
        run_id=agent_run.id,
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
        model=model_config.model_id,
        agent_name=entry_agent_name,
        stream_url=f"/api/agent-runs/{agent_run.id}/stream",
    )


async def stream_agent_run(run_id: str) -> AsyncGenerator[str, None]:
    start_time = time.perf_counter()
    event_seq = 0

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, run_id)
        if run is None:
            yield format_sse_event("run.error", {"run_id": run_id, "message": "Agent运行记录不存在"})
            return

        async def persist_event(
            event_type: str,
            data: dict[str, Any],
            event_name: str | None = None,
            *,
            persist: bool = True,
        ) -> str:
            nonlocal event_seq
            if persist:
                event_seq += 1
                await create_run_event(
                    db=db,
                    run_id=run.id,
                    seq=event_seq,
                    event_type=event_type,
                    event_name=event_name,
                    payload=data,
                )
            return format_sse_event(event_type, data)

        try:
            if run.model_config_id is None:
                raise ValueError("AgentRun 缺少 model_config_id")

            primary_config = await get_model_config(db=db, model_config_id=run.model_config_id)
            built_model = build_chat_model(primary_config)
            agent_mode = mode_from_agent_name(run.agent_name)

            yield await persist_event(
                "run.started",
                {
                    "run_id": run.id,
                    "agent_name": run.agent_name,
                    "agent_mode": agent_mode.value,
                    "model": primary_config.model_id,
                },
            )

            if agent_mode is AgentMode.AUTO:
                yield await persist_event(
                    "route.started",
                    {"run_id": run.id, "agent_name": "TriageRouteAgent"},
                )
                decision, route_source = await resolve_route_decision(built_model, run.input_text)
                yield await persist_event(
                    "route.decision",
                    {
                        "run_id": run.id,
                        **decision.model_dump(mode="json"),
                        "source": route_source,
                    },
                )
                if decision.specialist == "compare":
                    compare = await get_model_compare(db, run.id)
                    if compare is None:
                        configs = await resolve_compare_model_configs(db, [], use_defaults=True)
                        compare = await create_model_compare(
                            db,
                            run.id,
                            [item.id for item in configs],
                        )
                    async for event in _stream_compare_pipeline(
                        db=db,
                        run=run,
                        compare=compare,
                        primary_config=primary_config,
                        persist_event=persist_event,
                        start_time=start_time,
                    ):
                        yield event
                    return
                agent = build_triage_agent(built_model, decision)
            elif agent_mode is AgentMode.COMPARE:
                compare = await get_model_compare(db, run.id)
                if compare is None:
                    raise ValueError("Compare AgentRun 缺少模型对比配置")
                async for event in _stream_compare_pipeline(
                    db=db,
                    run=run,
                    compare=compare,
                    primary_config=primary_config,
                    persist_event=persist_event,
                    start_time=start_time,
                ):
                    yield event
                return
            else:
                agent = AgentFactory(built_model=built_model).build(agent_mode)

            async for event in _stream_standard_agent(
                db=db,
                run=run,
                agent=agent,
                model_config=primary_config,
                persist_event=persist_event,
                start_time=start_time,
            ):
                yield event

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            await fail_agent_run(db=db, run=run, error_message=str(exc), duration_ms=duration_ms)
            compare = await get_model_compare(db, run.id)
            if compare is not None and compare.status != "completed":
                await fail_model_compare(db, compare)
            yield await persist_event(
                "run.error",
                {"run_id": run.id, "message": str(exc), "duration_ms": duration_ms},
            )


async def _stream_standard_agent(
    *,
    db: AsyncSession,
    run: AgentRun,
    agent: Agent,
    model_config: ModelConfig,
    persist_event: Callable[..., Any],
    start_time: float,
) -> AsyncGenerator[str, None]:
    final_output_parts: list[str] = []
    pending_calls: dict[str, tuple[str, float]] = {}
    pending_without_id: list[tuple[str, float]] = []

    result = Runner.run_streamed(agent, input=run.input_text)
    async for event in result.stream_events():
        normalized = normalize_stream_event(event=event, run_id=run.id)
        if normalized is None:
            continue

        if normalized.event_type == "tool.called":
            tool_call = await create_tool_call(
                db=db,
                run_id=run.id,
                tool_name=str(normalized.data.get("tool_name") or "unknown_tool"),
                arguments=normalized.data.get("arguments"),
                sdk_tool_call_id=normalized.data.get("tool_call_id"),
            )
            value = (tool_call.id, time.perf_counter())
            sdk_id = normalized.data.get("tool_call_id")
            if isinstance(sdk_id, str):
                pending_calls[sdk_id] = value
            else:
                pending_without_id.append(value)

        if normalized.event_type == "tool.output":
            sdk_id = normalized.data.get("tool_call_id")
            pending = pending_calls.pop(sdk_id, None) if isinstance(sdk_id, str) else None
            if pending is None and pending_without_id:
                pending = pending_without_id.pop(0)
            if pending is not None:
                tool_call = await db.get(ToolCall, pending[0])
                if tool_call is not None:
                    await complete_tool_call(
                        db=db,
                        tool_call=tool_call,
                        output=normalized.data.get("output"),
                        started_at_perf=pending[1],
                    )

        if normalized.event_type == "token.delta":
            delta = str(normalized.data.get("delta") or "")
            if delta:
                final_output_parts.append(delta)

        yield await persist_event(
            normalized.event_type,
            normalized.data,
            normalized.event_name,
            persist=normalized.persist,
        )

    if result.run_loop_exception:
        raise result.run_loop_exception

    final_output = str(result.final_output or "".join(final_output_parts))
    final_agent_name = result.last_agent.name
    duration_ms = round((time.perf_counter() - start_time) * 1000)
    await complete_agent_run(db=db, run=run, final_output=final_output, duration_ms=duration_ms)
    await create_message(
        db=db,
        conversation_id=run.conversation_id,
        payload=MessageCreate(
            role="assistant",
            content=final_output,
            model=model_config.model_id,
            agent_name=final_agent_name,
        ),
    )
    yield await persist_event(
        "run.completed",
        {
            "run_id": run.id,
            "final_output": final_output,
            "duration_ms": duration_ms,
            "last_agent_name": final_agent_name,
        },
    )


async def _stream_compare_pipeline(
    *,
    db: AsyncSession,
    run: AgentRun,
    compare: ModelCompare,
    primary_config: ModelConfig,
    persist_event: Callable[..., Any],
    start_time: float,
) -> AsyncGenerator[str, None]:
    model_ids = json.loads(compare.model_config_ids_json)
    configs = await resolve_compare_model_configs(db, model_ids)
    await mark_compare_running(db, compare)

    for config in configs:
        yield await persist_event(
            "compare.model.started",
            {
                "run_id": run.id,
                "model_config_id": config.id,
                "display_name": config.display_name,
                "model_id": config.model_id,
            },
        )

    tasks = [asyncio.create_task(run_compare_candidate(config, run.input_text)) for config in configs]
    candidates: list[CandidateOutput] = []
    for task in asyncio.as_completed(tasks):
        candidate = await task
        candidates.append(candidate)
        await save_compare_result(
            db=db,
            compare=compare,
            model_config_id=candidate.model_config_id,
            display_name=candidate.display_name,
            model_id=candidate.model_id,
            status=candidate.status,
            output_text=candidate.output_text,
            error_message=candidate.error_message,
            duration_ms=candidate.duration_ms,
        )
        event_type = "compare.model.completed" if candidate.status == "completed" else "compare.model.failed"
        yield await persist_event(event_type, {"run_id": run.id, **candidate.to_event_data()})

    if not any(item.status == "completed" for item in candidates):
        raise ValueError("所选模型全部调用失败")

    yield await persist_event(
        "judge.started",
        {"run_id": run.id, "agent_name": "ModelJudgeAgent", "candidate_count": len(candidates)},
    )
    report = await judge_compare_candidates(primary_config, run.input_text, candidates)
    report_data = report.model_dump(mode="json")
    compare = await get_model_compare(db, run.id)
    if compare is None:
        raise ValueError("模型对比记录在评审阶段丢失")
    await complete_model_compare(db, compare, report_data)
    yield await persist_event("judge.completed", {"run_id": run.id, **report_data})

    final_output = format_judge_markdown(report)
    duration_ms = round((time.perf_counter() - start_time) * 1000)
    await complete_agent_run(db=db, run=run, final_output=final_output, duration_ms=duration_ms)
    await create_message(
        db=db,
        conversation_id=run.conversation_id,
        payload=MessageCreate(
            role="assistant",
            content=final_output,
            model=primary_config.model_id,
            agent_name="ModelJudgeAgent",
        ),
    )
    yield await persist_event(
        "run.completed",
        {
            "run_id": run.id,
            "final_output": final_output,
            "duration_ms": duration_ms,
            "last_agent_name": "ModelJudgeAgent",
            "compare_completed": True,
        },
    )


async def run_general_chat(db: AsyncSession, payload: ChatRequest, user_id: str) -> ChatResponse:
    conversation = await get_conversation(
        db=db, conversation_id=payload.conversation_id, user_id=user_id
    )
    model_config = await resolve_model_config(
        db=db,
        model_config_id=payload.primary_model_id,
        conversation_default_model=conversation.default_model,
    )
    agent_mode = resolve_agent_mode(
        requested_mode=payload.agent_mode,
        conversation_mode=conversation.agent_mode,
    )
    if agent_mode is AgentMode.COMPARE:
        raise AppException(message="Compare 模式仅支持 AgentRun + SSE 接口", code=40033)

    built_model = build_chat_model(model_config)
    user_message = await create_message(
        db=db,
        conversation_id=payload.conversation_id,
        payload=MessageCreate(role="user", content=payload.content, model=None, agent_name=None),
        user_id=user_id,
    )
    agent_run = await create_agent_run(
        db=db,
        conversation_id=payload.conversation_id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
        agent_name=agent_name_for_mode(agent_mode),
        model=model_config.model_id,
        input_text=payload.content,
    )
    started = time.perf_counter()

    try:
        if agent_mode is AgentMode.AUTO:
            decision, _ = await resolve_route_decision(built_model, payload.content)
            if decision.specialist == "compare":
                raise AppException(message="自动路由到 Compare 时请使用流式接口", code=40034)
            agent = build_triage_agent(built_model, decision)
        else:
            agent = AgentFactory(built_model=built_model).build(agent_mode)

        result = await Runner.run(agent, payload.content)
        final_output = str(result.final_output or "")
        final_agent_name = result.last_agent.name
        duration_ms = round((time.perf_counter() - started) * 1000)
        await complete_agent_run(db, agent_run, final_output, duration_ms)
        assistant_message = await create_message(
            db=db,
            conversation_id=payload.conversation_id,
            payload=MessageCreate(
                role="assistant",
                content=final_output,
                model=model_config.model_id,
                agent_name=final_agent_name,
            ),
            user_id=user_id,
        )
        return ChatResponse(
            run_id=agent_run.id,
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            model_config_id=model_config.id,
            model=model_config.model_id,
            agent_name=final_agent_name,
            final_output=final_output,
        )
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        await fail_agent_run(db, agent_run, str(exc), duration_ms)
        raise
