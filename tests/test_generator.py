from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ee_etl.importer import read_dataset
from ee_etl.quality import SIZE_TARGETS, run_quality_checks
from ee_generator import GeneratedProgramme, generate_programme


def test_same_seed_is_byte_identical(programme: GeneratedProgramme) -> None:
    again = generate_programme(seed=42)
    assert json.dumps(again.dataset, sort_keys=True) == json.dumps(programme.dataset, sort_keys=True)
    assert again.ground_truth == programme.ground_truth


def test_different_seed_differs(programme: GeneratedProgramme) -> None:
    other = generate_programme(seed=7)
    assert json.dumps(other.dataset["executions"]) != json.dumps(programme.dataset["executions"])


def test_size_targets_met(programme: GeneratedProgramme) -> None:
    for name, (lo, hi) in SIZE_TARGETS.items():
        assert lo <= programme.counts[name] <= hi, (name, programme.counts[name])


def test_size_targets_hold_across_seeds() -> None:
    for seed in (1, 2, 3, 99):
        prog = generate_programme(seed)
        for name, (lo, hi) in SIZE_TARGETS.items():
            assert lo <= prog.counts[name] <= hi, (seed, name, prog.counts[name])


def test_dataset_passes_quality_checks(dataset_dir: Path) -> None:
    data, manifest = read_dataset(dataset_dir)
    report = run_quality_checks(data)
    assert report.ok, report.errors
    assert manifest["seed"] == 42


def test_ground_truth_never_written_into_dataset(dataset_dir: Path) -> None:
    text = "".join(p.read_text() for p in dataset_dir.glob("*.json"))
    for hidden in ("latent_fragility", "test_sensitivity", "variant_scope", "injected_build", "F-0001"):
        assert hidden not in text
    assert not (dataset_dir / "ground_truth.json").exists()
    assert (dataset_dir.parent / "ground_truth" / "ground_truth.json").exists()


def test_all_entities_are_labelled_fictional(programme: GeneratedProgramme) -> None:
    assert all(c["fictional"] and "fictional" in c["name"] for c in programme.dataset["components"])
    assert all("Fictional" in v["name"] for v in programme.dataset["variants"])


def test_builds_contain_component_and_requirement_changes(programme: GeneratedProgramme) -> None:
    by_build = Counter((c["build_id"], c["target_type"]) for c in programme.dataset["build_changes"])
    for b in programme.dataset["builds"][1:]:
        assert by_build[(b["id"], "component")] >= 5
        assert by_build[(b["id"], "requirement")] >= 6


def test_engineer_selection_is_partial_and_labelled(programme: GeneratedProgramme) -> None:
    ex = programme.dataset["executions"]
    assert {e["selected_by"] for e in ex} == {"HISTORICAL_ENGINEER"}
    tv = programme.dataset["test_variants"]
    per_build = Counter(e["build_id"] for e in ex)
    assert all(n < len(tv) for n in per_build.values())


def test_fmea_occurrence_is_only_weakly_informative(programme: GeneratedProgramme) -> None:
    """The hidden fragility must not be recoverable exactly from FMEA occurrence."""
    frag = programme.ground_truth["latent_fragility"]
    comp_of = {rc["requirement_id"]: rc["component_id"] for rc in programme.dataset["requirement_components"]}
    pairs = [(r["fmea_occurrence"], frag[comp_of[r["id"]]]) for r in programme.dataset["requirements"]]
    n = len(pairs)
    mx, my = sum(p[0] for p in pairs) / n, sum(p[1] for p in pairs) / n
    cov = sum((a - mx) * (b - my) for a, b in pairs)
    var = (sum((a - mx) ** 2 for a, _ in pairs) * sum((b - my) ** 2 for _, b in pairs)) ** 0.5
    corr = cov / var
    assert 0.0 < corr < 0.8


def test_some_requirements_are_structurally_uncovered(programme: GeneratedProgramme) -> None:
    tested = {tr["requirement_id"] for tr in programme.dataset["test_requirements"]}
    assert 0 < len(programme.dataset["requirements"]) - len(tested) < 40


def test_defects_recur_by_error_code(programme: GeneratedProgramme) -> None:
    codes = Counter((d["component_id"], d["error_code"]) for d in programme.dataset["defects"])
    assert max(codes.values()) >= 3
