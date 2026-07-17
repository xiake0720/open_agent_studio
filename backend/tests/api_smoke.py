"""不调用模型网络的 API 合约冒烟测试。"""

import os
import sys
import tempfile
import asyncio
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

db_file = Path(tempfile.gettempdir()) / "open-agent-studio-api-smoke.sqlite3"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["APP_DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


try:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text

        register = client.post(
            "/api/auth/register",
            json={"username": "smoke_user", "password": "SmokePass123!", "password_confirm": "SmokePass123!"},
        )
        assert register.status_code == 200, register.text

        model_response = client.get("/api/models")
        assert model_response.status_code == 200, model_response.text
        models = model_response.json()["data"]
        assert len(models) >= 2
        assert {"provider", "display_name", "model_id", "support_tools"}.issubset(models[0])
        assert "api_key_env" not in models[0]

        conversation_response = client.post(
            "/api/conversations",
            json={"title": "API smoke", "agent_mode": "ecommerce", "default_model": models[0]["id"]},
        )
        assert conversation_response.status_code == 200, conversation_response.text
        conversation_id = conversation_response.json()["data"]["id"]

        ecommerce_run = client.post(
            "/api/agent-runs",
            json={
                "conversation_id": conversation_id,
                "content": "检查文案：全网第一，100%有效",
                "agent_mode": "ecommerce",
                "primary_model_id": models[0]["id"],
            },
        )
        assert ecommerce_run.status_code == 200, ecommerce_run.text
        assert ecommerce_run.json()["data"]["agent_name"] == "EcommerceAgent"

        compare_run = client.post(
            "/api/agent-runs",
            json={
                "conversation_id": conversation_id,
                "content": "比较两个模型",
                "agent_mode": "compare",
                "primary_model_id": models[0]["id"],
                "compare_model_ids": [models[0]["id"], models[1]["id"]],
            },
        )
        assert compare_run.status_code == 200, compare_run.text
        compare_run_id = compare_run.json()["data"]["run_id"]
        compare_state = client.get(f"/api/agent-runs/{compare_run_id}/compare-results")
        assert compare_state.status_code == 200, compare_state.text
        assert len(compare_state.json()["data"]["model_config_ids"]) == 2

        delete_response = client.delete(f"/api/conversations/{conversation_id}")
        assert delete_response.status_code == 200, delete_response.text

    print("API smoke passed")
finally:
    from backend.app.db.session import engine

    asyncio.run(engine.dispose())
    if db_file.exists():
        db_file.unlink()
