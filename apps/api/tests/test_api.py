from __future__ import annotations

import pytest
from ee_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine


@pytest.fixture(scope="module")
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine))


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert "synthetic" in r.json()["disclaimer"]


def test_stats_counts(client: TestClient) -> None:
    body = client.get("/stats").json()
    assert body["components"] == 40 and body["requirements"] == 150 and body["test_cases"] == 250
    assert 1500 <= body["executions"] <= 3000 and 80 <= body["defects"] <= 150


def test_components_pagination_and_filter(client: TestClient) -> None:
    page = client.get("/components", params={"limit": 5, "offset": 5}).json()
    assert page["total"] == 40 and len(page["items"]) == 5
    hv = client.get("/components", params={"domain": "hv_powertrain"}).json()
    assert hv["total"] > 0 and all(c["domain"] == "hv_powertrain" for c in hv["items"])


def test_component_detail(client: TestClient) -> None:
    body = client.get("/components/ECU-BMS").json()
    assert body["asil"] == "D"
    assert body["requirement_ids"] and body["test_ids"]
    assert client.get("/components/ECU-NOPE").status_code == 404


def test_build_detail_has_changes(client: TestClient) -> None:
    builds = client.get("/builds").json()
    assert [b["id"] for b in builds] == ["B001", "B002", "B003", "B004", "B005", "B006"]
    body = client.get("/builds/B003").json()
    assert body["changes"] and body["execution_count"] > 0
    assert client.get("/builds/B999").status_code == 404


def test_requirements_filters(client: TestClient) -> None:
    body = client.get("/requirements", params={"min_severity": 4}).json()
    assert all(r["severity"] >= 4 for r in body["items"])
    detail = client.get("/requirements/R-001").json()
    assert detail["component_ids"]


def test_tests_filter_by_component(client: TestClient) -> None:
    body = client.get("/tests", params={"component_id": "ECU-BMS"}).json()
    assert body["total"] > 0
    t = client.get(f"/tests/{body['items'][0]['id']}").json()
    assert "ECU-BMS" in t["component_ids"] and t["variant_ids"]


def test_executions_filter(client: TestClient) -> None:
    body = client.get("/executions", params={"build_id": "B002", "verdict": "FAIL", "limit": 1000}).json()
    assert body["total"] > 0
    assert all(e["build_id"] == "B002" and e["verdict"] == "FAIL" for e in body["items"])


def test_defects_filter_by_build(client: TestClient) -> None:
    body = client.get("/defects", params={"build_id": "B006"}).json()
    assert all(d["status"] == "OPEN" for d in body["items"])


def test_limit_validation(client: TestClient) -> None:
    assert client.get("/components", params={"limit": 5000}).status_code == 422


AGENTIC_WRITE_PATHS = {"/agent/plan", "/recommendations/{recommendation_id}/decision"}


def test_no_write_endpoints_for_authoritative_data(client: TestClient) -> None:
    """ADR-002: the only writes are the agentic layer (runs, recommendations, approvals, ledger)."""
    schema = client.get("/openapi.json").json()
    for path, ops in schema["paths"].items():
        for method in ops:
            if path in AGENTIC_WRITE_PATHS:
                assert method == "post", f"unexpected {method.upper()} {path}"
            else:
                assert method == "get", f"unexpected {method.upper()} {path}"
