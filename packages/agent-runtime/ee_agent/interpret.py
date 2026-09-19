"""Deterministic request interpretation: slots, prohibited intents, injection attempts and ambiguity.

The agent acts only when the build and variant are unambiguous. Otherwise it asks, because acting
prematurely on incomplete information is a known agent failure mode.

Besides planning, it recognises read-only questions (see ``ee_agent.questions``), for example
"Is TC-186 still valid for B006?", "Did TC-186 pass on B005?", "Is R-033 covered for B006 on V2?",
"Why is ECU-TPMS risky in B006?", "How many defects does ECU-BMS have?" or "Which tests failed in B005?".
Questions judged as of a build use the latest build when none is named, and say so.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from ee_agent.questions import AS_OF_KINDS, classify_question

PROHIBITED_INTENTS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\b(change|set|mark|flip|override|overwrite)\b.*\b(verdict|pass|fail|result)", re.I),
        "change_test_verdict",
        "set_test_verdict",
    ),
    (
        # indirect phrasing, e.g. "the recorded result ... reflected PASS" or "should be recorded as PASS"
        re.compile(
            r"\b(results?|verdicts?|outcomes?)\b[^.?!]*\b(recorded|reflects?|reflected|shows?|shown|marked|logged)\b"
            r"[^.?!]*\b(pass|passed|fail|failed)\b|\brecord(ed)?\s+as\s+(pass|fail)",
            re.I,
        ),
        "change_test_verdict",
        "set_test_verdict",
    ),
    (re.compile(r"\bclose\b.*\b(defect|D-\d+)", re.I), "close_defect", "close_defect"),
    (re.compile(r"\bapprove\b.*\brelease|\brelease\b.*\bapprov", re.I), "approve_release", "approve_release"),
    (
        re.compile(r"\b(modify|edit|change|update|rewrite|delete)\b.*\brequirements?\b", re.I),
        "modify_requirement",
        "update_requirement",
    ),
    (
        re.compile(r"\b(modify|edit|rewrite|update|delete)\b.*\b(test case|test definition|TC-\d+)", re.I),
        "modify_test_case",
        "update_test_case",
    ),
    (
        re.compile(r"\bapprove\b.*\b(recommendation|REC-\d+)", re.I),
        "approve_recommendation",
        "approve_recommendation",
    ),
    (
        re.compile(
            r"\b(run|execute|trigger|start)\b.*\btests?\b.*\b(now|immediately|automatically|yourself)\b", re.I
        ),
        "execute_test",
        "execute_test",
    ),
]
INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|policies|policy)"
    r"|disregard (the |your )?(policy|rules|instructions)|you are now|system override|developer mode"
    r"|bypass (the )?(policy|gate)"
    r"|pretend (that )?(the )?(policy|rules|gate)|act as if (the )?(policy|rules)"
    r"|(policy|rules) (now )?allows? everything|no (policy|rules) appl(y|ies)",
    re.I,
)
# de-obfuscation used only for intent and injection matching (never for slot parsing): "cl0se" -> "close"
_DEOBFUSCATE = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s"})


def _intent_views(text: str) -> tuple[str, ...]:
    return (text, text.translate(_DEOBFUSCATE))


@dataclass
class Interpretation:
    build_id: str | None = None
    variant_id: str | None = None
    component_ids: list[str] = field(default_factory=list)
    budget_minutes: float | None = None
    top_n: int = 5
    all_variants: bool = False
    prohibited: list[tuple[str, str]] = field(default_factory=list)  # (permission, tool)
    injection: bool = False
    clarification: str | None = None
    question: str | None = None  # read-only question kind (see ee_agent.questions); None for planning
    test_id: str | None = None
    requirement_id: str | None = None
    build_defaulted: bool = False  # no build named: the latest build was used for a read-only question

    @property
    def action(self) -> str:
        if self.prohibited or self.injection:
            return "refuse"
        if self.clarification:
            return "clarify"
        return "answer" if self.question else "plan"


def _single(kind: str, found: list[str], known: Sequence[str] | None) -> tuple[str | None, str | None]:
    """(id, clarification) for a question that needs exactly one known id of this kind."""
    if len(found) > 1:
        return None, f"You mentioned several {kind}s ({', '.join(found)}). Which single {kind} did you mean?"
    if known is not None and found[0] not in known:
        return None, f"{kind.capitalize()} {found[0]} is not in the programme. Which {kind} did you mean?"
    return found[0], None


QUESTION_ENTITY = {
    "test_evidence": "test",
    "test_history": "test",
    "requirement_coverage": "requirement",
    "component_risk": "component",
    "component_defects": "component",
}


def _interpret_question(
    it: Interpretation,
    kind: str,
    build_ids: list[str],
    variant_ids: list[str],
    ids: dict[str, list[str]],
    known: dict[str, Sequence[str] | None],
    builds: list[str],
    variants: list[str],
) -> Interpretation:
    it.question = kind
    build_list, variant_list = ", ".join(builds), ", ".join(variants)
    if len(build_ids) > 1:
        it.clarification = (
            f"You mentioned several builds ({', '.join(build_ids)}). Which single build did you mean?"
        )
    elif build_ids and build_ids[0].upper() not in builds:
        it.clarification = (
            f"Build {build_ids[0]} is unknown. Known builds: {build_list}. Which one did you mean?"
        )
    elif build_ids:
        it.build_id = build_ids[0].upper()
    elif kind in AS_OF_KINDS or kind == "build_failures":
        it.build_id, it.build_defaulted = builds[-1], True  # "now" = the latest build; said in the answer
    entity = QUESTION_ENTITY.get(kind)
    if it.clarification is None and entity:
        value, it.clarification = _single(entity, ids[entity], known[entity])
        if entity == "test":
            it.test_id = value
        elif entity == "requirement":
            it.requirement_id = value
        elif value:
            it.component_ids = [value]
    if it.clarification is None:
        if len(variant_ids) > 1:
            it.clarification = (
                f"You mentioned several variants ({', '.join(variant_ids)}). Which one? "
                "Leave the variant out to cover all of them."
            )
        elif variant_ids and variant_ids[0] not in variants:
            it.clarification = f"Variant {variant_ids[0]} is unknown. Known variants: {variant_list}. Which one did you mean?"
        elif variant_ids:
            it.variant_id = variant_ids[0]
    return it


def interpret_request(
    text: str,
    builds: list[str],
    variants: list[str],
    components: list[str],
    tests: Sequence[str] | None = None,
    requirements: Sequence[str] | None = None,
) -> Interpretation:
    it = Interpretation()
    views = _intent_views(text)
    matched = [
        (perm, tool) for pattern, perm, tool in PROHIBITED_INTENTS if any(pattern.search(v) for v in views)
    ]
    it.prohibited = list(dict.fromkeys(matched))
    it.injection = any(INJECTION.search(v) for v in views)

    build_ids = sorted(set(re.findall(r"\bB\d{3}\b", text, re.I)))
    if re.search(r"\b(latest|current|newest)\s+build\b", text, re.I) and not build_ids:
        build_ids = [builds[-1]]
    variant_ids = sorted({v.upper() for v in re.findall(r"\bV\d+\b", text, re.I)})
    it.all_variants = bool(re.search(r"\b(all|every|any)\s+variants?\b", text, re.I))
    mentioned = sorted({m.upper() for m in re.findall(r"\bECU-[A-Z0-9_]+\b", text, re.I)})
    test_ids = sorted({t.upper() for t in re.findall(r"\bTC-\d{3}\b", text, re.I)})
    requirement_ids = sorted({r.upper() for r in re.findall(r"\bR-\d{3}\b", text, re.I)})

    # read-only questions; prohibited or injected requests are always refused, planning requests go on below
    if not (it.prohibited or it.injection):
        kind = classify_question(text, test_ids, requirement_ids, mentioned)
        if kind:
            ids = {"test": test_ids, "requirement": requirement_ids, "component": mentioned}
            known = {"test": tests, "requirement": requirements, "component": components}
            return _interpret_question(it, kind, build_ids, variant_ids, ids, known, builds, variants)

    it.component_ids = [c for c in mentioned if c in components]
    if m := re.search(r"(\d+(?:\.\d+)?)\s*(h|hours?)\b", text, re.I):
        it.budget_minutes = float(m.group(1)) * 60
    elif m := re.search(r"(\d+(?:\.\d+)?)\s*(min|mins|minutes)\b", text, re.I):
        it.budget_minutes = float(m.group(1))
    if m := re.search(r"\btop\s*(\d+)\b", text, re.I):
        it.top_n = max(1, min(int(m.group(1)), 50))

    build_list, variant_list = ", ".join(builds), ", ".join(variants)
    if len(build_ids) > 1:
        it.clarification = (
            f"You mentioned several builds ({', '.join(build_ids)}). Which single build should I plan for?"
        )
    elif not build_ids:
        it.clarification = f"Which software build should I plan validation for? Known builds: {build_list}."
    elif build_ids[0].upper() not in builds:
        it.clarification = (
            f"Build {build_ids[0]} is unknown. Known builds: {build_list}. Which one did you mean?"
        )
    else:
        it.build_id = build_ids[0].upper()

    if it.clarification is None:
        if len(variant_ids) > 1:
            it.clarification = (
                f"You mentioned several variants ({', '.join(variant_ids)}). Which variant, or all variants?"
            )
        elif variant_ids and variant_ids[0] not in variants:
            it.clarification = f"Variant {variant_ids[0]} is unknown. Known variants: {variant_list}. Which one did you mean?"
        elif variant_ids:
            it.variant_id = variant_ids[0]
        elif not it.all_variants:
            it.clarification = (
                f"Which vehicle variant should the plan cover ({variant_list}), or all variants?"
            )
    unknown = [c for c in mentioned if c not in components]
    if it.clarification is None and unknown:
        it.clarification = (
            f"Component(s) {', '.join(unknown)} are not in the programme. Which component did you mean?"
        )
    return it
