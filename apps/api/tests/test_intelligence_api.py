from __future__ import annotations

import pytest
from ee_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine


@pytest.fixture(scope="module")
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine))


def test_component_risk_sorted_with_decomposition(client: TestClient) -> None:
    body = client.get("/builds/B006/risk/components").json()
    assert len(body) == 40
    scores = [r["score"] for r in body]
    assert scores == sorted(scores, reverse=True)
    assert set(body[0]["factors"]) == {
        "base",
        "recent_change",
        "historical_failure",
        "dependency",
        "evidence_staleness",
        "variant_exposure",
    }


def test_component_risk_detail_and_404s(client: TestClient) -> None:
    assert client.get("/builds/B004/risk/components/ECU-BMS").json()["component_id"] == "ECU-BMS"
    assert client.get("/builds/B004/risk/components/ECU-NOPE").status_code == 404
    assert client.get("/builds/B999/risk/components").status_code == 404


def test_requirement_risk_critical_filter(client: TestClient) -> None:
    all_reqs = client.get("/builds/B006/risk/requirements").json()
    critical = client.get("/builds/B006/risk/requirements", params={"critical_only": True}).json()
    assert 0 < len(critical) < len(all_reqs)
    assert all(r["critical"] for r in critical)


def test_coverage_summary(client: TestClient) -> None:
    body = client.get("/builds/B006/coverage").json()
    assert set(body["status_counts"]) == {"CURRENT", "STALE", "MISSING", "INCOMPATIBLE", "FAILED"}
    assert 0 < body["evidence_coverage"] < body["structural_coverage"]


def test_evidence_filters(client: TestClient) -> None:
    body = client.get("/builds/B006/evidence", params={"status": "STALE", "variant_id": "V1"}).json()
    assert body and all(r["status"] == "STALE" and r["variant_id"] == "V1" for r in body)
    assert client.get("/builds/B006/evidence", params={"status": "BOGUS"}).status_code == 422


def test_failure_families(client: TestClient) -> None:
    fams = client.get("/builds/B006/failure-families", params={"recurring_only": True}).json()
    assert fams and all(f["occurrences"] >= 2 for f in fams)
