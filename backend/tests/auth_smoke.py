"""本地账号、验证码与用户数据隔离的端到端冒烟测试。"""

import asyncio
import base64
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

db_file = Path(tempfile.gettempdir()) / "open-agent-studio-auth-smoke.sqlite3"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["APP_DEBUG"] = "false"

# 模拟升级前已经存在、尚无 user_id 的 conversations 表。
with sqlite3.connect(db_file) as legacy_db:
    legacy_db.execute(
        """
        CREATE TABLE conversations (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            agent_mode VARCHAR(50) NOT NULL,
            default_model VARCHAR(100),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    legacy_db.execute(
        "INSERT INTO conversations (id, title, agent_mode) VALUES (?, ?, ?)",
        ("legacy-conversation", "升级前的会话", "general"),
    )

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def register(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "password_confirm": password},
    )


try:
    with TestClient(app) as client:
        unauthorized = client.get("/api/conversations")
        assert unauthorized.status_code == 401, unauthorized.text
        assert unauthorized.json()["code"] == 40100

        alice = register(client, "Alice", "AlicePass123!")
        assert alice.status_code == 200, alice.text
        assert alice.json()["data"]["user"]["username"] == "Alice"
        assert client.get("/api/auth/me").json()["data"]["username"] == "Alice"
        claimed = client.get("/api/conversations").json()["data"]
        assert any(item["id"] == "legacy-conversation" for item in claimed), claimed

        conversation = client.post(
            "/api/conversations",
            json={"title": "Alice private", "agent_mode": "general"},
        )
        assert conversation.status_code == 200, conversation.text
        alice_conversation_id = conversation.json()["data"]["id"]
        model_id = client.get("/api/models").json()["data"][0]["id"]
        alice_run = client.post(
            "/api/agent-runs",
            json={
                "conversation_id": alice_conversation_id,
                "content": "Alice private message",
                "agent_mode": "general",
                "primary_model_id": model_id,
            },
        )
        assert alice_run.status_code == 200, alice_run.text
        alice_run_id = alice_run.json()["data"]["run_id"]

        assert client.post("/api/auth/logout").status_code == 200
        bob = register(client, "Bob", "BobPass123!")
        assert bob.status_code == 200, bob.text
        cross_user = client.get(f"/api/conversations/{alice_conversation_id}")
        assert cross_user.json()["code"] == 40401, cross_user.text
        cross_messages = client.get(f"/api/conversations/{alice_conversation_id}/messages")
        assert cross_messages.json()["code"] == 40401, cross_messages.text
        cross_run = client.get(f"/api/agent-runs/{alice_run_id}")
        assert cross_run.json()["code"] == 40401, cross_run.text

        duplicate_casefold = register(client, "bOb", "AnotherPass123!")
        assert duplicate_casefold.status_code == 409, duplicate_casefold.text

        client.post("/api/auth/logout")
        for attempt in range(3):
            failed = client.post(
                "/api/auth/login",
                json={"username": "Bob", "password": "wrong-password"},
            )
            assert failed.status_code == 401, failed.text
            if attempt == 2:
                assert failed.json()["data"]["captcha_required"] is True

        blocked = client.post(
            "/api/auth/login",
            json={"username": "Bob", "password": "BobPass123!"},
        )
        assert blocked.status_code == 401, blocked.text
        assert blocked.json()["code"] == 40102

        challenge = client.get("/api/auth/captcha").json()["data"]
        encoded_svg = challenge["image_data_uri"].split(",", 1)[1]
        svg = base64.b64decode(encoded_svg).decode("utf-8")
        match = re.search(r'letter-spacing="8">([^<]+)</text>', svg)
        assert match, svg
        code = match.group(1)

        logged_in = client.post(
            "/api/auth/login",
            json={
                "username": "Bob",
                "password": "BobPass123!",
                "captcha_id": challenge["captcha_id"],
                "captcha_code": code.lower(),
            },
        )
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["data"]["user"]["username"] == "Bob"

    print("Auth smoke passed")
finally:
    from backend.app.db.session import engine

    asyncio.run(engine.dispose())
    if db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            # Windows 偶尔会在解释器退出前短暂保留 sqlite 文件句柄。
            pass
