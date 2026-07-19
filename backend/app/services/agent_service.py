from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from uuid import uuid4

from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.context import AppRunContext
from backend.app.agents.factory import AgentFactory
from backend.app.agents.modes import (
    AgentMode,
    agent_name_for_mode,
    mode_from_agent_name,
    resolve_agent_mode,
)
from backend.app.agents.routing import resolve_route_decision
from backend.app.agents.triage_agent import build_triage_agent
from backend.app.core.agent_run_status import AgentRunStatus, TERMINAL_AGENT_RUN_STATUSES
from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.db.session import AsyncSessionLocal
from backend.app.models import ModelConfig
from backend.app.models.agent_run import AgentRun
from backend.app.models.model_compare import ModelCompare
from backend.app.models.run_event import RunEvent
from backend.app.models.tool_call import ToolCall
from backend.app.schemas.agent_run import AgentRunCreateRequest, AgentRunCreateResponse
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.message import MessageCreate
from backend.app.services.agent_run_service import (
    cancel_agent_run,
    claim_agent_run,
    complete_agent_run,
    create_agent_run,
    fail_agent_run,
    is_cancel_requested,
    timeout_agent_run,
    update_partial_output,
)
from backend.app.services.compare_runner import (
    CandidateOutput,
    format_judge_markdown,
    judge_compare_candidates,
    run_compare_candidate,
)
from backend.app.services.conversation_session import AppConversationSession
from backend.app.services.conversation_service import get_conversation
from backend.app.services.event_normalizer import normalize_stream_event
from backend.app.services.message_service import create_message
from backend.app.services.model_compare_service import (
    cancel_model_compare,
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
from backend.app.services.run_event_service import create_run_event, list_run_events
from backend.app.services.run_runtime import (
    cancellation_registry,
    run_event_broker,
)
from backend.app.services.system_exception_service import record_system_exception
from backend.app.services.token_usage_service import extract_token_usage, record_token_usage
from backend.app.services.tool_call_service import complete_tool_call, create_tool_call


PersistEvent = Callable[..., Awaitable[RunEvent | None]]


def format_sse_event(event: str, data: dict[str, Any], event_id: int) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def _safe_error_message(exc: BaseException, fallback: str = "Agent 执行失败") -> str:
    if isinstance(exc, AppException):
        raw = exc.message
    else:
        raw = str(exc).strip() or fallback
    raw = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1***", raw)
    raw = re.sub(
        r"(?i)(api[_-]?key|authorization|cookie|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2***",
        raw,
    )
    return raw[:500]


def _build_run_context(
    *,
    run: AgentRun,
    user_id: str,
    model_config_id: str,
    agent_mode: AgentMode,
) -> AppRunContext:
    permissions = {"tool.basic"}
    if agent_mode in {AgentMode.AUTO, AgentMode.IMAGE}:
        permissions.add("image.generate")
    return AppRunContext(
        user_id=user_id,
        conversation_id=run.conversation_id,
        run_id=run.id,
        selected_model_id=model_config_id,
        agent_mode=agent_mode.value,
        permissions=frozenset(permissions),
    )


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
            item.id for item in available if item.api_shape == "chat_completions"
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
    agent_mode = resolve_agent_mode(payload.agent_mode, conversation.agent_mode)
    entry_agent_name = agent_name_for_mode(agent_mode)
    if agent_mode is not AgentMode.COMPARE and not model_config.support_streaming:
        raise AppException(
            message=f"当前模型不支持流式输出：{model_config.display_name}",
            code=40032,
        )

    compare_configs: list[ModelConfig] = []
    if agent_mode is AgentMode.COMPARE:
        compare_configs = await resolve_compare_model_configs(db, payload.compare_model_ids)

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
        status=AgentRunStatus.PENDING,
        stream_url=f"/api/agent-runs/{agent_run.id}/stream",
    )


async def start_agent_run_if_pending(run_id: str, user_id: str) -> bool:
    execution_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        claimed = await claim_agent_run(db, run_id, execution_id)
    if claimed is None:
        return False

    await cancellation_registry.start(
        run_id,
        lambda cancellation_event: execute_claimed_agent_run(
            run_id=run_id,
            user_id=user_id,
            execution_id=execution_id,
            cancellation_event=cancellation_event,
        ),
    )
    return True


