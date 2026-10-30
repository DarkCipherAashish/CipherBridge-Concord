"""Chat-style Stakeholder Decision Workspace.

The user types a cryptography decision in a chat box. Two stakeholders discuss
it turn by turn (opening positions, trade-offs, convergence), then close with
one joint conclusion shown as a final card. Out-of-scope topics get a
professional scope message instead of a discussion."""
import html
from typing import Dict, List, Optional, Tuple

import streamlit as st

from config.personas import DEFAULT_PERSONAS, PERSONAS
from services.dialogue_manager import (
    MAX_TURNS,
    MIN_TURNS,
    STRESS_SCENARIOS,
    build_result,
    retrieve_sources,
    stream_dialogue,
    stress_test_turns,
    turn_plan,
)
from services.llm_client import LLMConfigurationError, LLMRequestError
from services.topic_validator import validate_topic
from utils.export_utils import transcript_to_json, transcript_to_markdown, transcript_to_text
from utils.history_store import save_result
from utils.pdf_export import transcript_to_pdf

DEFAULT_TURNS = 8

QUICK_STARTS = [
    ("🔑", "Password storage", "Choosing a secure approach for storing user passwords in a web application"),
    ("💬", "Secure messaging", "Selecting an encryption approach and key-management strategy for a secure messaging application"),
    ("☁️", "Cloud key management", "Choosing how encryption keys should be generated, stored, rotated, and recovered in a cloud application"),
    ("🗄️", "Database encryption", "Deciding between application-level encryption and managed database encryption for sensitive customer records"),
    ("⚛️", "Post-quantum migration", "Planning a practical migration path toward post-quantum cryptography for a service with long-lived sensitive data"),
    ("🔒", "TLS configuration", "Selecting a secure and maintainable TLS configuration for a public-facing web service"),
]

PHASE_ORDER = ["opening", "tradeoffs", "convergence", "closing", "conclusion"]
PHASE_LABELS = {
    "opening": "Opening position",
    "tradeoffs": "Trade-offs",
    "convergence": "Convergence",
    "closing": "Closing position",
    "conclusion": "Joint conclusion",
    "discussion": "Discussion",
    "stress": "Stress test",
    "stress_outcome": "Revised guidance",
}
_STRESS_ICONS = {"budget": "💸", "audit": "🧾", "attacker": "🕵️", "scale": "📈"}

_NOTICE_STYLE = {
    "scope": ("🧭", "notice-warn"),
    "clarify": ("💡", "notice-info"),
    "welcome": ("👋", "notice-info"),
    "setup": ("🔧", "notice-warn"),
    "error": ("🚨", "notice-bad"),
}

