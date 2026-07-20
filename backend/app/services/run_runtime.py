from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LiveRunEvent:
    event_type: str
    data: dict[str, Any]


class CancellationRegistry:
    """Best-effort in-process cancellation; database state remains authoritative."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        run_id: str,
        execute: Callable[[asyncio.Event], Awaitable[None]],
    ) -> asyncio.Task[None]:
        async with self._lock:
            existing = self._tasks.get(run_id)
            if existing is not None and not existing.done():
                return existing
            cancellation_event = asyncio.Event()
            task = asyncio.create_task(
                execute(cancellation_event),
                name=f"agent-run:{run_id}",
            )
            self._tasks[run_id] = task
            self._events[run_id] = cancellation_event
            task.add_done_callback(
                lambda completed, rid=run_id: asyncio.create_task(self._remove(rid, completed))
            )
            return task

    async def _remove(self, run_id: str, completed: asyncio.Task[None]) -> None:
        async with self._lock:
            if self._tasks.get(run_id) is completed:
                self._tasks.pop(run_id, None)
                self._events.pop(run_id, None)

    async def cancel(self, run_id: str) -> bool:
        async with self._lock:
            event = self._events.get(run_id)
            task = self._tasks.get(run_id)
            if event is not None:
                event.set()
            if task is None or task.done():
                return False
            task.cancel()
            return True

    async def cancel_and_wait(self, run_id: str, timeout: float = 1.0) -> bool:
        async with self._lock:
            event = self._events.get(run_id)
            task = self._tasks.get(run_id)
            if event is not None:
                event.set()
            if task is None or task.done():
                return False
            task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.CancelledError, TimeoutError):
            pass
        return True

    async def has_running_task(self, run_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(run_id)
            return task is not None and not task.done()


class RunEventBroker:
    """Fan out non-persisted token deltas to all local SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[LiveRunEvent]]] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[asyncio.Queue[LiveRunEvent]]:
        queue: asyncio.Queue[LiveRunEvent] = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subscribers.setdefault(run_id, set()).add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(run_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(run_id, None)

    async def publish(self, run_id: str, event_type: str, data: dict[str, Any]) -> None:
        event = LiveRunEvent(event_type=event_type, data=data)
        async with self._lock:
            queues = tuple(self._subscribers.get(run_id, ()))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Persisted token chunks and partial_output recover a slow client.
                pass


cancellation_registry = CancellationRegistry()
run_event_broker = RunEventBroker()
