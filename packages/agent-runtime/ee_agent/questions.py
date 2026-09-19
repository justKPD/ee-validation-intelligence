"""Deterministic question engine: which kind of read-only question was asked, and a grounded answer to it.

A question is recognised from the ids it names (TC-###, R-###, ECU-..., B###) plus keywords. Planning requests are
recognised first and go to the planner, so planning behaviour is unchanged. Every answer is written only from the
tool results passed in (no model), so it cannot mention anything that is not in the data.

Kinds:
- ``test_evidence``        TC-### + valid/evidence/current/stale/trust...   (as of a build; evidence engine)
- ``test_history``         TC-### + pass/fail/result/last run/history...    (recorded executions)
- ``requirement_coverage`` R-###  + covered/evidence/tested/status...      (as of a build; evidence engine)
- ``component_risk``       ECU-... + why/risk/score                        (as of a build; risk engine)
- ``component_defects``    ECU-... + defect/bug/issue                      (recorded defects)
- ``build_failures``       fail/defect + which/what/how many/list/show     (recorded executions)
"""

from __future__ import annotations

import re
from typing import Any

from ee_coverage import EvidenceStatus

# requests that ask for a test plan always go to the planner
PLANNING = re.compile(
    r"\b(plan|planning|top\s*\d+|priorit\w*|recommend\w*|propose|validate first|matter most"
    r"|(what|which) (tests? )?should (we|i|the team) (test|run|validate)|run first|test (next|first)"
    r"|re-?test\w*|re-?run|should (we|i|the team) (test|run|validate|retest|re-?run))\b",
    re.I,
)
_EVIDENCE = re.compile(
    r"\b(evidence|valid|validity|current|stale|up[ -]to[ -]date|still (good|ok|okay|valid)|trust\w*|covered|coverage)\b",
    re.I,
)
_HISTORY = re.compile(
    r"\b(pass|passed|passing|fail|failed|failing|result|results|verdict|history|last run|ran|run|runs|when)\b",
    re.I,
)
_REQUIREMENT = re.compile(
    r"\b(cover\w*|evidence|valid\w*|tested|test|tests|status|current|stale|verified)\b", re.I
)
_RISK = re.compile(r"\b(why|risk|risky|riskier|score|scored)\b", re.I)
_DEFECTS = re.compile(r"\b(defects?|bugs?|issues?|problems?)\b", re.I)
_FAILURES = re.compile(r"\b(fail|failed|failing|failures?|defects?|broke|broken)\b", re.I)
_ASKING = re.compile(r"\b(which|what|how many|list|show|any|were there|did)\b", re.I)

QUESTION_KINDS = (
    "test_evidence",
    "test_history",
    "requirement_coverage",
    "component_risk",
    "component_defects",
    "build_failures",
)
# kinds judged "as of" a build (default: the latest build); the others read recorded results
AS_OF_KINDS = {"test_evidence", "requirement_coverage", "component_risk"}


def classify_question(
    text: str, tests: list[str], requirements: list[str], components: list[str]
) -> str | None:
    """Question kind, or ``None`` when the text is a planning request (or not a recognised question)."""
    if PLANNING.search(text):
        return None
    if tests:
        if _EVIDENCE.search(text):
            return "test_evidence"
        if _HISTORY.search(text):
            return "test_history"
        return None
    if requirements and _REQUIREMENT.search(text):
        return "requirement_coverage"
    if components:
        if _DEFECTS.search(text):
            return "component_defects"
        if _RISK.search(text):
            return "component_risk"
    if _FAILURES.search(text) and _ASKING.search(text):
        return "build_failures"
    return None


RISK_LABELS = {"base": "FMEA base (impact x occurrence x detectability)"}


