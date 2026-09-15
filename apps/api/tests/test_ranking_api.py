from __future__ import annotations

import json
from pathlib import Path

import pytest
from ee_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine


@pytest.fixture(scope="module")
def bench_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("bench")


@pytest.fixture(scope="module")
def client(engine: Engine, bench_dir: Path) -> TestClient:
    return TestClient(create_app(engine, benchmark_dir=bench_dir))


def test_risk_based_ranking(client: TestClient) -> None:
    body = client.get("/builds/B004/ranking", params={"limit": 10}).json()
    assert len(body) == 10 and [r["rank"] for r in body] == list(range(1, 11))
    assert all(r["strategy"] == "risk_based" and r["reasons"] and r["evidence_ids"] for r in body)


def test_hybrid_ranking_and_model_info(client: TestClient) -> None:
    body = client.get("/builds/B004/ranking", params={"strategy": "hybrid", "limit": 5}).json()
    assert body[0]["learned_probability"] is not None
    info = client.get("/builds/B004/ranking/model").json()
    assert info["trained_on_builds"] == ["B001", "B002", "B003"]


def test_variant_filter_and_budget(client: TestClient) -> None:
    body = client.get(
        "/builds/B005/ranking", params={"variant_id": "V3", "budget_minutes": 120, "limit": 1000}
    ).json()
    assert body and all(r["variant_id"] == "V3" for r in body)
    assert sum(r["duration_min"] for r in body) <= 120


def test_invalid_strategy_and_build(client: TestClient) -> None:
    assert client.get("/builds/B004/ranking", params={"strategy": "magic"}).status_code == 422
    assert client.get("/builds/B999/ranking").status_code == 404


def test_shadow_benchmark_endpoint(client: TestClient, bench_dir: Path) -> None:
    assert client.get("/benchmarks/shadow").status_code == 404
    (bench_dir / "latest.json").write_text(json.dumps({"sentence": "computed"}))
    assert client.get("/benchmarks/shadow").json()["sentence"] == "computed"
