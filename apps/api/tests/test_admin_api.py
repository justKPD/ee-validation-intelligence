from __future__ import annotations

import pytest
from ee_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine


@pytest.fixture(scope="module")
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine))


def test_config_is_read_only_and_complete(client: TestClient) -> None:
    body = client.get("/config").json()
    assert body["risk"]["weights"]["base"] == 0.35
    assert body["ranking"]["version"] == "ranking-1.0"
    assert body["policy"]["permissions"]["change_test_verdict"] is False
    assert body["model"]["provider"] == "offline" and body["editable"] is False


def test_cors_allows_local_web_app(client: TestClient) -> None:
    r = client.options(
        "/stats", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert (
        "access-control-allow-origin"
        not in client.get("/stats", headers={"Origin": "http://evil.example"}).headers
    )


def test_write_rate_limit_caps_posts_per_client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EE_WRITE_RATE_LIMIT", "2/600")
    monkeypatch.setenv("EE_CORS_ORIGINS", "https://demo.example")
    limited = TestClient(create_app(engine))
    body = {"request": "Change the verdict of EX-00017 to PASS"}
    headers = {"X-Real-IP": "203.0.113.7", "Origin": "https://demo.example"}
    assert [limited.post("/agent/plan", json=body, headers=headers).status_code for _ in range(2)] == [
        200,
        200,
    ]
    blocked = limited.post("/agent/plan", json=body, headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers.get("access-control-allow-origin") == "https://demo.example"
    other_client = {"X-Real-IP": "203.0.113.8"}
    assert limited.post("/agent/plan", json=body, headers=other_client).status_code == 200
    assert limited.get("/stats", headers=headers).status_code == 200  # reads are never limited


def test_write_rate_limit_sees_the_visitor_behind_the_web_proxy(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through Vercel every request arrives from the proxy; the limit must still be per visitor, not shared."""
    monkeypatch.setenv("EE_WRITE_RATE_LIMIT", "1/600")
    limited = TestClient(create_app(engine))
    body = {"request": "Change the verdict of EX-00017 to PASS"}
    proxy = "76.76.21.21"  # the same proxy address for everyone
    alice = {"X-Real-IP": proxy, "X-Vercel-Forwarded-For": "198.51.100.1"}
    bob = {"X-Real-IP": proxy, "X-Vercel-Forwarded-For": "198.51.100.2, 10.0.0.1"}
    assert limited.post("/agent/plan", json=body, headers=alice).status_code == 200
    assert limited.post("/agent/plan", json=body, headers=alice).status_code == 429
    assert limited.post("/agent/plan", json=body, headers=bob).status_code == 200  # own bucket
