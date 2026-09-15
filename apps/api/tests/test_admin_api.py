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