_STATUS_BADGES = {
    "agreed": ("Consensus reached", "badge-ok"),
    "partial": ("Partial agreement · review needed", "badge-warn"),
    "incomplete": ("Incomplete · no joint conclusion", "badge-bad"),
}


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _shorten(text: str, limit: int = 650) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def _init_state() -> None:
    defaults = {
        "ws_messages": [],
        "ws_pending": None,
        "ws_stress": None,
        "ws_persona_a": DEFAULT_PERSONAS[0],
        "ws_persona_b": DEFAULT_PERSONAS[1],
        "ws_turns": DEFAULT_TURNS,
        "ws_context": "",
        "ws_save_history": True,
        "ws_use_rag": True,
        "ws_counter": 0,
        "ws_pdf_cache": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# --------------------------------------------------------------------------- #
# Header and settings
# --------------------------------------------------------------------------- #
def _render_header() -> None:
    left, right = st.columns([5, 1])
    with left:
        st.markdown(
            '<div class="eyebrow">CIPHERBRIDGE CONCORD</div>'
            '<p class="ws-title">Stakeholder Decision Workspace</p>'
            '<p class="ws-sub">Describe a cryptography decision. Two stakeholders discuss it and '
            'agree on one final conclusion.</p>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button("＋ New decision", key="ws_new", use_container_width=True,
                     disabled=not st.session_state.ws_messages):
            st.session_state.ws_messages = []
            st.rerun()


def _render_settings() -> Tuple[str, str, int, str]:
    names = list(PERSONAS)
    with st.expander("⚙️ Workspace settings · stakeholders, turns, context", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            persona_a = st.selectbox(
                "Stakeholder A · opens the discussion", names, key="ws_persona_a",
                format_func=lambda n: f"{PERSONAS[n]['icon']} {n}",
            )
        options_b = [n for n in names if n != persona_a]
        if st.session_state.get("ws_persona_b") not in options_b:
            fallback = DEFAULT_PERSONAS[1]
            st.session_state["ws_persona_b"] = fallback if fallback in options_b else options_b[0]
        with c2:
            persona_b = st.selectbox(
                "Stakeholder B · challenges and complements A", options_b, key="ws_persona_b",
                format_func=lambda n: f"{PERSONAS[n]['icon']} {n}",
            )
        ca, cb = st.columns(2)
        for col, name in ((ca, persona_a), (cb, persona_b)):
            with col:
                p = PERSONAS[name]
                st.markdown(
                    f'<div class="section-card"><strong>{p["icon"]} {_esc(name)}</strong>'
                    f'<p class="helper">{_esc(p["goal"])}</p>'
                    f'<small>Priorities: {_esc(", ".join(p["priorities"]))}</small></div>',
                    unsafe_allow_html=True,
                )
        turns = st.slider(
            "Number of turns", MIN_TURNS, MAX_TURNS, key="ws_turns",
            help="Stakeholders alternate, so an even number gives both equal airtime. The discussion moves from "
                 "opening positions through trade-offs to convergence; the last two turns are always reserved "
                 "for the closing position and the joint conclusion.",
        )
        context = st.text_area(
            "Context, constraints and success criteria (optional)", key="ws_context", height=90,
            placeholder="Example: small team; must use maintained libraries; latency matters; limited budget.",
            help="Add environment, budget, standards, or what a successful decision must address. "
                 "Do not enter passwords, private keys, or other secrets.",
        )
        st.checkbox(
            "Ground the discussion in the knowledge base (RAG)", key="ws_use_rag",
            help="Retrieves relevant cryptography notes and gives them to both stakeholders, who cite them as "
                 "[S1], [S2]… Passages are sent to the AI provider inside the prompt. Turn off to rely on the "
                 "model's general knowledge. Manage notes on the Knowledge Base page.",
        )
        st.checkbox(
            "Save completed decisions to local history", key="ws_save_history",
            help="Saves each completed transcript as a file on this computer (the data/ folder) so it can be "
                 "reopened from the Decision History page. Nothing is uploaded anywhere else.",
        )
    a, b = PERSONAS[persona_a], PERSONAS[persona_b]
    st.markdown(
        f'<div class="panel-strip">Panel:'
        f'<span class="panel-chip">{a["icon"]} {_esc(persona_a)}</span>↔'
        f'<span class="panel-chip">{b["icon"]} {_esc(persona_b)}</span>'
        f'<span class="panel-chip">{int(turns)} turns</span></div>',
        unsafe_allow_html=True,
    )
    return persona_a, persona_b, int(turns), (context or "").strip()


# --------------------------------------------------------------------------- #
# Small renderers
# --------------------------------------------------------------------------- #
def _turn_header(speaker: str, side: str, phase: str, turn: int, total: int, icon: str,
                 note: Optional[str] = None) -> str:
    s = side.lower()
    return (
        f'<div class="turn-head side-{s}"><span class="speaker">{icon} {_esc(speaker)}</span>'
        f'<span class="pill pill-{s}">Stakeholder {side}</span>'
        f'<span class="pill pill-phase">{PHASE_LABELS.get(phase, "")}</span>'
        f'<span class="turn-no">{_esc(note) if note else f"Turn {turn} of {total}"}</span></div>'
    )


def _tracker_html(phases: List[str], current: Optional[str] = None, counts: Optional[Dict[str, int]] = None) -> str:
    """Step indicator: Opening › Trade-offs › Convergence › Closing › Conclusion."""
    cur = phases.index(current) if current in phases else len(phases)
    parts = []
    for i, phase in enumerate(phases):
        state = "done" if i < cur else "active" if i == cur else "todo"
        label = PHASE_LABELS[phase] + (f" ×{counts[phase]}" if counts and counts.get(phase, 0) > 1 else "")
        parts.append(f'<span class="step step-{state}">{label}</span>')
    return '<div class="tracker">' + '<span class="sep">›</span>'.join(parts) + "</div>"


def _flow_from_turns(turns: List[Dict]) -> Tuple[List[str], Dict[str, int]]:
    counts: Dict[str, int] = {}
    for t in turns:
        if t.get("phase") in PHASE_ORDER:
            counts[t["phase"]] = counts.get(t["phase"], 0) + 1
    return [p for p in PHASE_ORDER if p in counts], counts


def _positions(result: Dict) -> Dict[str, Dict]:
    """Each stakeholder's first and last contribution, for the position comparison."""
    turns = result.get("turns", [])
    out = {}
    for side, name in (("A", result.get("persona_a")), ("B", result.get("persona_b"))):
        mine = [t for t in turns if t.get("speaker") == name]
        out[side] = {
            "name": name,
            "opening": mine[0]["content"] if mine else "",
            "closing": mine[-1]["content"] if len(mine) > 1 else "",
        }
    return out


def _pdf_bytes(result: Dict, rid) -> Optional[bytes]:
    cache = st.session_state.ws_pdf_cache
    if rid not in cache:
        try:
            cache[rid] = transcript_to_pdf(result)
        except Exception:  # noqa: BLE001 - PDF is optional; the other exports still work
            cache[rid] = None
    return cache[rid]


def _quick_start_buttons(prefix: str, items) -> None:
    cols = st.columns(3)
    for i, (icon, label, question) in enumerate(items):
        if cols[i % 3].button(f"{icon} {label}", key=f"ws_qs_{prefix}_{i}", use_container_width=True):
            st.session_state.ws_pending = question
            st.rerun()


# --------------------------------------------------------------------------- #
# Message rendering
# --------------------------------------------------------------------------- #
def _render_welcome() -> None:
    with st.chat_message("assistant", avatar="🔐"):
        st.markdown("**Welcome. What cryptography decision can I help you reach?**")
        st.markdown(
            '<div class="how-grid">'
            '<div class="how-card"><b>1 · Describe</b><span>Type your decision in the box below.</span></div>'
            '<div class="how-card"><b>2 · Discuss</b><span>Two stakeholders move from opening positions, through trade-offs, to a proposal.</span></div>'
            '<div class="how-card"><b>3 · Decide</b><span>They close with one agreed conclusion, action plan and risks, then you can stress-test it.</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("**Quick start — pick a common decision:**")
        _quick_start_buttons("welcome", QUICK_STARTS)


def _render_notice(msg: Dict, idx: int, show_examples: bool) -> None:
    icon, css = _NOTICE_STYLE.get(msg.get("level"), _NOTICE_STYLE["clarify"])
    with st.chat_message("assistant", avatar=icon):
        st.markdown(
            f'<div class="{css}"><div class="notice-title">{_esc(msg.get("title"))}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(msg.get("content", ""))
        if msg.get("examples") and show_examples:
            st.markdown("**Try a supported decision:**")
            _quick_start_buttons(f"n{idx}", QUICK_STARTS[:3])


def _render_sources(msg: Dict) -> None:
    sources = msg.get("sources") or []
    with st.chat_message("assistant", avatar="📚"):
        if not sources:
            st.markdown("**Knowledge base:** no relevant passages were found for this topic, so the stakeholders "
                        "rely on the model's general knowledge. Add your own notes on the **Knowledge Base** page "
                        "to improve coverage.")
            return
        plural = "s" if len(sources) != 1 else ""
        st.markdown(f"**Retrieved {len(sources)} reference passage{plural} from the knowledge base.** "
                    f"Both stakeholders can cite them as {', '.join('[' + x['id'] + ']' for x in sources)}.")
        for src in sources:
            heading = f" — {src['heading']}" if src.get("heading") else ""
            st.markdown(f"- **[{src['id']}]** {src['title']}{heading} · _{src['source']}_")
        with st.expander("Show retrieved passages"):
            for src in sources:
                st.markdown(f"**[{src['id']}] {src['title']}** · relevance {src['score']}")
                st.markdown(src["text"])


def _render_turn(msg: Dict) -> None:
    with st.chat_message("assistant", avatar=msg.get("icon", "💬")):
        st.markdown(
            _turn_header(msg["speaker"], msg["side"], msg["phase"], msg["turn"], msg["total"],
                         msg.get("icon", ""), msg.get("note")),
            unsafe_allow_html=True,
        )
        st.markdown(msg["content"])


def _render_conclusion(msg: Dict, show_stress: bool = False) -> None:
    result, rid = msg["result"], msg["id"]
    status = result.get("agreement_status", "incomplete")
    badge_text, badge_css = _STATUS_BADGES.get(status, _STATUS_BADGES["incomplete"])
    evaluation = result.get("evaluation") or {}
    agreement = evaluation.get("agreement") or {}
    consistency = evaluation.get("persona_consistency") or {}

    with st.chat_message("assistant", avatar="🤝"):
        st.markdown(
            f'<div class="concl-head"><span class="eyebrow">FINAL CONCLUSION</span>'
            f'<span class="badge {badge_css}">{badge_text}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**Decision question:** {result.get('topic', '')}")
        st.caption(f"{result.get('persona_a', '—')}  ↔  {result.get('persona_b', '—')} · {len(result.get('turns', []))} turns")

        if status == "incomplete":
            st.warning(
                "The discussion stopped before the closing turns, so there is no joint conclusion. "
                "The partial transcript above and the exports below are for reference only."
            )
        else:
            sections = result.get("conclusion") or {}
            with st.container(border=True):
                st.markdown('<div class="step-label">Joint decision</div>', unsafe_allow_html=True)
                st.markdown(sections.get("decision") or result.get("final_decision", ""))
            col_plan, col_risk = st.columns(2)
            with col_plan:
                with st.container(border=True):
                    st.markdown('<div class="step-label">Action plan</div>', unsafe_allow_html=True)
                    st.markdown(sections.get("action_plan") or "_Not stated in the closing turn._")
            with col_risk:
                with st.container(border=True):
                    st.markdown('<div class="step-label">Unresolved risks</div>', unsafe_allow_html=True)
                    st.markdown(sections.get("risks") or "_Not stated in the closing turn._")
            if status == "agreed":
                st.caption("Both stakeholders explicitly confirmed the shared direction. Structural checks passed; "
                           "this does not certify technical correctness.")
            else:
                st.warning("Full agreement was not confirmed. Treat the decision above as a proposed next step, "
                           "not a settled consensus.")

            phases, counts = _flow_from_turns(result.get("turns", []))
            if phases:
                st.markdown('<div class="step-label">How they got here</div>', unsafe_allow_html=True)
                st.markdown(_tracker_html(phases, None, counts), unsafe_allow_html=True)

            if agreement.get("checks"):
                st.progress(agreement["score"] / 100,
                            text=f"Agreement score: {agreement['score']}/100 · {agreement['label']}")
            if consistency:
                cols = st.columns(len(consistency))
                for col, (_side, info) in zip(cols, consistency.items()):
                    col.metric(
                        f"Role consistency · {str(info.get('persona', '')).split(' / ')[0]}",
                        f"{round(100 * info.get('coverage', 0))}%",
                        help="Share of this stakeholder's turns that mention terms tied to their role. "
                             "A keyword measure, not proof of persona fidelity.",
                    )

            grounding = evaluation.get("grounding") or {}
            if result.get("sources"):
                st.caption(f"📚 Evidence grounding: {grounding.get('turns_citing_sources', 0)} of "
                           f"{grounding.get('turns', 0)} turns cite a retrieved source. A citation shows the model "
                           "referred to a note; it does not verify the claim.")
                if grounding.get("invalid_citations"):
                    st.warning("Some turns cite sources that were not retrieved ("
                               + ", ".join(grounding["invalid_citations"]) + "). Treat those references as unverified.")

            if show_stress:
                st.markdown('<div class="step-label">Stress-test this decision</div>', unsafe_allow_html=True)
                cols = st.columns(len(STRESS_SCENARIOS))
                for col, (key, (label, _desc)) in zip(cols, STRESS_SCENARIOS.items()):
                    if col.button(f"{_STRESS_ICONS.get(key, '🧪')} {label}", key=f"ws_stress_{rid}_{key}",
                                  use_container_width=True, help=_desc):
                        st.session_state.ws_stress = (rid, key)
                        st.rerun()

            with st.expander("🔍 Compare positions · where each stakeholder started and ended"):
                positions = _positions(result)
                left, right = st.columns(2)
                for col, side in ((left, "A"), (right, "B")):
                    info = positions[side]
                    persona = PERSONAS.get(info["name"], {})
                    with col:
                        st.markdown(f"**{persona.get('icon', '')} {info['name']}**")
                        if persona.get("priorities"):
                            st.caption("Priorities: " + ", ".join(persona["priorities"]))
                        st.markdown("**Opening position**")
                        st.markdown(_shorten(info["opening"]) or "_Not available._")
                        st.markdown("**Closing position**")
                        st.markdown(_shorten(info["closing"]) or "_Not available._")

        if result.get("sources"):
            cited = set((evaluation.get("grounding") or {}).get("sources_cited", []))
            with st.expander(f"📚 Sources used · {len(cited)} cited of {len(result['sources'])} retrieved"):
                for src in result["sources"]:
                    heading = f" — {src['heading']}" if src.get("heading") else ""
                    mark = "✅ cited" if src["id"] in cited else "not cited"
                    st.markdown(f"**[{src['id']}] {src['title']}**{heading} · _{src['source']}_ · {mark}")
                    st.markdown(src["text"])

        with st.expander("🧪 Validation and human review"):
            if agreement.get("checks"):
                for check in agreement["checks"]:
                    st.write(("✅" if check["passed"] else "⚠️") + " " + check["name"])
                st.caption(agreement.get("note", ""))
            else:
                checks = (result.get("consensus_validation") or {}).get("checks", {})
                for name, passed in checks.items():
                    st.write(("✅" if passed else "⚠️") + " " + name.replace("_", " ").capitalize())
                if not checks:
                    st.caption("No complete validation report is available for a partial transcript.")
            for _side, info in consistency.items():
                if info.get("terms_used"):
                    st.caption(f"{info['persona']}: role terms seen — {', '.join(info['terms_used'])}")
            st.markdown("**Human review checklist**")
            st.checkbox("The recommendation matches the actual threat model and data sensitivity.", key=f"ws_rev_{rid}_1")
            st.checkbox("Algorithms, modes, parameters, and libraries are verified against authoritative guidance.", key=f"ws_rev_{rid}_2")
            st.checkbox("Key management, recovery, logging, and access controls have named owners.", key=f"ws_rev_{rid}_3")
            st.checkbox("Performance claims are measured rather than assumed.", key=f"ws_rev_{rid}_4")
            st.caption("These are review reminders, not automated security certification.")

        has_turns = bool(result.get("turns"))
        pdf = _pdf_bytes(result, rid) if has_turns else None
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button("⬇️ PDF report", pdf or b"", f"cipherbridge_decision_{rid}.pdf", "application/pdf",
                           key=f"ws_dl_pdf_{rid}", disabled=pdf is None, use_container_width=True,
                           help=None if pdf else "PDF export needs the reportlab package (pip install reportlab).")
        d2.download_button("⬇️ Markdown", transcript_to_markdown(result), f"cipherbridge_decision_{rid}.md",
                           "text/markdown", key=f"ws_dl_md_{rid}", disabled=not has_turns, use_container_width=True)
        d3.download_button("⬇️ TXT", transcript_to_text(result), f"cipherbridge_decision_{rid}.txt",
                           "text/plain", key=f"ws_dl_txt_{rid}", disabled=not has_turns, use_container_width=True)
        d4.download_button("⬇️ JSON", transcript_to_json(result), f"cipherbridge_decision_{rid}.json",
                           "application/json", key=f"ws_dl_json_{rid}", disabled=not has_turns, use_container_width=True)
        if result.get("history_id"):
            st.caption("💾 Saved to Decision History on this computer.")
        st.caption("Academic prototype · AI-generated content can be inaccurate. Review security-critical "
                   "recommendations before implementation.")


def _render_message(msg: Dict, idx: int, is_last: bool, show_stress: bool = False) -> None:
    kind = msg.get("kind")
    if kind == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    elif kind == "notice":
        _render_notice(msg, idx, show_examples=is_last)
    elif kind == "sources":
        _render_sources(msg)
    elif kind == "turn":
        _render_turn(msg)
    elif kind == "conclusion":
        _render_conclusion(msg, show_stress=show_stress)


# --------------------------------------------------------------------------- #
# Processing
# --------------------------------------------------------------------------- #
def _add_notice(level: str, title: str, content: str, examples: bool = False) -> None:
    msgs = st.session_state.ws_messages
    msgs.append({"kind": "notice", "level": level, "title": title, "content": content, "examples": examples})
    _render_notice(msgs[-1], len(msgs) - 1, show_examples=True)


def _run_turns(stream, steps: List[Dict], total: int, done: List[Dict], tracker=None,
               phases: Optional[List[str]] = None, note: Optional[str] = None) -> None:
    """Show each stakeholder turn live as it is generated and keep it in the chat history.

    Completed turns are appended to `done` so a partial transcript survives an error."""
    msgs = st.session_state.ws_messages
    for step in steps:
        icon = PERSONAS[step["speaker"]]["icon"]
        if tracker is not None and phases:
            tracker.markdown(_tracker_html(phases, step["phase"]), unsafe_allow_html=True)
        with st.chat_message("assistant", avatar=icon):
            st.markdown(
                _turn_header(step["speaker"], step["side"], step["phase"], step["turn"], total, icon, note),
                unsafe_allow_html=True,
            )
            holder = st.empty()
            holder.markdown(f"*{step['speaker']} is preparing a response…*")
            try:
                turn = next(stream, None)
            except Exception:
                holder.markdown("*This turn could not be generated.*")
                raise
            if turn is None:
                holder.markdown("*This turn could not be generated.*")
                raise RuntimeError("The discussion ended before all turns were generated.")
            holder.markdown(turn["content"])
        done.append(turn)
        msgs.append({
            "kind": "turn", "turn": turn["turn"], "total": total, "speaker": turn["speaker"],
            "side": step["side"], "phase": step["phase"], "icon": icon, "content": turn["content"],
            "note": note,
        })


def _report_error(exc: Exception) -> None:
    if isinstance(exc, (ValueError, LLMConfigurationError, LLMRequestError)):
        _add_notice("error", "The discussion could not be completed", str(exc))
    else:
        _add_notice("error", "The discussion could not be completed",
                    "Dialogue generation failed. Check the model configuration and your connection, then try again. "
                    f"(Technical detail: {type(exc).__name__})")


def _generate(topic: str, persona_a: str, persona_b: str, total: int, context: str) -> None:
    msgs = st.session_state.ws_messages
    plan = turn_plan(total, persona_a, persona_b)
    phases = [p for p in PHASE_ORDER if any(s["phase"] == p for s in plan)]
    sources: List[Dict] = []
    if st.session_state.get("ws_use_rag", True):
        try:
            sources = retrieve_sources(topic, context)
        except Exception:  # noqa: BLE001 - retrieval is an enhancement; never block the discussion
            sources = []
        sources_msg = {"kind": "sources", "sources": sources}
        msgs.append(sources_msg)
        _render_sources(sources_msg)
    done: List[Dict] = []
    tracker = st.empty()
    try:
        _run_turns(stream_dialogue(topic, persona_a, persona_b, total, context, sources=sources),
                   plan, total, done, tracker, phases)
    except Exception as exc:  # noqa: BLE001 - surface a controlled message to the user
        _report_error(exc)
    tracker.empty()

    if done:
        result = build_result(topic, persona_a, persona_b, done, context, total, sources=sources)
        if result["agreement_status"] in ("agreed", "partial") and st.session_state.get("ws_save_history", True):
            try:
                result["history_id"] = save_result(result)
            except OSError:
                pass  # history is a convenience; never block the decision on a disk problem
        st.session_state.ws_counter += 1
        msg = {"kind": "conclusion", "id": st.session_state.ws_counter, "result": result}
        msgs.append(msg)
        _render_conclusion(msg, show_stress=True)
        st.session_state.last_result = result
        st.session_state.last_topic = result["topic"]


def _run_stress(result: Dict, key: str, api_configured: bool) -> None:
    if not api_configured:
        _add_notice("setup", "AI configuration required",
                    "Stress tests need the AI model. Add your Groq API key to `.env` and restart the app.")
        return
    label = STRESS_SCENARIOS[key][0]
    base = result["turns"]
    persona_a, persona_b = result["persona_a"], result["persona_b"]
    last = base[-1]["speaker"]
    first = persona_b if last == persona_a else persona_a
    speakers = [first, last, first]
    phases = ["stress", "stress", "stress_outcome"]
    steps = [
        {"turn": len(base) + i + 1, "speaker": sp, "side": "A" if sp == persona_a else "B", "phase": ph}
        for i, (sp, ph) in enumerate(zip(speakers, phases))
    ]
    done: List[Dict] = []
    try:
        _run_turns(stress_test_turns(result, key), steps, len(base) + 3, done, note=f"Scenario: {label}")
        _add_notice("clarify", "Stress test complete",
                    "This is advisory guidance generated for the scenario you chose. It is not validated as "
                    "consensus, so review it before acting on it.")
    except Exception as exc:  # noqa: BLE001
        _report_error(exc)


def _process(prompt: str, api_configured: bool, settings: Tuple[str, str, int, str]) -> None:
    check = validate_topic(prompt)
    if check.status != "accepted":
        if check.title == "Welcome":
            level = "welcome"
        elif check.status == "rejected":
            level = "scope"
        else:
            level = "clarify"
        _add_notice(level, check.title or "Please refine your topic", check.message, examples=True)
        return
    if not api_configured:
        _add_notice(
            "setup", "AI configuration required",
            "The topic is in scope, but no Groq API key is configured. Copy `.env.example` to `.env`, "
            "add your key locally, and restart the app.",
        )
        return
    persona_a, persona_b, total, context = settings
    _generate(prompt, persona_a, persona_b, total, context)


def open_result_in_workspace(result: Dict) -> None:
    """Load a saved decision into the workspace chat. Safe to use as a button callback."""
    _init_state()
    turns = result.get("turns", [])
    persona_a = result.get("persona_a")
    total = len(turns)
    msgs: List[Dict] = [{"kind": "user", "content": result.get("topic", "")}]
    if result.get("sources"):
        msgs.append({"kind": "sources", "sources": result["sources"]})
    for i, turn in enumerate(turns):
        phase = turn.get("phase") or (
            "discussion" if turn.get("type") == "discussion" else ("closing" if i == total - 2 else "conclusion")
        )
        msgs.append({
            "kind": "turn", "turn": turn.get("turn", i + 1), "total": total, "speaker": turn.get("speaker", ""),
            "side": "A" if turn.get("speaker") == persona_a else "B", "phase": phase,
            "icon": PERSONAS.get(turn.get("speaker"), {}).get("icon", "💬"),
            "content": turn.get("content", ""), "note": None,
        })
    record = dict(result)
    record["history_id"] = result.get("history_id") or result.get("id")
    st.session_state.ws_counter += 1
    msgs.append({"kind": "conclusion", "id": st.session_state.ws_counter, "result": record})
    st.session_state.ws_messages = msgs
    st.session_state.page = "Stakeholder Dialogue"


def render_workspace(api_configured: bool) -> None:
    _init_state()
    _render_header()
    settings = _render_settings()

    typed = st.chat_input("Describe a cryptography decision, e.g. “Which encryption should our messaging app use?”")
    pending = st.session_state.ws_pending
    st.session_state.ws_pending = None
    prompt = (typed or pending or "").strip()

    msgs = st.session_state.ws_messages

    stress_result, stress_key = None, None
    requested = st.session_state.ws_stress
    st.session_state.ws_stress = None
    if requested and not prompt:
        rid, key = requested
        stress_result = next((m["result"] for m in msgs if m.get("kind") == "conclusion" and m.get("id") == rid), None)
        if stress_result is not None and key in STRESS_SCENARIOS:
            stress_key = key
            label, desc = STRESS_SCENARIOS[key]
            msgs.append({"kind": "user", "content": f"**Stress test · {label}:** {desc}"})

    if prompt:
        msgs.append({"kind": "user", "content": prompt})

    if not msgs:
        _render_welcome()
    else:
        latest_conclusion = max((i for i, m in enumerate(msgs) if m.get("kind") == "conclusion"), default=-1)
        for i, msg in enumerate(msgs):
            _render_message(msg, i, is_last=(i == len(msgs) - 1), show_stress=(i == latest_conclusion))

    if prompt:
        _process(prompt, api_configured, settings)
    elif stress_key:
        _run_stress(stress_result, stress_key, api_configured)
