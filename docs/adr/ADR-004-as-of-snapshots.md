# ADR-004 — As-of-build snapshots as the only engine input

Status: Accepted (2026-09-15)

## Context
Shadow test planning (Phase 4) replays historical decision points. If any engine can see results of the
build being planned, or of later builds, every benchmark number becomes optimistic and worthless.

## Decision
- All engines (risk, coverage, failures, ranking, learned models) take an immutable `ValidationSnapshot`
  built by `ee_domain.snapshot.build_snapshot(data, build_id)`.
- Visibility for decision build *B*: changes of builds up to and including *B*; executions and defects strictly
  before *B*; requirement revisions and defect status recomputed as of *B*. Stored final values are ignored.
- The API uses the same snapshot, so what the UI shows is exactly what a planner could have known.
- `tests/test_leakage.py` tampers with all future verdicts, defects and changes and asserts identical outputs.

## Consequences
Leakage safety is structural rather than based on convention. Snapshots are rebuilt per build and cached in
the API process, which is cheap at this data volume.