async def stream_agent_run(
    run_id: str,
    user_id: str,
    last_event_id: int = 0,
) -> AsyncGenerator[str, None]:
    """Attach to a run, replay missed persisted events, and follow live progress."""

    cursor = max(0, last_event_id)
    delivered_chars = 0
    seen_terminal = False
    async with run_event_broker.subscribe(run_id) as live_queue:
        await start_agent_run_if_pending(run_id, user_id)

        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            if run is None:
                yield format_sse_event(
                    "run.error",
                    {"run_id": run_id, "message": "Agent运行记录不存在"},
                    cursor,
                )
                return
            if run.partial_output:
                delivered_chars = len(run.partial_output)
                yield format_sse_event(
                    "run.snapshot",
                    {
                        "run_id": run.id,
                        "status": run.status,
                        "partial_output": run.partial_output,
                        "output_chars": delivered_chars,
                    },
                    cursor,
                )

            initial_events = await list_run_events(db, run_id, after_seq=cursor)
            for item in initial_events:
                cursor = item.seq
                seen_terminal = seen_terminal or item.event_type in {
                    "run.completed",
                    "run.failed",
                    "run.cancelled",
                    "run.timeout",
                    "run.interrupted",
                }
                yield format_sse_event(item.event_type, item.payload_json, item.seq)

        while True:
            async with AsyncSessionLocal() as db:
                persisted = await list_run_events(db, run_id, after_seq=cursor)
                for item in persisted:
                    cursor = item.seq
                    seen_terminal = seen_terminal or item.event_type in {
                        "run.completed",
                        "run.failed",
                        "run.cancelled",
                        "run.timeout",
                        "run.interrupted",
                    }
                    yield format_sse_event(item.event_type, item.payload_json, item.seq)
                run = await db.get(AgentRun, run_id)

            if run is None:
                return

            try:
                live = await asyncio.wait_for(live_queue.get(), timeout=0.15)
            except TimeoutError:
                live = None

            if live is not None:
                data = live.data
                start = int(data.get("offset_start") or 0)
                end = int(data.get("offset_end") or start)
                delta = str(data.get("delta") or "")
                if end > delivered_chars:
                    if start < delivered_chars:
                        delta = delta[delivered_chars - start :]
                        start = delivered_chars
                    delivered_chars = end
                    if delta:
                        yield format_sse_event(
                            live.event_type,
                            {**data, "delta": delta, "offset_start": start},
                            cursor,
                        )

            status = AgentRunStatus(run.status)
            if status in TERMINAL_AGENT_RUN_STATUSES:
                if not persisted and live_queue.empty():
                    if not seen_terminal:
                        event_type = f"run.{status.value}"
                        data: dict[str, Any] = {
                            "run_id": run.id,
                            "status": status.value,
                            "duration_ms": run.duration_ms,
                            "message": run.error_message,
                        }
                        if status is AgentRunStatus.COMPLETED:
                            data["final_output"] = run.final_output or run.partial_output or ""
                        yield format_sse_event(event_type, data, max(cursor, run.event_seq))
                    return


