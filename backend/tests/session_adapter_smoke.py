"""AppConversationSession 协议、旧库迁移和消息可见性的本地冒烟测试。"""

import asyncio
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

db_file = Path(tempfile.gettempdir()) / "open-agent-studio-session-smoke.sqlite3"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["APP_DEBUG"] = "false"

# 模拟 Session Adapter 上线前的 conversations/messages 表结构。
with sqlite3.connect(db_file) as legacy_db:
    legacy_db.executescript(
        """
        CREATE TABLE conversations (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            agent_mode VARCHAR(50) NOT NULL,
            default_model VARCHAR(100),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE messages (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            role VARCHAR(30) NOT NULL,
            content TEXT NOT NULL,
            model VARCHAR(100),
            agent_name VARCHAR(100),
            sequence_no INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO conversations (id, title, agent_mode)
        VALUES ('conversation-memory', 'Memory test', 'general');
        INSERT INTO messages (id, conversation_id, role, content, sequence_no)
        VALUES
            ('legacy-user', 'conversation-memory', 'user', '我叫小明', 1),
            ('legacy-assistant', 'conversation-memory', 'assistant', '你好，小明', 2);
        """
    )

from agents.memory import Session  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from backend.app.db.init_db import init_db  # noqa: E402
from backend.app.db.session import AsyncSessionLocal, engine  # noqa: E402
from backend.app.models.conversation import Conversation  # noqa: E402
from backend.app.models.message import Message  # noqa: E402
from backend.app.models.user import User  # noqa: E402
from backend.app.services.conversation_session import AppConversationSession  # noqa: E402
from backend.app.services.message_service import list_messages  # noqa: E402


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        user = User(
            id="user-memory",
            username="memory_user",
            username_key="memory_user",
            password_hash="not-used-in-this-test",
        )
        db.add(user)
        conversation = await db.get(Conversation, "conversation-memory")
        assert conversation is not None
        conversation.user_id = user.id
        pending = Message(
            id="pending-user",
            conversation_id=conversation.id,
            role="user",
            content="请记住我的城市是杭州",
            sequence_no=3,
        )
        db.add(pending)
        await db.commit()

    session = AppConversationSession(
        "conversation-memory",
        "user-memory",
        pending_user_message_id="pending-user",
        model="glm-5.1",
        agent_name="GeneralAgent",
    )
    assert isinstance(session, Session)

    history = await session.get_items()
    assert history == [
        {"role": "user", "content": "我叫小明"},
        {"role": "assistant", "content": "你好，小明"},
    ]

    current_user_item = {"role": "user", "content": "请记住我的城市是杭州"}
    await session.add_items([current_user_item])
    await session.add_items(
        [
            {
                "type": "function_call",
                "call_id": "call-memory",
                "name": "lookup_city",
                "arguments": '{"city":"杭州"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call-memory",
                "output": "杭州位于浙江省",
            },
            {"role": "assistant", "content": "记住了，你的城市是杭州。"},
        ]
    )

    all_items = await session.get_items()
    assert len(all_items) == 6
    assert all_items[-3]["type"] == "function_call"
    assert all_items[-2]["type"] == "function_call_output"
    assert all_items[-1]["role"] == "assistant"
    assert await session.get_items(limit=2) == all_items[-2:]

    async with AsyncSessionLocal() as db:
        visible = await list_messages(db, "conversation-memory", "user-memory")
        assert [item.id for item in visible] == [
            "legacy-user",
            "legacy-assistant",
            "pending-user",
            session.last_assistant_message_id,
        ]
        pending_row = await db.get(Message, "pending-user")
        assert pending_row is not None and pending_row.sdk_item_json is not None
        total = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == "conversation-memory")
        )
        assert total == 6

    popped = await session.pop_item()
    assert popped == {"role": "assistant", "content": "记住了，你的城市是杭州。"}
    popped_tool_output = await session.pop_item()
    assert popped_tool_output is not None
    assert popped_tool_output["type"] == "function_call_output"

    await session.clear_session()
    assert await session.get_items() == []

    print("Session adapter smoke passed")


try:
    asyncio.run(main())
finally:
    asyncio.run(engine.dispose())
    if db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            pass
