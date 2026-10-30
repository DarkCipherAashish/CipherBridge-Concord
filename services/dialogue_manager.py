import os
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

from config.personas import PERSONAS, get_persona
from services.consensus import (
    extract_conclusion_sections,
    get_consensus_report,
)
from services.evaluation import agreement_evaluation, persona_consistency
from services.rag import format_reference_notes, grounding_report
from services.rag import retrieve_sources as _retrieve_sources
from services.llm_client import chat_completion
from services.topic_validator import validate_topic


MIN_TURNS = 4
MAX_TURNS = 16


def retrieve_sources(topic: str, extra_context: str = "", top_k: int = 5) -> List[Dict]:
    """Retrieve knowledge-base passages relevant to a decision topic (RAG step)."""
    return _retrieve_sources(f"{topic} {(extra_context or '')[:300]}", top_k=top_k)


def _system_prompt(
    topic: str,
    persona_name: str,
    extra_context: str,
    reference_notes: str = "",
) -> str:
    """Build a role-specific prompt for a responsible security discussion."""
    persona = get_persona(persona_name)
    notes_block = f"\n{reference_notes}\n" if reference_notes else ""

    return f"""
You are a stakeholder in CipherBridge Concord, an educational
cryptography decision workspace.

YOUR ROLE: {persona_name}
ROLE GOAL: {persona['goal']}
COMMUNICATION STYLE: {persona['style']}
PRIORITIES: {', '.join(persona['priorities'])}

TOPIC: {topic}
ADDITIONAL CONTEXT: {extra_context or "No additional constraints supplied."}

SECURITY AND ACCURACY RULES:
1. Give technically responsible advice and distinguish facts from assumptions.
2. Never invent citations, test results, benchmarks, or security guarantees.
3. Prefer established standards and maintained, reputable libraries.
4. Never recommend inventing a custom cryptographic algorithm.
5. Avoid presenting example parameter values as universal requirements.
   Refer to current authoritative guidance and verify configurations
   before production deployment.
6. Identify meaningful uncertainty, operational risks, and unresolved
   decisions. Do not manufacture agreement.
7. Keep the response focused, practical, and readable.
8. Do not repeat your speaker name or add a turn number. The interface
   adds those labels automatically.

TOPIC-SPECIFIC GUIDANCE (apply only when it is relevant to the topic):
- Password storage: prefer a dedicated password-hashing algorithm such as
  Argon2id, with unique random salts and parameters benchmarked against the
  application's hardware and threat model. Do not suggest weakening rate
  limits merely because password hashing is computationally expensive.
- Pepper: treat it as an optional additional defense, not a replacement for
  salts, strong password hashing, or access controls. Keep pepper secrets
  separate from the password database, store only a pepper version as
  metadata, and never place secret pepper material in a stored hash string.
  Explain rotation and recovery trade-offs accurately.
{notes_block}
Return only the content of your contribution.
""".strip()


PHASE_INSTRUCTIONS = {
    "opening": (
        "OPENING POSITION: Briefly acknowledge the other stakeholder if they have already spoken, "
        "then state your role's key requirement and main concern about this decision. "
        "Do not propose a final decision yet."
    ),
    "tradeoffs": (
        "TRADE-OFFS: Respond to the other stakeholder's specific points. Concede what is valid, "
        "say which of your requirements are non-negotiable and which are flexible, and examine "
        "one concrete trade-off."
    ),
    "convergence": (
        "CONVERGENCE: Work toward a mutually acceptable approach. Propose or refine one concrete "
        "option that satisfies both roles' key requirements and state the conditions under which "
        "you could accept it. Do not claim a decision is final, and do not pretend to agree where "
        "you do not."
    ),
}


def _discussion_phase(index: int, discussion_turns: int) -> str:
    """Opening positions, then trade-offs, then convergence toward one proposal."""
    if index == discussion_turns - 1:
        return "convergence"
    if index == 0 or (index == 1 and discussion_turns >= 4):
        return "opening"
    return "tradeoffs" if index / discussion_turns < 0.6 else "convergence"


