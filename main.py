import os
import streamlit as st
from dotenv import load_dotenv

from services.llm_client import (
    LLMConfigurationError, LLMRequestError, stream_chat_completion,
)
from ui.styles import inject_css
from ui.history import render_history
from ui.knowledge import render_knowledge
from ui.mcp_page import render_mcp
from ui.workspace import render_workspace
from services.rag import format_reference_notes, get_knowledge_base, retrieve_sources
from utils.history_store import list_history

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
API_CONFIGURED = bool(os.getenv("GROQ_API_KEY", "").strip() not in ("", "replace_with_your_own_api_key"))

st.set_page_config(page_title="CipherBridge Concord", page_icon="🔐", layout="wide")
inject_css()

for key, default in {
    "page": "Dashboard", "chat_messages": [], "suggested_prompt": None,
    "last_result": None, "last_topic": "", "chat_sources": {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.markdown("## 🔐 CipherBridge Concord")
    st.caption("AI-assisted cryptography workspace")
    st.markdown("### Workspace navigation")
    page = st.radio("Navigate", ["Dashboard", "AI Chat", "Stakeholder Dialogue", "Decision History", "Knowledge Base", "MCP Server"],
                    key="page", label_visibility="collapsed")
    st.divider()
    st.markdown("### System Status")
    if API_CONFIGURED:
        st.success("Groq configuration detected")
    else:
        st.warning("Groq API key not configured")
    st.caption(f"Selected model: {MODEL}")
    st.caption("API key value is never displayed.")
    st.divider()
    st.markdown("### Core Capabilities")
    st.caption("• Groq-powered AI chat with three answer styles")
    st.caption("• Two-persona dialogue generation")
    st.caption("• Structural consensus checks")
    st.caption("• TXT and JSON exports")
    st.divider()
    with st.expander("Help & About"):
        st.write("Choose a workspace page above. Configure GROQ_API_KEY in a local .env file to use AI features.")
        st.caption("Educational prototype only. Structural consensus checks do not prove technical correctness.")

if page not in ("Stakeholder Dialogue", "Decision History", "Knowledge Base", "MCP Server"):
    st.markdown("""<div class="hero"><div class="eyebrow">CYBERSECURITY · CRYPTOGRAPHY · AI</div>
<h1>🔐 CipherBridge Concord</h1><p>Explore security questions, compare stakeholder perspectives, and develop reasoned cryptography decisions.</p></div>""", unsafe_allow_html=True)

if page == "Dashboard":
    st.subheader("Workspace Dashboard")
    a,b,c,d,e = st.columns(5)
    a.metric("AI configuration", "Configured" if API_CONFIGURED else "Needs setup")
    b.metric("Chat messages", len(st.session_state.chat_messages))
    c.metric("Saved dialogue", "Yes" if st.session_state.last_result else "No")
    try:
        d.metric("Saved decisions", len(list_history()))
    except OSError:
        d.metric("Saved decisions", "n/a")
    e.metric("Knowledge notes", get_knowledge_base().stats()["documents"])
    st.markdown("### Get started")
    st.write("Use **AI Chat** for cryptography and cybersecurity questions, or **Stakeholder Dialogue** to compare two perspectives and review a proposed action plan.")
    st.info("The application needs a valid Groq API key and an available model for AI generation. No API key is needed for local unit tests.")
    if st.session_state.last_result:
        r=st.session_state.last_result
        st.markdown("#### Latest dialogue")
        st.write(f"**Topic:** {r.get('topic','')}")
        st.write(f"**Turns:** {len(r.get('turns', []))} · **Structural validation:** {'Passed' if r.get('consensus_valid') else 'Needs review'}")

elif page == "AI Chat":
    st.subheader("Cryptography AI Assistant")
    answer_style = st.selectbox("Answer style", ["Beginner", "Expert", "Code-focused"], key="answer_style")
    style_instructions = {
        "Beginner": "Use simple language, define terms, and end with a takeaway.",
        "Expert": "Discuss threat models, assumptions, limitations, and standards where appropriate.",
        "Code-focused": "Prefer maintained Python cryptography libraries. Explain key management, nonce/IV requirements, and error handling. Never implement primitives from scratch.",
    }
    def show_chat_sources(sources):
        if sources is None:
            return
        if not sources:
            st.caption("📚 No relevant knowledge-base passages were found for this question.")
            return
        with st.expander(f"📚 Sources used ({len(sources)})"):
            for src in sources:
                heading = f" — {src['heading']}" if src.get("heading") else ""
                st.markdown(f"**[{src['id']}] {src['title']}**{heading} · _{src['source']}_ · relevance {src['score']}")
                st.markdown(src["text"])

    left,right=st.columns([1,3])
    if left.button("🗑️ Clear conversation"):
        st.session_state.chat_messages=[]
        st.session_state.chat_sources={}
        st.session_state.suggested_prompt=None
        st.rerun()
    right.caption("Responses stream as generated. Do not enter passwords, API keys, private keys, or production secrets.")
    use_rag=st.checkbox("📚 Ground answers in the knowledge base (RAG)", value=True, key="chat_use_rag",
                        help="Retrieves relevant cryptography notes and gives them to the AI, which cites them as [S1], [S2]. Retrieved passages are sent to the AI provider in the prompt.")
    st.markdown("**Example prompts**")
    examples=["Explain AES-GCM with a simple example.","How should a web app store passwords securely?","Explain TLS and how it protects data."]
    cols=st.columns(3)
    for i,example in enumerate(examples):
        if cols[i].button(example, key=f"example_{i}", use_container_width=True):
            st.session_state.suggested_prompt=example
            st.rerun()
    for idx, message in enumerate(st.session_state.chat_messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                show_chat_sources(st.session_state.chat_sources.get(idx))
    prompt=st.chat_input("Ask about encryption, passwords, TLS, or another security topic...")
    if st.session_state.suggested_prompt:
        prompt=st.session_state.suggested_prompt
        st.session_state.suggested_prompt=None
    if prompt and prompt.strip():
        prompt=prompt.strip()
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        sources=None
        if use_rag:
            try:
                sources=retrieve_sources(prompt, top_k=4)
            except Exception:
                sources=[]
        notes=format_reference_notes(sources)
        messages=[{"role":"system","content":(
            "You are CipherBridge Concord, an educational cryptography and cybersecurity assistant. "
            "Be accurate, distinguish facts from assumptions, prefer recognized standards and maintained "
            "libraries, never invent citations or security guarantees, and focus risky questions on authorized "
            "defensive guidance. Answer style: "+answer_style+". "+style_instructions[answer_style]
            +(("\n\n"+notes) if notes else "")
        )},*st.session_state.chat_messages]
        with st.chat_message("assistant"):
            try:
                answer=st.write_stream(stream_chat_completion(messages,temperature=0.6,max_tokens=2048))
                if isinstance(answer,str) and answer.strip():
                    st.session_state.chat_messages.append({"role":"assistant","content":answer})
                    if sources is not None:
                        st.session_state.chat_sources[len(st.session_state.chat_messages)-1]=sources
                    show_chat_sources(sources)
                else:
                    st.error("The AI returned an empty response. Please try again.")
                    st.session_state.chat_messages.pop()
            except (LLMConfigurationError, LLMRequestError) as exc:
                st.session_state.chat_messages.pop()
                st.error(str(exc))
            except Exception:
                st.session_state.chat_messages.pop()
                st.error("The AI request failed unexpectedly. Check your configuration and connection, then try again.")

elif page == "Stakeholder Dialogue":
    render_workspace(API_CONFIGURED)

elif page == "Decision History":
    render_history()

elif page == "Knowledge Base":
    render_knowledge()

elif page == "MCP Server":
    render_mcp(API_CONFIGURED)

st.markdown('<div class="footer">CipherBridge Concord · Academic prototype · Review security-critical decisions before deployment.</div>',unsafe_allow_html=True)
