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
- ``build_comparison``     compare/vs/difference + two builds              (each build as of its release + results)
- ``component_trend``      worse/better/increase/trend/over time + ECU     (risk as of every build in a range)
- ``agent_run``            RUN-#### named                                 (what that recorded run did)
- ``recommendation``       REC-#### named                                 (that proposal and its decision)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
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
_COMPARE = re.compile(
    r"\b(compare\w*|comparison|vs\.?|versus|difference\w*|diff|between|changed from)\b", re.I
)
LAST_TWO = re.compile(r"\b(last|latest) (two|2) builds\b", re.I)
PREVIOUS = re.compile(r"\b(previous|prior|last|preceding) (build|one|release)\b", re.I)
_TREND = re.compile(
    r"\b(worse|worsen\w*|better|improv\w*|increas\w*|decreas\w*|rise|rises|risen|rising|trend\w*|over time"
    r"|across (the )?builds|since|degrad\w*|grew|growing)\b",
    re.I,
)
# a trend question asking what got better (rather than worse) leads the answer with the improvers
ASKS_BETTER = re.compile(r"\b(improv\w*|better|safer|decreas\w*|fell|fall\w*|drop\w*|less risky)\b", re.I)
RUN_ID = re.compile(r"\bRUN-\d{4}\b", re.I)
REC_ID = re.compile(r"\bREC-\d{4}\b", re.I)
_COMPONENT_WORD = re.compile(r"\b(ecus?|components?|modules?)\b", re.I)

QUESTION_KINDS = (
    "test_evidence",
    "test_history",
    "requirement_coverage",
    "component_risk",
    "component_defects",
    "build_failures",
    "build_comparison",
    "component_trend",
    "agent_run",
    "recommendation",
)
# kinds judged "as of" a build (default: the latest build); the others read recorded results
AS_OF_KINDS = {"test_evidence", "requirement_coverage", "component_risk"}


def classify_question(
    text: str,
    tests: list[str],
    requirements: list[str],
    components: list[str],
    builds: Sequence[str] = (),
) -> str | None:
    """Question kind, or ``None`` when the text is a planning request (or not a recognised question)."""
    if PLANNING.search(text):
        return None
    # a named run or recommendation is unambiguous: look it up instead of planning something new
    if RUN_ID.search(text):
        return "agent_run"
    if REC_ID.search(text):
        return "recommendation"
    if tests:
        if _EVIDENCE.search(text):
            return "test_evidence"
        if _HISTORY.search(text):
            return "test_history"
        return None
    if requirements and _REQUIREMENT.search(text):
        return "requirement_coverage"
    if components and (_TREND.search(text) or (_COMPARE.search(text) and len(builds) > 1)):
        return "component_trend"
    if not components and _COMPONENT_WORD.search(text) and _TREND.search(text):
        return "component_trend"
    if _COMPARE.search(text) and (builds or LAST_TWO.search(text)):
        return "build_comparison"
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
        "build_comparison": _build_comparison,
        "component_trend": _component_trend,
        "agent_run": _agent_run,
        "recommendation": _recommendation,
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


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _signed(x: float, digits: int = 3) -> str:
    return f"{x:+.{digits}f}"


def _build_comparison(c: dict[str, Any]) -> str:
    a, b = c["build_a"], c["build_b"]
    A, B = c["builds"][a], c["builds"][b]  # noqa: N806 (the two builds, as in the question)
    scope = f" on {c['variant_id']}" if c["variant_id"] else ""

    measures = [
        (B["changes"] - A["changes"], "more changes", "fewer changes", "number of changes"),
        (
            B["current_share"] - A["current_share"],
            "more current evidence",
            "less current evidence",
            "share of current evidence",
        ),
        (B["mean_risk"] - A["mean_risk"], "higher average risk", "lower average risk", "average risk"),
        (B["fail"] - A["fail"], "more failed runs", "fewer failed runs", "number of failed runs"),
    ]
    differ = [more if d > 0 else less for d, more, less, _ in measures if d != 0]
    same = [name for d, _, _, name in measures if d == 0]
    if differ:
        listed = differ[0] if len(differ) == 1 else f"{', '.join(differ[:-1])} and {differ[-1]}"
        head = f"In short: {b} has {listed} than {a}{scope}."
    else:
        head = f"In short: {b} and {a}{scope} look the same on these measures."
    if same and differ:
        head += f" The {' and '.join(same)} stayed the same."
    lines = [
        head,
        f"Changes in the build: {A['changes']} -> {B['changes']} ({B['changes'] - A['changes']:+d}).",
        f"Current evidence: {_pct(A['current_share'])} -> {_pct(B['current_share'])} "
        f"({(B['current_share'] - A['current_share']) * 100:+.1f} pts); {c['evidence_lost']} requirement/variant pair(s) "
        f"lost current evidence, {c['evidence_gained']} gained it.",
        f"Average component risk: {A['mean_risk']:.3f} -> {B['mean_risk']:.3f} ({_signed(B['mean_risk'] - A['mean_risk'])}); "
        f"riskiest: {A['top_component']} {A['top_score']:.3f} -> {B['top_component']} {B['top_score']:.3f}.",
        f"Recorded test results: {A['runs']} runs, {A['fail']} failed, {A['defects']} defect(s) -> "
        f"{B['runs']} runs, {B['fail']} failed, {B['defects']} defect(s).",
    ]
    if c["risk_up"]:
        lines.append(
            "Risk rose most for: "
            + "; ".join(
                f"{r['component_id']} {_signed(r['delta'])} ({r['a']:.3f} -> {r['b']:.3f})"
                for r in c["risk_up"]
            )
            + "."
        )
    if c["risk_down"]:
        lines.append(
            "Risk fell most for: "
            + "; ".join(
                f"{r['component_id']} {_signed(r['delta'])} ({r['a']:.3f} -> {r['b']:.3f})"
                for r in c["risk_down"]
            )
            + "."
        )
    lines.append(
        "Evidence and risk are judged as of each build's release; results are the runs recorded for each build."
    )
    return "\n".join(lines)


