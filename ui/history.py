"""Decision History page: reopen, export, or delete saved decisions."""
import streamlit as st

from ui.workspace import open_result_in_workspace
from utils.export_utils import transcript_to_json, transcript_to_markdown
from utils.history_store import clear_history, delete_result, list_history
from utils.pdf_export import transcript_to_pdf

_STATUS = {"agreed": "✅ Consensus", "partial": "🟡 Partial agreement", "incomplete": "⚪ Incomplete"}


def _matches(record, needle: str) -> bool:
    haystack = " ".join(str(record.get(k, "")) for k in ("topic", "persona_a", "persona_b")).lower()
    return needle.lower() in haystack


PAGE_SIZE = 20


def _pdf_for(record):
    """Build each record's PDF once per session; a long history stays fast."""
    cache = st.session_state.setdefault("hist_pdf_cache", {})
    rid = record["id"]
    if rid not in cache:
        try:
            cache[rid] = transcript_to_pdf(record)
        except Exception:  # noqa: BLE001 - PDF is optional
            cache[rid] = None
    return cache[rid]


def render_history() -> None:
    st.markdown(
        '<div class="eyebrow">CIPHERBRIDGE CONCORD</div><p class="ws-title">Decision History</p>'
        '<p class="ws-sub">Completed decisions saved on this computer. Reopen one in the workspace, '
        'export it, or delete it.</p>',
        unsafe_allow_html=True,
    )
    try:
        records = list_history()
    except OSError as exc:
        st.warning(f"The history folder could not be read ({type(exc).__name__}).")
        return

    if not records:
        st.info("No saved decisions yet. Complete a discussion in **Stakeholder Dialogue** and it will appear here "
                "(unless saving is turned off in the workspace settings).")
        return

    agreed = sum(1 for r in records if r.get("agreement_status") == "agreed")
    c1, c2, c3 = st.columns(3)
    c1.metric("Saved decisions", len(records))
    c2.metric("Consensus reached", agreed)
    c3.metric("Needing review", len(records) - agreed)

    needle = st.text_input("Search", key="hist_search", placeholder="Filter by topic or stakeholder…",
                           label_visibility="collapsed")
    shown = [r for r in records if _matches(r, needle)] if needle else records
    if not shown:
        st.caption("No saved decisions match that search.")

    visible = shown if st.session_state.get("hist_show_all") else shown[:PAGE_SIZE]
    for record in visible:
        rid = record["id"]
        agreement = (record.get("evaluation") or {}).get("agreement") or {}
        score = f" · score {agreement['score']}/100" if agreement.get("checks") else ""
        title = f"{_STATUS.get(record.get('agreement_status'), '⚪')} · {record.get('topic', '')[:90]}"
        with st.expander(title):
            st.caption(f"{record.get('persona_a', '')} ↔ {record.get('persona_b', '')} · "
                       f"{len(record.get('turns', []))} turns · saved {str(record.get('saved_at', ''))[:10]}{score}")
            decision = (record.get("conclusion") or {}).get("decision") or record.get("final_decision", "")
            if decision:
                with st.container(border=True):
                    st.markdown('<div class="step-label">Joint decision</div>', unsafe_allow_html=True)
                    st.markdown(decision)
            b1, b2, b3, b4, b5 = st.columns(5)
            b1.button("↗ Open", key=f"hist_open_{rid}", use_container_width=True,
                      on_click=open_result_in_workspace, args=(record,))
            pdf = _pdf_for(record)
            b2.download_button("⬇️ PDF", pdf or b"", f"cipherbridge_decision_{rid}.pdf", "application/pdf",
                               key=f"hist_pdf_{rid}", disabled=pdf is None, use_container_width=True)
            b3.download_button("⬇️ Markdown", transcript_to_markdown(record), f"cipherbridge_decision_{rid}.md",
                               "text/markdown", key=f"hist_md_{rid}", use_container_width=True)
            b4.download_button("⬇️ JSON", transcript_to_json(record), f"cipherbridge_decision_{rid}.json",
                               "application/json", key=f"hist_json_{rid}", use_container_width=True)
            if b5.button("🗑 Delete", key=f"hist_del_{rid}", use_container_width=True):
                delete_result(rid)
                st.rerun()

    if len(shown) > len(visible):
        st.caption(f"Showing the newest {len(visible)} of {len(shown)} decisions.")
        if st.button("Show all", key="hist_show_all_btn"):
            st.session_state.hist_show_all = True
            st.rerun()

    st.divider()
    with st.expander("Danger zone"):
        confirm = st.checkbox("I understand this permanently deletes every saved decision.", key="hist_confirm")
        if st.button("Clear all history", key="hist_clear", disabled=not confirm):
            clear_history()
            st.rerun()
