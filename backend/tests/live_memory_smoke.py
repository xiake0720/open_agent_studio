"""真实 GLM 两轮会话记忆冒烟测试；不输出模型回答或密钥。"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

db_file = Path(tempfile.gettempdir()) / "open-agent-studio-live-memory.sqlite3"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["APP_DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def run_turn(client: TestClient, conversation_id: str, model_id: str, content: str) -> str:
    created = client.post(
        "/api/agent-runs",
        json={
            "conversation_id": conversation_id,
            "content": content,
            "agent_mode": "general",
            "primary_model_id": model_id,
        },
    )
    assert created.status_code == 200, created.text
    run = created.json()["data"]

    final_output = ""
    with client.stream("GET", run["stream_url"]) as response:
        assert response.status_code == 200, response.text
        event_name = ""
        for line in response.iter_lines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: ") and event_name == "run.completed":
                final_output = str(json.loads(line.removeprefix("data: "))["final_output"])
    assert final_output
    return final_output


try:
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "live_memory",
                "password": "LiveMemory123!",
                "password_confirm": "LiveMemory123!",
            },
        )
        assert registered.status_code == 200, registered.text

        models = client.get("/api/models").json()["data"]
        glm = next(item for item in models if item["provider"] == "glm")
        conversation = client.post(
            "/api/conversations",
            json={"title": "Live memory", "agent_mode": "general", "default_model": glm["id"]},
        ).json()["data"]

        run_turn(
            client,
            conversation["id"],
            glm["id"],
            "请记住暗号是海蓝星。只回复：已记住。",
        )
        recalled = run_turn(
            client,
            conversation["id"],
            glm["id"],
            "我上一轮让你记住的暗号是什么？只回复暗号。",
        )
        assert "海蓝星" in recalled, "第二轮没有召回第一轮记忆"

        visible_messages = client.get(
            f"/api/conversations/{conversation['id']}/messages"
        ).json()["data"]
        assert [item["role"] for item in visible_messages] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        print("Live GLM memory smoke passed | turns=2 | visible_messages=4")
finally:
    from backend.app.db.session import engine

    asyncio.run(engine.dispose())
    if db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            pass