def _component_trend(t: dict[str, Any]) -> str:
    first, last = t["build_from"], t["build_to"]
    if t["component_id"]:
        series = t["series"]
        start, end = series[0]["score"], series[-1]["score"]
        direction = "got worse" if end > start else "improved" if end < start else "did not change"
        peak = max(series, key=lambda x: x["score"])
        return "\n".join(
            [
                f"{t['component_id']} risk {first} -> {last}: {start:.3f} -> {end:.3f} ({_signed(end - start)}), so it {direction}.",
                f"Highest in {peak['build_id']} ({peak['score']:.3f}, rank {peak['rank']} of {t['of']}).",
                "Per build: "
                + ", ".join(f"{x['build_id']} {x['score']:.3f} (rank {x['rank']})" for x in series)
                + ".",
                "Recorded defects per build: "
                + ", ".join(f"{x['build_id']} {x['defects']}" for x in series)
                + ".",
                "Risk is judged as of each build's release.",
            ]
        )
    worse, better = t["worse"], t["better"]
    lines: list[str] = [
        f"From {first} to {last}, {t['n_worse']} of {t['of']} components got riskier and {t['n_better']} got safer."
    ]
    parts = []
    if worse:
        parts.append(
            "Got worse most: "
            + "; ".join(
                f"{r['component_id']} {_signed(r['delta'])} ({r['a']:.3f} -> {r['b']:.3f})" for r in worse
            )
            + "."
        )
    if better:
        parts.append(
            "Improved most: "
            + "; ".join(
                f"{r['component_id']} {_signed(r['delta'])} ({r['a']:.3f} -> {r['b']:.3f})" for r in better
            )
            + "."
        )
    if t.get("focus") == "better":
        parts.reverse()
    lines += parts
    lines.append(f"Riskiest in {last}: {t['riskiest']['component_id']} ({t['riskiest']['score']:.3f}).")
    lines.append("Risk is judged as of each build's release.")
    return "\n".join(lines)


def _agent_run(r: dict[str, Any]) -> str:
    if not r["found"]:
        return f"{r['run_id']} is not in the ledger. Open the Provenance Ledger to see the runs that exist."
    scope = " ".join(x for x in (r["build_id"] or "", r["variant_id"] or "") if x)
    lines = [
        f"{r['run_id']} · {r['status']}{' · ' + scope if scope else ''}, asked by {r['actor']} on {r['created_at'][:16].replace('T', ' ')}.",
        f'It was asked: "{r["user_request"]}"',
        f"Answer given: {r['response'].splitlines()[0]}",
    ]
    if r["recommendations"]:
        lines.append(f"It proposed {len(r['recommendations'])} test(s):")
        for rec in r["recommendations"]:
            decided = rec["status"] if rec["status"] != "PROPOSED" else "still PROPOSED"
            lines.append(
                f"{rec['recommendation_id']}: {rec['test_id']} on {rec['variant_id']}, priority {rec['priority_score']:.3f}, {decided}."
            )
    else:
        lines.append("It proposed nothing.")
    if r["denials"]:
        lines.append(
            "Policy denials: " + _join([f"{d['tool']} ({d['permission']})" for d in r["denials"]]) + "."
        )
    lines.append(
        f"Engine versions: {r['model']['provider']}/{r['model']['name']}, policy {r['policy_version']}, {r['latency_ms']} ms."
    )
    return "\n".join(lines)


def _recommendation(r: dict[str, Any]) -> str:
    if not r["found"]:
        return f"{r['recommendation_id']} is not in the ledger. Open the Provenance Ledger to see the recommendations that exist."
    lines = [
        f"{r['recommendation_id']} · {r['status']}: run {r['test_id']} on {r['variant_id']} for {r['build_id']}, "
        f"priority {r['priority_score']:.3f}, {r['estimated_minutes']:.1f} min, coverage gain {r['expected_coverage_gain'] * 100:.1f}%.",
        f"Proposed by {r['run_id']}.",
        "Why: " + _join(r["reasons"]) + ".",
        "Evidence: " + _join(r["evidence_ids"]) + ".",
    ]
    for d in r["decisions"]:
        reason = f' — "{d["reason"]}"' if d["reason"] else ""
        lines.append(f"{d['decision']} by {d['reviewer']} on {d['at'][:16].replace('T', ' ')}{reason}.")
    if not r["decisions"]:
        lines.append("No human decision yet; it stays PROPOSED until an engineer approves or rejects it.")
    return "\n".join(lines)