async def execute_claimed_agent_run(
    *,
    run_id: str,
    user_id: str,
    execution_id: str,
    cancellation_event: asyncio.Event,
) -> None:
    start_time = time.perf_counter()
    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, run_id)
        if (
            run is None
            or run.status != AgentRunStatus.RUNNING.value
            or run.execution_id != execution_id
        ):
            return

        async def persist_event(
            event_type: str,
            data: dict[str, Any],
            event_name: str | None = None,
            *,
            persist: bool = True,
        ) -> RunEvent | None:
            if not persist:
                await run_event_broker.publish(run.id, event_type, data)
                return None
            return await create_run_event(
                db=db,
                run_id=run.id,
                event_type=event_type,
                event_name=event_name,
                payload=data,
            )

        try:
            async with asyncio.timeout(settings.AGENT_RUN_TIMEOUT_SECONDS):
                await _execute_agent_pipeline(
                    db=db,
                    run=run,
                    user_id=user_id,
                    execution_id=execution_id,
                    cancellation_event=cancellation_event,
                    persist_event=persist_event,
                    start_time=start_time,
                )
        except TimeoutError:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            message = f"Agent 运行超过 {settings.AGENT_RUN_TIMEOUT_SECONDS:g} 秒，已超时终止"
            updated = await timeout_agent_run(
                db, run, message, duration_ms, execution_id=execution_id
            )
            compare = await get_model_compare(db, run.id)
            if compare is not None and compare.status not in {"completed", "timeout"}:
                await cancel_model_compare(db, compare, "timeout")
            if updated is not None:
                await persist_event(
                    "run.timeout",
                    {"run_id": run.id, "status": "timeout", "message": message, "duration_ms": duration_ms},
                )
        except asyncio.CancelledError:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            updated = await cancel_agent_run(db, run, duration_ms, execution_id=execution_id)
            compare = await get_model_compare(db, run.id)
            if compare is not None and compare.status not in {"completed", "cancelled"}:
                await cancel_model_compare(db, compare, "cancelled")
            if updated is not None:
                await persist_event(
                    "run.cancelled",
                    {
                        "run_id": run.id,
                        "status": "cancelled",
                        "cancelled_at": updated.cancelled_at.isoformat() if updated.cancelled_at else None,
                        "partial_output": updated.partial_output or "",
                        "duration_ms": duration_ms,
                    },
                )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            message = _safe_error_message(exc)
            try:
                await fail_agent_run(db, run, message, duration_ms, execution_id=execution_id)
            except RuntimeError:
                return
            await record_system_exception(
                db,
                message=message,
                category="agent_run",
                level="error",
                run_id=run.id,
                user_id=user_id,
                detail={"model": run.model, "agent_name": run.agent_name},
            )
            compare = await get_model_compare(db, run.id)
            if compare is not None and compare.status != "completed":
                await fail_model_compare(db, compare)
            data = {"run_id": run.id, "status": "failed", "message": message, "duration_ms": duration_ms}
            await persist_event("run.failed", data)
            await persist_event("run.error", data)


async def _execute_agent_pipeline(
    *,
    db: AsyncSession,
    run: AgentRun,
    user_id: str,
    execution_id: str,
    cancellation_event: asyncio.Event,
    persist_event: PersistEvent,
    start_time: float,
) -> None:
    if run.model_config_id is None:
        raise ValueError("AgentRun 缺少 model_config_id")
    primary_config = await get_model_config(db=db, model_config_id=run.model_config_id)
    built_model = build_chat_model(primary_config)
    agent_mode = mode_from_agent_name(run.agent_name)
    context = _build_run_context(
        run=run,
        user_id=user_id,
        model_config_id=primary_config.id,
        agent_mode=agent_mode,
    )
    session = AppConversationSession(
        conversation_id=run.conversation_id,
        user_id=user_id,
        pending_user_message_id=run.user_message_id,
        model=run.model,
        agent_name=run.agent_name,
    )

    await persist_event(
        "run.started",
        {
            "run_id": run.id,
            "execution_id": execution_id,
            "agent_name": run.agent_name,
            "agent_mode": agent_mode.value,
            "model": primary_config.model_id,
        },
    )
    if cancellation_event.is_set():
        raise asyncio.CancelledError

    if agent_mode is AgentMode.AUTO:
        await persist_event("route.started", {"run_id": run.id, "agent_name": "TriageRouteAgent"})
        decision, route_source = await resolve_route_decision(
            built_model, run.input_text, context
        )
        await persist_event(
            "route.decision",
            {"run_id": run.id, **decision.model_dump(mode="json"), "source": route_source},
        )
        if decision.specialist == "compare":
            compare = await get_model_compare(db, run.id)
            if compare is None:
                configs = await resolve_compare_model_configs(db, [], use_defaults=True)
                compare = await create_model_compare(db, run.id, [item.id for item in configs])
            async for _ in _stream_compare_pipeline(
                db=db,
                run=run,
                compare=compare,
                primary_config=primary_config,
                session=session,
                context=context,
                execution_id=execution_id,
                cancellation_event=cancellation_event,
                persist_event=persist_event,
                start_time=start_time,
            ):
                pass
            return
        agent = build_triage_agent(built_model, decision)
    elif agent_mode is AgentMode.COMPARE:
        compare = await get_model_compare(db, run.id)
        if compare is None:
            raise ValueError("Compare AgentRun 缺少模型对比配置")
        async for _ in _stream_compare_pipeline(
            db=db,
            run=run,
            compare=compare,
            primary_config=primary_config,
            session=session,
            context=context,
            execution_id=execution_id,
            cancellation_event=cancellation_event,
            persist_event=persist_event,
            start_time=start_time,
        ):
            pass
        return
    else:
        agent = AgentFactory(built_model=built_model).build(agent_mode)

    async for _ in _stream_standard_agent(
        db=db,
        run=run,
        agent=agent,
        model_config=primary_config,
        session=session,
        context=context,
        execution_id=execution_id,
        cancellation_event=cancellation_event,
        persist_event=persist_event,
        start_time=start_time,
    ):
        pass