def turn_plan(total_turns: int, persona_a: str, persona_b: str) -> List[Dict]:
    """Describe who speaks each turn and in which phase.

    Stakeholders strictly alternate (A first). Discussion turns move from
    opening positions through trade-offs to convergence. The last two turns are
    the reserved closing turns: a closing position, then the joint conclusion."""
    plan = []
    for i in range(total_turns):
        side = "A" if i % 2 == 0 else "B"
        if i < total_turns - 2:
            phase = _discussion_phase(i, total_turns - 2)
        elif i == total_turns - 2:
            phase = "closing"
        else:
            phase = "conclusion"
        plan.append({
            "turn": i + 1,
            "side": side,
            "speaker": persona_a if side == "A" else persona_b,
            "phase": phase,
        })
    return plan


def _call_stakeholder(
    topic: str,
    speaker: str,
    other_speaker: str,
    history: List[Dict[str, str]],
    extra_context: str,
    turn_number: int,
    phase: str = "tradeoffs",
    reference_notes: str = "",
) -> str:
    """Generate one discussion contribution."""
    messages = [
        {
            "role": "system",
            "content": _system_prompt(
                topic=topic,
                persona_name=speaker,
                extra_context=extra_context,
                reference_notes=reference_notes,
            ),
        },
        *history,
        {
            "role": "user",
            "content": (
                f"This is discussion turn {turn_number}. "
                f"The other stakeholder is {other_speaker}.\n\n"
                f"{PHASE_INSTRUCTIONS.get(phase, PHASE_INSTRUCTIONS['tradeoffs'])}\n\n"
                "Respond directly to the discussion so far. "
                "Where your role's priorities differ from the other "
                "stakeholder's, say so respectfully and explain the "
                "trade-off; where you are persuaded, acknowledge it. "
                "Ask a relevant question only if it genuinely helps the "
                "decision. Do not repeat the entire previous discussion. "
                "Use approximately 100-180 words and do not claim that "
                "a decision has been finalized."
            ),
        },
    ]

    response = chat_completion(
        messages,
        temperature=0.45,
        max_tokens=450,
    )

    return _clean_turn(response)


def _clean_turn(content: str) -> str:
    """Remove common unwanted labels and whitespace from model output."""
    text = (content or "").strip()
    labels = list(PERSONAS) + ["Security Engineer", "Turn content", "Response"]

    for label in labels:
        for candidate in (f"**{label}:**", f"**{label}**:", f"{label}:"):
            if text.lower().startswith(candidate.lower()):
                return text[len(candidate):].strip()

    return text