# --- answers --------------------------------------------------------------------------------------------------------
def _join(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def describe(kind: str, data: dict[str, Any]) -> str:
    writer = {
        "test_evidence": _test_evidence,
        "test_history": _test_history,
        "requirement_coverage": _requirement_coverage,
        "component_risk": _component_risk,
        "component_defects": _component_defects,
        "build_failures": _build_failures,
    }[kind]
    return writer(data) + "\nThis is a read-only answer; nothing was changed or proposed."


def _test_evidence(ev: dict[str, Any]) -> str:
    test, build = ev["test_id"], ev["build_id"]
    if not ev["known"]:
        return f"{test} is not linked to any requirement at {build}, so it provides no evidence there."
    rows = ev["variants"]
    valid = [r["variant_id"] for r in rows if r["verdict"] == "VALID"]
    others = [r["variant_id"] for r in rows if r["verdict"] != "VALID"]
    scope = (
        rows[0]["variant_id"]
        if len(rows) == 1
        else f"its variants ({', '.join(r['variant_id'] for r in rows)})"
    )
    if not others:
        lines = [f"Yes. {test} gives valid evidence for {build} on {scope}."]
    elif valid:
        lines = [
            f"Partly. {test} gives valid evidence for {build} on {_join(valid)}, but not on {_join(others)}."
        ]
    else:
        lines = [f"No. {test} does not give valid evidence for {build} on {scope}."]
    for r in rows:
        v, recs = r["variant_id"], r["records"]
        if r["verdict"] == "NOT_APPLICABLE":
            lines.append(
                f"{v}: not applicable, {test} is only defined for {_join(ev['applicable_variants'])}."
            )
        elif r["verdict"] == "NO_EVIDENCE":
            lines.append(f"{v}: {test} has not run on {v} before {build}, so there is no evidence.")
        else:
            first = recs[0]
            run = f"latest run {first['execution_id']} on {first['evidence_build_id']} ({first['age_days']} d before {build})"
            if r["verdict"] == "VALID":
                lines.append(
                    f"{v}: CURRENT, {run}, passed and compatible with the current revision of "
                    f"{_join([x['requirement_id'] for x in recs])}."
                )
            else:
                why = "; ".join(
                    f"{x['requirement_id']} is {x['status']}: {', '.join(x['reasons'])}" for x in recs
                )
                lines.append(f"{v}: {run}. {why}.")
    rerun = [r["variant_id"] for r in rows if r["verdict"] in ("NOT_VALID", "NO_EVIDENCE")]
    if rerun:
        lines.append(f"To restore current evidence, re-run {test} on {_join(rerun)} for {build}.")
    return "\n".join(lines)


def _test_history(h: dict[str, Any]) -> str:
    test, runs = h["test_id"], h["runs"]
    where = " ".join(
        x
        for x in (
            f"on {h['build_id']}" if h["build_id"] else "",
            f"on {h['variant_id']}" if h["variant_id"] else "",
        )
        if x
    )
    if not runs:
        return f"{test} has no recorded runs{' ' + where if where else ''}."
    counts = h["verdict_counts"]
    summary = ", ".join(f"{n} {v}" for v, n in counts.items() if n)
    last = runs[-1]
    lines = [
        f"{test} ran {len(runs)} time(s){' ' + where if where else ''}: {summary}.",
        f"Last run: {last['execution_id']} on {last['build_id']} ({last['variant_id']}) on {last['date']}: {last['verdict']}.",
    ]
    fails = [r for r in runs if r["verdict"] == "FAIL"]
    for r in fails[:5]:
        defect = (
            f", defect {r['defect_id']} ({r['defect_component']}, severity {r['defect_severity']})"
            if r["defect_id"]
            else ""
        )
        lines.append(f"Failed: {r['execution_id']} on {r['build_id']} ({r['variant_id']}){defect}.")
    if len(fails) > 5:
        lines.append(f"... and {len(fails) - 5} more failed run(s).")
    lines.append("Based on all recorded results.")
    return "\n".join(lines)


def _requirement_coverage(rc: dict[str, Any]) -> str:
    rid, build = rc["requirement_id"], rc["build_id"]
    rows = rc["variants"]
    current = [r["variant_id"] for r in rows if r["status"] == EvidenceStatus.CURRENT.value]
    others = [r["variant_id"] for r in rows if r["status"] != EvidenceStatus.CURRENT.value]
    scope = (
        rows[0]["variant_id"]
        if len(rows) == 1
        else f"its variants ({_join([r['variant_id'] for r in rows])})"
    )
    if not others:
        head = f"Yes. {rid} has valid (CURRENT) evidence for {build} on {scope}."
    elif current:
        head = (
            f"Partly. {rid} has valid evidence for {build} on {_join(current)}, but not on {_join(others)}."
        )
    else:
        head = f"No. {rid} has no valid evidence for {build} on {scope}."
    lines = [
        head,
        f'{rid}: "{rc["title"]}" (severity {rc["severity"]}, revision r{rc["revision"]}).',
        f"Linked tests: {_join(rc['linked_tests'])}. Components: {_join(rc['component_ids'])}.",
    ]
    for r in rows:
        if r["execution_id"]:
            lines.append(
                f"{r['variant_id']}: {r['status']}, best evidence {r['execution_id']} from {r['test_id']} on "
                f"{r['evidence_build_id']} ({r['age_days']} d before {build}): {', '.join(r['reasons'])}."
            )
        else:
            lines.append(f"{r['variant_id']}: {r['status']}: {', '.join(r['reasons'])}.")
    return "\n".join(lines)


def _component_risk(cr: dict[str, Any]) -> str:
    comp, build = cr["component_id"], cr["build_id"]
    parts = [
        f"{RISK_LABELS.get(name, name.replace('_', ' '))} +{value:.3f}"
        for name, value in cr["contributions"]
        if value > 0
    ]
    lines = [
        f"{comp} has risk {cr['score']:.3f} in {build}, rank {cr['rank']} of {cr['of']} components.",
        f"What makes up the score: {_join(parts)}.",
    ]
    for ch in cr["changes"]:
        lines.append(f"Changed in {build}: {ch['id']} ({ch['change_kind']}, magnitude {ch['magnitude']}).")
    lines.append(
        f"FMEA impact {cr['impact']:.2f}, occurrence {cr['occurrence']:.2f}, detectability {cr['detectability']:.2f}; "
        f"history {cr['past_executions']} past run(s) with {cr['past_defects']} defect(s); confidence {cr['confidence']:.2f}."
    )
    if cr["flags"]:
        lines.append(f"Flags: {_join(cr['flags'])}.")
    return "\n".join(lines)


def _component_defects(cd: dict[str, Any]) -> str:
    comp, defects = cd["component_id"], cd["defects"]
    where = f" on {cd['build_id']}" if cd["build_id"] else ""
    if not defects:
        return f"{comp} has no recorded defects{where}."
    by_build = ", ".join(f"{b} {n}" for b, n in cd["by_build"].items())
    by_sev = ", ".join(f"severity {s}: {n}" for s, n in cd["by_severity"].items())
    lines = [
        f"{comp} has {len(defects)} recorded defect(s){where}.",
        f"By build: {by_build}.",
        f"By severity: {by_sev}.",
    ]
    for d in defects[:5]:
        lines.append(
            f"{d['defect_id']} ({d['build_id']}, severity {d['severity']}, {d['error_code']}): {d['title']}."
        )
    if len(defects) > 5:
        lines.append(f"... and {len(defects) - 5} more.")
    return "\n".join(lines)


def _build_failures(bf: dict[str, Any]) -> str:
    build, fails = bf["build_id"], bf["failures"]
    scope = f" on {bf['variant_id']}" if bf["variant_id"] else ""
    counts = ", ".join(f"{n} {v}" for v, n in bf["verdict_counts"].items() if n)
    lines = [f"{build}{scope}: {bf['runs']} recorded test run(s): {counts}."]
    if not fails:
        lines.append("No test failed.")
    for f in fails[:10]:
        defect = (
            f", defect {f['defect_id']} ({f['defect_component']}, severity {f['defect_severity']})"
            if f["defect_id"]
            else ""
        )
        lines.append(f"{f['test_id']} failed on {f['variant_id']} ({f['execution_id']}){defect}.")
    if len(fails) > 10:
        lines.append(f"... and {len(fails) - 10} more failed run(s).")
    return "\n".join(lines)
