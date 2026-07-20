import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.tool_context import ToolContext
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.agents.context import AppRunContext
from backend.app.agents.modes import AgentMode
from backend.app.api.v1.agent_runs import get_owned_run
from backend.app.core.agent_run_status import AgentRunStatus
from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.db.base import Base
from backend.app.models import ModelConfig
from backend.app.models.agent_run import AgentRun
from backend.app.models.conversation import Conversation
from backend.app.models.user import User
from backend.app.services import agent_service, conversation_session
from backend.app.services.agent_run_service import (
    claim_agent_run,
    complete_agent_run,
    create_agent_run,
    request_agent_run_cancel,
)
from backend.app.services.model_compare_service import create_model_compare
from backend.app.services.run_event_service import create_run_event
from backend.app.services.run_runtime import cancellation_registry
from backend.app.tools.basic_tools import get_current_time


class AgentRunLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "agent-runs.sqlite3"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        self.session_patch = patch.object(
            agent_service, "AsyncSessionLocal", self.session_factory
        )
        self.conversation_session_patch = patch.object(
            conversation_session, "AsyncSessionLocal", self.session_factory
        )
        self.session_patch.start()
        self.conversation_session_patch.start()

        async with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id="user-a",
                        username="alice",
                        username_key="alice",
                        password_hash="test",
                    ),
                    User(
                        id="user-b",
                        username="bob",
                        username_key="bob",
                        password_hash="test",
                    ),
                    Conversation(
                        id="conversation-a",
                        title="Lifecycle",
                        agent_mode="general",
                        user_id="user-a",
                    ),
                    ModelConfig(
                        id="model-a",
                        provider="test",
                        display_name="Model A",
                        model_id="model-a",
                        base_url="https://example.invalid/v1",
                        api_key_env="TEST_MODEL_KEY",
                        api_shape="chat_completions",
                        support_streaming=True,
                        support_tools=True,
                        support_image=False,
                        enabled=True,
                    ),
                    ModelConfig(
                        id="model-b",
                        provider="test",
                        display_name="Model B",
                        model_id="model-b",
                        base_url="https://example.invalid/v1",
                        api_key_env="TEST_MODEL_KEY",
                        api_shape="chat_completions",
                        support_streaming=True,
                        support_tools=True,
                        support_image=False,
                        enabled=True,
                    ),
                ]
            )
            await db.commit()

    async def asyncTearDown(self) -> None:
        self.conversation_session_patch.stop()
        self.session_patch.stop()
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def create_pending(self, agent_name: str = "GeneralAgent") -> AgentRun:
        async with self.session_factory() as db:
            return await create_agent_run(
                db,
                conversation_id="conversation-a",
                user_message_id=None,
                model_config_id="model-a",
                agent_name=agent_name,
                model="model-a",
                input_text="hello",
            )

    async def get_run(self, run_id: str) -> AgentRun:
        async with self.session_factory() as db:
            run = await db.get(AgentRun, run_id)
            assert run is not None
            return run

    async def test_created_run_is_pending(self) -> None:
        run = await self.create_pending()
        self.assertEqual(run.status, AgentRunStatus.PENDING.value)
        self.assertIsNone(run.started_at)

    async def test_first_stream_claims_and_duplicate_starts_only_once(self) -> None:
        run = await self.create_pending()
        calls = 0
        release = asyncio.Event()

        async def fake_execute(**kwargs) -> None:
            nonlocal calls
            calls += 1
            await release.wait()
            async with self.session_factory() as db:
                claimed = await db.get(AgentRun, kwargs["run_id"])
                assert claimed is not None
                await complete_agent_run(
                    db,
                    claimed,
                    "done",
                    1,
                    execution_id=kwargs["execution_id"],
                )

        with patch.object(agent_service, "execute_claimed_agent_run", fake_execute):
            results = await asyncio.gather(
                agent_service.start_agent_run_if_pending(run.id, "user-a"),
                agent_service.start_agent_run_if_pending(run.id, "user-a"),
            )
            await asyncio.sleep(0)
            self.assertEqual(sorted(results), [False, True])
            self.assertEqual(calls, 1)
            claimed = await self.get_run(run.id)
            self.assertEqual(claimed.status, AgentRunStatus.RUNNING.value)
            self.assertIsNotNone(claimed.started_at)
            release.set()
            for _ in range(50):
                if not await cancellation_registry.has_running_task(run.id):
                    break
                await asyncio.sleep(0.01)

    async def test_completed_run_reconnect_does_not_execute(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            claimed = await claim_agent_run(db, run.id, "execution-complete")
            assert claimed is not None
            await complete_agent_run(
                db, claimed, "done", 2, execution_id="execution-complete"
            )
        started = await agent_service.start_agent_run_if_pending(run.id, "user-a")
        self.assertFalse(started)
        self.assertEqual((await self.get_run(run.id)).status, "completed")

    async def test_pending_run_can_be_cancelled(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            transition = await request_agent_run_cancel(db, run.id)
        self.assertFalse(transition.idempotent)
        self.assertEqual(transition.run.status, AgentRunStatus.CANCELLED.value)
        self.assertIsNotNone(transition.run.finished_at)
        self.assertIsNotNone(transition.run.cancelled_at)

    async def test_running_run_can_be_cancelled(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            claimed = await claim_agent_run(db, run.id, "execution-cancel")
        assert claimed is not None

        async def wait_forever(**kwargs) -> None:
            await asyncio.Event().wait()

        with patch.object(agent_service, "_execute_agent_pipeline", wait_forever):
            task = await cancellation_registry.start(
                run.id,
                lambda cancellation_event: agent_service.execute_claimed_agent_run(
                    run_id=run.id,
                    user_id="user-a",
                    execution_id="execution-cancel",
                    cancellation_event=cancellation_event,
                ),
            )
            await asyncio.sleep(0.01)
            async with self.session_factory() as db:
                transition = await request_agent_run_cancel(db, run.id)
            self.assertIsNotNone(transition.run.cancel_requested_at)
            self.assertTrue(await cancellation_registry.cancel(run.id))
            await task

        cancelled = await self.get_run(run.id)
        self.assertEqual(cancelled.status, AgentRunStatus.CANCELLED.value)
        self.assertIsNotNone(cancelled.finished_at)

    async def test_compare_cancellation_cancels_candidate_tasks(self) -> None:
        run = await self.create_pending("CompareAgent")
        async with self.session_factory() as db:
            claimed = await claim_agent_run(db, run.id, "execution-compare")
            assert claimed is not None
            compare = await create_model_compare(db, run.id, ["model-a", "model-b"])
            primary = await db.get(ModelConfig, "model-a")
            assert primary is not None

        child_started = asyncio.Event()
        child_cancelled = asyncio.Event()

        async def sleeping_candidate(*args, **kwargs):
            child_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                child_cancelled.set()

        context = AppRunContext(
            user_id="user-a",
            conversation_id="conversation-a",
            run_id=run.id,
            selected_model_id="model-a",
            agent_mode="compare",
            permissions=frozenset({"tool.basic"}),
        )

        async def consume() -> None:
            async with self.session_factory() as db:
                current = await db.get(AgentRun, run.id)
                current_compare = await agent_service.get_model_compare(db, run.id)
                current_primary = await db.get(ModelConfig, "model-a")
                assert current and current_compare and current_primary
                session = conversation_session.AppConversationSession(
                    "conversation-a", "user-a"
                )

                async def persist_event(*args, **kwargs):
                    return None

                async for _ in agent_service._stream_compare_pipeline(
                    db=db,
                    run=current,
                    compare=current_compare,
                    primary_config=current_primary,
                    session=session,
                    context=context,
                    execution_id="execution-compare",
                    cancellation_event=asyncio.Event(),
                    persist_event=persist_event,
                    start_time=0.0,
                ):
                    pass

        with patch.object(agent_service, "run_compare_candidate", sleeping_candidate):
            consumer = asyncio.create_task(consume())
            await asyncio.wait_for(child_started.wait(), timeout=1)
            consumer.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await consumer
        self.assertTrue(child_cancelled.is_set())

    async def test_timeout_sets_terminal_status(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            claimed = await claim_agent_run(db, run.id, "execution-timeout")
        assert claimed is not None

        async def slow_pipeline(**kwargs) -> None:
            await asyncio.sleep(1)

        with (
            patch.object(agent_service, "_execute_agent_pipeline", slow_pipeline),
            patch.object(settings, "AGENT_RUN_TIMEOUT_SECONDS", 0.01),
        ):
            await agent_service.execute_claimed_agent_run(
                run_id=run.id,
                user_id="user-a",
                execution_id="execution-timeout",
                cancellation_event=asyncio.Event(),
            )
        timed_out = await self.get_run(run.id)
        self.assertEqual(timed_out.status, AgentRunStatus.TIMEOUT.value)
        self.assertIsNotNone(timed_out.finished_at)

    async def test_other_user_cannot_access_run_for_stream_or_cancel(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            owned = await get_owned_run(db, run.id, "user-a")
            self.assertEqual(owned.id, run.id)
            with self.assertRaises(AppException):
                await get_owned_run(db, run.id, "user-b")

    async def test_last_event_id_replays_only_missing_events(self) -> None:
        run = await self.create_pending()
        async with self.session_factory() as db:
            claimed = await claim_agent_run(db, run.id, "execution-replay")
            assert claimed is not None
            await create_run_event(
                db, run.id, "run.started", {"run_id": run.id}
            )
            await complete_agent_run(
                db, claimed, "done", 3, execution_id="execution-replay"
            )
            await create_run_event(
                db,
                run.id,
                "run.completed",
                {"run_id": run.id, "final_output": "done"},
            )

        chunks = [
            item
            async for item in agent_service.stream_agent_run(
                run.id, "user-a", last_event_id=1
            )
        ]
        payload = "".join(chunks)
        self.assertNotIn("event: run.started", payload)
        self.assertIn("id: 2", payload)
        self.assertIn("event: run.completed", payload)

    async def test_app_run_context_is_readable_in_function_tool(self) -> None:
        context = AppRunContext(
            user_id="user-a",
            conversation_id="conversation-a",
            run_id="run-context",
            selected_model_id="model-a",
            agent_mode=AgentMode.GENERAL.value,
            permissions=frozenset({"tool.basic"}),
        )
        result = await get_current_time.on_invoke_tool(
            ToolContext(
                context=context,
                tool_name="get_current_time",
                tool_call_id="call-context",
                tool_arguments='{"timezone":"UTC"}',
            ),
            '{"timezone":"UTC"}',
        )
        self.assertIn("UTC", str(result))


if __name__ == "__main__":
    unittest.main()