def _generate_consensus(
    topic: str,
    speaker: str,
    other_speaker: str,
    history: List[Dict[str, str]],
    extra_context: str,
    turn_number: int,
    final_turn: bool,
    reference_notes: str = "",
) -> str:
    """Generate a concise, evidence-aware consensus or closing turn."""
    persona = get_persona(speaker)

    if final_turn:
        instruction = """
Write the SECOND and FINAL closing turn. Independently respond to the first
stakeholder's closing position. Use these exact headings:

Shared decision
Begin with an explicit sentence containing "I agree with the shared direction"
only if the discussion supports agreement. State the precise decision and
important boundaries. If agreement is incomplete, say "Full agreement has not
been reached" and label the outcome as a proposed next step, not consensus.

Action plan
Give no more than 3 numbered next steps. For each, name a responsible
stakeholder role and a concrete verification task.

Unresolved risks
List no more than 2 significant unresolved risks or dependencies.

Keep the response under 220 words. End with a complete sentence. Do not invent
owners, measurements, evidence, or security guarantees. Do not present an
untested configuration as production-ready. Explicitly confirm, qualify, or
reject the prior closing position; do not just summarize it.
"""
    else:
        instruction = """
Write the FIRST of the two closing turns: your explicit closing position.

Use these exact headings:
Closing position
Points of agreement
Conditions and remaining questions

State clearly whether YOU agree with a specific shared direction supported by
this discussion. If you agree, include the exact phrase "I agree with the
shared direction" and explain the conditions/limits. If genuine agreement is
not supported, say so clearly and propose the narrowest safe next step instead
of pretending consensus exists. Refer to the other stakeholder's actual points.
Do not write the final shared decision on behalf of both people; the next
stakeholder must independently confirm or qualify it. Keep under 160 words.
"""

    messages = [
        {
            "role": "system",
            "content": (
                f"You are {speaker} in CipherBridge Concord.\n"
                f"Role goal: {persona['goal']}\n\n"
                "Be concise, technically responsible, and honest about "
                "uncertainty. Review the actual dialogue before summarizing. "
                "Do not invent agreement, evidence, benchmarks, or security "
                "guarantees. Avoid repeating stakeholder labels inside the "
                "response. Follow the requested headings exactly. Return "
                "only the turn content."
                + (f"\n\n{reference_notes}" if reference_notes else "")
            ),
        },
        *history,
        {
            "role": "user",
            "content": (
                f"Topic: {topic}\n"
                f"Additional context: {extra_context or 'None supplied.'}\n"
                f"Other stakeholder: {other_speaker}\n"
                f"Turn number: {turn_number}\n\n"
                f"{instruction}"
            ),
        },
    ]

    response = chat_completion(
        messages,
        temperature=0.25,
        max_tokens=400 if final_turn else 300,
    )

    return _clean_turn(response)


def stream_dialogue(
    topic: str,
    persona_a: str,
    persona_b: str,
    total_turns: int = 8,
    extra_context: str = "",
    sources: Optional[List[Dict]] = None,
) -> Iterator[Dict]:
    """
    Yield each completed stakeholder turn to the UI.

    Each yielded turn is a complete model response. The application can
    display it immediately after that response finishes.
    """
    topic = (topic or "").strip()
    extra_context = (extra_context or "").strip()

    if not topic:
        raise ValueError("Topic cannot be empty.")
    topic_check = validate_topic(topic)
    if topic_check.status != "accepted":
        raise ValueError(topic_check.message)

    if persona_a == persona_b:
        raise ValueError("Choose two different stakeholder personas.")

    if not MIN_TURNS <= total_turns <= MAX_TURNS:
        raise ValueError(
            f"Total turns must be between {MIN_TURNS} and {MAX_TURNS}."
        )

    # Fail early if either persona is not recognized.
    get_persona(persona_a)
    get_persona(persona_b)

    history: List[Dict[str, str]] = []
    discussion_turns = total_turns - 2
    notes = format_reference_notes(sources)

    # Alternate stakeholders during the main discussion.
    for index in range(discussion_turns):
        speaker = persona_a if index % 2 == 0 else persona_b
        other = persona_b if speaker == persona_a else persona_a

        content = _call_stakeholder(
            topic=topic,
            speaker=speaker,
            other_speaker=other,
            history=history,
            extra_context=extra_context,
            turn_number=index + 1,
            phase=_discussion_phase(index, discussion_turns),
            reference_notes=notes,
        )

        if not content:
            raise RuntimeError(
                f"The model returned an empty response for turn {index + 1}."
            )

        turn = {
            "turn": index + 1,
            "speaker": speaker,
            "content": content,
            "type": "discussion",
            "phase": _discussion_phase(index, discussion_turns),
        }

        yield turn

        # Keep the transcript in the conversation history for the next turn.
        history.append(
            {
                "role": "assistant",
                "content": f"{speaker} said:\n{content}",
            }
        )
        history.append(
            {
                "role": "user",
                "content": (
                    f"Now continue as {other}. Respond to the previous "
                    "stakeholder's actual points and advance the discussion."
                ),
            }
        )

    # Penultimate turn: the first stakeholder states a closing position.
    # Keep every turn alternating, including the two reserved closing turns.
    penultimate_speaker = persona_a if discussion_turns % 2 == 0 else persona_b
    final_speaker = persona_b if penultimate_speaker == persona_a else persona_a

    penultimate_content = _generate_consensus(
        topic=topic,
        speaker=penultimate_speaker,
        other_speaker=final_speaker,
        history=history,
        extra_context=extra_context,
        turn_number=total_turns - 1,
        final_turn=False,
        reference_notes=notes,
    )

    if not penultimate_content:
        raise RuntimeError("The model returned an empty consensus turn.")

    yield {
        "turn": total_turns - 1,
        "speaker": penultimate_speaker,
        "content": penultimate_content,
        "type": "consensus",
        "phase": "closing",
    }

    history.append(
        {
            "role": "assistant",
            "content": (
                f"{penultimate_speaker} gave a closing position:\n"
                f"{penultimate_content}"
            ),
        }
    )

    # Final turn: the second stakeholder confirms or qualifies, and states the
    # joint decision, a short action plan, and unresolved risks.
    final_content = _generate_consensus(
        topic=topic,
        speaker=final_speaker,
        other_speaker=penultimate_speaker,
        history=history,
        extra_context=extra_context,
        turn_number=total_turns,
        final_turn=True,
        reference_notes=notes,
    )

    if not final_content:
        raise RuntimeError("The model returned an empty final turn.")

    yield {
        "turn": total_turns,
        "speaker": final_speaker,
        "content": final_content,
        "type": "consensus",
        "phase": "conclusion",
    }


