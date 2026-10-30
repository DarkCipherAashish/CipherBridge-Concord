"""Structural consensus checks; not a technical correctness verifier."""
import re
from typing import Dict, List


def _contains_action_plan(text: str) -> bool:
    return bool(re.search(r"\b(action plan|next steps|verification steps)\b", text, re.I)) and bool(
        re.search(r"\b(test|verify|review|implement|assign|document|validate|deploy|check|benchmark|audit)\w*\b", text, re.I)
    )


def _contains_decision(text: str) -> bool:
    return bool(re.search(r"\b(shared decision|agreed approach|we will|the decision is|joint recommendation|we recommend)\b", text, re.I))


def _explicit_agreement(text: str) -> bool:
    # Intentionally require a first-person or explicitly joint statement.
    return bool(re.search(r"\b(i agree|we agree|both stakeholders agree|both sides agree|i support this|we support this)\b", text, re.I))


def validate_consensus(turns: List[Dict]) -> bool:
    if not isinstance(turns, list) or len(turns) < 4:
        return False
    required = {"turn", "speaker", "content", "type"}
    speakers = []
    for i, turn in enumerate(turns, 1):
        if not isinstance(turn, dict) or not required.issubset(turn):
            return False
        if turn.get("turn") != i or not isinstance(turn.get("content"), str) or not turn["content"].strip():
            return False
        if not isinstance(turn.get("speaker"), str) or not turn["speaker"].strip():
            return False
        speakers.append(turn["speaker"])
    unique_speakers = set(speakers)
    if len(unique_speakers) != 2 or any(speakers[i] == speakers[i-1] for i in range(1, len(turns))):
        return False
    if turns[-2].get("type") != "consensus" or turns[-1].get("type") != "consensus":
        return False
    penultimate = turns[-2]["content"].lower()
    final = turns[-1]["content"].lower()
    # Both closing stakeholders must explicitly state their position. The
    # final turn must also name the shared decision, action plan, and risks.
    return (
        _explicit_agreement(penultimate)
        and _explicit_agreement(final)
        and _contains_decision(final)
        and _contains_action_plan(final)
        and turns[-2].get("speaker") != turns[-1].get("speaker")
        and bool(
        re.search(r"\b(unresolved risks|remaining risks|risks|assumptions)\b", final)
        )
        and final.rstrip().endswith((".", "!", "?"))
    )


def agreement_status(turns: List[Dict]) -> str:
    """Return 'agreed', 'partial' (closing turns exist but agreement is not
    confirmed), or 'incomplete' (the discussion did not reach its closing turns)."""
    if validate_consensus(turns):
        return "agreed"
    if (
        isinstance(turns, list)
        and len(turns) >= 4
        and all(isinstance(t, dict) and t.get("type") == "consensus" for t in turns[-2:])
    ):
        return "partial"
    return "incomplete"


_SECTION_ALIASES = (
    ("decision", ("shared decision", "joint decision", "decision")),
    ("action_plan", ("action plan", "next steps")),
    ("risks", ("unresolved risks", "remaining risks", "risks")),
)


def _heading_key(line: str):
    """Return (section_key, text_after_heading) if the line starts a section."""
    cleaned = re.sub(r"^[#>\-\s]+", "", line).replace("*", "").strip()
    low = cleaned.lower()
    for key, aliases in _SECTION_ALIASES:
        for alias in aliases:
            if low == alias or low == alias + ":":
                return key, ""
            if low.startswith(alias + ":"):
                return key, cleaned[len(alias) + 1:].strip()
    return None, ""


def extract_conclusion_sections(text: str) -> Dict[str, str]:
    """Split a final closing turn into decision / action plan / risks.

    Tolerates markdown headings, bold headings, and 'Heading: text' lines. Text
    with no recognisable headings is returned whole as the decision."""
    buffers = {"decision": [], "action_plan": [], "risks": []}
    preamble: List[str] = []
    current = None
    for line in (text or "").splitlines():
        key, rest = _heading_key(line)
        if key:
            current = key
            if rest:
                buffers[key].append(rest)
            continue
        (buffers[current] if current else preamble).append(line)
    sections = {k: "\n".join(v).strip() for k, v in buffers.items()}
    pre = "\n".join(preamble).strip()
    if pre:
        sections["decision"] = (pre + "\n\n" + sections["decision"]).strip()
    return sections


def get_consensus_report(turns: List[Dict]) -> Dict:
    valid = validate_consensus(turns)
    checks = {
        "minimum_turn_count": isinstance(turns, list) and len(turns) >= 4,
        "turn_structure": isinstance(turns, list) and all(isinstance(t, dict) and all(k in t for k in ("turn","speaker","content","type")) for t in turns),
        "alternating_speakers": isinstance(turns, list) and len(turns) >= 2 and all(turns[i].get("speaker") != turns[i-1].get("speaker") for i in range(1, len(turns)) if isinstance(turns[i],dict) and isinstance(turns[i-1],dict)),
        "both_closing_positions_explicit": isinstance(turns, list) and len(turns) >= 2 and isinstance(turns[-2], dict) and isinstance(turns[-1], dict) and _explicit_agreement(turns[-2].get("content", "")) and _explicit_agreement(turns[-1].get("content", "")),
        "final_consensus_sections": valid,
    }
    return {
        "valid": valid,
        "status": agreement_status(turns),
        "checks": checks,
        "message": "Structural checks passed; human review is still required." if valid else "Structural validation failed. Check turn order, alternating speakers, explicit agreement, shared decision, action plan, and risks.",
    }
