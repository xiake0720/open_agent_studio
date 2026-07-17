"""可选的 GLM 实际流式冒烟测试；只输出事件名，不输出模型内容或密钥。"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

db_file = Path(tempfile.gettempdir()) / "open-agent-studio-live-smoke.sqlite3"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["APP_DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


try:
    with TestClient(app) as client:
        register = client.post(
            "/api/auth/register",
            json={"username": "live_agent", "password": "LivePass123!", "password_confirm": "LivePass123!"},
        )
        assert register.status_code == 200, register.text
        models = client.get("/api/models").json()["data"]
        glm = next(item for item in models if item["provider"] == "glm")
        conversation = client.post(
            "/api/conversations",
            json={"title": "Live smoke", "agent_mode": "ecommerce", "default_model": glm["id"]},
        ).json()["data"]
        run = client.post(
            "/api/agent-runs",
            json={
                "conversation_id": conversation["id"],
                "content": "检查这句文案的风险词并简短改写：全网第一，100%有效。",
                "agent_mode": "ecommerce",
                "primary_model_id": glm["id"],
            },
        ).json()["data"]

        event_names: list[str] = []
        current_event = ""
        run_error = ""
        with client.stream("GET", run["stream_url"]) as response:
            assert response.status_code == 200, response.text
            for line in response.iter_lines():
                if line.startswith("event: "):
                    current_event = line.removeprefix("event: ")
                    event_names.append(current_event)
                elif line.startswith("data: ") and current_event == "run.error":
                    run_error = str(json.loads(line.removeprefix("data: ")).get("message") or "")

        assert "run.completed" in event_names, {"events": event_names, "run_error": run_error}
        assert "tool.called" in event_names, event_names
        assert "tool.output" in event_names, event_names
        print("Live GLM smoke passed | events=", ",".join(event_names))
finally:
    from backend.app.db.session import engine

    asyncio.run(engine.dispose())
    if db_file.exists():
        db_file.unlink()
