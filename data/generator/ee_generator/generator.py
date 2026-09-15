"""Seeded synthetic programme generator with a hidden fault model.

Observable data (written to ``dataset/``) and hidden truth (written to
``ground_truth/``) are strictly separated. Downstream engines only ever see the
observable dataset, so benchmarks cannot trivially rediscover the generating
formula.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ee_generator import catalog

GENERATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class GeneratorConfig:
    n_requirements: int = 150
    n_tests: int = 250
    n_builds: int = 6
    selection_ratio: float = 0.55
    base_fault_rate: float = 0.15
    change_fault_rate: float = 6.5
    propagation: float = 0.35
    fault_persistence: float = 0.6
    flaky_fail_rate: float = 0.015
    blocked_rate: float = 0.012
    start_date: date = date(2026, 1, 12)


@dataclass
class GeneratedProgramme:
    seed: int
    dataset: dict[str, list[dict[str, Any]]]
    ground_truth: dict[str, Any]
    counts: dict[str, int] = field(default_factory=dict)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _clip(v: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, round(v)))


def generate_programme(seed: int = 42, config: GeneratorConfig | None = None) -> GeneratedProgramme:
    cfg = config or GeneratorConfig()
    rng = random.Random(seed)
    ds: dict[str, list[dict[str, Any]]] = {}

    # --- components + hidden fragility -------------------------------------------------
    components: list[dict[str, Any]] = []
    fragility: dict[str, float] = {}
    asil_of: dict[str, str] = {}
    domain_of: dict[str, str] = {}
    for short, domain, asil in catalog.COMPONENTS:
        cid = f"ECU-{short}"
        components.append(
            {
                "id": cid,
                "name": f"{short.replace('_', ' ').title()} (fictional)",
                "domain": domain,
                "asil": asil,
                "supplier": rng.choice(catalog.SUPPLIERS),
                "fictional": True,
            }
        )
        fragility[cid] = rng.betavariate(1.3, 4.0)
        asil_of[cid], domain_of[cid] = asil, domain
    ds["components"] = components
    cids: list[str] = [c["id"] for c in components]

    deps: list[dict[str, Any]] = []
    downstream: dict[str, list[str]] = {c: [] for c in cids}
    for i, cid in enumerate(cids[1:], start=1):
        for up in rng.sample(cids[:i], k=min(i, rng.randint(1, 2))):
            deps.append(
                {
                    "upstream_id": up,
                    "downstream_id": cid,
                    "kind": rng.choice(["signal", "power", "gateway_route"]),
                }
            )
            downstream[up].append(cid)
    ds["component_dependencies"] = deps

    # --- builds / variants ------------------------------------------------------------------
    builds: list[dict[str, Any]] = [
        {
            "id": f"B{n:03d}",
            "sequence": n,
            "release_date": (cfg.start_date + timedelta(weeks=3 * (n - 1))).isoformat(),
            "build_family": f"26.{(n + 1) // 2:02d}",
        }
        for n in range(1, cfg.n_builds + 1)
    ]
    ds["builds"] = builds
    ds["variants"] = [
        {"id": v, "name": n, "powertrain": p, "market": m, "features": f}
        for v, n, p, m, f in catalog.VARIANTS
    ]
    variant_ids = [v[0] for v in catalog.VARIANTS]

    # --- requirements (FMEA is a noisy, partially stale expert estimate) --------------------
    asil_impact = {"QM": 3, "A": 4.5, "B": 6, "C": 7.5, "D": 9}
    requirements: list[dict[str, Any]] = []
    req_components: list[dict[str, Any]] = []
    comps_of_req: dict[str, list[str]] = {}
    for n in range(1, cfg.n_requirements + 1):
        rid = f"R-{n:03d}"
        primary = cids[(n - 1) % len(cids)] if n <= len(cids) else rng.choice(cids)
        linked = [primary]
        if rng.random() < 0.25:
            linked.append(rng.choice([c for c in cids if c != primary]))
        cat = (
            "safety"
            if asil_of[primary] in ("C", "D") and rng.random() < 0.5
            else rng.choice(catalog.REQ_CATEGORIES)
        )
        occ_signal = 0.3 * fragility[primary] / 0.5 + 0.7 * rng.random()  # weakly informative
        created = builds[0]["id"] if rng.random() < 0.8 else rng.choice(builds[1:4])["id"]
        requirements.append(
            {
                "id": rid,
                "title": catalog.REQ_TEMPLATES[cat].format(
                    c=primary.removeprefix("ECU-"), x=rng.choice(catalog.SIGNALS)
                ),
                "category": cat,
                "severity": _clip(asil_impact[asil_of[primary]] / 2 + rng.gauss(0, 0.8), 1, 5),
                "fmea_impact": _clip(asil_impact[asil_of[primary]] + rng.gauss(0, 1.2), 1, 10),
                "fmea_occurrence": _clip(1 + 9 * min(occ_signal, 1.0), 1, 10),
                "fmea_detectability": _clip(rng.gauss(5, 2), 1, 10),
                "revision": 1,
                "created_build_id": created,
            }
        )
        comps_of_req[rid] = linked
        req_components += [{"requirement_id": rid, "component_id": c} for c in linked]
    req_by_id = {r["id"]: r for r in requirements}
    build_seq = {b["id"]: b["sequence"] for b in builds}

    # --- tests ---------------------------------------------------------------------------------
    level_duration = {"SIL": (2, 8), "HIL": (6, 25), "VEHICLE": (20, 75)}
    sensitivity = {"SIL": 0.45, "HIL": 0.65, "VEHICLE": 0.8}
    uncovered = set(rng.sample([r["id"] for r in requirements], k=int(cfg.n_requirements * 0.12)))
    coverable = [r["id"] for r in requirements if r["id"] not in uncovered]
    tests: list[dict[str, Any]] = []
    t_req: list[dict[str, Any]] = []
    t_comp: list[dict[str, Any]] = []
    t_var: list[dict[str, Any]] = []
    reqs_of_test: dict[str, list[str]] = {}
    comps_of_test: dict[str, list[str]] = {}
    vars_of_test: dict[str, list[str]] = {}
    test_sensitivity: dict[str, float] = {}
    for n in range(1, cfg.n_tests + 1):
        tid = f"TC-{n:03d}"
        k = rng.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
        # first pass guarantees every coverable requirement gets at least one test
        linked_reqs = [coverable[n - 1] if n <= len(coverable) else rng.choice(coverable)]
        linked_reqs += rng.sample([r for r in coverable if r not in linked_reqs], k=k - 1)
        comps = sorted({c for r in linked_reqs for c in comps_of_req[r]})
        level = rng.choices(["SIL", "HIL", "VEHICLE"], weights=[0.35, 0.45, 0.2])[0]
        lo, hi = level_duration[level]
        family = rng.choice(catalog.FAMILY_BY_DOMAIN[domain_of[comps[0]]])
        tests.append(
            {
                "id": tid,
                "name": f"{family} check for {comps[0].removeprefix('ECU-')} #{n}",
                "test_family": family,
                "level": level,
                "duration_min": round(rng.uniform(lo, hi), 1),
                "automated": level != "VEHICLE" and rng.random() < 0.8,
            }
        )
        hv = any(domain_of[c] == catalog.HV_DOMAIN for c in comps)
        eligible = [v for v in variant_ids if not (hv and v == "V4")]
        variants = sorted(rng.sample(eligible, k=rng.randint(1, len(eligible))))
        reqs_of_test[tid], comps_of_test[tid], vars_of_test[tid] = linked_reqs, comps, variants
        test_sensitivity[tid] = min(0.95, sensitivity[level] * rng.uniform(0.7, 1.25))
        t_req += [{"test_id": tid, "requirement_id": r} for r in linked_reqs]
        t_comp += [{"test_id": tid, "component_id": c} for c in comps]
        t_var += [{"test_id": tid, "variant_id": v} for v in variants]
    ds["test_cases"], ds["requirement_components"] = tests, req_components
    ds["test_requirements"], ds["test_components"], ds["test_variants"] = t_req, t_comp, t_var
    # --- builds: changes, faults, engineer selection, executions, defects --------------------
    error_codes = {c: [f"E{rng.randint(0x1000, 0xFFFF):04X}" for _ in range(3)] for c in cids}
    changes: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    defects: list[dict[str, Any]] = []
    faults: list[dict[str, Any]] = []
    live: list[dict[str, Any]] = []
    last_run: set[tuple[str, str]] = set()
    change_n = exec_n = defect_n = fault_n = 0

    for b in builds:
        bid, seq = b["id"], b["sequence"]
        release = date.fromisoformat(b["release_date"])
        changed: dict[str, float]
        if seq == 1:
            changed = {c: 0.5 for c in cids}
        else:
            changed = {c: round(rng.uniform(0.2, 1.0), 2) for c in rng.sample(cids, k=rng.randint(5, 9))}
        for c, mag in changed.items():
            if seq > 1:
                change_n += 1
                changes.append(
                    {
                        "id": f"CH-{change_n:04d}",
                        "build_id": bid,
                        "target_type": "component",
                        "target_id": c,
                        "change_kind": rng.choice(
                            ["feature", "bugfix", "calibration", "refactor", "dependency_update"]
                        ),
                        "magnitude": mag,
                        "new_revision": None,
                    }
                )
        if seq > 1:
            active_reqs = [r for r in requirements if build_seq[r["created_build_id"]] <= seq]
            for r in rng.sample(active_reqs, k=rng.randint(6, 12)):
                r["revision"] += 1
                change_n += 1
                changes.append(
                    {
                        "id": f"CH-{change_n:04d}",
                        "build_id": bid,
                        "target_type": "requirement",
                        "target_id": r["id"],
                        "change_kind": "requirement_revision",
                        "magnitude": round(rng.uniform(0.2, 0.9), 2),
                        "new_revision": r["revision"],
                    }
                )
                for c in comps_of_req[r["id"]]:
                    changed[c] = max(changed.get(c, 0.0), 0.3)
        req_rev_now = {r["id"]: r["revision"] for r in requirements}

        # carry over undetected faults, inject new ones (hidden)
        live = [f for f in live if not f["detected"] and rng.random() < cfg.fault_persistence]
        exposure = {c: cfg.base_fault_rate * fragility[c] for c in cids}
        for c, mag in changed.items():
            exposure[c] += cfg.change_fault_rate * mag * fragility[c]
            for d in downstream[c]:
                exposure[d] += cfg.propagation * cfg.change_fault_rate * mag * fragility[d] * 0.5
        for c in cids:
            for _ in range(_poisson(rng, exposure[c])):
                fault_n += 1
                code_idx = 0 if rng.random() < 0.55 else rng.randint(1, 2)
                f: dict[str, Any] = {
                    "id": f"F-{fault_n:04d}",
                    "component_id": c,
                    "injected_build": bid,
                    "severity": _clip(rng.gauss(2.5 + (1.5 if asil_of[c] in "CD" else 0), 1), 1, 5),
                    "error_code": error_codes[c][code_idx],
                    "variant_scope": sorted(rng.sample(variant_ids, k=rng.randint(1, 4))),
                    "failure_stage": rng.choice(catalog.FAILURE_STAGES),
                    "signal": rng.choice(catalog.SIGNALS),
                    "detected": False,
                    "detected_by": None,
                }
                faults.append(f)
                live.append(f)

        # engineer selection: biased to severity, habit, automation (deliberately imperfect)
        pairs: list[tuple[float, str, str]] = []
        for t in tests:
            tid = t["id"]
            if not any(build_seq[req_by_id[r]["created_build_id"]] <= seq for r in reqs_of_test[tid]):
                continue
            sev = max(req_by_id[r]["severity"] for r in reqs_of_test[tid])
            for v in vars_of_test[tid]:
                score = (
                    0.45 * sev / 5
                    + 0.3 * ((tid, v) in last_run)
                    + 0.15 * t["automated"]
                    + 0.25 * rng.random()
                )
                pairs.append((score, tid, v))
        pairs.sort(reverse=True)
        selected = pairs[: int(len(pairs) * cfg.selection_ratio)]
        last_run = {(tid, v) for _, tid, v in selected}
        rng.shuffle(selected)

        for _, tid, v in selected:
            exec_n += 1
            eid = f"EX-{exec_n:05d}"
            t = tests[int(tid[3:]) - 1]
            verdict = "PASS"
            hit: dict[str, Any] | None = None
            for f in live:
                in_scope = f["component_id"] in comps_of_test[tid] and v in f["variant_scope"]
                if in_scope and not f["detected"] and rng.random() < test_sensitivity[tid]:
                    hit = f
                    break
            if hit is not None:
                verdict = "FAIL"
                hit["detected"], hit["detected_by"] = True, eid
            elif rng.random() < cfg.flaky_fail_rate:
                verdict = "FAIL"
            elif rng.random() < cfg.blocked_rate:
                verdict = "BLOCKED"
            executed_at = datetime.combine(release, datetime.min.time()) + timedelta(
                hours=rng.uniform(8, 24 * 12)
            )
            executions.append(
                {
                    "id": eid,
                    "test_id": tid,
                    "build_id": bid,
                    "variant_id": v,
                    "attempt": 1,
                    "verdict": verdict,
                    "duration_min": round(t["duration_min"] * rng.uniform(0.85, 1.3), 1),
                    "executed_at": executed_at.isoformat(timespec="seconds"),
                    "requirement_revision": max(req_rev_now[r] for r in reqs_of_test[tid]),
                    "selected_by": "HISTORICAL_ENGINEER",
                }
            )
            if hit is not None:
                defect_n += 1
                defects.append(
                    {
                        "id": f"D-{defect_n:03d}",
                        "execution_id": eid,
                        "component_id": hit["component_id"],
                        "severity": hit["severity"],
                        "error_code": hit["error_code"],
                        "failure_stage": hit["failure_stage"],
                        "signal_signature": f"{hit['signal']}|{hit['failure_stage']}",
                        "status": "RESOLVED" if seq < cfg.n_builds else "OPEN",
                        "title": f"{hit['signal'].capitalize()} {hit['failure_stage'].replace('_', ' ')} "
                        f"failure on {hit['component_id'].removeprefix('ECU-')}",
                    }
                )

    ds["requirements"], ds["build_changes"] = requirements, changes
    ds["executions"], ds["defects"] = executions, defects

    ground_truth = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "latent_fragility": {c: round(v, 4) for c, v in fragility.items()},
        "test_sensitivity": {t: round(v, 4) for t, v in test_sensitivity.items()},
        "faults": faults,
    }
    counts = {k: len(v) for k, v in ds.items()}
    return GeneratedProgramme(seed=seed, dataset=ds, ground_truth=ground_truth, counts=counts)


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, indent=1, sort_keys=True).encode()


def write_programme(prog: GeneratedProgramme, out_dir: Path) -> Path:
    dataset_dir, gt_dir = out_dir / "dataset", out_dir / "ground_truth"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, rows in prog.dataset.items():
        data = _dump(rows)
        (dataset_dir / f"{name}.json").write_bytes(data)
        checksums[name] = hashlib.sha256(data).hexdigest()
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "seed": prog.seed,
        "counts": prog.counts,
        "sha256": checksums,
        "disclaimer": "Entirely fictional synthetic data. No BMW Group data.",
    }
    (dataset_dir / "manifest.json").write_bytes(_dump(manifest))
    (gt_dir / "ground_truth.json").write_bytes(_dump(prog.ground_truth))
    return dataset_dir