async def _stream_standard_agent(
    *,
    db: AsyncSession,
    run: AgentRun,
    agent: Agent,
    model_config: ModelConfig,
    session: AppConversationSession,
    context: AppRunContext,
    execution_id: str,
    cancellation_event: asyncio.Event,
    persist_event: PersistEvent,
    start_time: float,
) -> AsyncGenerator[None, None]:
    output_parts: list[str] = []
    output_length = 0
    chunk_start = 0
    last_chunk_at = time.monotonic()
    flush_lock = asyncio.Lock()
    pending_calls: dict[str, tuple[str, float]] = {}
    pending_without_id: list[tuple[str, float]] = []

    async def flush_chunk(
        chunk_db: AsyncSession,
        *,
        force: bool = False,
        check_cancellation: bool = True,
    ) -> None:
        nonlocal chunk_start, last_chunk_at
        async with flush_lock:
            output = "".join(output_parts)
            chunk = output[chunk_start:]
            elapsed = time.monotonic() - last_chunk_at
            if not chunk:
                return
            if (
                not force
                and len(chunk) < settings.AGENT_TOKEN_CHUNK_CHARS
                and elapsed < settings.AGENT_TOKEN_CHUNK_SECONDS
            ):
                return
            if check_cancellation and (
                cancellation_event.is_set()
                or await is_cancel_requested(chunk_db, run.id, execution_id)
            ):
                raise asyncio.CancelledError
            await update_partial_output(
                chunk_db,
                run_id=run.id,
                execution_id=execution_id,
                partial_output=output,
            )
            await create_run_event(
                chunk_db,
                run_id=run.id,
                event_type="token.chunk",
                payload={
                    "run_id": run.id,
                    "chunk": chunk,
                    "offset_start": chunk_start,
                    "offset_end": len(output),
                },
            )
            chunk_start = len(output)
            last_chunk_at = time.monotonic()

    owner_task = asyncio.current_task()

    async def periodic_chunk_flush() -> None:
        interval = max(0.05, settings.AGENT_TOKEN_CHUNK_SECONDS)
        while True:
            await asyncio.sleep(interval)
            async with AsyncSessionLocal() as chunk_db:
                if cancellation_event.is_set() or await is_cancel_requested(
                    chunk_db, run.id, execution_id
                ):
                    if owner_task is not None:
                        owner_task.cancel()
                    return
                await flush_chunk(
                    chunk_db,
                    force=True,
                    check_cancellation=False,
                )

    result = Runner.run_streamed(
        agent,
        input=run.input_text,
        session=session,
        context=context,
    )
    chunk_flush_task = asyncio.create_task(
        periodic_chunk_flush(),
        name=f"agent-run-chunk-flush:{run.id}",
    )
    try:
        async for event in result.stream_events():
            if cancellation_event.is_set():
                raise asyncio.CancelledError
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
                    offset_start = output_length
                    output_parts.append(delta)
                    output_length += len(delta)
                    normalized.data.update(
                        {"offset_start": offset_start, "offset_end": output_length}
                    )

            await persist_event(
                normalized.event_type,
                normalized.data,
                normalized.event_name,
                persist=normalized.persist,
            )
            if normalized.event_type == "token.delta":
                await flush_chunk(db)
            yield None
    except asyncio.CancelledError:
        chunk_flush_task.cancel()
        await asyncio.gather(chunk_flush_task, return_exceptions=True)
        result.cancel("immediate")
        await flush_chunk(db, force=True, check_cancellation=False)
        raise
    finally:
        chunk_flush_task.cancel()
        await asyncio.gather(chunk_flush_task, return_exceptions=True)

    if result.run_loop_exception:
        raise result.run_loop_exception
    await flush_chunk(db, force=True)
    final_output = str(result.final_output or "".join(output_parts))
    final_agent_name = result.last_agent.name
    duration_ms = round((time.perf_counter() - start_time) * 1000)
    await complete_agent_run(
        db, run, final_output, duration_ms, execution_id=execution_id
    )
    await record_token_usage(
        db,
        run_id=run.id,
        model_config_id=model_config.id,
        model=model_config.model_id,
        usage_type="agent",
        usage=extract_token_usage(result),
    )
    await session.annotate_last_assistant(model=model_config.model_id, agent_name=final_agent_name)
    await persist_event(
        "run.completed",
        {
            "run_id": run.id,
            "status": "completed",
            "final_output": final_output,
            "duration_ms": duration_ms,
            "last_agent_name": final_agent_name,
        },
    )
    yield None


