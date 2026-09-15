from __future__ import annotations

import pytest
from ee_evaluation.metrics import SelectionEvaluator, average_precision_at_k, dcg, ndcg_at_k
from ee_evaluation.oracle import HiddenFault, Oracle


def test_ndcg_perfect_and_reversed() -> None:
    rels = [3.0, 2.0, 1.0, 0.0]
    assert ndcg_at_k(rels, rels, 4) == pytest.approx(1.0)
    assert ndcg_at_k(list(reversed(rels)), rels, 4) < 1.0
    assert ndcg_at_k([0.0, 0.0], [0.0, 0.0], 2) == 0.0
    assert dcg([1.0]) == pytest.approx(1.0)


def test_average_precision_known_values() -> None:
    assert average_precision_at_k([True, False, True], total_relevant=2, k=3) == pytest.approx(
        (1 + 2 / 3) / 2
    )
    assert average_precision_at_k([False, False], total_relevant=0, k=2) == 0.0


def _oracle() -> Oracle:
    faults = [
        HiddenFault("F1", "ECU-A", 5, frozenset({"V1"}), frozenset({"B002"})),
        HiddenFault("F2", "ECU-B", 2, frozenset({"V1", "V2"}), frozenset({"B002", "B003"})),
    ]
    return Oracle(
        faults, {"T1": 0.5, "T2": 0.8}, {"T1": frozenset({"ECU-A"}), "T2": frozenset({"ECU-A", "ECU-B"})}
    )


def test_oracle_live_faults_and_exposure() -> None:
    o = _oracle()
    assert [f.id for f in o.live_faults("B003")] == ["F2"]
    faults, idx = o.exposure_index("B002", [("T1", "V1"), ("T1", "V2"), ("T2", "V1")])
    assert ("T1", "V2") not in idx
    assert idx[("T1", "V1")] == [(0, 0.5)]
    assert sorted(idx[("T2", "V1")]) == [(0, 0.8), (1, 0.8)]


def test_selection_evaluator_expected_detection_math() -> None:
    o = _oracle()
    keys = [("T1", "V1"), ("T2", "V1")]
    faults, idx = o.exposure_index("B002", keys)
    ev = SelectionEvaluator(
        faults=faults,
        exposure=idx,
        pair_requirements={("T1", "V1"): ("R1",), ("T2", "V1"): ("R1", "R2")},
        durations={("T1", "V1"): 30.0, ("T2", "V1"): 30.0},
        critical_weights={("R1", "V1"): 20.0, ("R2", "V1"): 5.0},
        need_pairs={("R1", "V1"), ("R2", "V1")},
    )
    ev.add(("T1", "V1"))
    s = ev.summary()
    assert s["expected_defects"] == pytest.approx(0.5)
    assert s["critical_defect_recall"] == pytest.approx(0.5)
    assert s["critical_risk_coverage"] == pytest.approx(0.8)
    ev.add(("T2", "V1"))
    s = ev.summary()
    # F1: 1 - 0.5*0.2 = 0.9 ; F2: 0.8
    assert s["expected_defects"] == pytest.approx(1.7)
    assert s["critical_risk_coverage"] == pytest.approx(1.0)
    assert s["minutes"] == 60.0 and s["coverage_gain_per_hour"] == pytest.approx(1.0)
