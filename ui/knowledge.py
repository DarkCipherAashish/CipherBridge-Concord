"""Knowledge Base page: see what the RAG index contains, try retrieval, add your own notes."""
import streamlit as st

from services.rag import MAX_USER_DOC_CHARS, add_user_document, delete_user_document, get_knowledge_base


def render_knowledge() -> None:
    st.markdown(
        '<div class="eyebrow">CIPHERBRIDGE CONCORD</div><p class="ws-title">Knowledge Base</p>'
        '<p class="ws-sub">The cryptography notes that ground the stakeholder discussions and AI Chat '
        '(retrieval-augmented generation).</p>',
        unsafe_allow_html=True,
    )
    flash = st.session_state.pop("kb_flash", None)
    if flash:
        st.success(flash)

    kb = get_knowledge_base()
    stats = kb.stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Notes", stats["documents"])
    c2.metric("Passages", stats["chunks"])
    c3.metric("Your notes", stats["user_documents"])
    c4.metric("Retrieval", "BM25")
    st.markdown(
        '<div class="section-card"><div class="step-label">How it works</div>'
        '<p class="helper">1) Notes are split into passages and indexed. 2) For each question or decision, the '
        'best-matching passages are retrieved by keyword ranking (BM25). 3) They are added to the AI prompt with '
        'labels like [S1], and the stakeholders are asked to cite them. Retrieval matches words, not meaning, so '
        'use specific cryptography terms.</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="step-label">Try retrieval</div>', unsafe_allow_html=True)
    query = st.text_input("Search the knowledge base", key="kb_query", label_visibility="collapsed",
                          placeholder="e.g. AES-GCM nonce reuse, key rotation, post-quantum migration…")
    if query.strip():
        hits = kb.search(query, top_k=5)
        if not hits:
            st.info("No relevant passages found. Try more specific cryptography terms, or add your own notes below.")
        for rank, hit in enumerate(hits, 1):
            with st.container(border=True):
                heading = f" — {hit['heading']}" if hit["heading"] else ""
                st.markdown(f"**{rank}. {hit['title']}**{heading}")
                st.caption(f"{hit['source']} · {hit['origin']} note · relevance {hit['score']}")
                st.markdown(hit["text"])

    st.markdown('<div class="step-label">Notes in the knowledge base</div>', unsafe_allow_html=True)
    for doc in kb.documents:
        label = ("📝 " if doc["origin"] == "user" else "📘 ") + doc["title"]
        with st.expander(label):
            st.caption(f"{doc['source']} · {'your note' if doc['origin'] == 'user' else 'curated starter note'} · "
                       f"{doc['chunks']} passages")
            st.markdown(doc["text"])
            if doc["origin"] == "user" and st.button("🗑 Delete this note", key=f"kb_del_{doc['doc_id']}"):
                delete_user_document(doc["doc_id"])
                st.session_state.kb_flash = f"Deleted “{doc['title']}”."
                st.rerun()

    st.markdown('<div class="step-label">Add your own notes</div>', unsafe_allow_html=True)
    st.caption(
        "Add course notes or reference material (.md or .txt). Notes are stored on this computer, but passages "
        "retrieved from them are sent to the AI provider inside prompts, so do not add confidential material. "
        f"Limit {MAX_USER_DOC_CHARS // 1000} KB of text per note."
    )
    counter = st.session_state.setdefault("kb_upload_n", 0)
    uploaded = st.file_uploader("Upload a note", type=["md", "txt"], key=f"kb_upload_{counter}")
    pasted_name = st.text_input("…or paste text. Title", key=f"kb_paste_name_{counter}", placeholder="e.g. Unit 4 notes")
    pasted_text = st.text_area("Text", key=f"kb_paste_text_{counter}", height=120, label_visibility="collapsed",
                               placeholder="Paste notes here. Use '## Heading' lines to organise sections.")
    if st.button("Add to knowledge base", key="kb_add"):
        try:
            if uploaded is not None:
                name, text = uploaded.name, uploaded.getvalue().decode("utf-8")
            elif pasted_text.strip():
                name, text = pasted_name.strip() or "pasted-notes", pasted_text
            else:
                raise ValueError("Upload a file or paste some text first.")
            info = add_user_document(name, text)
            st.session_state.kb_upload_n = counter + 1
            st.session_state.kb_flash = f"Added “{info['title']}” ({info['chunks']} passages). It is searchable now."
            st.rerun()
        except UnicodeDecodeError:
            st.error("That file is not UTF-8 text. Save it as UTF-8 and try again.")
        except (ValueError, OSError) as exc:
            st.error(str(exc))