async def _stream_compare_pipeline(
    *,
    db: AsyncSession,
    run: AgentRun,
    compare: ModelCompare,
    primary_config: ModelConfig,
    session: AppConversationSession,
    context: AppRunContext,
    execution_id: str,
    cancellation_event: asyncio.Event,
    persist_event: PersistEvent,
    start_time: float,
) -> AsyncGenerator[None, None]:
    history = await session.get_items()
    current_input = {"role": "user", "content": run.input_text}
    await session.add_items([current_input])
    candidate_input = [*history, current_input]
    configs = await resolve_compare_model_configs(db, json.loads(compare.model_config_ids_json))
    await mark_compare_running(db, compare)

    for config in configs:
        await persist_event(
            "compare.model.started",
            {
                "run_id": run.id,
                "model_config_id": config.id,
                "display_name": config.display_name,
                "model_id": config.model_id,
            },
        )
        yield None

    tasks = [
        asyncio.create_task(run_compare_candidate(config, candidate_input, context))
        for config in configs
    ]
    candidates: list[CandidateOutput] = []
    try:
        for task in asyncio.as_completed(tasks):
            candidate = await task
            if cancellation_event.is_set() or await is_cancel_requested(db, run.id, execution_id):
                raise asyncio.CancelledError
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
            await record_token_usage(
                db,
                run_id=run.id,
                model_config_id=candidate.model_config_id,
                model=candidate.model_id,
                usage_type="compare_candidate",
                usage=(candidate.input_tokens, candidate.output_tokens, candidate.total_tokens),
            )
            event_type = (
                "compare.model.completed" if candidate.status == "completed" else "compare.model.failed"
            )
            await persist_event(event_type, {"run_id": run.id, **candidate.to_event_data()})
            yield None
    finally:
        unfinished = [task for task in tasks if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)

    if not any(item.status == "completed" for item in candidates):
        raise ValueError("所选模型全部调用失败")

    await persist_event(
        "judge.started",
        {"run_id": run.id, "agent_name": "ModelJudgeAgent", "candidate_count": len(candidates)},
    )
    yield None
    report, judge_usage = await judge_compare_candidates(
        primary_config, run.input_text, candidates, context
    )
    report_data = report.model_dump(mode="json")
    compare = await get_model_compare(db, run.id)
    if compare is None:
        raise ValueError("模型对比记录在评审阶段丢失")
    await complete_model_compare(db, compare, report_data)
    await persist_event("judge.completed", {"run_id": run.id, **report_data})
    yield None

    final_output = format_judge_markdown(report)
    duration_ms = round((time.perf_counter() - start_time) * 1000)
    await update_partial_output(
        db,
        run_id=run.id,
        execution_id=execution_id,
        partial_output=final_output,
    )
    await complete_agent_run(
        db, run, final_output, duration_ms, execution_id=execution_id
    )
    await record_token_usage(
        db,
        run_id=run.id,
        model_config_id=primary_config.id,
        model=primary_config.model_id,
        usage_type="judge",
        usage=judge_usage,
    )
    await session.add_items([{"role": "assistant", "content": final_output}])
    await session.annotate_last_assistant(
        model=primary_config.model_id, agent_name="ModelJudgeAgent"
    )
    await persist_event(
        "run.completed",
        {
            "run_id": run.id,
            "status": "completed",
            "final_output": final_output,
            "duration_ms": duration_ms,
            "last_agent_name": "ModelJudgeAgent",
            "compare_completed": True,
        },
    )
    yield None


