from fastapi.testclient import TestClient

from backend.app.main import app


def unwrap(response):
    assert response.status_code < 400, response.text
    payload = response.json()
    assert payload["code"] == 0, payload
    return payload["data"]


def main() -> None:
    with TestClient(app) as client:
        normal = unwrap(client.post("/api/auth/register", json={
            "username": "admin_smoke_user",
            "password": "SmokeUser@2026!",
            "password_confirm": "SmokeUser@2026!",
        }))
        conversation = unwrap(client.post("/api/conversations", json={
            "title": "管理后台联调会话",
            "agent_mode": "general",
        }))

        admin_login = unwrap(client.post("/api/admin/auth/login", json={
            "username": "admin",
            "password": "OpenAgent@2026!",
        }))
        assert admin_login["user"]["is_admin"] is True
        assert unwrap(client.get("/api/admin/auth/me"))["username"] == "admin"

        overview = unwrap(client.get("/api/admin/overview"))
        assert overview["users"] >= 1
        users = unwrap(client.get("/api/admin/users"))
        managed = next(item for item in users if item["id"] == normal["user"]["id"])
        assert managed["is_active"] is True

        disabled = unwrap(client.patch(f"/api/admin/users/{managed['id']}", json={"is_active": False}))
        assert disabled["is_active"] is False
        enabled = unwrap(client.patch(f"/api/admin/users/{managed['id']}", json={"is_active": True}))
        assert enabled["is_active"] is True

        created_model = unwrap(client.post("/api/admin/models", json={
            "provider": "smoke",
            "display_name": "Smoke Model",
            "model_id": "smoke-model-v1",
            "base_url": "https://example.invalid/v1",
            "api_key_env": "SMOKE_MODEL_KEY",
            "api_shape": "chat_completions",
            "support_streaming": True,
            "support_tools": False,
            "support_image": False,
            "enabled": False,
            "extra_body_json": "{}",
        }))
        assert created_model["model_id"] == "smoke-model-v1"
        assert any(item["id"] == created_model["id"] for item in unwrap(client.get("/api/admin/models")))

        conversations = unwrap(client.get("/api/admin/conversations"))
        assert any(item["id"] == conversation["id"] for item in conversations)
        detail = unwrap(client.get(f"/api/admin/conversations/{conversation['id']}"))
        assert detail["conversation"]["id"] == conversation["id"]

        stats = unwrap(client.get("/api/admin/token-stats"))
        assert "by_model" in stats and "by_time" in stats

        invalid = client.post("/api/admin/models", json={
            "provider": "bad", "display_name": "Bad", "model_id": "bad",
            "base_url": "https://example.invalid", "api_key_env": "BAD_KEY",
            "extra_body_json": "not-json",
        })
        assert invalid.status_code == 422
        exceptions = unwrap(client.get("/api/admin/exceptions"))
        assert isinstance(exceptions, list)

        print("admin_smoke: OK")


if __name__ == "__main__":
    main()
