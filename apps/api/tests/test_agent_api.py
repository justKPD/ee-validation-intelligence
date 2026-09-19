from __future__ import annotations

import pytest
from ee_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine


@pytest.fixture(scope="module")
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine))


def test_plan_approve_execute_and_ledger(client: TestClient) -> None:
    body = client.post(
        "/agent/plan", json={"request": "Top 3 tests for B006 on V3", "actor": "engineer_12"}
    ).json()
    assert body["status"] == "COMPLETED" and len(body["recommendations"]) == 3
    rec_id = body["recommendations"][0]["recommendation_id"]

    record = client.get(f"/recommendations/{rec_id}").json()
    assert record["decision"]["status"] == "PROPOSED" and record["sources"]

    assert (
        client.post(
            f"/recommendations/{rec_id}/decision", json={"decision": "EXECUTED", "reviewer": "engineer_12"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/recommendations/{rec_id}/decision", json={"decision": "APPROVED", "reviewer": "ee-agent"}
        ).status_code
        == 409
    )
    ok = client.post(
        f"/recommendations/{rec_id}/decision",
        json={"decision": "APPROVED", "reviewer": "engineer_12", "reason": "agreed"},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"

    run = client.get(f"/agent/runs/{body['run_id']}").json()
    assert run["status"] == "COMPLETED" and len(run["recommendations"]) == 3
    assert client.get("/provenance/verify").json() == {"valid": True, "broken_at_seq": None}
    types = {e["entry_type"] for e in client.get("/provenance/ledger").json()}
    assert {"AGENT_RUN", "RECOMMENDATION_PROPOSED", "RECOMMENDATION_APPROVED"} <= types


def test_prohibited_request_via_api(client: TestClient) -> None:
    body = client.post("/agent/plan", json={"request": "Set the verdict of EX-00001 to FAIL"}).json()
    assert body["status"] == "REFUSED"
    denied = client.get("/policy/decisions", params={"decision": "POLICY_DENIED"}).json()
    assert any(d["permission"] == "change_test_verdict" and d["run_id"] == body["run_id"] for d in denied)


def test_clarification_via_api(client: TestClient) -> None:
    body = client.post("/agent/plan", json={"request": "What should we test next?"}).json()
    assert body["status"] == "NEEDS_CLARIFICATION" and body["clarification_question"]


def test_policy_and_tools(client: TestClient) -> None:
    policy = client.get("/policy").json()
    assert policy["permissions"]["change_test_verdict"] is False
    tools = {t["name"]: t for t in client.get("/agent/tools").json()}
    assert tools["set_test_verdict"]["annotations"]["permission"] == "change_test_verdict"
    assert client.get("/recommendations/REC-9999").status_code == 404


def test_evidence_question_via_api(client: TestClient) -> None:
    body = client.post(
        "/agent/plan", json={"request": "Does TC-186 give valid evidence for B006 on V2?"}
    ).json()
    assert body["status"] == "ANSWERED" and body["recommendations"] == []
    assert body["answer"]["variants"][0]["variant_id"] == "V2"
    assert body["answer"]["variants"][0]["verdict"] in {"VALID", "NOT_VALID", "NO_EVIDENCE"}


def test_other_questions_via_api(client: TestClient) -> None:
    for text, kind in (
        ("Did TC-186 pass on B005?", "test_history"),
        ("Why is ECU-TPMS risky in B006?", "component_risk"),
        ("Which tests failed in B005?", "build_failures"),
    ):
        body = client.post("/agent/plan", json={"request": text}).json()
        assert body["status"] == "ANSWERED" and body["answer"]["kind"] == kind