async def run_general_chat(db: AsyncSession, payload: ChatRequest, user_id: str) -> ChatResponse:
    conversation = await get_conversation(
        db=db, conversation_id=payload.conversation_id, user_id=user_id
    )
    model_config = await resolve_model_config(
        db, payload.primary_model_id, conversation.default_model
    )
    agent_mode = resolve_agent_mode(payload.agent_mode, conversation.agent_mode)
    if agent_mode is AgentMode.COMPARE:
        raise AppException(message="Compare 模式仅支持 AgentRun + SSE 接口", code=40033)

    built_model = build_chat_model(model_config)
    user_message = await create_message(
        db=db,
        conversation_id=payload.conversation_id,
        payload=MessageCreate(role="user", content=payload.content, model=None, agent_name=None),
        user_id=user_id,
    )
    session = AppConversationSession(
        conversation_id=payload.conversation_id,
        user_id=user_id,
        pending_user_message_id=user_message.id,
        model=model_config.model_id,
        agent_name=agent_name_for_mode(agent_mode),
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
    execution_id = str(uuid4())
    claimed = await claim_agent_run(db, agent_run.id, execution_id)
    if claimed is None:
        raise RuntimeError("AgentRun 原子领取失败")
    agent_run = claimed
    context = _build_run_context(
        run=agent_run,
        user_id=user_id,
        model_config_id=model_config.id,
        agent_mode=agent_mode,
    )
    started = time.perf_counter()

    try:
        async with asyncio.timeout(settings.AGENT_RUN_TIMEOUT_SECONDS):
            if agent_mode is AgentMode.AUTO:
                decision, _ = await resolve_route_decision(
                    built_model, payload.content, context
                )
                if decision.specialist == "compare":
                    raise AppException(message="自动路由到 Compare 时请使用流式接口", code=40034)
                agent = build_triage_agent(built_model, decision)
            else:
                agent = AgentFactory(built_model=built_model).build(agent_mode)

            result = await Runner.run(
                agent,
                payload.content,
                session=session,
                context=context,
            )
        final_output = str(result.final_output or "")
        final_agent_name = result.last_agent.name
        duration_ms = round((time.perf_counter() - started) * 1000)
        await complete_agent_run(
            db, agent_run, final_output, duration_ms, execution_id=execution_id
        )
        await record_token_usage(
            db,
            run_id=agent_run.id,
            model_config_id=model_config.id,
            model=model_config.model_id,
            usage_type="agent",
            usage=extract_token_usage(result),
        )
        assistant_message_id = await session.annotate_last_assistant(
            model=model_config.model_id, agent_name=final_agent_name
        )
        if assistant_message_id is None:
            raise RuntimeError("Session 未保存 Agent 助手消息")
        return ChatResponse(
            run_id=agent_run.id,
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message_id,
            model_config_id=model_config.id,
            model=model_config.model_id,
            agent_name=final_agent_name,
            final_output=final_output,
        )
    except TimeoutError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        message = f"Agent 运行超过 {settings.AGENT_RUN_TIMEOUT_SECONDS:g} 秒，已超时终止"
        await timeout_agent_run(db, agent_run, message, duration_ms, execution_id)
        raise AppException(message=message, code=40801, status_code=408) from exc
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        message = _safe_error_message(exc)
        await fail_agent_run(db, agent_run, message, duration_ms, execution_id=execution_id)
        await record_system_exception(
            db,
            message=message,
            category="agent_run",
            level="error",
            run_id=agent_run.id,
            user_id=user_id,
            detail={"model": agent_run.model, "agent_name": agent_run.agent_name},
        )
        raise
