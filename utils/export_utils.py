import json
from typing import Dict

_STATUS_LABELS = {
    "agreed": "Consensus reached (structural checks passed)",
    "partial": "Partial agreement - human review needed",
    "incomplete": "Incomplete - no joint conclusion",
}


_PHASES = {
    "opening": "opening position", "tradeoffs": "trade-offs", "convergence": "convergence",
    "closing": "closing position", "conclusion": "joint conclusion",
    "stress": "stress test", "stress_outcome": "stress-test outcome",
}


def _scores_line(result: Dict) -> str:
    evaluation = result.get("evaluation") or {}
    agreement = evaluation.get("agreement") or {}
    parts = []
    if agreement.get("checks"):
        parts.append(f"Agreement score {agreement['score']}/100 ({agreement['label']})")
    for side, info in (evaluation.get("persona_consistency") or {}).items():
        parts.append(f"role consistency {side} {round(100 * info.get('coverage', 0))}%")
    return "; ".join(parts)


def _source_lines(result: Dict):
    for src in result.get("sources") or []:
        heading = f" - {src['heading']}" if src.get("heading") else ""
        yield f"[{src['id']}] {src.get('title', '')}{heading} ({src.get('source', '')})"


def _conclusion_blocks(result: Dict):
    conclusion = result.get("conclusion") or {}
    return [
        ("Joint decision", conclusion.get("decision") or result.get("final_decision", "")),
        ("Action plan", conclusion.get("action_plan", "")),
        ("Unresolved risks", conclusion.get("risks", "")),
    ]


def transcript_to_text(result: Dict) -> str:
    lines = [
        "CipherBridge Concord — Dialogue Transcript",
        "=" * 48,
        f"Topic: {result.get('topic', '')}",
        f"Stakeholder A: {result.get('persona_a', '')}",
        f"Stakeholder B: {result.get('persona_b', '')}",
        "",
    ]
    if _scores_line(result):
        lines += [_scores_line(result), ""]
    status = result.get("agreement_status")
    if status in ("agreed", "partial"):
        lines.append(f"FINAL CONCLUSION — {_STATUS_LABELS[status]}")
        lines.append("-" * 48)
        for title, body in _conclusion_blocks(result):
            if body:
                lines.append(f"{title}:")
                lines.append(body)
                lines.append("")
    for turn in result.get("turns", []):
        lines.append(f"Turn {turn['turn']} — {turn['speaker']} [{turn['type']}]")
        lines.append(turn["content"])
        lines.append("")
    sources = list(_source_lines(result))
    if sources:
        lines += ["Knowledge-base sources retrieved for this discussion:"] + sources + [""]
    lines.append("Consensus check: " + ("passed" if result.get("consensus_valid") else "needs manual review"))
    lines.append(result.get("consensus_note", ""))
    return "\n".join(lines)


def transcript_to_markdown(result: Dict) -> str:
    status = result.get("agreement_status", "incomplete")
    lines = [
        "# CipherBridge Concord — Decision Report",
        "",
        f"**Decision question:** {result.get('topic', '')}  ",
        f"**Stakeholders:** {result.get('persona_a', '')} ↔ {result.get('persona_b', '')}  ",
        f"**Outcome:** {_STATUS_LABELS.get(status, status)}",
        "",
    ]
    if _scores_line(result):
        lines += [f"**Quality checks:** {_scores_line(result)} (rule-based, not proof of correctness)", ""]
    meta = result.get("metadata") or {}
    if meta:
        lines += [f"**Generated:** {meta.get('generated_at', 'n/a')} · model {meta.get('model', 'n/a')}", ""]
    if result.get("context"):
        lines += [f"**Context and constraints:** {result['context']}", ""]
    if status in ("agreed", "partial"):
        lines += ["## Final conclusion", ""]
        for title, body in _conclusion_blocks(result):
            if body:
                lines += [f"### {title}", "", body, ""]
    lines += ["## Transcript", ""]
    for turn in result.get("turns", []):
        label = _PHASES.get(turn.get("phase"), turn["type"])
        lines += [f"### Turn {turn['turn']} — {turn['speaker']} ({label})", "", turn["content"], ""]
    sources = list(_source_lines(result))
    if sources:
        lines += ["## Sources (knowledge base)", ""] + [f"- {line}" for line in sources] + [
            "", "*Retrieved by BM25 keyword ranking. A citation shows the model referred to a note; it does not verify the claim.*", ""]
    lines += [
        "---",
        "*" + (result.get("consensus_note", "") or "Review required.") + "*",
        "*AI-generated content can be inaccurate. Review all security-critical recommendations before implementation.*",
    ]
    return "\n".join(lines)


def transcript_to_json(result: Dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
