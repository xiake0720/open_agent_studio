from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from agents.items import TResponseInputItem
from agents.memory import SessionSettings
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AppException
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message


def _jsonable_item(item: TResponseInputItem) -> dict[str, Any]:
    if isinstance(item, Mapping):
        value: Any = dict(item)
    elif hasattr(item, "model_dump"):
        value = item.model_dump(mode="json", exclude_none=True)
    else:
        raise TypeError(f"不支持的 SDK Session item 类型：{type(item)!r}")

    # 做一次 JSON 往返，确保写入数据库的对象与 SDK 下次读到的对象一致。
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    loaded = json.loads(serialized)
    if not isinstance(loaded, dict):
        raise TypeError("SDK Session item 必须序列化为 JSON object")
    return loaded


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_extract_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, Mapping):
        for key in ("text", "output", "content"):
            if key in value:
                text = _extract_text(value[key])
                if text:
                    return text
    return ""


def _message_projection(item: dict[str, Any]) -> tuple[str, str, bool]:
    item_type = str(item.get("type") or "")
    raw_role = str(item.get("role") or "")

    if raw_role in {"user", "assistant", "system", "developer"}:
        role = "system" if raw_role == "developer" else raw_role
        content = _extract_text(item.get("content"))
        visible = role in {"user", "assistant"}
    elif item_type in {
        "function_call_output",
        "computer_call_output",
        "local_shell_call_output",
        "shell_call_output",
        "apply_patch_call_output",
        "custom_tool_call_output",
    }:
        role = "tool"
        content = _extract_text(item.get("output"))
        visible = False
    else:
        role = "tool"
        content = _extract_text(item.get("content")) or _extract_text(item.get("arguments"))
        visible = False

    if not content:
        content = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    return role, content, visible


def _legacy_message_item(message: Message) -> TResponseInputItem | None:
    if message.role not in {"user", "assistant", "system"}:
        return None
    return cast(
        TResponseInputItem,
        {"role": message.role, "content": message.content},
    )


class AppConversationSession:
    """使用应用现有 messages 表实现 Agents SDK Session 协议。"""

    def __init__(
        self,
        conversation_id: str,
        user_id: str,
        *,
        pending_user_message_id: str | None = None,
        model: str | None = None,
        agent_name: str | None = None,
        session_settings: SessionSettings | None = None,
    ) -> None:
        self.session_id = conversation_id
        self.user_id = user_id
        self.pending_user_message_id = pending_user_message_id
        self.model = model
        self.agent_name = agent_name
        self.session_settings = session_settings or SessionSettings()
        self.last_assistant_message_id: str | None = None

    async def _ensure_owned(self, db: AsyncSession) -> None:
        owned = await db.scalar(
            select(Conversation.id).where(
                Conversation.id == self.session_id,
                Conversation.user_id == self.user_id,
            )
        )
        if owned is None:
            raise AppException(
                message="会话不存在",
                code=40401,
                data={"conversation_id": self.session_id},
            )

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]:
        resolved_limit = limit if limit is not None else self.session_settings.limit
        async with AsyncSessionLocal() as db:
            await self._ensure_owned(db)
            stmt = select(Message).where(Message.conversation_id == self.session_id)
            if self.pending_user_message_id is not None:
                stmt = stmt.where(Message.id != self.pending_user_message_id)

            if resolved_limit is None:
                stmt = stmt.order_by(Message.sequence_no.asc(), Message.created_at.asc())
                rows = list((await db.execute(stmt)).scalars().all())
            else:
                if resolved_limit <= 0:
                    return []
                stmt = stmt.order_by(desc(Message.sequence_no), desc(Message.created_at)).limit(
                    resolved_limit
                )
                rows = list(reversed((await db.execute(stmt)).scalars().all()))

            items: list[TResponseInputItem] = []
            for row in rows:
                if row.sdk_item_json:
                    try:
                        item = json.loads(row.sdk_item_json)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(item, dict):
                        items.append(cast(TResponseInputItem, item))
                    continue
                legacy_item = _legacy_message_item(row)
                if legacy_item is not None:
                    items.append(legacy_item)
            return items

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        if not items:
            return

        normalized = [_jsonable_item(item) for item in items]
        async with AsyncSessionLocal() as db:
            await self._ensure_owned(db)
            next_sequence = int(
                await db.scalar(
                    select(func.max(Message.sequence_no)).where(
                        Message.conversation_id == self.session_id
                    )
                )
                or 0
            ) + 1

            pending: Message | None = None
            if self.pending_user_message_id is not None:
                pending = await db.scalar(
                    select(Message).where(
                        Message.id == self.pending_user_message_id,
                        Message.conversation_id == self.session_id,
                    )
                )

            for item in normalized:
                role, content, visible = _message_projection(item)
                serialized = json.dumps(item, ensure_ascii=False, separators=(",", ":"))

                if pending is not None and role == "user" and pending.sdk_item_json is None:
                    pending.sdk_item_json = serialized
                    pending.content = content
                    pending.is_visible = True
                    pending = None
                    self.pending_user_message_id = None
                    continue

                message = Message(
                    conversation_id=self.session_id,
                    role=role,
                    content=content,
                    model=self.model if role == "assistant" else None,
                    agent_name=self.agent_name if role == "assistant" else None,
                    sdk_item_json=serialized,
                    is_visible=visible,
                    sequence_no=next_sequence,
                )
                next_sequence += 1
                db.add(message)
                await db.flush()
                if role == "assistant":
                    self.last_assistant_message_id = message.id

            await db.execute(
                update(Conversation)
                .where(Conversation.id == self.session_id)
                .values(updated_at=func.now())
            )
            await db.commit()

    async def pop_item(self) -> TResponseInputItem | None:
        async with AsyncSessionLocal() as db:
            await self._ensure_owned(db)
            while True:
                message = await db.scalar(
                    select(Message)
                    .where(Message.conversation_id == self.session_id)
                    .order_by(desc(Message.sequence_no), desc(Message.created_at))
                    .limit(1)
                )
                if message is None:
                    return None

                if message.sdk_item_json:
                    try:
                        raw_item = json.loads(message.sdk_item_json)
                        item = cast(TResponseInputItem, raw_item) if isinstance(raw_item, dict) else None
                    except (json.JSONDecodeError, TypeError):
                        item = None
                else:
                    item = _legacy_message_item(message)

                await db.delete(message)
                await db.commit()
                if item is not None:
                    return item

    async def clear_session(self) -> None:
        async with AsyncSessionLocal() as db:
            await self._ensure_owned(db)
            await db.execute(delete(Message).where(Message.conversation_id == self.session_id))
            await db.execute(
                update(Conversation)
                .where(Conversation.id == self.session_id)
                .values(updated_at=func.now())
            )
            await db.commit()
            self.pending_user_message_id = None
            self.last_assistant_message_id = None

    async def annotate_last_assistant(self, *, model: str, agent_name: str) -> str | None:
        if self.last_assistant_message_id is None:
            return None
        async with AsyncSessionLocal() as db:
            await self._ensure_owned(db)
            await db.execute(
                update(Message)
                .where(
                    Message.id == self.last_assistant_message_id,
                    Message.conversation_id == self.session_id,
                )
                .values(model=model, agent_name=agent_name)
            )
            await db.commit()
        return self.last_assistant_message_id
