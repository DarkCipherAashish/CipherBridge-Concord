"""Transparent, rule-based quality measures for a stakeholder dialogue.

These are lexical and structural heuristics. They make the result easier to
inspect, but they cannot prove genuine agreement, persona fidelity, or
technical correctness. Every check is listed so a reviewer can see why a score
was given."""
import re
from typing import Dict, List

from config.personas import PERSONAS
from services.consensus import (
    _contains_action_plan,
    _contains_decision,
    _explicit_agreement,
    extract_conclusion_sections,
    validate_consensus,
)

_VERIFY_WORDS = re.compile(r"\b(test|verify|review|benchmark|audit|validate|check|measure)\w*\b", re.I)


def _persona_terms(name: str) -> List[str]:
    persona = PERSONAS.get(name, {})
    terms = [t.lower() for t in persona.get("keywords", [])]
    for priority in persona.get("priorities", []):
        terms.append(priority.lower())
    return sorted(set(terms))


def _matches(text: str, terms: List[str]) -> List[str]:
    low = text.lower()
    return [t for t in terms if t in low]


def persona_consistency(turns: List[Dict], persona_a: str, persona_b: str) -> Dict:
    """Share of each stakeholder's turns that reflect at least one of their role's priorities."""
    out = {}
    for side, name in (("A", persona_a), ("B", persona_b)):
        terms = _persona_terms(name)
        mine = [t for t in turns if t.get("speaker") == name]
        hits, used = 0, set()
        for turn in mine:
            found = _matches(turn.get("content", ""), terms)
            if found:
                hits += 1
                used.update(found)
        coverage = round(hits / len(mine), 2) if mine else 0.0
        label = "Consistent" if coverage >= 0.8 else "Mostly consistent" if coverage >= 0.5 else "Low"
        out[side] = {
            "persona": name,
            "turns": len(mine),
            "turns_reflecting_role": hits,
            "coverage": coverage,
            "label": label,
            "terms_used": sorted(used)[:8],
        }
    return out


def agreement_evaluation(turns: List[Dict], persona_a: str, persona_b: str) -> Dict:
    """Score the closing exchange on seven visible checks (0-100)."""
    complete = (
        isinstance(turns, list)
        and len(turns) >= 4
        and all(isinstance(t, dict) and t.get("type") == "consensus" for t in turns[-2:])
    )
    if not complete:
        return {"score": 0, "label": "Not available", "checks": [],
                "note": "The discussion did not reach its closing turns."}

    closing, final = turns[-2]["content"], turns[-1]["content"]
    sections = extract_conclusion_sections(final)
    decision_plan = sections["decision"] + " " + sections["action_plan"]
    both_roles = all(_matches(decision_plan, _persona_terms(n)) for n in (persona_a, persona_b))
    owners = bool(
        re.search(r"\b(developer|cryptographer|researcher|engineer|manager|officer|owner)\b", sections["action_plan"], re.I)
        or persona_a.lower() in final.lower()
        or persona_b.lower() in final.lower()
    )
    checks = [
        ("Turn order and structure are valid", validate_consensus(turns) or _structure_ok(turns)),
        ("Both closing turns state agreement explicitly", _explicit_agreement(closing) and _explicit_agreement(final)),
        ("A shared decision is stated", _contains_decision(final) and bool(sections["decision"])),
        ("The action plan includes verification steps", _contains_action_plan(final) and bool(_VERIFY_WORDS.search(sections["action_plan"]))),
        ("Action steps name a responsible role", bool(sections["action_plan"]) and owners),
        ("Unresolved risks are listed", bool(sections["risks"])),
        ("The decision reflects both stakeholders' priorities", both_roles),
    ]
    passed = sum(1 for _, ok in checks if ok)
    score = round(100 * passed / len(checks))
    label = "Strong" if score >= 85 else "Moderate" if score >= 55 else "Weak"
    return {
        "score": score,
        "label": label,
        "checks": [{"name": n, "passed": bool(ok)} for n, ok in checks],
        "note": "Rule-based structural and keyword checks; not proof of agreement or correctness.",
    }


def _structure_ok(turns: List[Dict]) -> bool:
    """Turn numbering and strict alternation, ignoring the wording checks."""
    try:
        if any(t["turn"] != i for i, t in enumerate(turns, 1)):
            return False
        return all(turns[i]["speaker"] != turns[i - 1]["speaker"] for i in range(1, len(turns)))
    except (KeyError, TypeError):
        return False