def build_result(
    topic: str,
    persona_a: str,
    persona_b: str,
    turns: List[Dict],
    extra_context: str = "",
    total_turns: Optional[int] = None,
    model: Optional[str] = None,
    sources: Optional[List[Dict]] = None,
) -> Dict:
    """Assemble the decision record (complete or partial) from generated turns."""
    report = get_consensus_report(turns)
    complete = (
        len(turns) >= 4
        and all(t.get("type") == "consensus" for t in turns[-2:])
    )
    final_text = turns[-1]["content"] if complete else ""
    sections = (
        extract_conclusion_sections(final_text)
        if complete
        else {"decision": "", "action_plan": "", "risks": ""}
    )
    return {
        "schema_version": "1.2",
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": (model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")).strip(),
            "turns_requested": total_turns or len(turns),
            "turns_generated": len(turns),
            "stakeholder_a": persona_a,
            "stakeholder_b": persona_b,
            "retrieval": {
                "enabled": bool(sources),
                "method": "BM25 (lexical keyword ranking)",
                "sources_retrieved": len(sources or []),
            },
        },
        "sources": list(sources or []),
        "topic": (topic or "").strip(),
        "persona_a": persona_a,
        "persona_b": persona_b,
        "context": (extra_context or "").strip(),
        "turns": turns,
        "concluding_agreement": {
            "status": report["status"],
            "statement": (sections["decision"] or final_text) if complete else "",
            "closing_positions": [
                {"turn": t["turn"], "speaker": t["speaker"], "content": t["content"]}
                for t in turns[-2:]
            ] if complete else [],
        },
        "evaluation": {
            "agreement": agreement_evaluation(turns, persona_a, persona_b),
            "persona_consistency": persona_consistency(turns, persona_a, persona_b),
            "grounding": grounding_report(turns, sources),
        },
        "conclusion": sections,
        "final_decision": sections["decision"] or final_text,
        "rationale": turns[-2]["content"] if complete else "",
        "action_plan": sections["action_plan"],
        "remaining_risks": sections["risks"],
        "agreement_status": report["status"],
        "consensus_valid": report["valid"],
        "consensus_validation": report,
        "consensus_note": (
            report["message"]
            + " Technical correctness and genuine agreement still require human review."
            if complete
            else "Incomplete generation; manual review required."
        ),
    }


