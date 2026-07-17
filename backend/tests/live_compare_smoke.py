"""可选的实际 Compare + Judge 冒烟测试；不输出模型回答或密钥。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
db_file = Path(tempfile.gettempdir()) / "open-agent-studio-live-compare.sqlite3"
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
            json={"username": "live_compare", "password": "LivePass123!", "password_confirm": "LivePass123!"},
        )
        assert register.status_code == 200, register.text
        models = client.get("/api/models").json()["data"]
        glm = next(item for item in models if item["provider"] == "glm")
        other = next(item for item in models if item["provider"] != "glm" and item["api_shape"] == "chat_completions")
        conversation = client.post(
            "/api/conversations",
            json={"title": "Compare smoke", "agent_mode": "compare", "default_model": glm["id"]},
        ).json()["data"]
        run = client.post(
            "/api/agent-runs",
            json={
                "conversation_id": conversation["id"],
                "content": "用一句话解释 SSE。",
                "agent_mode": "compare",
                "primary_model_id": glm["id"],
                "compare_model_ids": [glm["id"], other["id"]],
            },
        ).json()["data"]

        event_names: list[str] = []
        with client.stream("GET", run["stream_url"]) as response:
            assert response.status_code == 200, response.text
            for line in response.iter_lines():
                if line.startswith("event: "):
                    event_names.append(line.removeprefix("event: "))

        assert "compare.model.started" in event_names, event_names
        assert "compare.model.completed" in event_names, event_names
        assert "judge.started" in event_names, event_names
        assert "judge.completed" in event_names, event_names
        assert "run.completed" in event_names, event_names

        state = client.get(f"/api/agent-runs/{run['run_id']}/compare-results").json()["data"]
        assert state["status"] == "completed", state["status"]
        assert len(state["results"]) == 2
        assert any(item["status"] == "completed" for item in state["results"])
        assert state["judge_report"]["winner_model_config_id"]
        statuses = ",".join(sorted(item["status"] for item in state["results"]))
        print("Live Compare smoke passed | result_statuses=", statuses)
finally:
    from backend.app.db.session import engine

    asyncio.run(engine.dispose())
    if db_file.exists():
        db_file.unlink()
