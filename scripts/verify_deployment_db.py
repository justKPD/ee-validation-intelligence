"""Verify a deployed database from inside the deployment (no public database port needed).

Run after `ee-seed` against `EE_DATABASE_URL`. Prints only non-secret facts:
server version, migration head, pgvector usability, seed-42 table counts, agentic-layer counts and the
provenance hash-chain status. Exits 1 if pgvector is unusable, a seeded count differs from the generated
manifest, or the hash chain is broken.
"""

from __future__ import annotations

import json
import sys

from ee_domain import models as m
from ee_domain.db import REPO_ROOT, make_engine, redacted_url
from ee_provenance import ProvenanceService
from ee_provenance.models import AgentRun, Approval, PolicyDecisionRecord, ProvenanceRecord, Recommendation
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

SEEDED = {
    "components": m.Component,
    "requirements": m.Requirement,
    "test_cases": m.TestCase,
    "builds": m.SoftwareBuild,
    "variants": m.VehicleVariant,
    "executions": m.TestExecution,
    "defects": m.Defect,
}
AGENTIC = {
    "agent_runs": AgentRun,
    "recommendations": Recommendation,
    "approvals": Approval,
    "policy_decisions": PolicyDecisionRecord,
    "provenance_records": ProvenanceRecord,
}


def main() -> int:
    engine = make_engine()
    failed = False
    print(f"db-verify: target {redacted_url()}")
    with engine.connect() as conn:
        print("db-verify: server", conn.execute(text("SHOW server_version")).scalar())
        print(
            "db-verify: alembic head", conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        )
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        version = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
        l2 = conn.execute(text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")).scalar()
        cosine = conn.execute(text("SELECT '[1,0]'::vector <=> '[0,1]'::vector")).scalar()
        conn.execute(text("CREATE TEMP TABLE db_verify_vec (id int, emb vector(3))"))
        conn.execute(text("INSERT INTO db_verify_vec VALUES (1, '[1,1,1]'), (2, '[5,5,5]'), (3, '[-3,0,9]')"))
        nearest = conn.execute(
            text("SELECT id FROM db_verify_vec ORDER BY emb <-> '[1,1,2]' LIMIT 1")
        ).scalar()
        conn.rollback()
        ok = version is not None and l2 == 1 and cosine == 1 and nearest == 1
        failed |= not ok
        print(
            f"db-verify: pgvector {version} l2={l2} cosine={cosine} nearest_id={nearest} -> {'OK' if ok else 'FAIL'}"
        )

    expected = json.loads((REPO_ROOT / "data/synthetic/dataset/manifest.json").read_text(encoding="utf-8"))[
        "counts"
    ]
    with Session(engine) as db:
        for name, model in SEEDED.items():
            n = db.scalar(select(func.count()).select_from(model))
            ok = n == expected[name]
            failed |= not ok
            print(f"db-verify: {name}={n} expected={expected[name]} -> {'OK' if ok else 'FAIL'}")
        agentic = {
            name: db.scalar(select(func.count()).select_from(model)) for name, model in AGENTIC.items()
        }
        print("db-verify: agentic layer " + " ".join(f"{k}={v}" for k, v in agentic.items()))
        valid, broken_at = ProvenanceService(db).verify_chain()
        failed |= not valid
        print(f"db-verify: provenance hash chain valid={valid} broken_at_seq={broken_at}")
    print("db-verify: FAIL" if failed else "db-verify: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