def generate_dialogue(
    topic: str,
    persona_a: str,
    persona_b: str,
    total_turns: int = 8,
    extra_context: str = "",
    use_knowledge_base: bool = True,
) -> Dict:
    """Generate and return a complete transcript, optionally grounded in the knowledge base (RAG)."""
    sources = retrieve_sources(topic, extra_context) if use_knowledge_base else []
    turns = list(
        stream_dialogue(
            topic=topic,
            persona_a=persona_a,
            persona_b=persona_b,
            total_turns=total_turns,
            extra_context=extra_context,
            sources=sources,
        )
    )
    return build_result(topic, persona_a, persona_b, turns, extra_context, total_turns, sources=sources)


STRESS_SCENARIOS = {
    "budget": ("Limited budget", "Budget and engineering time are cut by half."),
    "audit": ("External audit", "An external auditor will review this decision and asks for evidence."),
    "attacker": ("Stronger attacker", "The threat model is upgraded to a well-resourced attacker with access to backups and logs."),
    "scale": ("100x growth", "Usage and data volume grow 100 times within a year."),
}


def _transcript_block(turns: List[Dict]) -> str:
    return "\n\n".join(f"[Turn {t['turn']} - {t['speaker']}]\n{t['content']}" for t in turns)


def stress_test_turns(result: Dict, scenario_key: str) -> Iterator[Dict]:
    """Test a completed decision against a new scenario.

    Three turns follow the original conclusion: one stakeholder assesses whether
    the decision still holds, the other confirms or challenges that assessment,
    and the first then writes revised guidance. This is advisory output and is
    not validated as consensus."""
    if scenario_key not in STRESS_SCENARIOS:
        raise ValueError("Unknown stress-test scenario.")
    if result.get("agreement_status") not in ("agreed", "partial") or not result.get("turns"):
        raise ValueError("Stress tests need a completed discussion with a conclusion.")

    persona_a, persona_b = result["persona_a"], result["persona_b"]
    get_persona(persona_a)
    get_persona(persona_b)
    base = result["turns"]
    label, scenario = STRESS_SCENARIOS[scenario_key]
    last = base[-1]["speaker"]
    second = last
    first = persona_b if last == persona_a else persona_a

    steps = [
        (first, "stress",
         "State whether the agreed decision still holds from your role's perspective, what would "
         "change, and what you would need. Use at most 120 words."),
        (second, "stress",
         "Respond to the other stakeholder's assessment. Confirm, qualify, or challenge it from your "
         "role's perspective. Use at most 120 words."),
        (first, "stress_outcome",
         "Write REVISED GUIDANCE under that heading: say whether the decision stands or what should "
         "be adjusted (at most 2 adjustments, each with a verification step) and one remaining risk. "
         "If you and the other stakeholder still disagree, say so plainly. Use under 150 words."),
    ]

    produced: List[Dict] = []
    for i, (speaker, phase, instruction) in enumerate(steps):
        other = second if speaker == first else first
        discussion = _transcript_block(produced) if produced else "None yet."
        messages = [
            {
                "role": "system",
                "content": _system_prompt(
                    result["topic"], speaker, result.get("context", ""),
                    format_reference_notes(result.get("sources")),
                ),
            },
            {
                "role": "user",
                "content": (
                    f"ORIGINAL DISCUSSION AND CONCLUSION:\n{_transcript_block(base)}\n\n"
                    f"NEW SCENARIO ({label}): {scenario}\n\n"
                    f"STRESS-TEST DISCUSSION SO FAR:\n{discussion}\n\n"
                    f"You are {speaker}; the other stakeholder is {other}.\n{instruction}\n"
                    "Do not invent evidence, benchmarks, or security guarantees."
                ),
            },
        ]
        content = _clean_turn(chat_completion(messages, temperature=0.35, max_tokens=420))
        if not content:
            raise RuntimeError("The model returned an empty stress-test turn.")
        turn = {
            "turn": len(base) + i + 1,
            "speaker": speaker,
            "content": content,
            "type": "stress",
            "phase": phase,
            "scenario": scenario_key,
        }
        produced.append(turn)
        yield turn
